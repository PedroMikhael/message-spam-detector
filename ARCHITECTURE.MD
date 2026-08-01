# ARCHITECTURE.MD — VerificAI

> **Fonte única de verdade** para IA e desenvolvedores que forem alterar este projeto.
> Toda informação aqui é factual — baseada no código existente em `2026-08-01`.

---

## 1. Visão Geral

**VerificAI** é um sistema de detecção de spam e phishing desenvolvido pelo LARCES/UECE. Analisa e-mails e mensagens via LLM (Ollama Cloud ou Gemini como fallback), usando RAG com ChromaDB para enriquecimento de contexto histórico.

### Canais de entrada de mensagens

| Canal | Descrição |
|---|---|
| **Bot de E-mail** | Monitoramento automático de caixas Gmail (polling a cada 10s) |
| **WhatsApp Webhook** | Webhook POST da Meta WhatsApp Business API |
| **API REST** | Endpoint `POST /api/analisar/` consumido pela extensão Chrome ou outros clientes |
| **Extensão Chrome** | Popup que lê o e-mail aberto no Gmail/Outlook e chama a API |

---

## 2. Estrutura de Diretórios

```
zap-spam-detector/
├── spamapi/                  # Configuração Django (settings, urls, wsgi)
├── detector/                 # App Django principal (lógica de negócio)
│   ├── models.py             # Modelo Feedback (log de análises)
│   ├── views.py              # Endpoints da API REST + página visual
│   ├── services.py           # Lógica de IA: Ollama, Gemini, RAG, SafeBrowsing
│   ├── serializers.py        # Serializers DRF para request/response
│   ├── sanitizer.py          # Sanitização de PII (regex)
│   ├── admin.py              # Configuração do admin Django
│   └── migrations/           # Histórico de migrations (0001–0006)
├── chrome_extension/         # Extensão Chrome (MV3)
│   ├── manifest.json         # Declaração de permissões e scripts
│   ├── content_script.js     # Extrator de e-mail do Gmail/Outlook
│   ├── popup.html/js/css     # Interface do popup
│   └── background.js         # Service Worker
├── database/                 # Datasets de treinamento
│   ├── email_dataset.csv     # Dataset de e-mails (~52MB)
│   ├── sms_dataset.csv       # Dataset de SMS
│   └── balanced_urls.csv     # Dataset de URLs
├── scripts/
│   ├── build_vector_db.py    # Script para popular o ChromaDB no build
│   ├── autorizar_gmail.py    # Script de autorização OAuth Gmail
│   └── teste_rag.py          # Teste isolado do RAG
├── evaluate/                 # Scripts de avaliação de desempenho do modelo
├── tools/                    # Ferramentas auxiliares (geração de gráficos)
├── chroma_db/                # Banco vetorial persistido (gerado em runtime)
├── media/                    # Arquivos de mídia (logos, semáforos)
├── email_bot.py              # Bot de monitoramento de e-mail (processo separado)
├── start.sh                  # Script de startup: migrations + email_bot + gunicorn
├── Dockerfile                # Build Docker (base python:3.11-slim)
├── requirements.txt          # Dependências Python
└── .env                      # Variáveis de ambiente (não commitado)
```

---

## 3. Modelo de Dados

### Tabela: `detector_feedback` (único modelo)

Registra cada análise realizada pelo sistema.

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | AutoField (PK) | Identificador único da análise |
| `mensagem` | TextField | Texto sanitizado (PII removido) da mensagem analisada |
| `remetente` | CharField(255) | E-mail/número sanitizado do remetente |
| `risco_ia` | CharField(50) | Classificação: `SAFE`, `SUSPICIOUS`, `MALICIOUS`, `VAZIO`, `INDETERMINADO` |
| `analise_ia` | TextField | JSON string completo retornado pela IA |
| `treinamento_concluido` | BooleanField | `True` se o dado já foi ingerido no ChromaDB |
| `hash_conteudo` | CharField(64, index) | SHA-256 do texto normalizado — busca rápida por duplicatas |
| `timestamp` | DateTimeField | Data/hora da análise (auto_now_add) |

> **Nota:** O campo `feedback_usuario_correto` foi **removido** na migration `0006`. Não existe mais feedback humano.

### Geração do hash (`Feedback.gerar_hash`)
```python
normalizado = re.sub(r'\s+', ' ', texto).strip().lower()
return hashlib.sha256(normalizado.encode('utf-8')).hexdigest()
```
O hash é gerado automaticamente no `save()` se `hash_conteudo` estiver vazio.

---

## 4. API REST — Endpoints

Base URL de produção: `https://pedromikhael-verificai.hf.space`

