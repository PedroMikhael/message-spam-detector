/**
 * VerificAI - Background Service Worker
 * 
 * Service worker do Manifest V3.
 * Registra evento de instalação da extensão.
 */

chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === "install") {
    console.log("[VerificAI] Extensão instalada com sucesso!");
  } else if (details.reason === "update") {
    console.log("[VerificAI] Extensão atualizada para versão", chrome.runtime.getManifest().version);
  }
});
