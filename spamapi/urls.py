from django.contrib import admin
from django.urls import path, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from detector.views import (
    analisar_mensagem,
    visualizar_analise,
    listar_analises,
    detalhe_analise,
    treinar_rag,
    webhook_whatsapp,
)

schema_view = get_schema_view(
   openapi.Info(
      title="VerificAI API",
      default_version='v1',
      description="API de detecção de spam e phishing em emails — LARCES/UECE",
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('', RedirectView.as_view(url='/swagger/', permanent=False)),
    path('health/', lambda request: __import__('django.http', fromlist=['JsonResponse']).JsonResponse({'status': 'ok'})),
    path('admin/', admin.site.urls),

    # API endpoints
    path('api/analisar/', analisar_mensagem, name='analisar_mensagem'),
    path('api/analises/', listar_analises, name='listar_analises'),
    path('api/analises/<int:analise_id>/', detalhe_analise, name='detalhe_analise'),
    path('api/treinar/', treinar_rag, name='treinar_rag'),

    # WhatsApp webhook
    re_path(r'^api/spam/?$', webhook_whatsapp, name="webhook_whatsapp"),

    # Swagger
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),


    # Visual report
    path('analise/<int:feedback_id>/visualizar/', visualizar_analise, name='visualizar_analise'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)