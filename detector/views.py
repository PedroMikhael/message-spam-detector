from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.conf import settings
from .models import Feedback
from .services import analisar_com_IA, enviar_mensagem_whatsapp, adicionar_ao_chromadb
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

    try:
        resultado_analise = analisar_com_IA(texto, debug=True)
        
        feedback_obj = Feedback.objects.create(
            mensagem_original=texto,
            remetente=remetente,
            risco_ia=resultado_analise.get('risk_level', 'INDETERMINADO'),
            analise_ia=str(resultado_analise)
        )

        # Enrich response with structured fields
        risk_level = resultado_analise.get('risk_level', 'INDETERMINADO')
        semaforo = SEMAFORO_MAP.get(risk_level, SEMAFORO_DEFAULT)

        resultado_analise['classificacao'] = semaforo['label']
        resultado_analise['semaforo_image_url'] = f"{HF_MEDIA_BASE}/{semaforo['img']}"
        resultado_analise['feedback_id'] = feedback_obj.id
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

    base_url = request.build_absolute_uri('/')[:-1]
    link_correto = f"{base_url}/feedback/{feedback_id}/correto/"
    link_incorreto = f"{base_url}/feedback/{feedback_id}/incorreto/"

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
            .feedback-section {{
                text-align: center;
                padding: 20px 32px 8px;
                border-top: 1px solid #eee;
            }}
            .feedback-section p {{
                font-size: 14px;
                color: #777;
                margin-bottom: 12px;
            }}
            .btn {{
                display: inline-block;
                padding: 10px 22px;
                color: white;
                text-decoration: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
                margin: 0 6px;
                transition: opacity 0.2s;
            }}
            .btn:hover {{ opacity: 0.85; }}
            .btn-correct {{ background: #28a745; }}
            .btn-incorrect {{ background: #dc3545; }}
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
            <div class="feedback-section">
                <p><em>Minha análise foi útil?</em></p>
                <a href="{link_correto}" class="btn btn-correct">Sim, acertou</a>
                <a href="{link_incorreto}" class="btn btn-incorrect">Não, errou</a>
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
                resultado_analise = analisar_com_IA(texto_mensagem)

                if origem == "whatsapp":
                    Feedback.objects.create(
                        mensagem_original=texto_mensagem,
                        remetente=remetente,
                        risco_ia=resultado_analise.get('risk_level', 'INDETERMINADO'),
                        analise_ia=str(resultado_analise.get('analysis_details', ''))
                    )
                    return HttpResponse("OK", status=200)
                elif origem == "script_evaluate":
                    return JsonResponse(resultado_analise, status=200)
            
            return HttpResponse("Formato de POST não reconhecido", status=400)
        except Exception as e:
            return HttpResponse(f"Erro interno: {e}", status=500)


def registrar_feedback(request, feedback_id, resultado):
    try:
        analise = Feedback.objects.get(id=feedback_id)
        
        if analise.feedback_usuario_correto is not None:
            status_antigo = "Correto" if analise.feedback_usuario_correto else "Incorreto"
            return HttpResponse(f"""
            <html><head><title>Feedback Já Registrado</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1 style="color: #ffc107;">⚠️ Feedback Já Registrado</h1>
                <p>Registrado como: <strong>{status_antigo}</strong>.</p>
            </body></html>""")

        analise.feedback_usuario_correto = (resultado == 'correto')
        analise.save()
        
        return HttpResponse("""
        <html><head><title>Obrigado!</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1 style="color: #28a745;">✅ Obrigado pelo seu feedback!</h1>
            <p>Sua resposta foi registrada com sucesso.</p>
        </body></html>""")
        
    except Feedback.DoesNotExist:
        return HttpResponse("<h1>Análise não encontrada.</h1>", status=404)
    

def processar_feedback_treinamento(request):
    """Recebe feedback do usuário e aciona treinamento RAG."""
    if request.method == 'GET':
        feedback_id = request.GET.get('id')
        novo_rotulo = request.GET.get('rotulo') 

        if not feedback_id or not novo_rotulo:
            return JsonResponse({'status': 'erro', 'mensagem': 'Parâmetros ID e RÓTULO são obrigatórios.'}, status=400)
        
        try:
            feedback_registro = get_object_or_404(Feedback, id=feedback_id)

            if feedback_registro.treinamento_concluido:
                return HttpResponse("Este feedback já foi processado anteriormente.")

            sucesso_treinamento = adicionar_ao_chromadb(
                texto=feedback_registro.mensagem_original,
                rotulo=novo_rotulo
            )

            if sucesso_treinamento:
                feedback_registro.treinamento_concluido = True
                feedback_registro.save()
                return HttpResponse("✅ Feedback processado com sucesso!")
            else:
                return HttpResponse("❌ Erro ao atualizar o modelo.", status=500)

        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)
    
    return JsonResponse({'status': 'erro', 'mensagem': 'Método não permitido.'}, status=405)