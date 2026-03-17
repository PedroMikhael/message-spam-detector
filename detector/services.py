import os
import requests
import json
import re
from django.conf import settings
from decouple import config
from ollama import Client
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
import random
import google.generativeai as genai

# Ollama Cloud clients (load balancing)
OLLAMA_API_KEY = config("OLLAMA_API_KEY", default="")
OLLAMA_API_KEY2 = config("OLLAMA_API_KEY2", default="")
MODELO_OLLAMA = config("OLLAMA_MODEL", default="gemini-3-flash-preview:cloud")

ollama_clients = []

if OLLAMA_API_KEY:
    ollama_clients.append(Client(
        host="https://ollama.com",
        headers={'Authorization': f'Bearer {OLLAMA_API_KEY}'}
    ))
    print(f"Ollama Key 1 configurada: {MODELO_OLLAMA}")

if OLLAMA_API_KEY2:
    ollama_clients.append(Client(
        host="https://ollama.com",
        headers={'Authorization': f'Bearer {OLLAMA_API_KEY2}'}
    ))
    print(f"Ollama Key 2 configurada: {MODELO_OLLAMA}")

if not ollama_clients:
    print("Nenhuma chave Ollama configurada.")

# Gemini fallback
genai.configure(api_key=settings.GEMINI_API_KEY)
print("Gemini configurado como fallback.")

try:
    embedding_function = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")
    vector_store = Chroma(
        persist_directory="chroma_db",
        embedding_function=embedding_function
    )
    RAG_ATIVO = True

    # Auto-populate se ChromaDB estiver vazio
    if vector_store._collection.count() == 0:
        print("ChromaDB vazio. Populando com 100 linhas de cada dataset...")
        try:
            import pandas as pd
            datasets = ["database/email_dataset.csv", "database/sms_dataset.csv"]
            text_cols = ["text", "message", "Email Text", "Message"]
            label_cols = ["label", "Label", "Email Type"]
            all_docs = []

            for ds in datasets:
                if not os.path.exists(ds):
                    continue
                df = pd.read_csv(ds, nrows=100)
                tc = next((c for c in text_cols if c in df.columns), None)
                lc = next((c for c in label_cols if c in df.columns), None)
                if tc and lc:
                    for _, row in df[[tc, lc]].dropna().iterrows():
                        all_docs.append(Document(page_content=str(row[tc]), metadata={"label": str(row[lc])}))

            if all_docs:
                vector_store.add_documents(all_docs)
                print(f"ChromaDB populado com {len(all_docs)} documentos.")
            else:
                print("Nenhum dataset encontrado para popular o ChromaDB.")
        except Exception as e:
            print(f"Erro ao popular ChromaDB: {e}")
    else:
        print(f"RAG carregado ({vector_store._collection.count()} docs).")

except Exception as e:
    RAG_ATIVO = False
    print(f"RAG indisponível: {e}")


def buscar_exemplos_similares(texto_usuario):
    """Busca exemplos similares no ChromaDB para contexto RAG."""
    if not RAG_ATIVO:
        return ""
    try:
        resultados = vector_store.similarity_search(texto_usuario, k=3)
        contexto_rag = "\n--- HISTORICAL SIMILAR EXAMPLES (from Vector Database) ---\n"
        if not resultados:
             contexto_rag += "No similar historical data found.\n"
        else:
            for i, doc in enumerate(resultados):
                rotulo = doc.metadata.get('label', 'Unknown')
                conteudo = doc.page_content.replace("\n", " ")[:300] 
                contexto_rag += f"Example {i+1} (Actual Label: {rotulo}): \"{conteudo}\"\n"
        return contexto_rag
    except Exception as e:
        print(f"Erro na busca RAG: {e}")
        return ""


def buscar_exemplo_igual(texto_usuario):
    """Busca mensagem exata no ChromaDB. Retorna o label ou None."""
    if not RAG_ATIVO:
        return None
    try:
        resultados = vector_store.similarity_search(texto_usuario, k=1)
        if resultados and resultados[0].page_content == texto_usuario:
            return resultados[0].metadata.get('label', 'Unknown')
        return None
    except Exception as e:
        print(f"Erro na busca RAG: {e}")
        return None


def _mapear_label_para_risk_level(label: str) -> str:
    """Mapeia labels do ChromaDB para risk_level."""
    mapeamento = {
        "HAM": "SAFE",
        "SAFE": "SAFE",
        "SPAM": "MALICIOUS",
        "MALICIOUS": "MALICIOUS",
        "PHISHING": "MALICIOUS",
        "SUSPICIOUS": "SUSPICIOUS",
    }
    return mapeamento.get(label.upper().strip(), "SUSPICIOUS")


