
from django.contrib import admin
from .models import Feedback

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('id', 'timestamp', 'risco_ia', 'treinamento_concluido', 'remetente')
    list_filter = ('risco_ia', 'treinamento_concluido')
    search_fields = ('mensagem', 'remetente')
    ordering = ('-timestamp',)