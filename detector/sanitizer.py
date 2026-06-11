"""
Módulo de sanitização de dados sensíveis (PII) usando Regex.

Remove dados pessoais do texto antes de enviar para a LLM e armazenar
no banco de dados, substituindo por placeholders genéricos.

Links HTTP/HTTPS são sempre preservados (necessários para análise de phishing).
"""

import re
from dataclasses import dataclass, field


@dataclass
class SanitizationResult:
    """Resultado da sanitização de um texto."""
    texto_sanitizado: str
    dados_removidos: dict = field(default_factory=dict)
    total_removidos: int = 0


# ========================
# PADRÕES REGEX (ordenados do mais específico ao mais genérico)
# ========================

# A ordem de aplicação é CRÍTICA:
# CNPJ antes de CPF (CNPJ tem mais dígitos e poderia ser parcialmente capturado por CPF)
# Cartão antes de telefone (16 dígitos vs 8-11)
# CEP por último entre os numéricos (8 dígitos, muito genérico)

PADROES_PII = [
    # 1. CNPJ: 12.345.678/0001-90 ou 12345678000190
    {
        "nome": "cnpj",
        "regex": re.compile(
            r'\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b'
        ),
        "placeholder": "[CNPJ]",
    },
    # 2. CPF: 123.456.789-00 ou 12345678900
    {
        "nome": "cpf",
        "regex": re.compile(
            r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b'
        ),
        "placeholder": "[CPF]",
    },
    # 3. Cartão de crédito: 4111 1111 1111 1111 ou variações
    {
        "nome": "cartao_credito",
        "regex": re.compile(
            r'\b\d{4}[\s.-]?\d{4}[\s.-]?\d{4}[\s.-]?\d{4}\b'
        ),
        "placeholder": "[CARTAO]",
    },
    # 4. Chave PIX aleatória (UUID)
    {
        "nome": "pix",
        "regex": re.compile(
            r'\b[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\b',
            re.IGNORECASE
        ),
        "placeholder": "[PIX]",
    },
    # 5. Dados bancários: agência e conta
    {
        "nome": "dados_bancarios",
        "regex": re.compile(
            r'(?:ag[êe]ncia|ag)\s*:?\s*\d{3,5}(?:-?\d)?',
            re.IGNORECASE
        ),
        "placeholder": "[DADOS_BANCARIOS]",
    },
    {
        "nome": "dados_bancarios",
        "regex": re.compile(
            r'conta\s*:?\s*[\d][\d.\-]+\d',
            re.IGNORECASE
        ),
        "placeholder": "[DADOS_BANCARIOS]",
    },
    # 6. Telefone brasileiro: (85) 99999-1234, +55 85 999991234, etc.
    {
        "nome": "telefone",
        "regex": re.compile(
            r'(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)\d{4,5}[-.\s]?\d{4}\b'
        ),
        "placeholder": "[TELEFONE]",
    },
    # 7. CEP: 60000-000 ou 60000000
    {
        "nome": "cep",
        "regex": re.compile(
            r'\b\d{5}-\d{3}\b'
        ),
        "placeholder": "[CEP]",
    },
    # 8. Email: preserva o domínio após o @
    #    pedro.silva@gmail.com -> [USUARIO]@gmail.com
    {
        "nome": "email",
        "regex": re.compile(
            r'\b[a-zA-Z0-9._%+-]+@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'
        ),
        "placeholder": r"[USUARIO]@\1",
    },
    # 9. RG: 12.345.678-9 ou 123456789
    {
        "nome": "rg",
        "regex": re.compile(
            r'\b\d{1,2}\.?\d{3}\.?\d{3}-?[0-9Xx]\b'
        ),
        "placeholder": "[RG]",
    },
]


def sanitizar_texto(texto: str) -> SanitizationResult:
    """
    Sanitiza dados sensíveis (PII) de um texto usando regex.

    Substitui CPF, CNPJ, telefones, emails, PIX, cartões de crédito,
    CEP, RG e dados bancários por placeholders genéricos.

    Links HTTP/HTTPS são preservados (necessários para análise de phishing).
    Emails têm apenas a parte do usuário removida, preservando o domínio.

    Args:
        texto: Texto bruto com possíveis dados sensíveis.

    Returns:
        SanitizationResult com texto sanitizado e métricas.
    """
    if not texto:
        return SanitizationResult(texto_sanitizado="", dados_removidos={}, total_removidos=0)

    texto_sanitizado = texto
    dados_removidos = {}
    total = 0

    for padrao in PADROES_PII:
        nome = padrao["nome"]
        regex = padrao["regex"]
        placeholder = padrao["placeholder"]

        # Contar matches antes de substituir
        matches = regex.findall(texto_sanitizado)
        quantidade = len(matches)

        if quantidade > 0:
            texto_sanitizado = regex.sub(placeholder, texto_sanitizado)
            dados_removidos[nome] = dados_removidos.get(nome, 0) + quantidade
            total += quantidade

    return SanitizationResult(
        texto_sanitizado=texto_sanitizado,
        dados_removidos=dados_removidos,
        total_removidos=total,
    )
