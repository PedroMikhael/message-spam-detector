import ollama
import pandas as pd
import time
import os
import csv
from datetime import datetime
from sklearn.metrics import accuracy_score, precision_score, recall_score, confusion_matrix, f1_score
import numpy as np
from scipy import stats

MODELO_OLLAMA = 'llama3.2:3b' 
ARQUIVO_RELATORIO_FINAL = 'relatorio_metrics_ollama.txt'

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
    
    **FORMATO DE SAÍDA (Obrigatório e Estrito):**
    Your final response MUST BE a single, valid JSON object and nothing else.
    {{
      "risk_level": "SAFE, SUSPICIOUS, or MALICIOUS",
      "analysis_details": ["point 1", "point 2"],
      "user_response": "Texto em português"
    }}
    </INSTRUCTIONS>
"""

DATASETS_PARA_TESTAR = [
    {
        "nome": "SMS Dataset",
        "arquivo_entrada": "sms_dataset.csv", 
        "arquivo_saida": "sms_ollama_output.csv", 
        "coluna_texto": "Message",
        "coluna_rotulo": "Label",
        "rotulo_positivo": "spam",
        "rotulo_negativo": "ham",
        "max_rows": 100
    },
    {
        "nome": "Email Dataset",
        "arquivo_entrada": "email_dataset.csv", 
        "arquivo_saida": "email_ollama_output.csv", 
        "coluna_texto": "Email Text",
        "coluna_rotulo": "Email Type",
        "rotulo_positivo": "Phishing Email",
        "rotulo_negativo": "Safe Email",
        "max_rows": 100
    }
]

def map_risk_to_label(risk_level, positive_label, negative_label):
    risk_level = str(risk_level).upper()
    if 'MALICIOUS' in risk_level or 'SUSPICIOUS' in risk_level:
        return positive_label
    return negative_label

def process_dataset_ollama(config):
    filename_in = config['arquivo_entrada']
    filename_out = config['arquivo_saida']
    text_column = config['coluna_texto']
    label_column = config['coluna_rotulo']
    positive_norm = config['rotulo_positivo'].lower()
    negative_norm = config['rotulo_negativo'].lower()
    max_rows = config.get('max_rows', 100)

    print(f"\n--- Processando: {config['nome']} | Modelo: {MODELO_OLLAMA} ---")

    skip_count = 0
    if os.path.isfile(filename_out):
        try:
            df_check = pd.read_csv(filename_out)
            skip_count = len(df_check)
            if skip_count >= max_rows: return True
            print(f"Retomando da linha {skip_count + 1}...")
        except: skip_count = 0

    try:
        df = pd.read_csv(filename_in, nrows=max_rows)
        total_samples = len(df)
    except Exception as e:
        print(f"Erro: {e}")
        return False

    file_exists = os.path.isfile(filename_out)
    
    with open(filename_out, 'a', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['original_text', 'true_label', 'predicted_label', 'risk_level', 'user_response', 'tempo_resposta']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists or skip_count == 0: writer.writeheader()

        for index, row in df.iterrows():
            if index < skip_count: continue

            texto = str(row[text_column])
            rotulo_verdadeiro = str(row[label_column]).lower()
            
            prompt_final = f"""
            <CONTEXT>
            <USER_MESSAGE>{texto}</USER_MESSAGE>
            <TECHNICAL_LINK_ANALYSIS_RESULT>SEGURO</TECHNICAL_LINK_ANALYSIS_RESULT>
            <HISTORICAL_SIMILAR_EXAMPLES>Nenhum exemplo histórico fornecido para este teste.</HISTORICAL_SIMILAR_EXAMPLES>
            </CONTEXT>
            """
            
            inicio_msg = time.time()
            try:
                response = ollama.chat(model=MODELO_OLLAMA, messages=[
                    {'role': 'system', 'content': PROMPT_SISTEMA_BASE},
                    {'role': 'user', 'content': prompt_final}
                ])
                
                resposta_ia = response['message']['content']
                tempo_ia = round(time.time() - inicio_msg, 2)
                
                risk_level = "SAFE"
                if "MALICIOUS" in resposta_ia.upper(): risk_level = "MALICIOUS"
                elif "SUSPICIOUS" in resposta_ia.upper(): risk_level = "SUSPICIOUS"
                
                predicted_label = map_risk_to_label(risk_level, positive_norm, negative_norm)
                user_response_preview = resposta_ia.replace('\n', ' ')[:300]

            except Exception as e:
                predicted_label, risk_level, user_response_preview, tempo_ia = "error", "ERROR", str(e), 0

            writer.writerow({
                'original_text': texto[:500],
                'true_label': rotulo_verdadeiro,
                'predicted_label': predicted_label,
                'risk_level': risk_level,
                'user_response': user_response_preview,
                'tempo_resposta': tempo_ia
            })

            if (index + 1) % 20 == 0:
                csvfile.flush()
                print(f"  [Checkpoint] {index + 1}/{total_samples}...")

    return True

def calculate_metrics(config):
    filename_out = config['arquivo_saida']
    pos = config['rotulo_positivo'].lower()
    neg = config['rotulo_negativo'].lower()
    res = [f"\n--- {config['nome']} ---"]
    try:
        df = pd.read_csv(filename_out)
        df = df[df['predicted_label'] != 'error']
        y_t, y_p = df['true_label'].tolist(), df['predicted_label'].tolist()
        res.append(f"Acurácia: {accuracy_score(y_t, y_p)*100:.2f}%")
        res.append(f"F1-Score: {f1_score(y_t, y_p, pos_label=pos, zero_division=0)*100:.2f}%")
        
        # --- Intervalo de Confiança (95%) para o Tempo de Resposta ---
        tempos = df['tempo_resposta'].dropna().values
        n = len(tempos)
        media = np.mean(tempos)
        desvio_padrao = np.std(tempos, ddof=1)  # desvio padrão amostral
        erro_padrao = desvio_padrao / np.sqrt(n)
        
        # t crítico bicaudal para 95% de confiança
        t_critico = stats.t.ppf(0.975, df=n - 1)
        margem_erro = t_critico * erro_padrao
        ic_inferior = media - margem_erro
        ic_superior = media + margem_erro
        
        res.append(f"Tempo Médio: {media:.2f}s")
        res.append(f"Desvio Padrão: {desvio_padrao:.2f}s")
        res.append(f"IC 95%: {media:.2f}s ± {margem_erro:.2f}s  [{ic_inferior:.2f}s, {ic_superior:.2f}s]")
        res.append(f"Amostras (n): {n}")
    except Exception as e:
        res.append(f"Erro ao processar métricas: {e}")
    return res

if __name__ == "__main__":
    for config in DATASETS_PARA_TESTAR:
        process_dataset_ollama(config)
    
    relatorio = [f"Relatório Ollama - {datetime.now()}"]
    for config in DATASETS_PARA_TESTAR:
        relatorio.extend(calculate_metrics(config))
    
    with open(ARQUIVO_RELATORIO_FINAL, 'w', encoding='utf-8') as f:
        f.write("\n".join(relatorio))
    print(f"Relatório salvo!")