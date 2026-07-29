import os
import csv
import matplotlib.pyplot as plt
import numpy as np

# Configurações de estilo clássico/claro premium (semelhante ao exemplo do usuário)
plt.style.use('default')
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = 'white'
plt.rcParams['text.color'] = 'black'
plt.rcParams['axes.labelcolor'] = 'black'
plt.rcParams['xtick.color'] = 'black'
plt.rcParams['ytick.color'] = 'black'
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['grid.color'] = '#E5E5E5'
plt.rcParams['grid.linestyle'] = '--'
plt.rcParams['grid.alpha'] = 0.7

# Cores únicas e distintas para cada modelo (paleta premium)
MODEL_COLORS = {
    'Llama 3 8B': '#9467BD',                # Lilás / Roxo
    'Gemma 4 12B (Q6_K)': '#D62728',        # Vermelho
    'Mellum 2 12B (Q4_K_M)': '#E377C2',     # Rosa
    'Qwen 3.5 9B': '#17BECF',               # Ciano
    'Ministral 3 14B': '#BCBD22',           # Amarelo-esverdeado
    'DeepSeek v4 Flash': '#1F77B4',         # Azul escuro
    'DeepSeek v4 Pro': '#AEC7E8',           # Azul claro
    'GLM 5.1': '#FF7F0E',                   # Laranja
    'GPT OSS 120B': '#FFBB78',              # Laranja claro
    'Qwen 3.5 397B': '#2CA02C',             # Verde
    'MiniMax m2.7': '#8C564B',              # Marrom
}

def limpar_nome_modelo(nome_completo):
    nome = nome_completo.strip()
    if 'gemma-4-12B' in nome:
        return 'Gemma 4 12B (Q6_K)'
    if 'Mellum2-12B' in nome:
        return 'Mellum 2 12B (Q4_K_M)'
    if 'deepseek-v4-flash' in nome:
        return 'DeepSeek v4 Flash'
    if 'deepseek-v4-pro' in nome:
        return 'DeepSeek v4 Pro'
    if 'glm-5.1' in nome:
        return 'GLM 5.1'
    if 'gpt-oss' in nome:
        return 'GPT OSS 120B'
    if 'qwen3.5:397b' in nome:
        return 'Qwen 3.5 397B'
    if 'qwen3.5:9b' in nome:
        return 'Qwen 3.5 9B'
    if 'llama3:8b' in nome:
        return 'Llama 3 8B'
    if 'ministral-3:14b' in nome:
        return 'Ministral 3 14B'
    if 'minimax-m2.7' in nome:
        return 'MiniMax m2.7'
    return nome

def extrair_tempo(valor_str):
    try:
        return float(valor_str.replace('s', '').strip())
    except ValueError:
        return 0.0

def obter_tipo_modelo(nome_original):
    nome_lower = nome_original.lower()
    if 'cloud' in nome_lower or 'gemini' in nome_lower or 'gpt' in nome_lower or 'glm' in nome_lower or 'minimax' in nome_lower:
        return 'Cloud'
    return 'Local'

def obter_cor_modelo(nome_limpo, index):
    if nome_limpo in MODEL_COLORS:
        return MODEL_COLORS[nome_limpo]
    default_colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
    return default_colors[index % len(default_colors)]

def ler_tabela_todos_modelos(filepath):
    dados = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            modelo = row['Modelo']
            tipo = obter_tipo_modelo(modelo)
            
            sms_tempo = extrair_tempo(row['SMS_Tempo_Média'])
            email_tempo = extrair_tempo(row['Email_Tempo_Média'])
            
            dados.append({
                'modelo_limpo': limpar_nome_modelo(modelo),
                'tipo': tipo,
                'sms_tempo': sms_tempo,
                'email_tempo': email_tempo
            })
    return dados

def ler_resumo_metricas_judge(filepath):
    dados = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=',')
        for row in reader:
            modelo = row['Modelo Principal']
            tipo = obter_tipo_modelo(modelo)
            
            sms_mp_tempo = extrair_tempo(row['SMS Dataset_Tempo_MP_Media'])
            sms_judge_tempo = extrair_tempo(row['SMS Dataset_Tempo_Judge_Media'])
            sms_total = extrair_tempo(row['SMS Dataset_Total_Pipeline'])
            
            email_mp_tempo = extrair_tempo(row['Email Dataset_Tempo_MP_Media'])
            email_judge_tempo = extrair_tempo(row['Email Dataset_Tempo_Judge_Media'])
            email_total = extrair_tempo(row['Email Dataset_Total_Pipeline'])
            
            dados.append({
                'modelo_limpo': limpar_nome_modelo(modelo),
                'tipo': tipo,
                'sms_mp_tempo': sms_mp_tempo,
                'sms_judge_tempo': sms_judge_tempo,
                'sms_total': sms_total,
                'email_mp_tempo': email_mp_tempo,
                'email_judge_tempo': email_judge_tempo,
                'email_total': email_total
            })
    return dados