| Método | Rota | View | Descrição |
|---|---|---|---|
| `POST` | `/api/analisar/` | `analisar_mensagem` | Analisa e-mail/mensagem com a IA |
| `GET` | `/api/analises/` | `listar_analises` | Lista todas as análises (histórico) |
| `GET` | `/api/analises/<id>/` | `detalhe_analise` | Detalhe de uma análise específica |
| `POST` | `/api/treinar/` | `treinar_rag` | Adiciona exemplo manualmente ao ChromaDB |
| `GET/POST` | `/api/spam/` | `webhook_whatsapp` | Webhook WhatsApp Business |
| `GET` | `/analise/<id>/visualizar/` | `visualizar_analise` | Página HTML visual com semáforo |
| `GET` | `/swagger/` | drf-yasg | Documentação Swagger automática |
| `GET` | `/health/` | lambda | Health check (`{"status": "ok"}`) |
| `GET` | `/admin/` | Django admin | Painel administrativo |
| `GET` | `/` | RedirectView | Redireciona para `/swagger/` |

### Payload `POST /api/analisar/`

```json
{
  "texto": "string (obrigatório)",
  "remetente": "string (opcional, default: swagger-test)",
  "imagens": ["base64_string"]
}
```

### Resposta `POST /api/analisar/`

```json
{
  "risk_level": "SAFE | SUSPICIOUS | MALICIOUS | INDETERMINADO",
  "classificacao": "Segura | Suspeita | Maliciosa | Indeterminado",
  "motivo": "Explicação em português para o usuário",
  "precaucao": "Recomendação prática em português",
  "semaforo_image_url": "URL da imagem do semáforo",
  "analise_url": "URL da página visual de análise",
  "analysis_details": ["lista de pontos técnicos (uso interno)"]
}
```

> **Não existe mais** campo `feedback_id` na resposta. Não há botões de feedback humano.

---

## 5. Fluxo de Análise da IA (`analisar_com_IA`)

```
Texto recebido
      │
      ▼
[1] Sanitização PII (sanitizar_texto)
      │
      ▼
[2] Busca por hash no Django DB (Feedback.hash_conteudo)
      │ ← Encontrado: retorna resultado cacheado imediatamente
      ▼
[3] Busca exata no ChromaDB (buscar_exemplo_igual, k=1)
      │ ← Encontrado: retorna resultado mapeado imediatamente
      ▼
[4] Verificação de links via Google Safe Browsing API
      │   (apenas o 1º link encontrado com regex https?://\S+)
      ▼
[5] Busca de exemplos similares no ChromaDB (k=3, similarity_search)
      │   → contexto_historico injetado no prompt
      ▼
[6] Chamada à LLM
      │   → Ollama Cloud (load balancing com 2 keys, ordem aleatória)
      │   → Gemini 3 Flash Preview (fallback se Ollama falhar)
      ▼
[7] Parse do JSON retornado pela LLM
      ▼
Resultado: {risk_level, motivo, precaucao, analysis_details}
```

### Mapeamento de labels ChromaDB → risk_level

| Label ChromaDB | risk_level |
|---|---|
| `HAM`, `SAFE` | `SAFE` |
| `SPAM`, `MALICIOUS`, `PHISHING` | `MALICIOUS` |
| `SUSPICIOUS` | `SUSPICIOUS` |
| (qualquer outro) | `SUSPICIOUS` (default) |

---

## 6. RAG / ChromaDB

- **Embedding model:** `BAAI/bge-small-en-v1.5` (HuggingFace)
- **Persist directory:** `chroma_db/` (relativo à raiz do projeto)
- **Inicialização:** no módulo `services.py` no momento do `import` (startup do Django)

### Auto-populate

Se vazio na inicialização, popula com **100 linhas** de cada dataset em `database/`.

### Retroalimentação automática (Active Learning)

Toda análise bem-sucedida chama `adicionar_ao_chromadb(texto, rotulo=risk_level)` automaticamente. Sem intervenção humana. O campo `treinamento_concluido` é marcado `True` após a ingestão.

---

## 7. Sanitizador de PII (`detector/sanitizer.py`)

Aplicado antes de qualquer armazenamento no banco e antes de enviar para a LLM.

| Dado | Placeholder |
|---|---|
| CNPJ | `[CNPJ]` |
| CPF | `[CPF]` |
| Cartão de crédito | `[CARTAO]` |
| Chave PIX (UUID) | `[PIX]` |
| Dados bancários (agência/conta) | `[DADOS_BANCARIOS]` |
| Telefone brasileiro | `[TELEFONE]` |
| CEP | `[CEP]` |
| E-mail (só parte do usuário) | `[USUARIO]@dominio.com` |
| RG | `[RG]` |

> **Regra:** Links HTTP/HTTPS nunca são removidos — necessários para análise de phishing.

---

## 8. Bot de E-mail (`email_bot.py`)

Processo Python independente rodando em paralelo ao Django.