def verificar_link_com_safe_browsing(link: str) -> str:
    """Verifica URL via Google Safe Browsing API."""
    url_api = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
    api_key = settings.SAFE_BROWSING_API_KEY
    payload = {"client": {"clientId": "spamapiproject", "clientVersion": "1.0.0"},"threatInfo": {"threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],"platformTypes": ["ANY_PLATFORM"],"threatEntryTypes": ["URL"],"threatEntries": [{"url": link}]}}
    params = {'key': api_key}
    try:
        response = requests.post(url_api, params=params, json=payload)
        response.raise_for_status()
        data = response.json()
        if 'matches' in data:
            threat_type = data['matches'][0]['threatType']
            return f"PERIGOSO (Threat detected: {threat_type})"
        return "SEGURO"
    except requests.exceptions.RequestException:
        return "INDETERMINADO (Verification failed)"


PROMPT_SISTEMA = """
    <ROLE>
    You are "VerificAI," a cybersecurity AI agent developed by LARCES (Networking and Security Laboratory) at the State University of Ceará (UECE). You analyze email messages in Brazilian Portuguese. Your communication is friendly, protective, and simple.
    </ROLE>

    <MISSION>
    1. Analyze the incoming email message to determine its risk level.
    2. If the message is SAFE, respond naturally as a helpful assistant.
    </MISSION>

    <INSTRUCTIONS>
    1. **ANALYSIS:** Evaluate the message for:
        - Dangerous URLs (check `TECHNICAL_LINK_ANALYSIS_RESULT`; "PERIGOSO" = MALICIOUS immediately)
        - Domain impersonation (official-looking messages with unrelated domains = MALICIOUS)
        - Social engineering (urgency, greed, authority, scarcity tactics)
        - Historical context from RAG examples

    2. **CLASSIFICATION:** Assign ONE of: `SAFE`, `SUSPICIOUS`, or `MALICIOUS`.

    3. **RESPONSE FIELDS (CRITICAL):**
        You must provide THREE separate fields in Portuguese:

        - `motivo`: A SHORT explanation (2-3 sentences MAX) of WHY the message received this classification. Use simple, non-technical language that any person can understand. Do NOT include technical details like "análise de vetores", "engenharia social", API names, or security jargon. Write as if explaining to a non-technical family member.

        - `precaucao`: A practical recommendation (1-2 sentences) telling the user what to DO. Examples: "Não clique em nenhum link desta mensagem.", "Apague este email imediatamente.", "Esta mensagem parece segura, pode prosseguir normalmente."

        - `analysis_details`: A list of technical analysis points in English (for internal use, not shown to the user).

    4. **STYLE RULES:**
        - NEVER use generic chatbot closings like "Como posso te ajudar?" or "Posso ajudar com mais alguma coisa?"
        - Keep it SHORT and DIRECT. No long paragraphs.
        - Write as if explaining to a non-technical family member.

    **OUTPUT FORMAT (Required and Strict):**
    Your final response MUST BE a single, valid JSON object and nothing else:
    {{
      "risk_level": "SAFE, SUSPICIOUS, or MALICIOUS",
      "analysis_details": ["A list of strings with your technical analysis points (internal use only)."],
      "motivo": "Short Portuguese explanation of WHY this classification was given.",
      "precaucao": "Short Portuguese practical recommendation for the user."
    }}
    </INSTRUCTIONS>
"""


def _normalizar_texto(texto: str) -> str:
    """Normaliza texto para comparações de duplicata:
    - Remove espaços extras, tabs, múltiplas quebras de linha
    - Lowercase
    - Strip
    """
    import re as _re
    normalizado = _re.sub(r'\s+', ' ', texto).strip().lower()
    return normalizado


def analisar_com_IA(texto: str, debug: bool = False) -> dict:
    """Analisa texto com Ollama (load balancing) ou Gemini (fallback).
    Se debug=True, retorna campos extras (para Swagger).
    """
    from .models import Feedback

    # Normalizar para busca de duplicatas
    texto_normalizado = _normalizar_texto(texto)

    # Verificar match no Django DB 
    feedbacks_existentes = Feedback.objects.all()
    feedback_existente = None
    for fb in feedbacks_existentes:
        if _normalizar_texto(fb.mensagem_original) == texto_normalizado:
            feedback_existente = fb
            break
    
    exemplo_exato = None

    if feedback_existente and feedback_existente.risco_ia:
        exemplo_exato = {
            "fonte": "Django DB",
            "id": feedback_existente.id,
            "classificacao": feedback_existente.risco_ia,
            "data": feedback_existente.timestamp.strftime('%d/%m/%Y %H:%M') if feedback_existente.timestamp else 'N/A'
        }
        resultado = {
            "risk_level": feedback_existente.risco_ia,
            "analysis_details": [
                "Mensagem idêntica já analisada anteriormente.",
                f"Classificação: {feedback_existente.risco_ia}",
                f"Data: {exemplo_exato['data']}"
            ],
            "motivo": (
                f"Esta mensagem já foi analisada anteriormente pelo VerificAI. "
                f"Classificação anterior: {feedback_existente.risco_ia}."
            ),
            "precaucao": "A mensagem é idêntica a uma que já consta em nosso banco de dados. Não foi necessário reprocessá-la pela IA."
        }
        if debug:
            resultado["exemplo_exato"] = exemplo_exato
        return resultado

    # Verificar vetor exato no ChromaDB
    label_chromadb = buscar_exemplo_igual(texto)
    if label_chromadb:
        risk_level = _mapear_label_para_risk_level(label_chromadb)
        exemplo_exato = {
            "fonte": "ChromaDB",
            "label": label_chromadb,
            "classificacao_mapeada": risk_level
        }
        resultado = {
            "risk_level": risk_level,
            "analysis_details": [
                "Mensagem idêntica encontrada no ChromaDB.",
                f"Label: {label_chromadb}",
                f"Classificação: {risk_level}"
            ],
            "motivo": (
                f"Esta mensagem já foi analisada anteriormente pelo VerificAI. "
                f"Classificação anterior: {risk_level}."
            ),
            "precaucao": "A mensagem é idêntica a uma que já consta em nosso banco de dados vetorial. Não foi necessário reprocessá-la pela IA."
        }
        if debug:
            resultado["exemplo_exato"] = exemplo_exato
        return resultado

    # Análise de links
    links_encontrados = re.findall(r'(https?://\S+)', texto)
    resultado_safe_browsing = "Nenhum link na mensagem."
    if links_encontrados:
        resultado_safe_browsing = verificar_link_com_safe_browsing(links_encontrados[0])
    
    contexto_historico = buscar_exemplos_similares(texto)

    prompt_usuario = f"""
    <CONTEXT>
    <USER_MESSAGE>{texto}</USER_MESSAGE>
    <TECHNICAL_LINK_ANALYSIS_RESULT>{resultado_safe_browsing}</TECHNICAL_LINK_ANALYSIS_RESULT>
    {contexto_historico} 
    </CONTEXT>
    
    ---
    **MENSAGEM REAL PARA ANÁLISE:**
    "{texto}"
    """
    
    # Chamar IA 
    resposta_ia = None
    modelo_usado = None
    
    if ollama_clients:
        clients_embaralhados = list(ollama_clients)
        random.shuffle(clients_embaralhados)
        
        for i, client in enumerate(clients_embaralhados):
            try:
                response = client.chat(
                    model=MODELO_OLLAMA,
                    messages=[
                        {'role': 'system', 'content': PROMPT_SISTEMA},
                        {'role': 'user', 'content': prompt_usuario}
                    ]
                )
                resposta_ia = response['message']['content']
                modelo_usado = f"Ollama ({MODELO_OLLAMA}) Key {i+1}"
                print(f"✅ {modelo_usado}")
                break
            except Exception as e:
                print(f"⚠️ Ollama Key {i+1} falhou: {e}")
                continue
    
    
    if resposta_ia is None:
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(PROMPT_SISTEMA + "\n" + prompt_usuario)
            resposta_ia = response.text
            modelo_usado = "Gemini 2.5 Flash (fallback)"
            print(f"{modelo_usado}")
        except Exception as e:
            print(f"Todas as APIs falharam: {e}")
            return {
                "risk_level": "INDETERMINADO",
                "analysis_details": [f"Todas as APIs falharam: {e}"],
                "motivo": "Não foi possível processar a análise neste momento pois todos os serviços de IA estão indisponíveis.",
                "precaucao": "Por favor, tente novamente mais tarde."
            }
    
    # Processar resposta JSON
    try:
        cleaned_response = resposta_ia.strip().replace("`", "").replace("json", "")
        match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
        if not match:
            raise ValueError("Nenhum JSON válido na resposta da IA.")
        resultado_json = json.loads(match.group(0))
        
        if "risk_level" not in resultado_json or "motivo" not in resultado_json:
             raise ValueError("Resposta da IA sem chaves esperadas.")

    
        if debug:
            resultado_json["debug"] = {
                "modelo_usado": modelo_usado,
                "links_encontrados": links_encontrados if links_encontrados else [],
                "resultado_links": resultado_safe_browsing,
                "exemplos_similares": contexto_historico.strip() if contexto_historico else "Nenhum exemplo similar encontrado.",
                "exemplo_exato": None
            }

        return resultado_json

    except Exception as e:
        print(f"Erro ao processar resposta: {e}")
        return {
            "risk_level": "INDETERMINADO",
            "analysis_details": [f"Erro ao processar resposta da IA: {e}"],
            "motivo": "Ocorreu um erro ao processar a resposta da inteligência artificial.",
            "precaucao": "Por favor, tente novamente mais tarde."
        }


def enviar_mensagem_whatsapp(numero_destinatario: str, mensagem: str):
    """Envia mensagem via WhatsApp Business API."""
    url = f"https://graph.facebook.com/v19.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": numero_destinatario, "type": "text", "text": {"body": mensagem}}
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return True, response.json()
    except requests.exceptions.RequestException as e:
        return False, str(e)
    

def adicionar_ao_chromadb(texto: str, rotulo: str) -> bool:
    """Adiciona documento ao ChromaDB (treinamento Active Learning)."""
    global vector_store, RAG_ATIVO
    
    if not RAG_ATIVO:
        print("RAG indisponível para treinamento.")
        return False
        
    try:
        novo_documento = Document(
            page_content=texto,
            metadata={"label": rotulo}
        )
        vector_store.add_documents([novo_documento])
        print(f"ChromaDB: adicionado com rótulo '{rotulo}'")
        return True
    except Exception as e:
        print(f"ChromaDB erro: {e}")
        return False