from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.conf import settings
from .models import Feedback
from .services import analisar_com_IA, enviar_mensagem_whatsapp, adicionar_ao_chromadb
from .sanitizer import sanitizar_texto
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render, get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .serializers import (
    AnalisarEmailSerializer,
    AnaliseResponseSerializer,
    FeedbackSerializer,
    TreinarRAGSerializer,
    TreinarRAGResponseSerializer,
)


SEMAFORO_MAP = {
    "SAFE": {"img": "semaforoVerde.png", "cor": "#28a745", "label": "Segura"},
    "SUSPICIOUS": {"img": "semaforoAmarelo.png", "cor": "#ffc107", "label": "Suspeita"},
    "MALICIOUS": {"img": "semaforoVermelho.png", "cor": "#dc3545", "label": "Maliciosa"},
}
SEMAFORO_DEFAULT = {"img": "semaforoAmarelo.png", "cor": "#ffc107", "label": "Indeterminado"}

HF_MEDIA_BASE = "https://huggingface.co/spaces/PedroMikhael/VerificAI/resolve/main/media"
LARCES_LOGO_URL = f"{HF_MEDIA_BASE}/larcesLogo.png"


@swagger_auto_schema(
    method='post',
    operation_id='analisar_mensagem',
    operation_summary='Analisar Email/Mensagem',
    operation_description='Envia um texto para análise de spam/phishing pela IA. Retorna classificação, motivo, precaução e imagem do semáforo.',
    request_body=AnalisarEmailSerializer,
    responses={200: AnaliseResponseSerializer, 400: 'Texto não fornecido'},
    tags=['Análise'],
)
@api_view(['POST'])
def analisar_mensagem(request):
    """Analisa um email/mensagem e retorna a classificação de risco."""
    serializer = AnalisarEmailSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    texto = serializer.validated_data['texto']
    remetente = serializer.validated_data.get('remetente', 'swagger-test')
    imagens = serializer.validated_data.get('imagens', None) or None

    # Sanitizar dados sensíveis antes de qualquer processamento
    texto = sanitizar_texto(texto).texto_sanitizado
    remetente = sanitizar_texto(remetente).texto_sanitizado

    try:
        resultado_analise = analisar_com_IA(texto, imagens=imagens, debug=True)
        
        risk_level = resultado_analise.get('risk_level', 'INDETERMINADO')

        feedback_obj = Feedback.objects.create(
            mensagem=texto,
            remetente=remetente,
            risco_ia=risk_level,
            analise_ia=str(resultado_analise)
        )

        # Retroalimentação automática: classificação da IA vai direto pro banco vetorial
        adicionar_ao_chromadb(texto=texto, rotulo=risk_level)
        feedback_obj.treinamento_concluido = True
        feedback_obj.save(update_fields=['treinamento_concluido'])

        # Enrich response with structured fields
        semaforo = SEMAFORO_MAP.get(risk_level, SEMAFORO_DEFAULT)

        resultado_analise['classificacao'] = semaforo['label']
        resultado_analise['semaforo_image_url'] = f"{HF_MEDIA_BASE}/{semaforo['img']}"
        resultado_analise['analise_url'] = request.build_absolute_uri(f'/analise/{feedback_obj.id}/visualizar/')
        
        return Response(resultado_analise, status=status.HTTP_200_OK)
    
    except Exception as e:
        print(f"Erro ao processar análise: {e}")
        return Response(
            {"error": f"Erro interno: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def visualizar_analise(request, feedback_id):
    """Renderiza um relatório visual em HTML com semáforo, tabela e logo LARCES."""
    try:
        analise = Feedback.objects.get(id=feedback_id)
    except Feedback.DoesNotExist:
        return HttpResponse("<h1>Análise não encontrada.</h1>", status=404)

    risk_level = analise.risco_ia or "INDETERMINADO"
    semaforo = SEMAFORO_MAP.get(risk_level, SEMAFORO_DEFAULT)
    semaforo_url = f"{HF_MEDIA_BASE}/{semaforo['img']}"
    classificacao = semaforo['label']
    cor = semaforo['cor']

    
    motivo = "Informação não disponível."
    precaucao = "Informação não disponível."
    try:
        import ast
        dados = ast.literal_eval(analise.analise_ia)
        if isinstance(dados, dict):
            motivo = dados.get('motivo', motivo)
            precaucao = dados.get('precaucao', precaucao)
        elif isinstance(dados, list):
            motivo = "; ".join(dados)
    except Exception:
        if analise.analise_ia:
            motivo = analise.analise_ia[:500]



    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>VerificAI - Análise #{feedback_id}</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: 'Segoe UI', Arial, sans-serif;
                background: #f4f6f8;
                color: #333;
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: flex-start;
                padding: 40px 20px;
            }}
            .card {{
                background: #fff;
                border-radius: 16px;
                box-shadow: 0 4px 24px rgba(0,0,0,0.08);
                max-width: 640px;
                width: 100%;
                overflow: hidden;
            }}
            .header {{
                background: {cor};
                color: white;
                text-align: center;
                padding: 30px 20px 20px;
            }}
            .header img {{ width: 80px; height: auto; margin-bottom: 12px; }}
            .header h2 {{ font-size: 22px; margin: 0; }}
            .content {{ padding: 28px 32px; }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 8px;
            }}
            table th {{
                text-align: left;
                padding: 12px 16px;
                background: #f8f9fa;
                border-bottom: 2px solid #dee2e6;
                font-size: 13px;
                text-transform: uppercase;
                color: #6c757d;
                letter-spacing: 0.5px;
            }}
            table td {{
                padding: 14px 16px;
                border-bottom: 1px solid #eee;
                font-size: 15px;
                line-height: 1.5;
            }}
            .footer {{
                text-align: center;
                padding: 20px;
                border-top: 1px solid #f0f0f0;
            }}
            .footer img {{ width: 100px; height: auto; opacity: 0.8; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <img src="{semaforo_url}" alt="Semáforo {classificacao}">
                <h2>Classificação: {classificacao}</h2>
            </div>
            <div class="content">
                <table>
                    <tr>
                        <th>Classificação</th>
                        <td><strong style="color: {cor};">{classificacao}</strong></td>
                    </tr>
                    <tr>
                        <th>Motivo</th>
                        <td>{motivo}</td>
                    </tr>
                    <tr>
                        <th>Precaução</th>
                        <td>{precaucao}</td>
                    </tr>
                </table>
            </div>
            <div class="footer">
                <img src="{LARCES_LOGO_URL}" alt="LARCES - UECE">
            </div>
        </div>
    </body>
    </html>
    """
    return HttpResponse(html)


@swagger_auto_schema(
    method='get',
    operation_id='listar_analises',
    operation_summary='Listar Análises',
    operation_description='Lista todas as análises realizadas, da mais recente à mais antiga.',
    responses={200: FeedbackSerializer(many=True)},
    tags=['Histórico'],
)
@api_view(['GET'])
def listar_analises(request):
    """Retorna todas as análises salvas no banco de dados."""
    analises = Feedback.objects.all().order_by('-timestamp')
    serializer = FeedbackSerializer(analises, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='get',
    operation_id='detalhe_analise',
    operation_summary='Detalhe de Análise',
    operation_description='Retorna os detalhes de uma análise específica pelo ID.',
    responses={200: FeedbackSerializer, 404: 'Não encontrada'},
    tags=['Histórico'],
)
@api_view(['GET'])
def detalhe_analise(request, analise_id):
    """Retorna detalhes de uma análise específica."""
    try:
        analise = Feedback.objects.get(id=analise_id)
        serializer = FeedbackSerializer(analise)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Feedback.DoesNotExist:
        return Response({"error": "Análise não encontrada."}, status=status.HTTP_404_NOT_FOUND)


@swagger_auto_schema(
    method='post',
    operation_id='treinar_rag',
    operation_summary='Treinar RAG',
    operation_description='Adiciona um exemplo ao ChromaDB. Rótulos: SPAM, HAM, PHISHING, etc.',
    request_body=TreinarRAGSerializer,
    responses={200: TreinarRAGResponseSerializer, 400: 'Parâmetros inválidos'},
    tags=['Treinamento'],
)
@api_view(['POST'])
def treinar_rag(request):
    """Adiciona um novo exemplo ao banco vetorial ChromaDB."""
    serializer = TreinarRAGSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    texto = serializer.validated_data['texto']
    rotulo = serializer.validated_data['rotulo']

    sucesso = adicionar_ao_chromadb(texto=texto, rotulo=rotulo)
    
    if sucesso:
        return Response(
            {"status": "sucesso", "mensagem": f"Exemplo adicionado com rótulo: {rotulo}"},
            status=status.HTTP_200_OK
        )
    else:
        return Response(
            {"status": "erro", "mensagem": "Falha ao adicionar ao ChromaDB."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Webhook WhatsApp (não aparece no Swagger)
@api_view(['GET', 'POST'])
@csrf_exempt
def webhook_whatsapp(request):
    if request.method == 'GET':
        if request.GET.get("hub.mode") == "subscribe" and request.GET.get("hub.verify_token") == settings.WHATSAPP_VERIFY_TOKEN:
            return HttpResponse(request.GET.get("hub.challenge"), status=200)
        return HttpResponse("Token de verificação inválido", status=403)

    elif request.method == 'POST':
        try:
            data = request.data
            texto_mensagem = None
            remetente = None
            origem = "desconhecida"

            if 'entry' in data and data.get('entry', [{}])[0].get('changes', [{}])[0].get('value', {}).get('messages', [{}])[0].get('text'):
                texto_mensagem = data['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
                remetente = data['entry'][0]['changes'][0]['value']['messages'][0]['from']
                origem = "whatsapp"
            elif 'texto' in data:
                texto_mensagem = data.get('texto')
                origem = "script_evaluate"

            if texto_mensagem:
                # Sanitizar dados sensíveis antes de qualquer processamento
                texto_mensagem = sanitizar_texto(texto_mensagem).texto_sanitizado

                resultado_analise = analisar_com_IA(texto_mensagem)

                if origem == "whatsapp":
                    remetente_sanitizado = sanitizar_texto(remetente).texto_sanitizado if remetente else None
                    Feedback.objects.create(
                        mensagem=texto_mensagem,
                        remetente=remetente_sanitizado,
                        risco_ia=resultado_analise.get('risk_level', 'INDETERMINADO'),
                        analise_ia=str(resultado_analise.get('analysis_details', ''))
                    )
                    return HttpResponse("OK", status=200)
                elif origem == "script_evaluate":
                    return JsonResponse(resultado_analise, status=200)
            
            return HttpResponse("Formato de POST não reconhecido", status=400)
        except Exception as e:
            return HttpResponse(f"Erro interno: {e}", status=500)


# As views registrar_feedback e processar_feedback_treinamento foram removidas.
# O feedback humano foi eliminado — a classificação da IA retroalimenta o ChromaDB automaticamente.