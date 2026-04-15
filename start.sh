#!/bin/bash
# Startup script para rodar Django + Email Bot (multi-conta)

echo "===== Application Startup at $(date) ====="

# Rodar migrações do banco de dados
echo "Gerando migrações..."
python manage.py makemigrations --noinput
echo "Aplicando migrações do banco de dados..."
python manage.py migrate --noinput

# Backfill hash_conteudo para registros existentes (sem hash)
echo "Atualizando hashes de registros existentes..."
python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spamapi.settings')
django.setup()
from detector.models import Feedback
updated = 0
for fb in Feedback.objects.filter(hash_conteudo=''):
    fb.hash_conteudo = Feedback.gerar_hash(fb.mensagem_original)
    fb.save(update_fields=['hash_conteudo'])
    updated += 1
print(f'Hashes atualizados: {updated} registros')
"

# Criar superusuário automaticamente (se variáveis estiverem configuradas)
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ]; then
    echo "Criando superusuário..."
    python manage.py createsuperuser --noinput 2>/dev/null || echo "Superusuário já existe ou erro na criação."
else
    echo "Variáveis DJANGO_SUPERUSER_* não configuradas, pulando criação de superusuário."
fi

# ─── Email Bot (multi-conta) ───────────────────────────────────────
# O email_bot.py detecta automaticamente quais contas estão configuradas:
#   - TOKEN_JSON_UECE     → conta UECE
#   - TOKEN_JSON_PESSOAL  → conta Pessoal
#   - TOKEN_JSON          → fallback legado (conta única)
#
# Para desabilitar uma conta específica sem remover o token:
#   - EMAIL_BOT_UECE_ENABLED=false
#   - EMAIL_BOT_PESSOAL_ENABLED=false

HAS_UECE=${TOKEN_JSON_UECE:+1}
HAS_PESSOAL=${TOKEN_JSON_PESSOAL:+1}
HAS_LEGACY=${TOKEN_JSON:+1}

if [ -n "$HAS_UECE" ] || [ -n "$HAS_PESSOAL" ] || [ -n "$HAS_LEGACY" ]; then
    echo "Iniciando email_bot em background..."
    [ -n "$HAS_UECE" ] && echo "  → Conta UECE: habilitada"
    [ -n "$HAS_PESSOAL" ] && echo "  → Conta Pessoal: habilitada"
    [ -n "$HAS_LEGACY" ] && [ -z "$HAS_UECE" ] && [ -z "$HAS_PESSOAL" ] && echo "  → Conta Legado: habilitada"
    python email_bot.py &
else
    echo "Nenhum TOKEN_JSON configurado, email_bot não será iniciado."
fi

# Self-ping keep-alive (evita que o HF Space durma por inatividade)
echo "Iniciando self-ping keep-alive (a cada 25 min)..."
(while true; do
    sleep 1500
    curl -s http://localhost:7860/health/ > /dev/null 2>&1
    echo "[KEEP-ALIVE] Ping enviado em $(date)"
done) &

# Rodar o Django com gunicorn
exec python -m gunicorn spamapi.wsgi:application --bind 0.0.0.0:7860 --workers 2 --threads 4 --timeout 120
