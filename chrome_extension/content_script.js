/**
 * VerificAI - Content Script
 * 
 * Injetado nas páginas do Gmail e Outlook Web para extrair
 * o conteúdo do e-mail aberto (texto, remetente e imagens inline).
 * 
 * Comunica-se com popup.js via chrome.runtime.onMessage.
 */

// ─── Separador de encaminhamento (mesmo padrão do email_bot.py) ─────
const FORWARD_SEPARATOR = "---------- Forwarded message ---------";

/**
 * Remove cabeçalhos de encaminhamento do texto do e-mail.
 * Reaplica a mesma lógica de extrair_conteudo_original() do email_bot.py.
 */
function limparEncaminhamento(texto) {
  if (!texto.includes(FORWARD_SEPARATOR)) {
    return texto.trim();
  }

  const blocos = texto.split(FORWARD_SEPARATOR);
  const ultimoBloco = blocos[blocos.length - 1].trim();
  const linhas = ultimoBloco.split("\n");
  const conteudoLimpo = [];
  const headersAPular = ["de:", "from:", "date:", "subject:", "to:", "cc:", "bcc:"];
  let headerEncontrado = false;

  for (const linha of linhas) {
    const linhaStripped = linha.trim().toLowerCase();

    if (!headerEncontrado && !linhaStripped) {
      continue;
    }

    if (headersAPular.some((h) => linhaStripped.startsWith(h))) {
      headerEncontrado = true;
      continue;
    }

    if (headerEncontrado && !linhaStripped) {
      headerEncontrado = false;
      continue;
    }

    headerEncontrado = false;
    conteudoLimpo.push(linha);
  }

  return conteudoLimpo.join("\n").trim();
}

/**
 * Converte um elemento <img> para string base64 padrão via canvas.
 * Retorna null se a imagem não puder ser convertida (CORS, etc).
 */
function imagemParaBase64(imgElement) {
  try {
    // Ignorar imagens muito pequenas (ícones, trackers, etc.)
    if (imgElement.naturalWidth < 50 || imgElement.naturalHeight < 50) {
      return null;
    }
    // Ignorar tracking pixels e imagens sem src real
    const src = imgElement.src || "";
    if (!src || src.startsWith("data:image/gif")) {
      return null;
    }

    const canvas = document.createElement("canvas");
    canvas.width = imgElement.naturalWidth;
    canvas.height = imgElement.naturalHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(imgElement, 0, 0);

    // Exportar como JPEG base64 (sem o prefixo data:image/...)
    const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
    return dataUrl.split(",")[1]; // Remove "data:image/jpeg;base64,"
  } catch (e) {
    // CORS ou outra restrição impede o acesso ao pixel da imagem
    console.warn("[VerificAI] Imagem não pôde ser convertida:", e.message);
    return null;
  }
}

// ─── Extratores por plataforma ──────────────────────────────────────

/**
 * Extrai dados do e-mail aberto no Gmail.
 */
function extrairGmail() {
  // Assunto: tag h2 com classe hP
  const assuntoEl = document.querySelector("h2.hP");
  const assunto = assuntoEl ? assuntoEl.innerText.trim() : "";

  // Remetente: span com classe gD (contém atributo 'email')
  const remetenteEl = document.querySelector("span.gD");
  const remetente = remetenteEl
    ? remetenteEl.getAttribute("email") || remetenteEl.innerText.trim()
    : "";

  // Corpo do e-mail: pega a última mensagem visível na thread
  const corpoElements = document.querySelectorAll("div.a3s.aiL");
  if (corpoElements.length === 0) {
    return null;
  }

  const ultimoCorpo = corpoElements[corpoElements.length - 1];
  const textoRaw = ultimoCorpo.innerText || "";
  const texto = limparEncaminhamento(textoRaw);

  // Imagens inline dentro do corpo do e-mail
  const imagens = [];
  const imgElements = ultimoCorpo.querySelectorAll("img");
  for (const img of imgElements) {
    const b64 = imagemParaBase64(img);
    if (b64) {
      imagens.push(b64);
    }
  }

  return { assunto, remetente, texto, imagens };
}

/**
 * Extrai dados do e-mail aberto no Outlook Web (outlook.live.com / outlook.office.com).
 */
function extrairOutlook() {
  // Assunto
  const assuntoEl = document.querySelector('[role="heading"]');
  const assunto = assuntoEl ? assuntoEl.innerText.trim() : "";

  // Remetente
  const remetenteEl = document.querySelector('span[title*="@"]');
  const remetente = remetenteEl ? remetenteEl.getAttribute("title") || remetenteEl.innerText.trim() : "";

  // Corpo do e-mail
  const corpoEl =
    document.querySelector('div[aria-label="Message body"]') ||
    document.querySelector('div[aria-label="Corpo da mensagem"]') ||
    document.querySelector('div[role="document"]');

  if (!corpoEl) {
    return null;
  }

  const textoRaw = corpoEl.innerText || "";
  const texto = limparEncaminhamento(textoRaw);

  // Imagens inline
  const imagens = [];
  const imgElements = corpoEl.querySelectorAll("img");
  for (const img of imgElements) {
    const b64 = imagemParaBase64(img);
    if (b64) {
      imagens.push(b64);
    }
  }

  return { assunto, remetente, texto, imagens };
}

// ─── Função principal de extração ───────────────────────────────────

/**
 * Detecta a plataforma de e-mail e extrai os dados.
 * Retorna { assunto, remetente, texto, imagens } ou null em caso de falha.
 */
function extrairDadosEmail() {
  const url = window.location.hostname;

  if (url.includes("mail.google.com")) {
    return extrairGmail();
  }

  if (url.includes("outlook.live.com") || url.includes("outlook.office")) {
    return extrairOutlook();
  }

  return null;
}

// ─── Listener de mensagens do popup ─────────────────────────────────

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "extrairEmail") {
    const dados = extrairDadosEmail();
    sendResponse(dados);
  }
  return true; // Necessário para manter o canal aberto para resposta assíncrona
});
