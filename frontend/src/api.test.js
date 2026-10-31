import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError, httpFailure, reloadHelps } from './api';

const answer = (status, body, type = 'text/html') => () => Promise.resolve(new Response(body, { status, headers: { 'content-type': type } }));
const failure = async () => api('/campaigns').catch(error => error);

afterEach(() => vi.unstubAllGlobals());

describe('erros da API', () => {
  it('sem rede: mensagem em portugues e recarregar ajuda', async () => {
    vi.stubGlobal('fetch', () => Promise.reject(new TypeError('Failed to fetch')));
    const error = await failure();
    expect(error).toBeInstanceOf(ApiError);
    expect(error.kind).toBe('network');
    expect(error.message).not.toMatch(/Failed to fetch/);
    expect(reloadHelps(error.message)).toBe(true);
  });

  it('413 com pagina HTML diz que o arquivo e grande e nao oferece recarregar', async () => {
    vi.stubGlobal('fetch', answer(413, '<html>Request Entity Too Large</html>'));
    const error = await failure();
    expect(error.kind).toBe('too_large');
    expect(error.status).toBe(413);
    expect(error.message).toMatch(/arquivo/i);
    expect(error.message).not.toMatch(/aplicativo local/);
    expect(reloadHelps(error.message)).toBe(false);
  });

  it('502 e 504 sem JSON viram demora; 401 vira sessao; 429 pede para esperar', async () => {
    for (const [status, kind] of [[502, 'timeout'], [504, 'timeout'], [401, 'auth'], [429, 'rate'], [503, 'server']]) {
      vi.stubGlobal('fetch', answer(status, '<html></html>'));
      const error = await failure();
      expect(error.kind, String(status)).toBe(kind);
    }
  });

  it('mensagem do servidor tem prioridade e 409 vira conflito que o recarregar resolve', async () => {
    vi.stubGlobal('fetch', answer(409, JSON.stringify({ error: 'A campanha mudou em outra janela. Recarregue antes de salvar.' }), 'application/json'));
    const error = await failure();
    expect(error.kind).toBe('conflict');
    expect(error.message).toBe('A campanha mudou em outra janela. Recarregue antes de salvar.');
    expect(reloadHelps(error.message)).toBe(true);
  });

  it('erro de validacao do servidor (400) nao oferece recarregar', async () => {
    vi.stubGlobal('fetch', answer(400, JSON.stringify({ error: 'Campo name: texto inválido ou muito longo.' }), 'application/json'));
    const error = await failure();
    expect(error.kind).toBe('request');
    expect(reloadHelps(error.message)).toBe(false);
  });

  it('httpFailure sempre devolve um ApiError com o codigo HTTP', () => {
    const error = httpFailure(418);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(418);
    expect(error.message).toMatch(/418/);
  });
});
