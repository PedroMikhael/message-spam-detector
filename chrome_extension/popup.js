/**
 * VerificAI - Popup Logic
 * 
 * Controla a interface da extensão:
 * 1. Solicita ao content_script a extração do e-mail aberto.
 * 2. Envia os dados para a API do VerificAI (HuggingFace Spaces).
 * 3. Exibe o veredito com semáforo ou o tutorial de encaminhamento.
 */

// ─── Configurações ──────────────────────────────────────────────────
const API_URL = "https://pedromikhael-verificai.hf.space/api/analisar/";
const FEEDBACK_BASE_URL = "https://pedromikhael-verificai.hf.space";

const SEMAFORO_MAP = {
  SAFE: {
    img: "semaforoVerde.png",
    cor: "#28a745",
    label: "Segura",
    classe: "safe",
  },
  SUSPICIOUS: {
    img: "semaforoAmarelo.png",
    cor: "#ffc107",
    label: "Suspeita",
    classe: "suspicious",
  },
  MALICIOUS: {
    img: "semaforoVermelho.png",
    cor: "#dc3545",
    label: "Maliciosa",
    classe: "malicious",
  },
};

const SEMAFORO_DEFAULT = {
  img: "semaforoAmarelo.png",
  cor: "#6c757d",
  label: "Indeterminado",
  classe: "indeterminado",
};

const HF_MEDIA_BASE =
  "https://huggingface.co/spaces/PedroMikhael/VerificAI/resolve/main/media";

// ─── Referências DOM ────────────────────────────────────────────────
const telaLoading = document.getElementById("tela-loading");
const telaResultado = document.getElementById("tela-resultado");
const telaErro = document.getElementById("tela-erro");
const loadingText = document.querySelector(".loading-text");

// ─── Funções de Navegação ───────────────────────────────────────────

function mostrarTela(tela) {
  telaLoading.classList.remove("ativa");
  telaResultado.classList.remove("ativa");
  telaErro.classList.remove("ativa");
  tela.classList.add("ativa");
}

// ─── Exibir Veredito da IA ──────────────────────────────────────────

function exibirVeredito(resultado) {
  const riskLevel = resultado.risk_level || "INDETERMINADO";
  const semaforo = SEMAFORO_MAP[riskLevel] || SEMAFORO_DEFAULT;

  // Banner do semáforo
  const banner = document.getElementById("resultado-banner");
  banner.className = "resultado-banner " + semaforo.classe;

  const semaforoImg = document.getElementById("resultado-semaforo-img");
  semaforoImg.src = `${HF_MEDIA_BASE}/${semaforo.img}`;
  semaforoImg.alt = `Semáforo ${semaforo.label}`;

  const classificacaoH2 = document.getElementById("resultado-classificacao");
  classificacaoH2.textContent = `Classificação: ${semaforo.label}`;

  // Tabela
  const classificacaoText = document.getElementById(
    "resultado-classificacao-text"
  );
  classificacaoText.innerHTML = `<span class="valor-classificacao" style="color: ${semaforo.cor}">${semaforo.label}</span>`;

  document.getElementById("resultado-motivo").textContent =
    resultado.motivo || "Análise indisponível.";

  document.getElementById("resultado-precaucao").textContent =
    resultado.precaucao || "";

  // Botões de feedback
  const feedbackId = resultado.feedback_id;
  if (feedbackId) {
    document.getElementById("btn-correto").href =
      `${FEEDBACK_BASE_URL}/feedback/${feedbackId}/correto/`;
    document.getElementById("btn-incorreto").href =
      `${FEEDBACK_BASE_URL}/feedback/${feedbackId}/incorreto/`;
  }

  mostrarTela(telaResultado);
}

// ─── Tutorial de Encaminhamento ─────────────────────────────────────

function exibirTutorialEncaminhamento() {
  mostrarTela(telaErro);
}

// ─── Enviar Dados para a API ────────────────────────────────────────

async function enviarParaAPI(dadosEmail) {
  loadingText.textContent = "Analisando com Inteligência Artificial...";

  const payload = {
    texto: dadosEmail.texto,
    remetente: dadosEmail.remetente || "chrome-extension",
  };

  // Incluir imagens se disponíveis (análise multimodal)
  if (dadosEmail.imagens && dadosEmail.imagens.length > 0) {
    payload.imagens = dadosEmail.imagens;
  }

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Erro HTTP: ${response.status}`);
    }

    const resultado = await response.json();
    exibirVeredito(resultado);
  } catch (error) {
    console.error("[VerificAI] Erro ao enviar para API:", error);
    exibirTutorialEncaminhamento();
  }
}

// ─── Fluxo Principal ────────────────────────────────────────────────

async function analisarEmailAberto() {
  mostrarTela(telaLoading);
  loadingText.textContent = "Lendo e-mail aberto...";

  try {
    // Obter a aba ativa
    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });

    if (!tab || !tab.id) {
      exibirTutorialEncaminhamento();
      return;
    }

    // Enviar mensagem ao content_script para extrair o e-mail
    chrome.tabs.sendMessage(
      tab.id,
      { action: "extrairEmail" },
      (response) => {
        // Verificar se houve erro de comunicação
        if (chrome.runtime.lastError) {
          console.warn(
            "[VerificAI] Content script não acessível:",
            chrome.runtime.lastError.message
          );
          exibirTutorialEncaminhamento();
          return;
        }

        // Verificar se os dados foram extraídos
        if (!response || !response.texto || response.texto.trim().length < 5) {
          exibirTutorialEncaminhamento();
          return;
        }

        // Dados extraídos com sucesso — enviar para a API
        enviarParaAPI(response);
      }
    );
  } catch (error) {
    console.error("[VerificAI] Erro no fluxo principal:", error);
    exibirTutorialEncaminhamento();
  }
}

// ─── Event Listeners ────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  analisarEmailAberto();
});

// Botão "Tentar Novamente"
document.getElementById("btn-tentar-novamente")?.addEventListener("click", () => {
  analisarEmailAberto();
});
