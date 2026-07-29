import ollama
import pandas as pd
import time
import os
import csv
import re
import json
import requests
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
from ollama import Client
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, confusion_matrix
)
from scipy import stats
from tqdm import tqdm

# =====================================================
# CONFIGURACOES
# =====================================================

# Raiz do projeto (um nível acima de evaluate/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

MODELO_OLLAMA = 'llama3.2:3b'
MODELO_JUDGE  = ''                    # <- preencher com o modelo judge desejado

# Pasta de saida de todas as metricas e CSVs do judge
METRICAS_JUDGE_PATH = os.path.join(PROJECT_ROOT, 'metricas_judge')
os.makedirs(METRICAS_JUDGE_PATH, exist_ok=True)

ARQUIVO_RELATORIO_FINAL = os.path.join(METRICAS_JUDGE_PATH, 'relatorio_metrics_ollama.txt')

# Cliente cloud para o Judge
OLLAMA_API_KEY = os.getenv("OLLAMA_CLOUD_API_KEY") or os.getenv("OLLAMA_API_KEY")
judge_client = Client(
    host="https://ollama.com",
    headers={'Authorization': f'Bearer {OLLAMA_API_KEY}'}
)


PADROES_PII = [
    {"nome": "cnpj",    "regex": re.compile(r'\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b'),                          "placeholder": "[CNPJ]"},
    {"nome": "cpf",     "regex": re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b'),                                  "placeholder": "[CPF]"},
    {"nome": "cartao",  "regex": re.compile(r'\b\d{4}[\s.-]?\d{4}[\s.-]?\d{4}[\s.-]?\d{4}\b'),                     "placeholder": "[CARTAO]"},
    {"nome": "pix",     "regex": re.compile(r'\b[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\b', re.IGNORECASE), "placeholder": "[PIX]"},
    {"nome": "dados_bancarios", "regex": re.compile(r'(?:ag[êe]ncia|ag)\s*:?\s*\d{3,5}(?:-?\d)?', re.IGNORECASE),  "placeholder": "[DADOS_BANCARIOS]"},
    {"nome": "dados_bancarios", "regex": re.compile(r'conta\s*:?\s*[\d][\d.\-]+\d', re.IGNORECASE),                "placeholder": "[DADOS_BANCARIOS]"},
    {"nome": "telefone","regex": re.compile(r'(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)\d{4,5}[-.\s]?\d{4}\b'),              "placeholder": "[TELEFONE]"},
    {"nome": "cep",     "regex": re.compile(r'\b\d{5}-\d{3}\b'),                                                    "placeholder": "[CEP]"},
    {"nome": "email",   "regex": re.compile(r'\b[a-zA-Z0-9._%+-]+@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'),             "placeholder": r"[USUARIO]@\1"},
    {"nome": "rg",      "regex": re.compile(r'\b\d{1,2}\.?\d{3}\.?\d{3}-?[0-9Xx]\b'),                              "placeholder": "[RG]"},
]


def sanitizar_texto(texto: str) -> str:
    """Sanitiza PII do texto usando regex (mesma lógica de detector/sanitizer.py)."""
    if not texto:
        return ""
    for padrao in PADROES_PII:
        texto = padrao["regex"].sub(padrao["placeholder"], texto)
    return texto

# =====================================================
# RAG - ChromaDB (isolado para avaliacao)
# =====================================================
# Usa um banco SEPARADO do de producao para nao contamina-lo.
# O banco e resetado a cada execucao e populado com amostras
# que NAO fazem parte do conjunto de teste (evita data leakage).

import shutil

CHROMA_DB_EVAL_PATH = os.path.join(PROJECT_ROOT, "chroma_db_evaluate")
RAG_SAMPLES_PER_DATASET = 100  # Quantas amostras usar para popular o RAG

RAG_ATIVO = False
vector_store = None
embedding_function = None

try:
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_chroma import Chroma
    from langchain_core.documents import Document

    embedding_function = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")
except Exception as e:
    print(f"⚠️ Dependencias RAG indisponiveis: {e}")


def resetar_e_popular_chromadb(datasets_config):
    """Reseta o ChromaDB de avaliacao e popula com amostras que NAO estao no teste."""
    global vector_store, RAG_ATIVO

    if embedding_function is None:
        print("⚠️ RAG nao sera usado (dependencias indisponiveis).")
        RAG_ATIVO = False
        return

    # 1. Deletar banco antigo
    if os.path.exists(CHROMA_DB_EVAL_PATH):
        shutil.rmtree(CHROMA_DB_EVAL_PATH)
        print(f"🗑️  ChromaDB de avaliacao anterior removido: {CHROMA_DB_EVAL_PATH}")

    # 2. Coletar amostras de cada dataset (fora do conjunto de teste)
    all_docs = []
    for config in datasets_config:
        arquivo        = config['arquivo_entrada']
        col_texto      = config['coluna_texto']
        col_rotulo     = config['coluna_rotulo']
        max_rows_teste = config.get('max_rows', 8000)

        try:
            df_full = pd.read_csv(arquivo)
            total_linhas = len(df_full)

            # Pegar amostras APOS as linhas de teste (sem overlap)
            if total_linhas > max_rows_teste:
                df_rag = df_full.iloc[max_rows_teste:max_rows_teste + RAG_SAMPLES_PER_DATASET]
                origem = f"linhas {max_rows_teste}-{max_rows_teste + len(df_rag)}"
            else:
                df_rag = df_full.tail(RAG_SAMPLES_PER_DATASET)
                origem = f"ultimas {len(df_rag)} linhas (dataset tem apenas {total_linhas})"

            for _, row in df_rag[[col_texto, col_rotulo]].dropna().iterrows():
                all_docs.append(Document(
                    page_content=str(row[col_texto]),
                    metadata={"label": str(row[col_rotulo])}
                ))

            print(f"  📄 {config['nome']}: {len(df_rag)} amostras para RAG ({origem})")

        except Exception as e:
            print(f"  ⚠️ Erro ao carregar {arquivo} para RAG: {e}")

    # 3. Criar novo ChromaDB e popular
    if all_docs:
        vector_store = Chroma.from_documents(
            documents=all_docs,
            embedding=embedding_function,
            persist_directory=CHROMA_DB_EVAL_PATH
        )
        RAG_ATIVO = True
        print(f"✅ ChromaDB de avaliacao criado com {len(all_docs)} docs em: {CHROMA_DB_EVAL_PATH}")
    else:
        vector_store = None
        RAG_ATIVO = False
        print("⚠️ Nenhum documento disponivel para RAG. Avaliacao sera sem RAG.")


def buscar_exemplos_similares(texto: str) -> str:
    """Busca exemplos similares no ChromaDB para contexto RAG."""
    if not RAG_ATIVO:
        return ""
    try:
        resultados = vector_store.similarity_search(texto, k=3)
        contexto_rag = "\n--- HISTORICAL SIMILAR EXAMPLES (from Vector Database) ---\n"
        if not resultados:
            contexto_rag += "No similar historical data found.\n"
        else:
            for i, doc in enumerate(resultados):
                rotulo   = doc.metadata.get('label', 'Unknown')
                conteudo = doc.page_content.replace("\n", " ")[:300]
                contexto_rag += f'Example {i+1} (Actual Label: {rotulo}): "{conteudo}"\n'
        return contexto_rag
    except Exception as e:
        print(f"Erro na busca RAG: {e}")
        return ""

# =====================================================
# SAFE BROWSING (identico a detector/services.py)
# =====================================================

SAFE_BROWSING_API_KEY = os.getenv("SAFE_BROWSING_API_KEY", "")

if SAFE_BROWSING_API_KEY:
    print(f"✅ Safe Browsing API Key configurada.")
else:
    print(f"⚠️ Safe Browsing API Key não encontrada no .env.")


def verificar_link_com_safe_browsing(link: str) -> str:
    """Verifica URL via Google Safe Browsing API."""
    if not SAFE_BROWSING_API_KEY:
        return "INDETERMINADO (API Key não configurada)"

    url_api = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
    payload = {
        "client": {"clientId": "spamapiproject", "clientVersion": "1.0.0"},
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": link}]
        }
    }
    params = {'key': SAFE_BROWSING_API_KEY}
    try:
        response = requests.post(url_api, params=params, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        if 'matches' in data:
            threat_type = data['matches'][0]['threatType']
            return f"PERIGOSO (Threat detected: {threat_type})"
        return "SEGURO"
    except requests.exceptions.RequestException:
        return "INDETERMINADO (Verification failed)"

# =====================================================
# PROMPT DO MODELO PRINCIPAL
# =====================================================

PROMPT_SISTEMA_BASE = """
    <ROLE>
    You are the "Digital Guardian," a highly specialized and elite cybersecurity AI agent. You were developed as a research project by LARCES (Networking and Security Laboratory) at the State University of Ceará (UECE). Your expertise is the forensic analysis of WhatsApp and email text messages in Brazilian Portuguese. Your communication is friendly, protective, and didactic.
    </ROLE>

    <MISSION>
    Your mission is twofold and sequential:
    1.  **PROTECT (Priority Maximum):** Perform a methodical and deep analysis of the incoming message to determine its risk level.
    2.  **INTERACT:** If the risk is null (SAFE), act as a helpful virtual assistant and engage the user in a natural conversation.
    </MISSION>

    <INSTRUCTIONS>
    Follow these steps rigorously:
    1.  **METHODICAL ANALYSIS:** Conduct your analysis focusing on the vectors: URL Analysis, Domain Impersonation, Social Engineering, and Historical Context.
    2.  **RISK ASSESSMENT:** Classify into SAFE, SUSPICIOUS, or MALICIOUS.
    3.  **RESPONSE FORMULATION:** Create a didactic response in Portuguese.

    **FORMATO DE SAIDA (Obrigatorio e Estrito):**
    Your final response MUST BE a single, valid JSON object and nothing else.
    {{
      "risk_level": "SAFE, SUSPICIOUS, or MALICIOUS",
      "analysis_details": ["point 1", "point 2"],
      "user_response": "Texto em portugues"
    }}
    </INSTRUCTIONS>
"""

# =====================================================
# PROMPT DO JUDGE (Arbitro de Classificacao)
# =====================================================

PROMPT_SISTEMA_JUDGE = """
    <ROLE>
    You are the "Arbiter" — a senior cybersecurity forensic analyst and the final authority in a two-stage threat classification system developed by LARCES/UECE.
    Your role is NOT to classify messages from scratch. Your role is to perform a rigorous second-opinion review of a classification already made by a first-stage AI model, exposing its flaws, blind spots, and errors.
    You are skeptical, methodical, and evidence-driven. You do not confirm a classification simply because it was given — you validate every claim against the actual content of the message.
    </ROLE>

    <MISSION>
    Conduct an independent forensic audit of the first-stage AI classification.
    Your audit must determine whether the assigned risk level is:
      - CONFIRMED: The classification is justified and supported by concrete evidence in the message.
      - CORRECTED: The classification is wrong, incomplete, or biased, and must be overridden.

    You are the last line of defense. Errors that pass your review will be counted as system failures.
    </MISSION>

    <EVALUATION_CRITERIA>
    Scrutinize the first-stage classification across these forensic dimensions:

    1. URGENCY & PRESSURE TACTICS
       - Does the message create artificial urgency ("act now", "limited time", "your account will be blocked")?
       - Is the user being pushed to make a decision without time to think?

    2. IMPERSONATION & BRAND SPOOFING
       - Is the message impersonating a bank, government agency, delivery service, or well-known brand?
       - Are there subtle misspellings, lookalike domains, or unofficial contact channels used?

    3. SOCIAL ENGINEERING PATTERNS
       - Does the message exploit fear, greed, curiosity, or compassion to manipulate the recipient?
       - Is there an unsolicited offer, prize, or alert that was not requested?

    4. LINK & PAYLOAD ANALYSIS
       - Are there URLs present? Do they match the claimed sender domain?
       - Is the link shortened, obfuscated, or pointing to a suspicious TLD?
       - Does the Safe Browsing result align with the risk classification?

    5. FINANCIAL EXTRACTION SIGNALS
       - Is the message requesting payment, bank data, PIX keys, card numbers, or personal documents?
       - Is there a false pretense being used to justify the financial request?

    6. LANGUAGE & GRAMMATICAL ANOMALIES
       - Is the Portuguese grammatically poor in a way inconsistent with the claimed sender?
       - Are there translation artifacts, odd formatting, or excessive punctuation/emojis used manipulatively?

    7. CONSISTENCY AUDIT
       - Does the first-stage classification correctly identify the dominant threat vector?
       - Is the risk level proportional to the actual severity of signals found?
       - Were any critical red flags ignored or downplayed? Were benign features misinterpreted as threats?
    </EVALUATION_CRITERIA>

    <INSTRUCTIONS>
    Step 1 — Read the original message carefully and independently assess its threat signals.
    Step 2 — Read the first-stage classification and its analysis details.
    Step 3 — Cross-reference the classification against the actual message content using all 7 criteria above.
    Step 4 — Issue your final forensic verdict.

    CRITICAL RULES:
    - If the first-stage model classified SAFE but you find clear threat signals -> CORRECTED to SUSPICIOUS or MALICIOUS.
    - If the first-stage model classified SUSPICIOUS or MALICIOUS but the message is clearly benign -> CORRECTED to SAFE.
    - If the classification is correct but incomplete or poorly justified -> still CONFIRMED, note gaps in your reason.
    - Your "reason" MUST cite specific content, phrases, or patterns from the actual message. Generic justifications are NOT acceptable.
    - Output ONLY a valid JSON object. No preamble, no explanation, no markdown, no text outside the JSON.

    OUTPUT FORMAT (strict):
    {{
      "verdict": "CONFIRMED" or "CORRECTED",
      "final_risk_level": "SAFE" or "SUSPICIOUS" or "MALICIOUS",
      "reason": "Justificativa forense detalhada em portugues, citando evidencias concretas da mensagem."
    }}
    </INSTRUCTIONS>
"""

# =====================================================
# DATASETS (8000 linhas por dataset)
# =====================================================

DATASETS_PARA_TESTAR = [
    {
        "nome": "SMS Dataset",
        "arquivo_entrada": os.path.join(PROJECT_ROOT, "database", "sms_dataset.csv"),
        "arquivo_saida": os.path.join(METRICAS_JUDGE_PATH, "sms_ollama_output.csv"),
        "coluna_texto": "Message",
        "coluna_rotulo": "Label",
        "rotulo_positivo": "spam",
        "rotulo_negativo": "ham",
        "max_rows": 8000
    },
    {
        "nome": "Email Dataset",
        "arquivo_entrada": os.path.join(PROJECT_ROOT, "database", "email_dataset.csv"),
        "arquivo_saida": os.path.join(METRICAS_JUDGE_PATH, "email_ollama_output.csv"),
        "coluna_texto": "Email Text",
        "coluna_rotulo": "Email Type",
        "rotulo_positivo": "Phishing Email",
        "rotulo_negativo": "Safe Email",
        "max_rows": 8000
    }
]

# =====================================================
# FUNCOES DE PROCESSAMENTO
# =====================================================

def map_risk_to_label(risk_level, positive_label, negative_label):
    risk_level = str(risk_level).upper()
    if 'MALICIOUS' in risk_level or 'SUSPICIOUS' in risk_level:
        return positive_label
    return negative_label


def chamar_judge(texto: str, risk_level_modelo: str, analysis_details) -> dict:
    """
    Chama o modelo Judge para auditar a classificacao do modelo principal.
    Retorna dict com 'judge_verdict', 'judge_risk_level', 'judge_reason'.
    Em caso de erro, faz fallback silencioso para o resultado original.
    """
    fallback = {
        "judge_verdict": "CONFIRMED",
        "judge_risk_level": risk_level_modelo,
        "judge_reason": "Fallback: judge indisponivel, mantido resultado original."
    }

    if not MODELO_JUDGE:
        fallback["judge_reason"] = "MODELO_JUDGE nao configurado. Mantido resultado original."
        return fallback

    details_str = json.dumps(analysis_details, ensure_ascii=False) if isinstance(analysis_details, list) else str(analysis_details)

    prompt_judge = f"""
    <ORIGINAL_MESSAGE>
    {texto}
    </ORIGINAL_MESSAGE>

    <FIRST_STAGE_CLASSIFICATION>
      risk_level: {risk_level_modelo}
      analysis_details: {details_str}
    </FIRST_STAGE_CLASSIFICATION>
    """

    try:
        response = judge_client.chat(
            model=MODELO_JUDGE,
            messages=[
                {'role': 'system', 'content': PROMPT_SISTEMA_JUDGE},
                {'role': 'user',   'content': prompt_judge}
            ],think=False
        )
        raw = response['message']['content']

        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return {
                "judge_verdict":    data.get("verdict", "CONFIRMED").upper(),
                "judge_risk_level": data.get("final_risk_level", risk_level_modelo).upper(),
                "judge_reason":     data.get("reason", "")[:500]
            }
        return fallback

    except Exception as e:
        fallback["judge_reason"] = f"Erro no judge: {str(e)[:200]}"
        return fallback


def process_dataset_ollama(config):
    """Processa dataset com pipeline completo: Sanitizacao -> RAG -> Safe Browsing -> LLM -> Judge."""
    filename_in  = config['arquivo_entrada']
    filename_out = config['arquivo_saida']
    text_column  = config['coluna_texto']
    label_column = config['coluna_rotulo']
    positive_norm = config['rotulo_positivo'].lower()
    negative_norm = config['rotulo_negativo'].lower()
    max_rows      = config.get('max_rows', 8000)

    print(f"\n{'='*60}")
    print(f"  Processando: {config['nome']} | Modelo: {MODELO_OLLAMA}")
    print(f"  Judge: {MODELO_JUDGE or '(nao configurado)'}")
    print(f"  Pipeline: Sanitizacao -> RAG -> Safe Browsing -> LLM -> Judge")
    print(f"  Max linhas: {max_rows}")
    print(f"{'='*60}")

    skip_count = 0
    if os.path.isfile(filename_out):
        try:
            df_check = pd.read_csv(filename_out)
            skip_count = len(df_check)
            if skip_count >= max_rows:
                print(f"  ✅ Dataset ja processado ({skip_count} linhas). Pulando.")
                return True
            print(f"  ↩️ Retomando da linha {skip_count + 1}...")
        except:
            skip_count = 0

    try:
        df = pd.read_csv(filename_in, nrows=max_rows)
        total_samples = len(df)
    except Exception as e:
        print(f"  ❌ Erro ao ler {filename_in}: {e}")
        return False

    file_exists = os.path.isfile(filename_out)

    fieldnames = [
        'original_text', 'true_label',
        # --- Modelo Principal ---
        'risk_level_modelo',
        'predicted_label_modelo',
        'tempo_inferencia_modelo',
        # --- Judge ---
        'risk_level',
        'predicted_label',
        'judge_verdict',
        'judge_reason',
        'tempo_inferencia_judge',
        # --- Pipeline Auxiliar ---
        'user_response',
        'resultado_safe_browsing',
        'contexto_rag_preview',
        'tempo_sanitizacao',
        'tempo_rag',
        'tempo_safe_browsing',
        'tempo_total',
    ]

    with open(filename_out, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists or skip_count == 0:
            writer.writeheader()

        pbar = tqdm(
            total=total_samples,
            initial=skip_count,
            desc=f"  {config['nome']}",
            unit="msg",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
            ncols=100
        )

        for index, row in df.iterrows():
            if index < skip_count:
                continue

            texto_original = str(row[text_column])
            rotulo_verdadeiro = str(row[label_column]).lower()

            risk_level_modelo       = "ERROR"
            predicted_label_modelo  = "error"
            tempo_inferencia_modelo = 0
            risk_level              = "ERROR"
            predicted_label         = "error"
            judge_verdict           = "N/A"
            judge_reason            = "N/A"
            tempo_inferencia_judge  = 0
            user_response_preview   = ""
            resultado_sb            = "N/A"
            contexto_rag_preview    = "N/A"
            tempo_sanitizacao       = 0
            tempo_rag               = 0
            tempo_safe_browsing     = 0
            tempo_total             = 0

            try:
                # ETAPA 1: Sanitizacao
                t0 = time.time()
                texto = sanitizar_texto(texto_original)
                tempo_sanitizacao = round(time.time() - t0, 4)

                # ETAPA 2: RAG
                t1 = time.time()
                contexto_rag = buscar_exemplos_similares(texto)
                tempo_rag = round(time.time() - t1, 4)

                # ETAPA 3: Safe Browsing
                t2 = time.time()
                links_encontrados = re.findall(r'(https?://\S+)', texto)
                resultado_sb = "Nenhum link na mensagem."
                if links_encontrados:
                    resultado_sb = verificar_link_com_safe_browsing(links_encontrados[0])
                tempo_safe_browsing = round(time.time() - t2, 4)

                # ETAPA 4: Montagem do prompt
                prompt_final = f"""
                <CONTEXT>
                <USER_MESSAGE>{texto}</USER_MESSAGE>
                <TECHNICAL_LINK_ANALYSIS_RESULT>{resultado_sb}</TECHNICAL_LINK_ANALYSIS_RESULT>
                {contexto_rag}
                </CONTEXT>
                """

                # ETAPA 5: Inferencia LLM Principal
                t3 = time.time()
                response = ollama.chat(model=MODELO_OLLAMA, messages=[
                    {'role': 'system', 'content': PROMPT_SISTEMA_BASE},
                    {'role': 'user', 'content': prompt_final}
                ], think=False)
                tempo_inferencia_modelo = round(time.time() - t3, 4)

                resposta_ia = response['message']['content']
                user_response_preview = resposta_ia.replace('\n', ' ')[:300]
                contexto_rag_preview = contexto_rag.replace('\n', ' ')[:200] if contexto_rag else "RAG desativado"

                analysis_details_modelo = []
                risk_level_modelo = "SAFE"
                try:
                    match_json = re.search(r'\{.*\}', resposta_ia, re.DOTALL)
                    if match_json:
                        parsed = json.loads(match_json.group())
                        risk_level_modelo       = parsed.get("risk_level", "SAFE").upper()
                        analysis_details_modelo = parsed.get("analysis_details", [])
                    else:
                        if "MALICIOUS" in resposta_ia.upper():
                            risk_level_modelo = "MALICIOUS"
                        elif "SUSPICIOUS" in resposta_ia.upper():
                            risk_level_modelo = "SUSPICIOUS"
                except Exception:
                    if "MALICIOUS" in resposta_ia.upper():
                        risk_level_modelo = "MALICIOUS"
                    elif "SUSPICIOUS" in resposta_ia.upper():
                        risk_level_modelo = "SUSPICIOUS"

                predicted_label_modelo = map_risk_to_label(risk_level_modelo, positive_norm, negative_norm)

                # ETAPA 6: Judge LLM
                t4 = time.time()
                resultado_judge = chamar_judge(texto, risk_level_modelo, analysis_details_modelo)
                tempo_inferencia_judge = round(time.time() - t4, 4)

                risk_level      = resultado_judge["judge_risk_level"]
                judge_verdict   = resultado_judge["judge_verdict"]
                judge_reason    = resultado_judge["judge_reason"]
                predicted_label = map_risk_to_label(risk_level, positive_norm, negative_norm)

                tempo_total = round(
                    tempo_sanitizacao + tempo_rag + tempo_safe_browsing +
                    tempo_inferencia_modelo + tempo_inferencia_judge, 4
                )

            except Exception as e:
                user_response_preview = str(e)[:300]

            writer.writerow({
                'original_text':           texto_original[:500],
                'true_label':              rotulo_verdadeiro,
                'risk_level_modelo':       risk_level_modelo,
                'predicted_label_modelo':  predicted_label_modelo,
                'tempo_inferencia_modelo': tempo_inferencia_modelo,
                'risk_level':              risk_level,
                'predicted_label':         predicted_label,
                'judge_verdict':           judge_verdict,
                'judge_reason':            judge_reason[:300],
                'tempo_inferencia_judge':  tempo_inferencia_judge,
                'user_response':           user_response_preview,
                'resultado_safe_browsing': resultado_sb,
                'contexto_rag_preview':    contexto_rag_preview,
                'tempo_sanitizacao':       tempo_sanitizacao,
                'tempo_rag':               tempo_rag,
                'tempo_safe_browsing':     tempo_safe_browsing,
                'tempo_total':             tempo_total,
            })

            pbar.set_postfix({
                'LLM':     f'{tempo_inferencia_modelo}s',
                'Judge':   f'{tempo_inferencia_judge}s',
                'verdict': judge_verdict[:4] if judge_verdict != "N/A" else "N/A"
            })
            pbar.update(1)

            if (index + 1) % 50 == 0:
                csvfile.flush()

        pbar.close()

    print(f"  ✅ Processamento concluido para {config['nome']}.")
    return True

# =====================================================
# METRICAS ESTENDIDAS
# =====================================================

def _ic95(valores):
    """Retorna (media, desvio, margem, ic_inf, ic_sup, n) com IC 95% via t de Student."""
    n = len(valores)
    if n < 2:
        return None
    media       = np.mean(valores)
    desvio      = np.std(valores, ddof=1)
    erro_padrao = desvio / np.sqrt(n)
    t_critico   = stats.t.ppf(0.975, df=n - 1)
    margem      = t_critico * erro_padrao
    return media, desvio, margem, media - margem, media + margem, n


def calculate_metrics(config):
    """Calcula metricas completas com IC 95% separado por modelo + estatisticas do Judge."""
    filename_out = config['arquivo_saida']
    pos = config['rotulo_positivo'].lower()
    neg = config['rotulo_negativo'].lower()
    res = []

    res.append(f"\n{'='*55}")
    res.append(f"  {config['nome']}")
    res.append(f"{'='*55}")

    try:
        df = pd.read_csv(filename_out)
        total_original = len(df)
        df_valido = df[df['predicted_label'] != 'error'].copy()
        total_valido = len(df_valido)
        erros = total_original - total_valido

        y_true = df_valido['true_label'].astype(str).tolist()
        y_pred = df_valido['predicted_label'].astype(str).tolist()

        acc  = accuracy_score(y_true, y_pred)
        prec = precision_score(y_true, y_pred, pos_label=pos, zero_division=0)
        rec  = recall_score(y_true, y_pred, pos_label=pos, zero_division=0)
        f1   = f1_score(y_true, y_pred, pos_label=pos, zero_division=0)

        cm = confusion_matrix(y_true, y_pred, labels=[neg, pos])
        tn, fp, fn, tp = cm.ravel()

        especificidade = tn / (tn + fp) if (tn + fp) > 0 else 0

        res.append(f"  Amostras: {total_valido} validas ({erros} erros descartados)")
        res.append(f"")
        res.append(f"  Metricas de Classificacao (resultado pos-Judge):")
        res.append(f"    Acuracia:         {acc*100:.2f}%")
        res.append(f"    Precisao:         {prec*100:.2f}%")
        res.append(f"    Recall:           {rec*100:.2f}%")
        res.append(f"    Especificidade:   {especificidade*100:.2f}%")
        res.append(f"    F1-Score:         {f1*100:.2f}%")
        res.append(f"")
        res.append(f"  Matriz de Confusao:")
        res.append(f"    {'':20s} Previsto '{neg}'{' '*(max(0,14-len(neg)))}Previsto '{pos}'")
        res.append(f"    Real '{neg}'{' '*(max(0,15-len(neg)))}{tn:<12}{fp:<12}")
        res.append(f"    Real '{pos}'{' '*(max(0,15-len(pos)))}{fn:<12}{tp:<12}")
        res.append(f"")
        res.append(f"    TP={tp}  FP={fp}  FN={fn}  TN={tn}")

        # Estatisticas do Judge
        if 'judge_verdict' in df_valido.columns:
            total_j      = len(df_valido)
            confirmados  = (df_valido['judge_verdict'] == 'CONFIRMED').sum()
            corrigidos   = (df_valido['judge_verdict'] == 'CORRECTED').sum()
            pct_conf     = (confirmados / total_j * 100) if total_j > 0 else 0
            pct_corr     = (corrigidos  / total_j * 100) if total_j > 0 else 0
            res.append(f"")
            res.append(f"  Estatisticas do Judge:")
            res.append(f"    Confirmacoes:   {confirmados} ({pct_conf:.1f}%)")
            res.append(f"    Correcoes:      {corrigidos} ({pct_corr:.1f}%)")

        # IC 95% - Modelo Principal
        if 'tempo_inferencia_modelo' in df_valido.columns:
            vals = df_valido['tempo_inferencia_modelo'].dropna().values
            ic = _ic95(vals)
            res.append(f"")
            res.append(f"  Tempo de Inferencia - Modelo Principal ({MODELO_OLLAMA}):")
            if ic:
                media, desvio, margem, ic_inf, ic_sup, n = ic
                res.append(f"    Media:          {media:.2f}s")
                res.append(f"    Desvio Padrao:  {desvio:.2f}s")
                res.append(f"    IC 95%:         {media:.2f}s +/- {margem:.2f}s  [{ic_inf:.2f}s, {ic_sup:.2f}s]")
                res.append(f"    Amostras (n):   {n}")
            else:
                res.append(f"    Dados insuficientes.")

        # IC 95% - Judge
        if 'tempo_inferencia_judge' in df_valido.columns:
            vals_j = df_valido['tempo_inferencia_judge'].dropna().values
            vals_j = vals_j[vals_j > 0]
            ic_j = _ic95(vals_j)
            res.append(f"")
            judge_label = MODELO_JUDGE if MODELO_JUDGE else 'nao configurado'
            res.append(f"  Tempo de Inferencia - Judge ({judge_label}):")
            if ic_j:
                media, desvio, margem, ic_inf, ic_sup, n = ic_j
                res.append(f"    Media:          {media:.2f}s")
                res.append(f"    Desvio Padrao:  {desvio:.2f}s")
                res.append(f"    IC 95%:         {media:.2f}s +/- {margem:.2f}s  [{ic_inf:.2f}s, {ic_sup:.2f}s]")
                res.append(f"    Amostras (n):   {n}")
            else:
                res.append(f"    Dados insuficientes (judge pode nao ter sido configurado).")

        # Tempos Auxiliares
        if 'tempo_rag' in df_valido.columns and 'tempo_safe_browsing' in df_valido.columns:
            tempo_rag_medio   = df_valido['tempo_rag'].dropna().mean()
            tempo_sb_medio    = df_valido['tempo_safe_browsing'].dropna().mean()
            tempo_san_medio   = df_valido['tempo_sanitizacao'].dropna().mean() if 'tempo_sanitizacao' in df_valido.columns else 0
            tempo_total_medio = df_valido['tempo_total'].dropna().mean() if 'tempo_total' in df_valido.columns else 0

            res.append(f"")
            res.append(f"  Tempos Auxiliares (nao incluidos nos ICs):")
            res.append(f"    Sanitizacao (media):    {tempo_san_medio:.4f}s")
            res.append(f"    RAG (media):            {tempo_rag_medio:.4f}s")
            res.append(f"    Safe Browsing (media):  {tempo_sb_medio:.4f}s")
            res.append(f"    Total Pipeline (media): {tempo_total_medio:.2f}s")

    except Exception as e:
        res.append(f"  ❌ Erro ao processar metricas: {e}")

    return res

# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":
    print(f"\n{'#'*60}")
    print(f"  AVALIACAO OLLAMA - Pipeline Completo com Judge")
    print(f"  Modelo Principal: {MODELO_OLLAMA}")
    print(f"  Modelo Judge:     {MODELO_JUDGE or '(nao configurado)'}")
    print(f"  Preparando base do RAG isolada...")

    resetar_e_popular_chromadb(DATASETS_PARA_TESTAR)

    print(f"  RAG: {'Ativo' if RAG_ATIVO else 'Inativo'}")
    print(f"  Safe Browsing: {'Ativo' if SAFE_BROWSING_API_KEY else 'Inativo'}")
    print(f"  Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")

    for config in DATASETS_PARA_TESTAR:
        process_dataset_ollama(config)

    rag_info = f"Ativo ({vector_store._collection.count()} docs)" if RAG_ATIVO else "Inativo"
    sb_info  = "Ativo" if SAFE_BROWSING_API_KEY else "Inativo"

    relatorio = []
    relatorio.append(f"Relatorio Ollama - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    relatorio.append(f"Modelo Principal: {MODELO_OLLAMA} | Judge: {MODELO_JUDGE or 'nao configurado'}")
    relatorio.append(f"RAG: {rag_info} | Safe Browsing: {sb_info}")
    relatorio.append(f"Pipeline: Sanitizacao -> RAG -> Safe Browsing -> LLM Principal -> Judge")

    for config in DATASETS_PARA_TESTAR:
        relatorio.extend(calculate_metrics(config))

    relatorio_texto = "\n".join(relatorio)

    with open(ARQUIVO_RELATORIO_FINAL, 'w', encoding='utf-8') as f:
        f.write(relatorio_texto)

    print(f"\n{relatorio_texto}")
    print(f"\n✅ Relatorio salvo em: {ARQUIVO_RELATORIO_FINAL}")
