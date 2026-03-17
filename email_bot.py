
import os
import time
import base64
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spamapi.settings') 
django.setup()
from detector.services import analisar_com_IA
from detector.models import Feedback 


SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
CHECK_INTERVAL_SECONDS = 10 

# ─── Configuração das contas ────────────────────────────────────────
# Cada conta é um dicionario com:
#   - name: nome para exibir nos logs
#   - token_file: caminho do arquivo token local
#   - token_env: nome da variável de ambiente com o token JSON
#   - enabled_env: variável de ambiente para habilitar/desabilitar (default: True)

ACCOUNTS = [
    {
        "name": "UECE",
        "token_file": "token_uece.json",
        "token_env": "TOKEN_JSON_UECE",
        "enabled_env": "EMAIL_BOT_UECE_ENABLED",
    },
    {
        "name": "Pessoal",
        "token_file": "token_pessoal.json",
        "token_env": "TOKEN_JSON_PESSOAL",
        "enabled_env": "EMAIL_BOT_PESSOAL_ENABLED",
    },
]


# ─── Pré-processamento de emails ────────────────────────────────────

def extrair_conteudo_original(email_body):
    """Extrai o conteúdo real de um email, removendo cadeias de encaminhamento."""
    FORWARD_SEPARATOR = "---------- Forwarded message ---------"
    
    if FORWARD_SEPARATOR not in email_body:
        return email_body.strip()
    
    
    blocos = email_body.split(FORWARD_SEPARATOR)
    ultimo_bloco = blocos[-1].strip()
    
    
    linhas = ultimo_bloco.split('\n')
    conteudo_limpo = []
    headers_a_pular = ('de:', 'from:', 'date:', 'subject:', 'to:', 'cc:', 'bcc:')
    header_encontrado = False
    
    for linha in linhas:
        linha_stripped = linha.strip().lower()
        
        
        if not header_encontrado and not linha_stripped:
            continue  
        
        if any(linha_stripped.startswith(h) for h in headers_a_pular):
            header_encontrado = True
            continue
        
        
        if header_encontrado and not linha_stripped:
            header_encontrado = False
            continue
        
        
        header_encontrado = False
        conteudo_limpo.append(linha)
    
    return '\n'.join(conteudo_limpo).strip()


def is_mensagem_vazia(texto):
    """Verifica se o conteúdo extraído é vazio ou sem substância."""
    if not texto:
        return True
    
    limpo = texto.strip()
    if len(limpo) < 5:  
        return True
    return False


def authenticate(account):
    """Autentica com a API do Gmail para uma conta específica."""
    creds = None
    account_name = account["name"]
    token_file = account["token_file"]
    token_env = account["token_env"]

    print(f"[{account_name}] Iniciando autenticação...")

    token_json_env = os.environ.get(token_env)
    if token_json_env:
        try:
            token_data = json.loads(token_json_env)
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
            print(f"[{account_name}] Token carregado de variável de ambiente ({token_env}).")
        except Exception as e:
            print(f"[{account_name}] Erro ao carregar token de env: {e}")

    if not creds and os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        print(f"[{account_name}] Token carregado de arquivo ({token_file}).")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print(f"[{account_name}] Renovando token de acesso...")
            creds.refresh(Request())
            if not token_json_env:
                with open(token_file, "w") as f:
                    f.write(creds.to_json())
        else:
            print(f"[{account_name}] Nenhum token válido encontrado. Iniciando autorização manual.")
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            auth_url, _ = flow.authorization_url(prompt='consent')
            print('Por favor, visite este URL para autorizar o acesso:')
            print(auth_url)
            code = input(f'[{account_name}] Digite o código de autorização do navegador aqui: ')
            flow.fetch_token(code=code)
            creds = flow.credentials
            with open(token_file, "w") as f:
                f.write(creds.to_json())

    print(f"[{account_name}]  Autenticação bem-sucedida.")
    return build("gmail", "v1", credentials=creds)


