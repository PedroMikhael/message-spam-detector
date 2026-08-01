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
![Chrome Extension](https://img.shields.io/badge/Chrome_Extension-4285F4?style=for-the-badge&logo=googlechrome&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Hugging Face](https://img.shields.io/badge/Hugging_Face-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black)

<br>

*An intelligent spam and phishing detection system powered by generative AI, LLM-as-a-Judge architecture, RAG (Retrieval-Augmented Generation), real-time link verification, and a dedicated Google Chrome Extension.*

**[Live Demo](https://pedromikhael-verificai.hf.space/swagger/)** · **[Admin Panel](https://pedromikhael-verificai.hf.space/admin/)** · **[Examples](EXAMPLES.md)**

</div>

---

## Table of Contents

- [About the Project](#about-the-project)
- [Features](#features)
- [Google Chrome Extension](#google-chrome-extension)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [API Endpoints](#api-endpoints)
- [LLM-as-a-Judge & Model Benchmarks](#llm-as-a-judge--model-benchmarks)
- [Local Installation](#local-installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Authors](#authors)

---

## About the Project

**VerificAI** is a message and email analysis system that combines **generative AI** with **real-time link verification** and **LLM-as-a-Judge evaluation** to identify spam, phishing, and digital scam attempts.

The system operates across multiple channels:
1. **Automated Email Bot:** Users forward suspicious emails to a dedicated address, and the bot replies with a detailed analysis and traffic light risk classification.
2. **Google Chrome Extension:** Users analyze emails open in their browser (Gmail / Outlook Web) with a single click.
3. **REST API & Webhooks:** Integrations for external tools and automated workflows.

> Developed as an academic requirement for the **Computer Science** program at **UECE** (State University of Ceara), within **LARCES** (Computer Networks and Security Laboratory), under the supervision of Prof. **Rafael Lopes Gomes**.

---

## Features

### Dual AI Engine & LLM-as-a-Judge Pipeline
- **Ollama Cloud** as the primary engine with **load balancing** across multiple API keys (`gpt-oss:120b-cloud`, `deepseek-v4-pro`, etc.)
- **Google Gemini** as an automatic fallback for high availability
- **LLM-as-a-Judge Verification:** A secondary LLM evaluator (`deepseek-v4-flash:cloud`) that validates primary classifications, measuring confirmations vs. corrections for continuous accuracy refinement

### RAG (Retrieval-Augmented Generation)
- **ChromaDB** vector store with **10,000+ documents** from real spam/ham datasets
- Embeddings powered by **BAAI/bge-small-en-v1.5** via HuggingFace
- Similarity search to contextualize analyses with real-world historical examples
- **Active Learning**: user feedback is incorporated back into the vector store

### Real-Time Link Verification
- Integration with **Google Safe Browsing API v4**
- Detection of malware, phishing, social engineering, and unwanted software
- Results feed into the AI analysis context

### Google Chrome Extension (Manifest V3)
- One-click analysis of active emails in **Gmail** and **Outlook Web**
- Intelligent DOM parser extracting subject, sender, body text, and inline Base64 images for multimodal analysis
- Visual traffic light output matching the email bot formatting with instant feedback buttons
- Automatic error handling with a step-by-step forwarding tutorial (`verificai@uece.br`)

### Automated Email Bot
- Continuous monitoring via **Gmail API** (polling every 10s)
- Processing of forwarded emails with intelligent extraction of original content
- Styled **HTML responses** with risk traffic light (green/yellow/red) and feedback links
- **OAuth 2.0** authentication with automatic token refresh

### Admin Dashboard & Active Learning Loop
- Dashboard built with **Django Admin + Jazzmin**
- Real-time accuracy metrics and feedback management
- Incorrect feedback automatically retrains the vector database

---

## Google Chrome Extension

The project includes a Manifest V3 Google Chrome Extension located in `chrome_extension/`.

### Highlights:
- **Zero User Configuration:** Pre-configured to communicate directly with the production backend API (`https://pedromikhael-verificai.hf.space/api/analisar/`).
- **Multimodal Extraction:** Captures text and inline Base64 images directly from the webmail DOM.
- **Traffic Light UI:** Displays color-coded risk levels (**Green** #28a745 for Safe, **Yellow** #ffc107 for Suspicious, **Red** #dc3545 for Malicious), simple Portuguese explanations, practical safety precautions, and feedback buttons.
- **Error Fallback:** If no active email is detected, displays a user-friendly tutorial guiding the user to forward the email to **`verificai@uece.br`**.

### Installation (Developer Mode):
1. Open Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode** (top right).
3. Click **Load unpacked** and select the `chrome_extension/` directory.

---

## Architecture

<div align="center">

![Architecture Diagram](media/architecture_diagram.png)

</div>

**Analysis Flow:**
```
User (Chrome Extension / Email Bot / REST API)
  +-> DOM Parser / Gmail API / Request Payload
       +-> Sanitization (PII Regex removal)
            +-> RAG Search (ChromaDB similarity search)
            +-> URL Verification (Google Safe Browsing API)
            +-> Primary LLM Analysis (Ollama Cloud -> Gemini fallback)
                 +-> LLM-as-a-Judge Validation (DeepSeek Flash)
                      +-> HTML / Popup Response (Traffic light + Feedback links)
                           +-> User Feedback -> Active Learning RAG update
```

---

## Tech Stack

### Application & AI

| Technology | Purpose |
|---|---|
| **Python 3.11** | Primary backend language |
| **Django 5.0+** | Web framework / ORM / Admin |
| **Django REST Framework** | REST API with serializers and CORS support |
| **Google Chrome Extension (MV3)** | Client extension for Gmail & Outlook Web |
| **drf-yasg** | Interactive Swagger/OpenAPI documentation |
| **Google Gemini API** | LLM for message analysis (fallback) |
| **Ollama Cloud** | Primary LLM engine with load balancing |
| **LLM-as-a-Judge** | Secondary LLM evaluator (`deepseek-v4-flash`) for metrics & verification |
| **Google Safe Browsing API v4** | Real-time malicious URL verification |
| **Gmail API (OAuth 2.0)** | Automated email monitoring bot |
| **LangChain** | RAG orchestration (`langchain-chroma`, `langchain-huggingface`) |
| **ChromaDB** | Vector database for RAG |
| **HuggingFace Transformers** | Embeddings (`BAAI/bge-small-en-v1.5`) |

### Infrastructure & DevOps

| Technology | Purpose |
|---|---|
| **Docker** | Application containerization |
| **Hugging Face Spaces** | Cloud hosting & container deployment |
| **Gunicorn** | Production WSGI server |
| **WhiteNoise** | Static file serving |
| **PostgreSQL (Supabase)** | Production database |
| **SQLite** | Local database (fallback) |
| **Git & GitHub** | Version control |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/analisar/` | Analyzes text and optional Base64 images, returning risk classification |
| `GET` | `/api/analises/` | Lists all saved analyses |
| `GET` | `/api/analises/{id}/` | Details of a specific analysis |
| `POST` | `/api/treinar-rag/` | Adds an example to the vector store (Active Learning) |
| `GET` | `/feedback/{id}/{resultado}/` | Registers user feedback (correct/incorrect) |
| `GET` | `/health/` | Health check endpoint |

> **Interactive documentation:** [Swagger UI](https://pedromikhael-verificai.hf.space/swagger/)

---

## LLM-as-a-Judge & Model Benchmarks

The system was rigorously evaluated using an **LLM-as-a-Judge** framework where a high-capability primary model performs initial classification and a dedicated Judge model (`deepseek-v4-flash:cloud`) evaluates decisions, confirming or correcting verdicts across email and SMS datasets.

### Benchmark Results (Email & SMS Datasets)

| Primary Model | Judge Model | SMS Acc. | SMS F1-Score | Email Acc. | Email F1-Score | Email Pipeline Latency |
|---|---|---|---|---|---|---|
| **GLM 5.1** | `deepseek-v4-flash` | **97.47%** | **90.66%** | **93.00%** | **90.35%** | 10.46s |
| **DeepSeek v4 Pro** | `deepseek-v4-flash` | 97.09% | 89.43% | 91.85% | 88.66% | 8.94s |
| **Qwen 3.5 397B** | `deepseek-v4-flash` | 97.02% | 89.11% | 92.16% | 89.21% | 9.85s |
| **MiniMax M2.7** | `deepseek-v4-flash` | 97.22% | 89.78% | 91.79% | 88.50% | 20.49s |
| **GPT-OSS 120B** | `deepseek-v4-flash` | 97.00% | 88.98% | 90.27% | 86.05% | 10.91s |
| **Ministral 3 14B** | `deepseek-v4-flash` | 97.06% | 89.15% | 90.84% | 87.02% | 25.18s |
| **Llama 3 8B** | `deepseek-v4-flash` | 96.79% | 88.04% | 90.18% | 86.07% | 7.38s |

> Detailed evaluation scripts and raw reports available in `metricas_judge/` and `evaluate/`.

---

## Local Installation

### Prerequisites
- Python 3.11+
- Git
- API keys: Google Gemini, Google Safe Browsing, Gmail OAuth (optional)

### Step by Step

**1. Clone the repository:**
```bash
git clone https://github.com/PedroMikhael/whatsapp-spam-detector.git
cd whatsapp-spam-detector
```

**2. Create and activate virtual environment:**
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

**4. Configure environment variables (`.env`):**
```env
SECRET_KEY=your_django_secret_key
GEMINI_API_KEY=your_gemini_key
SAFE_BROWSING_API_KEY=your_safe_browsing_key
OLLAMA_API_KEY=your_ollama_key
OLLAMA_MODEL=gpt-oss:120b-cloud
```

**5. Build vector database and run server:**
```bash
python scripts/build_vector_db.py
python manage.py migrate
python manage.py runserver
```

---

## Usage

### 1. Via Chrome Extension
- Open Chrome, click the **VerificAI** extension icon on any open email in Gmail or Outlook Web to analyze instantly.

### 2. Via Email Bot
- Forward suspicious emails to `verificai@uece.br` / `chatbot.larces@gmail.com` to receive an automated analysis reply.

### 3. Via REST API
- Send a `POST` request to `/api/analisar/` with `{ "texto": "...", "remetente": "..." }`.

---

## Project Structure

```
zap-spam-detector/
├── manage.py                  # Django entry point
├── email_bot.py               # Gmail monitoring bot
├── Dockerfile                 # Production Docker container
├── start.sh                   # Startup script
├── requirements.txt           # Dependencies
│
├── chrome_extension/          # Manifest V3 Google Chrome Extension
│   ├── manifest.json          # Extension configuration & permissions
│   ├── content_script.js      # Gmail & Outlook DOM parser (text + base64 images)
│   ├── popup.html             # Extension UI (Traffic light + Forwarding tutorial)
│   ├── popup.css              # Traffic light styling (#28a745, #ffc107, #dc3545)
│   ├── popup.js               # API caller & UI renderer
│   ├── background.js          # Service worker
│   └── icons/                 # Extension icons (16x16, 48x48, 128x128)
│
├── spamapi/                   # Django settings & URLs
│   ├── settings.py            # Configuration (DB, CORS, Jazzmin)
│   └── urls.py                # Main URL router
│
├── detector/                  # Core application
│   ├── models.py              # Feedback model & hash generation
│   ├── views.py               # API endpoints (analisar, feedback, train)
│   ├── services.py            # AI Engine (Ollama/Gemini), Safe Browsing & RAG
│   ├── serializers.py         # DRF serializers (includes base64 images support)
│   └── sanitizer.py           # PII Regex sanitizer (CPF, CNPJ, phone, cards)
│
├── database/                  # Datasets
│   ├── email_dataset.csv      # Email dataset for RAG
│   └── sms_dataset.csv        # SMS dataset for RAG
│
├── metricas_judge/            # LLM-as-a-Judge reports & metric CSVs
│   ├── resumo_metricas_modelos.csv
│   └── relatorio_metrics_*.txt
│
└── evaluate/                  # Evaluation & benchmark scripts
    ├── evaluate_ollama_cloud.py
    └── generate_csv.py
```

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
