"""
Testes unitários para o módulo de sanitização de dados sensíveis (PII).
"""

import unittest
from detector.sanitizer import sanitizar_texto


class TestSanitizarCPF(unittest.TestCase):
    """Testes para sanitização de CPF."""

    def test_cpf_formatado(self):
        resultado = sanitizar_texto("Meu CPF é 123.456.789-00")
        self.assertIn("[CPF]", resultado.texto_sanitizado)
        self.assertNotIn("123.456.789-00", resultado.texto_sanitizado)
        self.assertEqual(resultado.dados_removidos.get("cpf"), 1)

    def test_cpf_sem_formatacao(self):
        resultado = sanitizar_texto("CPF: 12345678900")
        self.assertIn("[CPF]", resultado.texto_sanitizado)
        self.assertNotIn("12345678900", resultado.texto_sanitizado)

    def test_multiplos_cpfs(self):
        resultado = sanitizar_texto("CPF1: 123.456.789-00, CPF2: 987.654.321-00")
        self.assertEqual(resultado.dados_removidos.get("cpf"), 2)
        self.assertEqual(resultado.total_removidos, 2)


class TestSanitizarCNPJ(unittest.TestCase):
    """Testes para sanitização de CNPJ."""

    def test_cnpj_formatado(self):
        resultado = sanitizar_texto("CNPJ: 12.345.678/0001-90")
        self.assertIn("[CNPJ]", resultado.texto_sanitizado)
        self.assertNotIn("12.345.678/0001-90", resultado.texto_sanitizado)
        self.assertEqual(resultado.dados_removidos.get("cnpj"), 1)

    def test_cnpj_sem_formatacao(self):
        resultado = sanitizar_texto("CNPJ: 12345678000190")
        self.assertIn("[CNPJ]", resultado.texto_sanitizado)

    def test_cnpj_nao_confundido_com_cpf(self):
        """CNPJ deve ser capturado pelo padrão CNPJ, não CPF."""
        resultado = sanitizar_texto("CNPJ: 12.345.678/0001-90")
        self.assertIn("[CNPJ]", resultado.texto_sanitizado)
        # Não deve ter CPF capturado quando é claramente um CNPJ
        self.assertNotIn("[CPF]", resultado.texto_sanitizado)


class TestSanitizarEmail(unittest.TestCase):
    """Testes para sanitização de email (preservando domínio)."""

    def test_email_preserva_dominio(self):
        resultado = sanitizar_texto("Contato: pedro.silva@gmail.com")
        self.assertIn("[USUARIO]@gmail.com", resultado.texto_sanitizado)
        self.assertNotIn("pedro.silva@", resultado.texto_sanitizado)
        self.assertEqual(resultado.dados_removidos.get("email"), 1)

    def test_email_dominio_institucional(self):
        resultado = sanitizar_texto("Email: aluno123@aluno.uece.br")
        self.assertIn("[USUARIO]@aluno.uece.br", resultado.texto_sanitizado)
        self.assertNotIn("aluno123@", resultado.texto_sanitizado)

    def test_multiplos_emails(self):
        resultado = sanitizar_texto("De: user@gmail.com Para: admin@empresa.com.br")
        self.assertIn("[USUARIO]@gmail.com", resultado.texto_sanitizado)
        self.assertIn("[USUARIO]@empresa.com.br", resultado.texto_sanitizado)
        self.assertEqual(resultado.dados_removidos.get("email"), 2)


class TestSanitizarTelefone(unittest.TestCase):
    """Testes para sanitização de telefones brasileiros."""

    def test_telefone_com_ddd_formatado(self):
        resultado = sanitizar_texto("Ligue: (85) 99999-1234")
        self.assertIn("[TELEFONE]", resultado.texto_sanitizado)
        self.assertNotIn("99999-1234", resultado.texto_sanitizado)

    def test_telefone_com_codigo_pais(self):
        resultado = sanitizar_texto("WhatsApp: +55 85 999991234")
        self.assertIn("[TELEFONE]", resultado.texto_sanitizado)

    def test_telefone_fixo(self):
        resultado = sanitizar_texto("Tel: (85) 3108-0135")
        self.assertIn("[TELEFONE]", resultado.texto_sanitizado)


class TestSanitizarCartaoCredito(unittest.TestCase):
    """Testes para sanitização de cartão de crédito."""

    def test_cartao_com_espacos(self):
        resultado = sanitizar_texto("Cartão: 4111 1111 1111 1111")
        self.assertIn("[CARTAO]", resultado.texto_sanitizado)
        self.assertEqual(resultado.dados_removidos.get("cartao_credito"), 1)

    def test_cartao_com_hifen(self):
        resultado = sanitizar_texto("Cartão: 4111-1111-1111-1111")
        self.assertIn("[CARTAO]", resultado.texto_sanitizado)

    def test_cartao_sem_separador(self):
        resultado = sanitizar_texto("Cartão: 4111111111111111")
        self.assertIn("[CARTAO]", resultado.texto_sanitizado)