def check_and_process_emails(service, account_name="Bot"):
    """Verifica por e-mails não lidos, analisa com IA e responde."""
    try:
        results = service.users().messages().list(userId="me", labelIds=["INBOX"], q="is:unread").execute()
        messages = results.get("messages", [])

        if not messages:
            print(f"[{account_name}] [{time.strftime('%d/%m/%Y %H:%M:%S')}] Nenhum e-mail novo. Próxima verificação em {CHECK_INTERVAL_SECONDS}s.")
            return

        print(f"\n[{account_name}] [{time.strftime('%d/%m/%Y %H:%M:%S')}] 📬 {len(messages)} e-mail(s) não lido(s) encontrado(s)!")

        for message_info in messages:
            msg = service.users().messages().get(userId="me", id=message_info["id"], format='full').execute()

            headers = msg["payload"]["headers"]
            subject = next((header["value"] for header in headers if header["name"].lower() == "subject"), "Sem Assunto")
            sender = next((header["value"] for header in headers if header["name"].lower() == "from"), "Remetente Desconhecido")

            print(f"\n{'='*60}")
            print(f" [{account_name}] NOVO E-MAIL RECEBIDO")
            print(f"   De: {sender}")
            print(f"   Assunto: {subject}")
            print(f"   ID: {message_info['id']}")
            print(f"{'='*60}")

            if "data" in msg["payload"]["body"]:
                email_body_encoded = msg["payload"]["body"]["data"]
            else:
                parts = msg["payload"].get("parts", [])
                part = next(iter(p for p in parts if p["mimeType"] == "text/plain"), None)
                email_body_encoded = part["body"]["data"] if part else ""

            email_body = base64.urlsafe_b64decode(email_body_encoded).decode("utf-8", errors='ignore')
            
            
            conteudo_limpo = extrair_conteudo_original(email_body)
            
            preview = conteudo_limpo[:200].replace('\n', ' ')
            print(f"   Preview (limpo): {preview}...")

            
            if is_mensagem_vazia(conteudo_limpo):
                print(f"     Mensagem vazia detectada — respondendo sem IA.")
                
                nova_analise = Feedback.objects.create(
                    mensagem_original=conteudo_limpo,
                    remetente=sender,
                    risco_ia="VAZIO",
                    analise_ia="Mensagem vazia — nenhuma análise necessária."
                )
                
                send_reply_vazio(service, sender, subject, nova_analise.id)
                service.users().messages().modify(userId="me", id=message_info["id"], body={'removeLabelIds': ['UNREAD']}).execute()
                print(f"    [{account_name}] Resposta (vazia) enviada e e-mail marcado como lido!")
                print(f"{'='*60}\n")
                continue

            
            print(f"\n Analisando com IA...")
            resultado_analise = analisar_com_IA(conteudo_limpo)
            
            risk_level = resultado_analise.get('risk_level', 'INDETERMINADO')
            motivo = resultado_analise.get('motivo', 'Análise indisponível.')
            precaucao = resultado_analise.get('precaucao', '')
            
            print(f"    Classificação: {risk_level}")
            print(f"    Motivo: {motivo[:150]}...")

            nova_analise = Feedback.objects.create(
                mensagem_original=conteudo_limpo,
                remetente=sender,
                risco_ia=risk_level,
                analise_ia=str(resultado_analise)
            )
            
            print(f"    Salvo no banco (Feedback ID: {nova_analise.id})")

            send_reply(service, sender, subject, motivo, precaucao, nova_analise.id, risk_level)

            service.users().messages().modify(userId="me", id=message_info["id"], body={'removeLabelIds': ['UNREAD']}).execute()
            print(f"    [{account_name}] Resposta enviada e e-mail marcado como lido!")
            print(f"{'='*60}\n")

    except HttpError as error:
        print(f"[{account_name}] [{time.strftime('%d/%m/%Y %H:%M:%S')}] ❌ Erro na API do Gmail: {error}")
    except Exception as e:
        print(f"[{account_name}] [{time.strftime('%d/%m/%Y %H:%M:%S')}] ❌ Erro inesperado: {e}")


def _formatar_resposta_html(message_text):
    """Converte markdown básico (**bold**) e quebras de linha para HTML."""
    # Converter **texto** para <b>texto</b>
    texto_html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', message_text)
    # Converter quebras de linha para <br>
    texto_html = texto_html.replace('\n', '<br>')
    return texto_html


