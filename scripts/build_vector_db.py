import os
import pandas as pd
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Limite de documentos para evitar timeout no HF Spaces build
# 5000 de cada dataset = 10000 total
MAX_ROWS_PER_DATASET = 5000

DATASETS = [
    "database/email_dataset.csv",
    "database/sms_dataset.csv"
]

def load_dataset(path):
    print(f"-> Carregando dados do arquivo: {os.path.abspath(path)}")

    if not os.path.exists(path):
        print(f"❌ Arquivo não encontrado: {path}")
        return []

    # Limita número de linhas para evitar timeout no HF Spaces
    df = pd.read_csv(path, nrows=MAX_ROWS_PER_DATASET)

    # Detecta automaticamente nome das colunas
    possible_text_cols = ["text", "message", "Email Text", "Message"]
    possible_label_cols = ["label", "Label", "Email Type"]

    text_col = next((c for c in possible_text_cols if c in df.columns), None)
    label_col = next((c for c in possible_label_cols if c in df.columns), None)

    if not text_col or not label_col:
        print(f"❌ Arquivo inválido (faltando colunas de texto/label): {path}")
        print("   Colunas encontradas:", df.columns.tolist())
        return []

    df = df[[text_col, label_col]].dropna()

    documents = [
        Document(page_content=row[text_col], metadata={"label": row[label_col]})
        for _, row in df.iterrows()
    ]

    print(f"   Documentos carregados e válidos: {len(documents)}")
    return documents


def main():
    all_docs = []

    # Carrega os dois datasets
    for dataset in DATASETS:
        docs = load_dataset(dataset)
        all_docs.extend(docs)

    print(f"\nTotal de documentos para processamento: {len(all_docs)}")

    # Splitter
    print("\n-> Dividindo documentos em chunks...")
    splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)

    chunks = splitter.split_documents(all_docs)
    print("   Total de chunks criados:", len(chunks))

    if not chunks:
        print("\n⚠️ Nenhum documento/chunk para processar. Pulando criação do ChromaDB.")
        return

    # Embeddings (usando langchain_huggingface atualizado)
    print("\n-> Carregando modelo de embeddings (bge-small)...")
    embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")

    # Cria o banco vetorial
    print("\n-> Criando embeddings e populando o ChromaDB...")

    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory="chroma_db"
    )
    print("\n✅ ChromaDB criado com sucesso!")


if __name__ == "__main__":
    main()