class TestSanitizarPIX(unittest.TestCase):
    """Testes para sanitização de chave PIX (UUID)."""

    def test_pix_uuid(self):
        resultado = sanitizar_texto("PIX: a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        self.assertIn("[PIX]", resultado.texto_sanitizado)
        self.assertEqual(resultado.dados_removidos.get("pix"), 1)


class TestSanitizarCEP(unittest.TestCase):
    """Testes para sanitização de CEP."""

    def test_cep_formatado(self):
        resultado = sanitizar_texto("CEP: 60000-000")
        self.assertIn("[CEP]", resultado.texto_sanitizado)
        self.assertEqual(resultado.dados_removidos.get("cep"), 1)


class TestSanitizarDadosBancarios(unittest.TestCase):
    """Testes para sanitização de dados bancários."""

    def test_agencia(self):
        resultado = sanitizar_texto("Agência: 1234")
        self.assertIn("[DADOS_BANCARIOS]", resultado.texto_sanitizado)

    def test_conta(self):
        resultado = sanitizar_texto("Conta: 12345-6")
        self.assertIn("[DADOS_BANCARIOS]", resultado.texto_sanitizado)

    def test_agencia_e_conta(self):
        resultado = sanitizar_texto("Agência: 1234 Conta: 56789-0")
        self.assertEqual(resultado.dados_removidos.get("dados_bancarios"), 2)


class TestSanitizarRG(unittest.TestCase):
    """Testes para sanitização de RG."""

    def test_rg_formatado(self):
        resultado = sanitizar_texto("RG: 12.345.678-9")
        self.assertIn("[RG]", resultado.texto_sanitizado)

    def test_rg_com_x(self):
        resultado = sanitizar_texto("RG: 12.345.678-X")
        self.assertIn("[RG]", resultado.texto_sanitizado)


class TestPreservacao(unittest.TestCase):
    """Testes de preservação de links e texto sem PII."""

    def test_links_preservados(self):
        """Links HTTP/HTTPS não devem ser alterados."""
        texto = "Acesse https://malicious-site.com/phishing?id=123 agora!"
        resultado = sanitizar_texto(texto)
        self.assertIn("https://malicious-site.com/phishing?id=123", resultado.texto_sanitizado)

    def test_texto_sem_pii(self):
        """Texto sem dados sensíveis deve retornar inalterado."""
        texto = "Esta é uma mensagem normal sobre uma promoção imperdível!"
        resultado = sanitizar_texto(texto)
        self.assertEqual(resultado.texto_sanitizado, texto)
        self.assertEqual(resultado.total_removidos, 0)
        self.assertEqual(resultado.dados_removidos, {})

    def test_texto_vazio(self):
        resultado = sanitizar_texto("")
        self.assertEqual(resultado.texto_sanitizado, "")
        self.assertEqual(resultado.total_removidos, 0)


class TestMultiplosDados(unittest.TestCase):
    """Testes com múltiplos tipos de PII no mesmo texto."""

    def test_mensagem_com_varios_pii(self):
        texto = (
            "Prezado cliente, CPF 123.456.789-00, "
            "entre em contato pelo (85) 99999-1234 "
            "ou email pedro@empresa.com"
        )
        resultado = sanitizar_texto(texto)
        self.assertIn("[CPF]", resultado.texto_sanitizado)
        self.assertIn("[TELEFONE]", resultado.texto_sanitizado)
        self.assertIn("[USUARIO]@empresa.com", resultado.texto_sanitizado)
        self.assertGreaterEqual(resultado.total_removidos, 3)

    def test_spam_tipico_com_pii(self):
        """Simula um spam típico com dados pessoais misturados."""
        texto = (
            "PARABÉNS! Você foi selecionado! "
            "Envie seus dados: CPF 111.222.333-44, "
            "PIX a1b2c3d4-e5f6-7890-abcd-ef1234567890. "
            "Acesse http://golpe.com/premio para resgatar!"
        )
        resultado = sanitizar_texto(texto)
        self.assertIn("[CPF]", resultado.texto_sanitizado)
        self.assertIn("[PIX]", resultado.texto_sanitizado)
        # Link deve ser preservado
        self.assertIn("http://golpe.com/premio", resultado.texto_sanitizado)
        # O contexto de spam deve permanecer
        self.assertIn("PARABÉNS", resultado.texto_sanitizado)
        self.assertIn("selecionado", resultado.texto_sanitizado)


if __name__ == "__main__":
    unittest.main()
