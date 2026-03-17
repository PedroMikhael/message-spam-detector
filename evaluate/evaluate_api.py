
import requests
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, confusion_matrix, f1_score
import time
import os
from datetime import datetime
import csv 

API_URL = ""
TEMPO_DE_ESPERA_SEGUNDOS = 7.0 
ARQUIVO_RELATORIO_FINAL = 'evaluation_metrics_report.txt' 

# Definir os arquivos CSV, colunas e limites de linhas
DATASETS_PARA_TESTAR = [
    {
        "nome": "SMS Dataset",
        "arquivo_entrada": "sms_dataset.csv", 
        "arquivo_saida": "sms_evaluation_output.csv", 
        "coluna_texto": "Message",
        "coluna_rotulo": "Label",
        "rotulo_positivo": "spam",
        "rotulo_negativo": "ham",
        "max_rows": 100
    },
    {
        "nome": "Email Dataset",
        "arquivo_entrada": "email_dataset.csv", 
        "arquivo_saida": "email_evaluation_output.csv", 
        "coluna_texto": "Email Text",
        "coluna_rotulo": "Email Type",
        "rotulo_positivo": "Phishing Email",
        "rotulo_negativo": "Safe Email",
        "max_rows": 100
    }
]

def map_risk_to_label(risk_level, positive_label, negative_label):
    if risk_level in ['SUSPICIOUS', 'MALICIOUS']:
        return positive_label
    elif risk_level == 'SAFE':
        return negative_label
    else:
        return negative_label