def send_reply(service, to, subject, motivo, precaucao, feedback_id, risk_level="INDETERMINADO"):
    """Cria e envia um e-mail de resposta em HTML com semáforo, tabela e logo LARCES."""
    
    base_url = os.environ.get("FEEDBACK_BASE_URL", "https://pedromikhael-verificai.hf.space")
    link_correto = f"{base_url}/feedback/{feedback_id}/correto/"
    link_incorreto = f"{base_url}/feedback/{feedback_id}/incorreto/"

    
    semaforo_map = {
        "SAFE": {"img": "semaforoVerde.png", "cor": "#28a745", "label": "Segura"},
        "SUSPICIOUS": {"img": "semaforoAmarelo.png", "cor": "#ffc107", "label": "Suspeita"},
        "MALICIOUS": {"img": "semaforoVermelho.png", "cor": "#dc3545", "label": "Maliciosa"},
    }
    semaforo = semaforo_map.get(risk_level, semaforo_map["SUSPICIOUS"])
    semaforo_url = f"https://huggingface.co/spaces/PedroMikhael/VerificAI/resolve/main/media/{semaforo['img']}"
    classificacao = semaforo["label"]
    cor = semaforo["cor"]
    larces_logo = "https://huggingface.co/spaces/PedroMikhael/VerificAI/resolve/main/media/larcesLogo.png"

    html_content = f"""
    <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                @media screen and (max-width: 480px) {{
                    .email-wrapper {{
                        padding: 8px !important;
                    }}
                    .email-container {{
                        border-radius: 8px !important;
                    }}
                    .email-header {{
                        padding: 18px 12px !important;
                    }}
                    .email-header h2 {{
                        font-size: 18px !important;
                    }}
                    .email-body {{
                        padding: 16px 12px !important;
                    }}
                    .email-table td {{
                        display: block !important;
                        width: 100% !important;
                        box-sizing: border-box !important;
                    }}
                    .email-table .label-cell {{
                        border-bottom: none !important;
                        padding-bottom: 2px !important;
                    }}
                    .email-table .value-cell {{
                        padding-top: 2px !important;
                        padding-bottom: 14px !important;
                    }}
                    .btn-feedback {{
                        display: block !important;
                        width: 100% !important;
                        margin-right: 0 !important;
                        margin-bottom: 10px !important;
                        text-align: center !important;
                        box-sizing: border-box !important;
                    }}
                }}
            </style>
        </head>
        <body class="email-wrapper" style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; background: #f4f6f8; padding: 20px; margin: 0;">
            <div class="email-container" style="max-width: 600px; margin: 0 auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08);">
                <div class="email-header" style="background: {cor}; color: white; text-align: center; padding: 24px 16px;">
                    <img src="{semaforo_url}" alt="Semáforo {classificacao}" style="width: 70px; height: auto; margin-bottom: 8px;">
                    <h2 style="margin: 0; font-size: 20px;">Classificação: {classificacao}</h2>
                </div>
                <div class="email-body" style="padding: 24px;">
                    <table class="email-table" style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td class="label-cell" style="padding: 10px 12px; background: #f8f9fa; border-bottom: 2px solid #dee2e6; font-size: 12px; text-transform: uppercase; color: #6c757d; font-weight: bold; letter-spacing: 0.5px; width: 120px;">Classificação</td>
                            <td class="value-cell" style="padding: 10px 12px; border-bottom: 1px solid #eee;"><strong style="color: {cor};">{classificacao}</strong></td>
                        </tr>
                        <tr>
                            <td class="label-cell" style="padding: 10px 12px; background: #f8f9fa; border-bottom: 2px solid #dee2e6; font-size: 12px; text-transform: uppercase; color: #6c757d; font-weight: bold; letter-spacing: 0.5px;">Motivo</td>
                            <td class="value-cell" style="padding: 10px 12px; border-bottom: 1px solid #eee;">{motivo}</td>
                        </tr>
                        <tr>
                            <td class="label-cell" style="padding: 10px 12px; background: #f8f9fa; border-bottom: 2px solid #dee2e6; font-size: 12px; text-transform: uppercase; color: #6c757d; font-weight: bold; letter-spacing: 0.5px;">Precaução</td>
                            <td class="value-cell" style="padding: 10px 12px; border-bottom: 1px solid #eee;">{precaucao}</td>
                        </tr>
                    </table>
                </div>
                <div style="text-align: center; padding: 16px 24px; border-top: 1px solid #eee;">
                    <p style="font-size: 14px; color: #777; margin-bottom: 12px;"><em>Minha análise foi útil?</em></p>
                    <a class="btn-feedback" href="{link_correto}" style="display: inline-block; padding: 12px 20px; background-color: #28a745; color: white; text-decoration: none; border-radius: 8px; margin-right: 8px; font-weight: 600; font-size: 14px; min-height: 44px; line-height: 20px;">Sim, acertou</a>
                    <a class="btn-feedback" href="{link_incorreto}" style="display: inline-block; padding: 12px 20px; background-color: #dc3545; color: white; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 14px; min-height: 44px; line-height: 20px;">Não, errou</a>
                </div>
                <div style="text-align: center; padding: 16px; border-top: 1px solid #f0f0f0;">
                    <img src="{larces_logo}" alt="LARCES - UECE" style="width: 100px; height: auto; opacity: 0.8;">
                </div>
            </div>
        </body>
    </html>
    """
    message = MIMEMultipart("alternative")
    message["subject"] = f"Re: {subject}"
    
    match = re.search(r'<(.+?)>', to)
    if match:
        message["to"] = match.group(1)
    else:
        message["to"] = to
        
    message.attach(MIMEText(html_content, "html"))
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    create_message = {"raw": encoded_message}
    
    service.users().messages().send(userId="me", body=create_message).execute()