### Contas configuradas

```python
ACCOUNTS = [
    {"name": "UECE",    "token_file": "token_uece.json",    "token_env": "TOKEN_JSON_UECE",    "enabled_env": "EMAIL_BOT_UECE_ENABLED"},
    {"name": "Pessoal", "token_file": "token_pessoal.json", "token_env": "TOKEN_JSON_PESSOAL", "enabled_env": "EMAIL_BOT_PESSOAL_ENABLED"},
]
# Fallback legado: TOKEN_JSON / token.json
```

### Fluxo por conta (a cada 10s)

```
Gmail API polling → filtra não lidos INBOX → extrai partes MIME →
extrair_conteudo_original() → sanitizar_texto() → is_mensagem_vazia()? →
analisar_com_IA() → Feedback.objects.create() →
adicionar_ao_chromadb() → send_reply() → marcar como lido
```

### Funções principais

| Função | Descrição |
|---|---|
| `authenticate(account)` | OAuth2 Gmail com refresh automático |
| `check_and_process_emails(service, account_name)` | Loop principal |
| `extrair_partes_email(payload)` | Parser MIME recursivo |
| `obter_texto_email(partes)` | Extrai text/plain ou text/html |
| `obter_imagens_base64(...)` | Extrai imagens inline via attachment download |
| `extrair_conteudo_original(email_body)` | Remove cadeias de encaminhamento |
| `send_reply(service, to, subject, motivo, precaucao, risk_level)` | HTML com semáforo |
| `send_reply_vazio(service, to, subject)` | Resposta para e-mails sem conteúdo |

---

## 9. Extensão Chrome

**Manifest Version:** 3 | **Versão:** 1.0.0

### Arquivos

| Arquivo | Responsabilidade |
|---|---|
| `manifest.json` | Permissões, scripts, ícones |
| `content_script.js` | Extrai assunto, remetente, corpo e imagens do Gmail/Outlook |
| `popup.html` | Tela de loading, resultado (semáforo + tabela), tela de erro |
| `popup.js` | Solicita dados via `chrome.runtime.sendMessage`, chama `/api/analisar/`, exibe resultado |
| `popup.css` | Estilos (sem seção de feedback desde `2026-08-01`) |
| `background.js` | Service Worker mínimo |

### Extração por plataforma

- **Gmail:** `h2.hP` (assunto), `span.gD` (remetente), `div.a3s.aiL` (corpo, última da thread)
- **Outlook:** `[role="heading"]`, `span[title*="@"]`, `div[aria-label="Message body"]`

### API URL (hardcoded em popup.js)

```javascript
const API_URL = "https://pedromikhael-verificai.hf.space/api/analisar/";
```

---

## 10. Integração com LLMs

### Ollama Cloud

- Endpoint: `https://ollama.com`
- Modelo: `gpt-oss:120b-cloud` (configurável via `OLLAMA_MODEL`)
- Load balancing: 2 clientes (`OLLAMA_API_KEY`, `OLLAMA_API_KEY2`), ordem aleatória

### Gemini (fallback)

- Modelo: `gemini-3-flash-preview`
- SDK: `google.generativeai` (depreciado — migração recomendada para `google.genai`)

### System Prompt

Instruções em inglês. Identidade: "VerificAI, desenvolvido pelo LARCES/UECE". Saída: JSON estrito com `risk_level`, `analysis_details`, `motivo`, `precaucao`. O parse usa `re.search(r'\{.*\}', ..., re.DOTALL)`.

---

## 11. Integrações Externas

| Serviço | Uso | Variável de Configuração |
|---|---|---|
| Google Gmail API | Ler/responder e-mails | OAuth2, `credentials.json`, tokens por conta |
| Google Safe Browsing v4 | Verificar URLs | `SAFE_BROWSING_API_KEY`, `SAFE_BROWSING_API_KEY2` |
| Ollama Cloud | LLM principal | `OLLAMA_API_KEY`, `OLLAMA_API_KEY2`, `OLLAMA_MODEL` |
| Google Gemini API | LLM fallback | `GEMINI_API_KEY` |
| WhatsApp Business API | Webhook de mensagens | `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN` |
| HuggingFace Spaces | Deploy produção | Container Docker, porta 7860 |

---

## 12. Infraestrutura e Deploy

### Docker

- Base: `python:3.11-slim`, usuário `user` (uid 1000, não-root)
- Porta: `7860`
- Build: instala deps → collectstatic → `build_vector_db.py`

### Startup (`start.sh`)

```
makemigrations → migrate → backfill hashes →
[createsuperuser] → email_bot.py & → self-ping & → gunicorn
```

Gunicorn: `--workers 2 --threads 4 --timeout 120`
Self-ping: `curl http://localhost:7860/health/` a cada 1500s (25min)

### Banco de dados