def plotar_grafico_simples(dados, tipo_dataset, output_path):
    """Gera o gráfico vertical com Locais primeiro, depois Cloud, sem barras de erro (para proporção correta)"""
    # Separar locais e cloud
    locais = [d for d in dados if d['tipo'] == 'Local']
    clouds = [d for d in dados if d['tipo'] == 'Cloud']
    
    chave_tempo = 'sms_tempo' if tipo_dataset == 'SMS' else 'email_tempo'
    
    locais = sorted(locais, key=lambda x: x[chave_tempo])
    clouds = sorted(clouds, key=lambda x: x[chave_tempo])
    
    dados_ordenados = locais + clouds
    num_locais = len(locais)
    
    nomes = [d['modelo_limpo'] for d in dados_ordenados]
    tempos = [d[chave_tempo] for d in dados_ordenados]
    
    # Rótulos para a legenda com a indicação Local/Cloud
    labels_legenda = [f"{d['modelo_limpo']} ({d['tipo']})" for d in dados_ordenados]
    cores = [obter_cor_modelo(d['modelo_limpo'], i) for i, d in enumerate(dados_ordenados)]
    
    fig, ax = plt.subplots(figsize=(11, 8.5), facecolor='white')
    ax.set_facecolor('white')
    
    # Plotar barras verticais sem barras de erro
    x_indices = np.arange(len(nomes))
    bars = ax.bar(x_indices, tempos, color=cores, edgecolor='black', linewidth=0.8, width=0.5)
    
    # Rótulo de tempo em cima de cada barra
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.2f}s',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 4),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=10, fontweight='bold', color='black')
        
    # Título e rótulo do eixo Y
    ax.set_ylabel('Average Inference Time (s)', fontsize=12, fontweight='bold', labelpad=10)
    ax.set_title(f'Model Execution Time - {tipo_dataset}', fontsize=14, fontweight='bold', pad=15)
    
    # Ajustar rótulos do eixo X (rotacionados 40 graus)
    ax.set_xticks(x_indices)
    ax.set_xticklabels(nomes, rotation=40, ha='right', fontsize=10)
    
    # Grid sutil apenas no eixo Y
    ax.grid(axis='y', color='#E5E5E5', linestyle='--', alpha=0.7)
    
    # Linha vertical separadora entre Local e Cloud
    if num_locais > 0 and len(clouds) > 0:
        ax.axvline(x=num_locais - 0.5, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
        max_val = max(tempos)
        ax.text((num_locais - 1) / 2, max_val * 1.35, 'LOCAL MODELS', 
                ha='center', va='center', fontsize=11, fontweight='bold', color='#71717A',
                bbox=dict(facecolor='white', alpha=0.9, edgecolor='none'))
        ax.text(num_locais + (len(clouds) - 1) / 2, max_val * 1.35, 'CLOUD MODELS', 
                ha='center', va='center', fontsize=11, fontweight='bold', color='#F59E0B',
                bbox=dict(facecolor='white', alpha=0.9, edgecolor='none'))
    
    # Definir limite do eixo Y para garantir que a legenda não corte e não tampe os valores
    max_total = max(tempos)
    ax.set_ylim(0, max_total * 1.55)
    
    # Criar legenda customizada no topo centralizada
    handles_ficticios = [plt.Rectangle((0,0),1,1, color=c, ec='k', lw=0.8) for c in cores]
    ax.legend(handles_ficticios, labels_legenda, loc='upper center', bbox_to_anchor=(0.5, 0.98),
              ncol=3, fancybox=True, shadow=True, edgecolor='black', facecolor='white', fontsize=9)
    
    # Ocultar espinhas superior e direita
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#27272A')
    ax.spines['bottom'].set_color('#27272A')
    
    plt.subplots_adjust(bottom=0.22)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Grafico salvo em: {output_path}")

def plotar_grafico_judge(dados, tipo_dataset, output_path):
    """Gera o gráfico empilhado (Modelo Principal + Judge) sem rótulos internos para ficar limpo"""
    # Separar locais e cloud
    locais = [d for d in dados if d['tipo'] == 'Local']
    clouds = [d for d in dados if d['tipo'] == 'Cloud']
    
    chave_mp = 'sms_mp_tempo' if tipo_dataset == 'SMS' else 'email_mp_tempo'
    chave_judge = 'sms_judge_tempo' if tipo_dataset == 'SMS' else 'email_judge_tempo'
    chave_total = 'sms_total' if tipo_dataset == 'SMS' else 'email_total'
    
    # Ordenar cada grupo por tempo total de execução
    locais = sorted(locais, key=lambda x: x[chave_total])
    clouds = sorted(clouds, key=lambda x: x[chave_total])
    
    dados_ordenados = locais + clouds
    num_locais = len(locais)
    
    nomes = [d['modelo_limpo'] for d in dados_ordenados]
    tempos_mp = [d[chave_mp] for d in dados_ordenados]
    tempos_judge = [d[chave_judge] for d in dados_ordenados]
    tempos_total = [d[chave_total] for d in dados_ordenados]
    
    cores_mp = [obter_cor_modelo(d['modelo_limpo'], i) for i, d in enumerate(dados_ordenados)]
    
    fig, ax = plt.subplots(figsize=(11, 9), facecolor='white')
    ax.set_facecolor('white')
    
    # Índices do eixo X
    x_indices = np.arange(len(nomes))
    
    # Plotar Modelo Principal
    bars_mp = ax.bar(x_indices, tempos_mp, color=cores_mp, edgecolor='black', linewidth=0.8, width=0.5)
    # Plotar Judge empilhado
    bars_judge = ax.bar(x_indices, tempos_judge, bottom=tempos_mp, color='#D3D3D3', hatch='//', edgecolor='black', linewidth=0.8, width=0.5)
    
    # Rótulo de tempo total no topo da pilha
    for i, (bar_mp, bar_judge) in enumerate(zip(bars_mp, bars_judge)):
        total = tempos_total[i]
        ax.annotate(f'{total:.2f}s',
                    xy=(bar_mp.get_x() + bar_mp.get_width() / 2, total),
                    xytext=(0, 4),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=10, fontweight='bold', color='black')

    # Título e rótulo do eixo Y
    ax.set_ylabel('Average Pipeline Execution Time (s)', fontsize=12, fontweight='bold', labelpad=10)
    ax.set_title(f'Total Pipeline Execution Time (Model + Judge) - {tipo_dataset}', fontsize=14, fontweight='bold', pad=15)
    
    # Ajustar rótulos do eixo X
    ax.set_xticks(x_indices)
    ax.set_xticklabels(nomes, rotation=40, ha='right', fontsize=10)
    
    # Grid sutil apenas no eixo Y
    ax.grid(axis='y', color='#E5E5E5', linestyle='--', alpha=0.7)
    
    # Linha vertical separadora entre Local e Cloud
    if num_locais > 0 and len(clouds) > 0:
        ax.axvline(x=num_locais - 0.5, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
        max_val = max(tempos_total)
        ax.text((num_locais - 1) / 2, max_val * 1.35, 'LOCAL MODELS', 
                ha='center', va='center', fontsize=11, fontweight='bold', color='#71717A',
                bbox=dict(facecolor='white', alpha=0.9, edgecolor='none'))
        ax.text(num_locais + (len(clouds) - 1) / 2, max_val * 1.35, 'CLOUD MODELS', 
                ha='center', va='center', fontsize=11, fontweight='bold', color='#F59E0B',
                bbox=dict(facecolor='white', alpha=0.9, edgecolor='none'))
        
    # Limite Y com folga para a legenda
    max_total = max(tempos_total)
    ax.set_ylim(0, max_total * 1.55)
    
    # Criar legenda customizada no topo
    handles_legenda = []
    labels_legenda = []
    
    # Adicionar modelos principais à legenda
    for i, d in enumerate(dados_ordenados):
        handles_legenda.append(plt.Rectangle((0,0),1,1, color=cores_mp[i], ec='k', lw=0.8))
        labels_legenda.append(f"{d['modelo_limpo']} ({d['tipo']})")
        
    # Adicionar a barra do Judge
    handles_legenda.append(plt.Rectangle((0,0),1,1, color='#D3D3D3', hatch='//', ec='k', lw=0.8))
    labels_legenda.append("Judge (DeepSeek-v4-Flash Cloud)")
    
    ax.legend(handles_legenda, labels_legenda, loc='upper center', bbox_to_anchor=(0.5, 0.98),
              ncol=3, fancybox=True, shadow=True, edgecolor='black', facecolor='white', fontsize=9)
    
    # Ocultar espinhas superior e direita
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#27272A')
    ax.spines['bottom'].set_color('#27272A')
    
    plt.subplots_adjust(bottom=0.22)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Grafico salvo em: {output_path}")

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Caminhos dos arquivos CSV
    csv_todos_modelos = os.path.join(base_dir, 'metricas_novas', 'tabela_1_todos_modelos.csv')
    csv_judge_modelos = os.path.join(base_dir, 'metricas_judge', 'resumo_metricas_modelos.csv')
    
    # Caminhos de output (renomeados para _v2 para evitar problemas de cache)
    media_dir = os.path.join(base_dir, 'media')
    
    print("Processando tabela_1_todos_modelos.csv...")
    if os.path.exists(csv_todos_modelos):
        dados_simples = ler_tabela_todos_modelos(csv_todos_modelos)
        plotar_grafico_simples(dados_simples, 'SMS', os.path.join(media_dir, 'tempo_modelos_sms_v2.png'))
        plotar_grafico_simples(dados_simples, 'Email', os.path.join(media_dir, 'tempo_modelos_email_v2.png'))
    else:
        print(f"Erro: Arquivo não encontrado: {csv_todos_modelos}")
        
    print("\nProcessando resumo_metricas_modelos.csv...")
    if os.path.exists(csv_judge_modelos):
        dados_judge = ler_resumo_metricas_judge(csv_judge_modelos)
        plotar_grafico_judge(dados_judge, 'SMS', os.path.join(media_dir, 'tempo_judge_sms_v2.png'))
        plotar_grafico_judge(dados_judge, 'Email', os.path.join(media_dir, 'tempo_judge_email_v2.png'))
    else:
        print(f"Erro: Arquivo não encontrado: {csv_judge_modelos}")

if __name__ == '__main__':
    main()