def send_reply_vazio(service, to, subject, feedback_id):
    """Envia resposta para emails com conteúdo vazio — sem chamar IA."""
    
    larces_logo = "https://huggingface.co/spaces/PedroMikhael/VerificAI/resolve/main/media/larcesLogo.png"
    
    html_content = f"""
    <html>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; background: #f4f6f8; padding: 20px; margin: 0;">
            <div style="max-width: 600px; margin: 0 auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08);">
                <div style="background: #6c757d; color: white; text-align: center; padding: 24px 16px;">
                    <h2 style="margin: 0; font-size: 20px;">Mensagem sem conteúdo</h2>
                </div>
                <div style="padding: 24px;">
                    <p style="font-size: 15px; color: #333;">
                        Olá! Recebi seu email, mas não encontrei nenhum conteúdo para analisar. 
                        A mensagem parece estar vazia ou contém apenas dados de encaminhamento.
                    </p>
                    <p style="font-size: 15px; color: #333;">
                        <strong>Para que eu possa ajudar:</strong> encaminhe o email suspeito 
                        com o conteúdo original visível, ou cole o texto diretamente no corpo do email.
                    </p>
                </div>
                <div style="text-align: center; padding: 16px; border-top: 1px solid #f0f0f0;">
                    <img src="{larces_logo}" alt="LARCES - UECE" style="width: 100px; height: auto; opacity: 0.8;">
                </div>
            </div>
        </body>
    </html>
    """
    message = MIMEMultipart("alternative")
    message["subject"] = f"Re: {subject}"
    
    match = re.search(r'<(.+?)>', to)
    if match:
        message["to"] = match.group(1)
    else:
        message["to"] = to
        
    message.attach(MIMEText(html_content, "html"))
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    create_message = {"raw": encoded_message}
    
    service.users().messages().send(userId="me", body=create_message).execute()


def run_account_loop(service, account_name):
    """Loop de monitoramento para uma conta específica. Roda em thread separada."""
    print(f"[{account_name}] [{time.strftime('%d/%m/%Y %H:%M:%S')}] ✅ Monitorando e-mails...\n")
    while True:
        check_and_process_emails(service, account_name)
        time.sleep(CHECK_INTERVAL_SECONDS)


def get_enabled_accounts():
    """Retorna lista das contas habilitadas (com token disponível)."""
    enabled = []
    for account in ACCOUNTS:
        
        enabled_flag = os.environ.get(account["enabled_env"], "true").strip().lower()
        if enabled_flag in ("false", "0", "no", "off"):
            print(f"[{account['name']}] ⏭️  Conta desabilitada via {account['enabled_env']}.")
            continue

        
        has_token_env = bool(os.environ.get(account["token_env"]))
        has_token_file = os.path.exists(account["token_file"])

        if not has_token_env and not has_token_file:
            print(f"[{account['name']}] ⚠️  Nenhum token encontrado ({account['token_env']} ou {account['token_file']}). Pulando.")
            continue

        enabled.append(account)

    
    if not enabled:
        legacy_env = os.environ.get("TOKEN_JSON")
        legacy_file = os.path.exists("token.json")
        if legacy_env or legacy_file:
            print("[Legado] Usando TOKEN_JSON / token.json (modo conta única).")
            enabled.append({
                "name": "Legado",
                "token_file": "token.json",
                "token_env": "TOKEN_JSON",
                "enabled_env": "EMAIL_BOT_ENABLED",
            })

    return enabled


if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f" VerificAI Email Bot — Multi-Conta")
    print(f"   Intervalo de verificação: {CHECK_INTERVAL_SECONDS}s")
    print(f"{'='*60}\n")

    enabled_accounts = get_enabled_accounts()

    if not enabled_accounts:
        print(" Nenhuma conta configurada. Configure TOKEN_JSON_UECE e/ou TOKEN_JSON_PESSOAL.")
        sys.exit(1)

    print(f" {len(enabled_accounts)} conta(s) habilitada(s): {', '.join(a['name'] for a in enabled_accounts)}\n")

    
    services = []
    for account in enabled_accounts:
        try:
            service = authenticate(account)
            services.append((service, account["name"]))
        except Exception as e:
            print(f"[{account['name']}]  Falha na autenticação: {e}")

    if not services:
        print(" Nenhuma conta autenticada com sucesso.")
        sys.exit(1)

    
    if len(services) == 1:
        service, name = services[0]
        run_account_loop(service, name)
    else:
        threads = []
        for service, name in services:
            t = threading.Thread(target=run_account_loop, args=(service, name), daemon=True)
            t.start()
            threads.append(t)
            print(f"[{name}]  Thread iniciada.")

       
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print("\n Bot encerrado pelo usuário.")