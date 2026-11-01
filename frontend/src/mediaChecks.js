// Conferencias de midia que so AVISAM (services/media_checks.py guarda as regras no servidor).

// Avisos do detail() de um tipo (image/video); com ``slot`` so os dessa cor.
export function warningsFor(warnings, {kind, slot} = {}) {
  return (Array.isArray(warnings) ? warnings : []).filter(w => w && (!kind || w.kind === kind) && (slot === undefined || (w.slot || '') === slot));
}

const FRAME_TIMEOUT_MS = 20000;

// Ultimo quadro de um video no navegador (nuvem, ou video da galeria): pula para o fim e desenha num canvas.
// ``src`` pode ser URL do servidor, link do Storage ou blob: do aparelho.
export function lastFrameInBrowser(src) {
  return new Promise((resolve, reject) => {
    const video = document.createElement('video');
    let done = false;
    let timer = null;
    const finish = (fn, value) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      video.removeAttribute('src');
      video.load();
      fn(value);
    };
    timer = setTimeout(() => finish(reject, new Error('O vídeo demorou demais para abrir. Tente de novo.')), FRAME_TIMEOUT_MS);
    video.muted = true;
    video.playsInline = true;
    video.preload = 'auto';
    if (!String(src).startsWith('blob:')) video.crossOrigin = 'anonymous';
    video.onerror = () => finish(reject, new Error('Não consegui abrir o vídeo para tirar o último quadro.'));
    video.onloadedmetadata = () => {
      const end = Number.isFinite(video.duration) ? video.duration : 0;
      // duration exato pode cair em quadro preto: recua um quadro (~1/24 s).
      video.currentTime = Math.max(0, end - 0.05);
    };
    video.onseeked = () => {
      try {
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        canvas.toBlob(blob => blob ? finish(resolve, blob) : finish(reject, new Error('Não consegui gerar a imagem do último quadro.')), 'image/png');
      } catch {
        finish(reject, new Error('O navegador bloqueou a leitura deste vídeo. Baixe o MP4 e tire o último quadro no aparelho.'));
      }
    };
    video.src = src;
  });
}

// Baixa o ultimo quadro: tenta o ffmpeg do servidor (PC) e cai para o navegador (nuvem). Nada e gravado na campanha.
export async function downloadLastFrame({assetId, src, name = 'video'}) {
  let blob = null;
  if (assetId) {
    try {
      const res = await fetch(`/api/assets/${assetId}/last-frame`, {credentials: 'same-origin', headers: {'X-Local-App': 'fabrica-tiktok'}});
      if (res.ok && (res.headers.get('content-type') || '').includes('image/png')) blob = await res.blob();
    } catch { /* sem servidor com ffmpeg: usa o navegador */ }
  }
  if (!blob) blob = await lastFrameInBrowser(src);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${String(name).replace(/\.mp4$/i, '').slice(0, 80) || 'video'}-ultimo-quadro.png`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
