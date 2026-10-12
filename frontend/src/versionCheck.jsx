import React, { useEffect, useRef, useState } from 'react';
import { RefreshCw } from 'lucide-react';

// Aba aberta há dias continua rodando o JavaScript antigo: o computador mostrava 4 formatos de vídeo e nota 6 enquanto o
// celular, recém-aberto, mostrava os 11 formatos e nota 10. O servidor entrega o index.html sem cache, e os arquivos de
// /assets/ têm o hash no nome; se os nomes do index.html atual forem outros, a aba está velha e avisamos.
const CHECK_EVERY_MS = 10 * 60 * 1000;
const MIN_GAP_MS = 60 * 1000;

export function assetSignature(html) {
  const found = [...String(html || '').matchAll(/(?:src|href)="(\/assets\/[^"?#]+)"/g)].map(m => m[1]);
  return [...new Set(found)].sort().join('|');
}

function loadedSignature() {
  const urls = [...document.querySelectorAll('script[src^="/assets/"], link[rel="stylesheet"][href^="/assets/"]')]
    .map(el => el.getAttribute('src') || el.getAttribute('href'));
  return [...new Set(urls)].sort().join('|');
}

export default function NewVersionBanner() {
  const [latest, setLatest] = useState('');
  const [dismissed, setDismissed] = useState('');
  const current = useRef(loadedSignature());
  const lastCheck = useRef(Date.now());

  useEffect(() => {
    // Servidor de desenvolvimento ou build sem hash: não há o que comparar.
    if (!current.current) return undefined;
    let alive = true;
    const check = async () => {
      const now = Date.now();
      if (now - lastCheck.current < MIN_GAP_MS) return;
      lastCheck.current = now;
      try {
        const response = await fetch('/', { cache: 'no-store', credentials: 'same-origin', headers: { Accept: 'text/html' } });
        if (!response.ok) return;
        // Sem nenhum arquivo de /assets/ (tela de PIN, erro, página de login do proxy) não há informação: nada de aviso.
        const signature = assetSignature(await response.text());
        if (alive && signature && signature !== current.current) setLatest(signature);
      } catch (error) { /* offline ou servidor reiniciando: tenta de novo na próxima volta */ }
    };
    const onWake = () => { if (document.visibilityState === 'visible') check(); };
    document.addEventListener('visibilitychange', onWake);
    window.addEventListener('focus', onWake);
    window.addEventListener('online', onWake);
    const timer = setInterval(onWake, CHECK_EVERY_MS);
    return () => {
      alive = false;
      document.removeEventListener('visibilitychange', onWake);
      window.removeEventListener('focus', onWake);
      window.removeEventListener('online', onWake);
      clearInterval(timer);
    };
  }, []);

  if (!latest || latest === dismissed) return null;
  return (
    <div className="toast update-toast" role="status" aria-live="polite">
      <RefreshCw size={19} aria-hidden="true" />
      <span>Há uma versão nova da Fábrica. Recarregue para usar as correções mais recentes.</span>
      <div className="update-toast-actions">
        <button type="button" onClick={() => setDismissed(latest)}>Depois</button>
        <button type="button" className="primary" onClick={() => window.location.reload()}>Recarregar</button>
      </div>
    </div>
  );
}
