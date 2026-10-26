import { useEffect, useState } from 'react';
import { api } from './api';

// Publicacao no TikTok pela Content Posting API. So envia quando a usuaria clica em Publicar.
// O video vai direto do navegador para o endereco de upload devolvido pelo TikTok (nao passa pela Vercel).
export function TikTokPublish() {
  const [conn, setConn] = useState(null);
  const [file, setFile] = useState(null);
  const [caption, setCaption] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    api('/tiktok/status').then(setConn).catch(() => setConn({ connected: false }));
  }, []);

  async function publicar(e) {
    e.preventDefault();
    if (!file || !conn?.connected) return;
    setBusy(true); setMsg('Preparando envio...');
    try {
      const init = await api('/tiktok/publish/init', { method: 'POST', body: { size: file.size, caption } });
      setMsg('Enviando video ao TikTok...');
      const up = await fetch(init.upload_url, {
        method: 'PUT',
        headers: {
          'Content-Type': file.type || 'video/mp4',
          'Content-Range': `bytes 0-${file.size - 1}/${file.size}`,
        },
        body: file,
      });
      if (!up.ok) throw new Error(`Upload recusado pelo TikTok (HTTP ${up.status}).`);
      setMsg('Video recebido. Aguardando o TikTok processar...');
      for (let i = 0; i < 40; i++) {
        await new Promise(r => setTimeout(r, 5000));
        const st = await api(`/tiktok/publish/status?publish_id=${encodeURIComponent(init.publish_id)}`);
        if (st.status === 'PUBLISH_COMPLETE') { setMsg('Publicado (visivel so para voce, ate o TikTok liberar a publicacao publica).'); return; }
        if (st.status === 'FAILED') { setMsg(`TikTok nao publicou: ${st.fail_reason || 'motivo nao informado'}.`); return; }
        setMsg(`Status no TikTok: ${st.status}...`);
      }
      setMsg('O TikTok ainda processa. Confira no app do TikTok.');
    } catch (err) {
      setMsg(err.message || 'Falha ao publicar.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rd-tiktok-publish" aria-label="Publicar no TikTok">
      <h2>Publicar no TikTok</h2>
      {!conn ? <p>Verificando conexao...</p> : !conn.connected ? (
        <p>
          <a className="rd-tiktok-connect" href="/api/tiktok/connect">Conectar conta do TikTok</a>
        </p>
      ) : (
        <form onSubmit={publicar}>
          <p>Conta conectada.</p>
          <label>
            Video (MP4 ou MOV)
            <input type="file" accept="video/mp4,video/quicktime" disabled={busy}
              onChange={e => setFile(e.target.files?.[0] || null)} />
          </label>
          <label>
            Legenda
            <textarea value={caption} maxLength={2200} disabled={busy}
              onChange={e => setCaption(e.target.value)} />
          </label>
          <button type="submit" disabled={busy || !file}>Publicar</button>
        </form>
      )}
      {msg && <p role="status">{msg}</p>}
    </section>
  );
}
