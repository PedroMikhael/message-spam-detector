---
title: VerificAI - Spam Detector
emoji: 🛡️
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
---

<div align="center">

# VerificAI

**Intelligent protection against spam, phishing and digital threats.**

[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)
![Google Gemini](https://img.shields.io/badge/Google_Gemini-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logo=ollama&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6F61?style=for-the-badge)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Hugging Face](https://img.shields.io/badge/Hugging_Face-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black)

<br>

*An intelligent spam and phishing detection system powered by generative AI, RAG (Retrieval-Augmented Generation), and real-time link verification.*

**[Live Demo](https://pedromikhael-verificai.hf.space/swagger/)** · **[Admin Panel](https://pedromikhael-verificai.hf.space/admin/)** · **[Examples](EXAMPLES.md)**

</div>

---

## Table of Contents

- [About the Project](#about-the-project)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [API Endpoints](#api-endpoints)
- [Model Benchmarks](#model-benchmarks)
- [Local Installation](#local-installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Authors](#authors)

---

## About the Project

**VerificAI** is a message and email analysis system that combines **generative AI** with **real-time link verification** to identify spam, phishing, and digital scam attempts.

The system operates as an email bot: the user forwards suspicious messages to a dedicated Gmail address, and the bot automatically replies with a detailed analysis, risk classification (traffic light system), and feedback links.

> Developed as an academic requirement for the **Computer Science** program at **UECE** (State University of Ceara), within **LARCES** (Computer Networks and Security Laboratory), under the supervision of Prof. **Rafael Lopes Gomes**.

---

## Features

### Dual AI Engine
- **Ollama Cloud** as the primary engine with **load balancing** across multiple API keys
- **Google Gemini** as an automatic fallback for high availability
- Contextual analysis with a cybersecurity-specialized prompt

### RAG (Retrieval-Augmented Generation)
- **ChromaDB** vector store with **10,000+ documents** from real spam/ham datasets
- Embeddings powered by **BAAI/bge-small-en-v1.5** via HuggingFace
- Similarity search to contextualize analyses with real-world examples
- **Active Learning**: user feedback is incorporated back into the vector store

### Real-Time Link Verification
- Integration with **Google Safe Browsing API v4**
- Detection of malware, phishing, social engineering, and unwanted software
- Results feed into the AI analysis context

### Automated Email Bot
- Continuous monitoring via **Gmail API** (polling every 10s)
- Processing of forwarded emails with intelligent extraction of original content
- Styled **HTML responses** with risk traffic light (green/yellow/red) and feedback links
- **OAuth 2.0** authentication with automatic token refresh

### Admin Dashboard
- Dashboard built with **Django Admin + Jazzmin**
- Real-time performance metrics
- Filters by risk level and feedback status
- Search by content and sender

### Feedback Loop System
- Feedback links embedded in responses ("Correct" / "Incorrect")
- Feedback stored in the database for metrics
- Active Learning: incorrect feedback automatically retrains the RAG

---

## Architecture

<div align="center">

![Architecture Diagram](media/architecture_diagram.png)

</div>

**Email Bot Flow:**
```
User forwards suspicious email
  +-> Gmail API (polling)
       +-> Original content extraction
            +-> RAG search (similar examples from ChromaDB)
            +-> Link verification (Safe Browsing API)
            +-> AI analysis (Ollama Cloud -> Gemini fallback)
                 +-> HTML response with traffic light + feedback links
                      +-> User feedback -> Active Learning
```

---

## Tech Stack

### Application & AI

| Technology | Purpose |
|---|---|
| **Python 3.11** | Primary language |
| **Django 5.0+** | Web framework / ORM / Admin |
| **Django REST Framework** | REST API with serializers and views |
| **drf-yasg** | Interactive Swagger/OpenAPI documentation |
| **Google Gemini API** | LLM for message analysis (fallback) |
| **Ollama Cloud** | Primary LLM with load balancing |
| **Google Safe Browsing API v4** | Real-time malicious URL verification |
| **Gmail API (OAuth 2.0)** | Email monitoring and sending |
| **LangChain** | RAG orchestration (langchain-chroma, langchain-huggingface) |
| **ChromaDB** | Vector database for RAG |
| **HuggingFace Transformers** | Embeddings (BAAI/bge-small-en-v1.5) |
| **scikit-learn** | Model evaluation metrics |

### Infrastructure & DevOps

| Technology | Purpose |
|---|---|
| **Docker** | Application containerization |
| **Hugging Face Spaces** | Cloud hosting (production) |
| **Gunicorn** | Production WSGI server |
| **WhiteNoise** | Static file serving |
| **PostgreSQL (Supabase)** | Production database |
| **SQLite** | Local database (fallback) |
| **Git & GitHub** | Version control |

### Data Science & Evaluation

| Technology | Purpose |
|---|---|
| **pandas / numpy** | Dataset processing |
| **matplotlib / seaborn / plotly** | Metrics visualization |
| **scikit-learn** | Accuracy, Precision, Recall, F1-Score |

---

## API Endpoints

The REST API is automatically documented via the Swagger UI.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/analisar/` | Analyzes a message/email and returns its classification |
| `GET` | `/api/analises/` | Lists all saved analyses |
| `GET` | `/api/analises/{id}/` | Details of a specific analysis |
| `POST` | `/api/treinar-rag/` | Adds an example to the vector store (Active Learning) |
| `GET` | `/api/feedback/{id}/{resultado}/` | Registers user feedback (correct/incorrect) |
| `GET` | `/health/` | Health check endpoint |

> **Interactive documentation:** [Swagger UI](https://pedromikhael-verificai.hf.space/swagger/)

### Request Example

```bash
curl -X POST https://pedromikhael-verificai.hf.space/api/analisar/ \
  -H "Content-Type: application/json" \
  -d '{
    "texto": "Congratulations! You have been selected to receive $10,000. Click here: http://suspicious-example.com",
    "remetente": "test@email.com"
  }'
```

### Response Example

```json
{
  "risco": "MALICIOUS",
  "analise": "This message shows typical characteristics of a scam...",
  "links_encontrados": ["http://suspicious-example.com"],
  "resultado_safe_browsing": "MALICIOUS",
  "feedback_id": 42
}
```

---

## Model Benchmarks

The system was evaluated with multiple models using real email and SMS datasets:

### Results -- Email Dataset

| Model | Accuracy | Precision | Recall | F1-Score | Avg. Time |
|---|---|---|---|---|---|
| **Gemini 2.5 Flash** | **89.90%** | **100.00%** | 72.97% | **84.38%** | 4.38s |
| Ollama 8B | 74.13% | 56.74% | **86.71%** | 68.59% | 1.89s |

### Results -- SMS Dataset

| Model | Accuracy | Precision | Recall | F1-Score | Avg. Time |
|---|---|---|---|---|---|
| **Gemini 2.5 Flash** | **89.90%** | **70.59%** | 70.59% | **70.59%** | 2.30s |
| Ollama 8B | 64.33% | 23.54% | **93.52%** | 37.62% | 1.28s |

> Evaluation scripts available in `evaluate/`. Full reports in `metrics/`.

---

## Local Installation

### Prerequisites

- Python 3.11+
- Git
- API keys: Google Gemini, Google Safe Browsing, Gmail OAuth

### Step by Step

**1. Clone the repository:**
```bash
git clone https://github.com/PedroMikhael/message-spam-detector.git
cd message-spam-detector
```

**2. Create and activate a virtual environment:**
```bash
# Windows
py -m venv venv
.\venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
```

**4. Configure environment variables:**

Create a `.env` file in the project root:
```env
SECRET_KEY=your_django_secret_key
GEMINI_API_KEY=your_gemini_key
SAFE_BROWSING_API_KEY=your_safe_browsing_key
OLLAMA_API_KEY=your_ollama_key          # optional
OLLAMA_API_KEY2=your_second_key         # optional (load balancing)
```

**5. Set up Gmail credentials (OAuth 2.0):**
- Create an **OAuth 2.0 Client ID** (Desktop App) in the [Google Cloud Console](https://console.cloud.google.com/)
- Download `credentials.json` and place it in the project root
- Run the authorization script:
```bash
python autorizar_gmail.py
```

**6. Build the vector database (RAG):**
```bash
python build_vector_db.py
```
> This processes the datasets in `database/` and creates the ChromaDB with embeddings.

**7. Run migrations and start the server:**
```bash
python manage.py migrate
python manage.py createsuperuser  # create an admin user
python manage.py runserver
```

**8. (Optional) Start the Email Bot:**

In a separate terminal:
```bash
python email_bot.py
```

---

## Usage

### Via Email
1. Forward a suspicious email to `chatbot.larces@gmail.com`
2. The bot automatically analyzes the content and links
3. You receive a reply with:
   - **SAFE** -- Message is safe
   - **SUSPICIOUS** -- Message is suspicious, proceed with caution
   - **MALICIOUS** -- Message is malicious, do not interact
4. Click "Correct" or "Incorrect" to contribute to the training

### Via API
Send a `POST` request to `/api/analisar/` with the message text (see examples above).

### Admin Panel
Access `/admin/` to view feedback, performance metrics, and manage data.

---

## Project Structure

```
verificai/
|-- manage.py                  # Django entry point
|-- email_bot.py               # Gmail monitoring bot
|-- build_vector_db.py         # ChromaDB build script
|-- autorizar_gmail.py         # OAuth authorization script
|-- requirements.txt           # Python dependencies
|-- Dockerfile                 # Production container
|-- start.sh                   # Startup script (migrations + bot + gunicorn)
|-- .env                       # Environment variables (not committed)
|
|-- spamapi/                   # Django configuration
|   |-- settings.py            # Settings (DB, CORS, Jazzmin, APIs)
|   |-- urls.py                # Main URL routes
|   +-- wsgi.py                # WSGI application
|
|-- detector/                  # Main application
|   |-- models.py              # Feedback model (analysis + feedback loop)
|   |-- views.py               # REST views (analyze, feedback, train RAG)
|   |-- services.py            # Core: AI (Ollama/Gemini), RAG, Safe Browsing
|   |-- serializers.py         # DRF serializers
|   |-- admin.py               # Custom admin with accuracy dashboard
|   +-- tests.py               # Tests
|
|-- database/                  # Datasets for RAG
|   |-- email_dataset.csv      # ~50MB of real emails (spam/ham)
|   +-- sms_dataset.csv        # ~500KB of SMS messages (spam/ham)
|
|-- chroma_db/                 # ChromaDB vector store (generated)
|
|-- evaluate/                  # Model evaluation scripts
|   |-- evaluate_api.py        # Evaluation via REST API
|   |-- evaluate_ollama.py     # Local Ollama benchmark
|   +-- evaluate_ollama_cloud.py # Ollama Cloud benchmark
|
|-- metrics/                   # Performance reports
|   |-- relatorio_metrics_gemini2.5flash.txt
|   |-- relatorio_metrics_ollama3b_v2.txt
|   |-- relatorio_metrics_ollama8b_v2.txt
|   +-- relatorio_metrics_ollama12b_v2.txt
|
+-- EXAMPLES.md                # Documented real test cases
```

---

## Security

- All API keys are managed via **environment variables** (never hardcoded)
- **HTTPS** enabled by default on Hugging Face Spaces
- **CSRF protection** and **CORS** properly configured
- SSL proxy headers configured for reverse proxy
- Container runs as a **non-root user**
- **OAuth 2.0** for Gmail authentication (no passwords stored)

---

## Authors

| Name | Role |
|---|---|
| **Pedro Mikhael** | Developer |
| **Joao Victor** | Developer |
| **Valderlan Nobre** | Scrum Master |


---

<div align="center">

**LARCES** -- Computer Networks and Security Laboratory
**UECE** -- State University of Ceara

*Advisor: Prof. Rafael Lopes Gomes*

</div>
