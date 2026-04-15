
from django.db import models
import hashlib
import re


class Feedback(models.Model):
    mensagem_original = models.TextField()
    remetente = models.CharField(max_length=255)

    # Como a IA classificou
    risco_ia = models.CharField(max_length=50) # SAFE, SUSPICIOUS, MALICIOUS
    analise_ia = models.TextField()

    # O feedback do usuário
    feedback_usuario_correto = models.BooleanField(null=True, blank=True) # True = IA acertou, False = IA errou

    # --- NOVO CAMPO PARA O RAG/ACTIVE LEARNING ---
    treinamento_concluido = models.BooleanField(default=False) # True se o dado foi usado para treinar o RAG
    # -----------------------------------------------

    # Hash SHA-256 do conteúdo normalizado — busca rápida por duplicatas
    hash_conteudo = models.CharField(max_length=64, db_index=True, blank=True, default="")

    timestamp = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def gerar_hash(texto: str) -> str:
        """Gera SHA-256 do texto normalizado (lowercase, espaços colapsados)."""
        normalizado = re.sub(r'\s+', ' ', texto).strip().lower()
        return hashlib.sha256(normalizado.encode('utf-8')).hexdigest()

    def save(self, *args, **kwargs):
        if not self.hash_conteudo and self.mensagem_original:
            self.hash_conteudo = Feedback.gerar_hash(self.mensagem_original)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Análise para {self.remetente} em {self.timestamp.strftime('%d/%m/%Y %H:%M')}"