- Desenvolvimento: SQLite (`db.sqlite3`)
- Produção: PostgreSQL via `DATABASE_URL`

---

## 13. Variáveis de Ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `SECRET_KEY` | ✅ | Django secret key |
| `DATABASE_URL` | ✅ (prod) | URL PostgreSQL |
| `GEMINI_API_KEY` | ✅ | Chave Gemini (fallback LLM) |
| `SAFE_BROWSING_API_KEY` | ✅ | Chave Safe Browsing |
| `SAFE_BROWSING_API_KEY2` | ➖ | Chave alternativa Safe Browsing |
| `OLLAMA_API_KEY` | ➖ | Chave Ollama Cloud (LLM 1) |
| `OLLAMA_API_KEY2` | ➖ | Chave Ollama Cloud (LLM 2) |
| `OLLAMA_MODEL` | ➖ | Modelo Ollama (default: `gpt-oss:120b-cloud`) |
| `WHATSAPP_ACCESS_TOKEN` | ➖ | Token WhatsApp Business |
| `WHATSAPP_PHONE_NUMBER_ID` | ➖ | ID do número WhatsApp |
| `WHATSAPP_VERIFY_TOKEN` | ➖ | Token de verificação webhook |
| `TOKEN_JSON_UECE` | ➖ | Token OAuth Gmail conta UECE |
| `TOKEN_JSON_PESSOAL` | ➖ | Token OAuth Gmail conta Pessoal |
| `TOKEN_JSON` | ➖ | Token OAuth Gmail legado |
| `EMAIL_BOT_UECE_ENABLED` | ➖ | `false` para desabilitar conta UECE |
| `EMAIL_BOT_PESSOAL_ENABLED` | ➖ | `false` para desabilitar conta Pessoal |
| `DJANGO_SUPERUSER_USERNAME` | ➖ | Auto-criação superusuário |
| `DJANGO_SUPERUSER_PASSWORD` | ➖ | Auto-criação superusuário |
| `DJANGO_SUPERUSER_EMAIL` | ➖ | Auto-criação superusuário |
| `ALLOWED_HOSTS` | ➖ | Hosts permitidos pelo Django |
| `CORS_ALLOWED_ORIGINS` | ➖ | Origens permitidas para CORS |

---

## 14. Dependências Python Principais

| Grupo | Pacotes |
|---|---|
| **Web Framework** | Django≥5.0, djangorestframework, drf-yasg, gunicorn, whitenoise, django-cors-headers, django-jazzmin |
| **LLM / IA** | `google-generativeai`, `ollama`, `langchain-chroma`, `langchain-huggingface`, `langchain-google-genai` |
| **Vector DB** | `chromadb` |
| **ML** | `torch`, `transformers`, `sentence-transformers`, `scikit-learn` |
| **Google APIs** | `google-api-python-client`, `google-auth-oauthlib` |
| **Dados** | `pandas`, `numpy` |
| **HTML/Imagem** | `beautifulsoup4`, `Pillow` |
| **Utilitários** | `python-decouple`, `requests`, `dj-database-url`, `psycopg2-binary` |
| **Visualização** | `matplotlib`, `seaborn`, `plotly` |

---

## 15. Padrões e Convenções do Projeto

1. **PII nunca chega ao banco nem à LLM sem sanitização.** `sanitizar_texto()` é chamada explicitamente em toda entrada de usuário.

2. **Sem feedback humano.** Não existe campo `feedback_usuario_correto`. Toda retroalimentação é automática via `adicionar_ao_chromadb()` após cada análise.

3. **Deduplicação por hash SHA-256.** Verificado sempre antes de chamar a LLM. Hash gerado automaticamente no `save()` do modelo.

4. **Classificação interna em inglês** (`SAFE`, `SUSPICIOUS`, `MALICIOUS`). Strings em português (`Segura`, `Suspeita`, `Maliciosa`) são apenas para exibição ao usuário.

5. **Semáforo visual** é o elemento central da UI: `#28a745` (SAFE), `#ffc107` (SUSPICIOUS), `#dc3545` (MALICIOUS).

6. **Imagens inline** trafegam sempre como base64. Content script usa Canvas API; email_bot usa Gmail Attachment API.

7. **O email_bot é um processo Python independente**, não task do Django. Gerenciado pelo `start.sh` via `&`.

8. **A extensão Chrome aponta fixamente** para `https://pedromikhael-verificai.hf.space/api/analisar/`. Para mudar o ambiente, altere `API_URL` em `popup.js`.

9. **O parse da resposta da LLM é tolerante** (`re.search` com DOTALL). Se não encontrar JSON válido, retorna `INDETERMINADO`.

10. **Migrations são sequenciais de 0001 a 0006.** Nunca editar migrations existentes; sempre criar novas via `makemigrations`.