def process_dataset(config):
    """Lê uma amostra do dataset, chama a API e SALVA cada resultado, retomando de onde parou."""
    
    filename_in = config['arquivo_entrada']
    filename_out = config['arquivo_saida']
    text_column = config['coluna_texto']
    label_column = config['coluna_rotulo']
    positive_label = config['rotulo_positivo']
    negative_label = config['rotulo_negativo']
    max_rows = config.get('max_rows', None)
    
    print(f"\n--- Iniciando Processamento do Dataset: {config['nome']} ---")
    
    skip_count = 0
    file_exists = os.path.isfile(filename_out)
    
    if file_exists:
        try:
            df_out = pd.read_csv(filename_out)
            skip_count = len(df_out)
            print(f"Arquivo de saída '{filename_out}' encontrado com {skip_count} resultados. Resumindo a partir da linha {skip_count + 1}...")
        except pd.errors.EmptyDataError:
            print(f"Arquivo de saída '{filename_out}' está vazio. Começando do zero.")
            skip_count = 0
        except Exception as e:
            print(f"ERRO ao ler arquivo de saída '{filename_out}': {e}. Começando do zero.")
            skip_count = 0
    else:
        print(f"Arquivo de saída '{filename_out}' não encontrado. Começando do zero.")

    try:
        df = pd.read_csv(filename_in, nrows=max_rows -1 if max_rows else None)
        total_samples = len(df)
        
        total_samples_in_memory = total_samples
        if total_samples_in_memory <= skip_count:
            print(f"Amostra já está completa com {skip_count} registros. Nenhuma linha nova a processar.")
            return True 
        print(f"Dataset de entrada '{filename_in}' carregado. Processando {total_samples_in_memory - skip_count} novas amostras...")
    except FileNotFoundError:
        print(f"ERRO: Arquivo de entrada '{filename_in}' não encontrado.")
        return False
    except Exception as e:
        print(f"ERRO ao ler o arquivo CSV de entrada: {e}")
        return False

    if text_column not in df.columns or label_column not in df.columns:
        print(f"ERRO: Colunas '{text_column}' ou '{label_column}' não encontradas no arquivo de entrada.")
        return False

    start_time = time.time()
    
    try:
        with open(filename_out, 'a', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['original_text', 'true_label', 'predicted_label', 'risk_level', 'analysis_details']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            if not file_exists or skip_count == 0:
                writer.writeheader() 

            
            for index, row in df.iterrows():
                
               
                if index < skip_count:
                    continue 
                # -------------------------------------
                
                texto = str(row[text_column])
                rotulo_verdadeiro = str(row[label_column])
                rotulo_verdadeiro_norm = rotulo_verdadeiro.lower()
                positive_norm = positive_label.lower()
                negative_norm = negative_label.lower()
                
                if rotulo_verdadeiro_norm not in [positive_norm, negative_norm]:
                    continue

                predicted_label = negative_norm
                risk_level = "ERROR"
                analysis_details_str = "Erro na chamada da API"

                try:
                    response = requests.post(API_URL, json={'texto': texto}, timeout=90)
                    if response.status_code == 200:
                        resultado_api = response.json()
                        risk_level = resultado_api.get('risk_level', 'INDETERMINADO')
                        predicted_label = map_risk_to_label(risk_level, positive_norm, negative_norm)
                        analysis_details_str = str(resultado_api.get('analysis_details', 'N/A'))
                    else:
                        analysis_details_str = f"API Error {response.status_code}: {response.text}"
                        print(f"\nERRO da API na linha {index+1}: Status {response.status_code}.")
                except Exception as e:
                    analysis_details_str = f"Erro Inesperado: {e}"
                    print(f"\nERRO inesperado ao processar linha {index+1}: {e}.")
                
                
                writer.writerow({
                    'original_text': texto[:500],
                    'true_label': rotulo_verdadeiro_norm,
                    'predicted_label': predicted_label,
                    'risk_level': risk_level,
                    'analysis_details': analysis_details_str[:1000]
                })

                
                if (index + 1) % 10 == 0:
                    print(f"  Processado linha {index + 1}/{total_samples}...")
                
                time.sleep(TEMPO_DE_ESPERA_SEGUNDOS) 

    except Exception as e:
        print(f"\nERRO GERAL durante o processamento de {filename_in}: {e}")
        return False 

    end_time = time.time()
    tempo_total_min = (end_time - start_time)/60
    print(f"\n--- Processamento Concluído para {config['nome']} ---")
    print(f"Tempo total (nesta execução): {tempo_total_min:.2f} minutos")
    print(f"Resultados detalhados salvos em: {filename_out}")
    return True 

def calculate_metrics_from_output(config):
   
    filename_out = config['arquivo_saida']
    positive_label = config['rotulo_positivo'].lower()
    negative_label = config['rotulo_negativo'].lower()
    report_lines = []
    report_lines.append(f"\n--- Métricas de Avaliação para: {config['nome']} ---")
    try:
        df_results = pd.read_csv(filename_out)
        if df_results.empty:
            report_lines.append("Arquivo de resultados vazio ou não encontrado.")
            return report_lines
        labels_verdadeiros = df_results['true_label'].tolist()
        predicoes_ia = df_results['predicted_label'].tolist()
        accuracy = accuracy_score(labels_verdadeiros, predicoes_ia)
        precision = precision_score(labels_verdadeiros, predicoes_ia, pos_label=positive_label, zero_division=0)
        recall = recall_score(labels_verdadeiros, predicoes_ia, pos_label=positive_label, zero_division=0)
        f1 = f1_score(labels_verdadeiros, predicoes_ia, pos_label=positive_label, zero_division=0)
        conf_matrix = confusion_matrix(labels_verdadeiros, predicoes_ia, labels=[negative_label, positive_label])
        report_lines.append(f"\nResultados para '{positive_label}' como classe positiva:")
        report_lines.append(f"Acurácia Geral: {accuracy * 100:.2f}%")
        report_lines.append(f"Precisão (Spam): {precision * 100:.2f}%")
        report_lines.append(f"Recall (Spam):   {recall * 100:.2f}%")
        report_lines.append(f"F1-Score:        {f1 * 100:.2f}%")
        report_lines.append("\nMatriz de Confusão:")
        report_lines.append(f"                Previsto '{negative_label}'  Previsto '{positive_label}'")
        report_lines.append(f"Real '{negative_label}'      {conf_matrix[0][0]:<6}           {conf_matrix[0][1]:<6}")
        report_lines.append(f"Real '{positive_label}'      {conf_matrix[1][0]:<6}           {conf_matrix[1][1]:<6}")
        report_lines.append("--------------------------------------------------")
    except Exception as e:
         report_lines.append(f"ERRO ao calcular métricas do arquivo '{filename_out}': {e}")
    return report_lines


if __name__ == "__main__":
    
    
    for config in DATASETS_PARA_TESTAR:
        process_dataset(config)
            
    
    all_report_lines = []
    all_report_lines.append(f"Relatório de Métricas da API VerificAI - Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    all_report_lines.append("==================================================")
    
    for config in DATASETS_PARA_TESTAR:
        metric_lines = calculate_metrics_from_output(config)
        all_report_lines.extend(metric_lines)
        all_report_lines.append("\n") 

   
    try:
        with open(ARQUIVO_RELATORIO_FINAL, 'w', encoding='utf-8') as f:
            for line in all_report_lines:
                f.write(line + '\n')
        print(f"\n\nRelatório de métricas final salvo no arquivo: {ARQUIVO_RELATORIO_FINAL}")
    except Exception as e:
        print(f"\nERRO ao salvar o arquivo de relatório final: {e}")