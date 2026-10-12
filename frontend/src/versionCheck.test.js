import { describe, expect, it } from 'vitest';
import { assetSignature } from './versionCheck.jsx';

const INDEX = `<!doctype html><html><head>
<link rel="icon" type="image/svg+xml" href="/favicon.svg"/>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Instrument+Sans&display=swap"/>
<script type="module" crossorigin src="/assets/index-AAA111.js"></script>
<link rel="stylesheet" crossorigin href="/assets/index-BBB222.css">
</head><body><div id="root"></div></body></html>`;

describe('assetSignature', () => {
  it('junta os arquivos de /assets/ em ordem fixa', () => {
    expect(assetSignature(INDEX)).toBe('/assets/index-AAA111.js|/assets/index-BBB222.css');
  });

  it('ignora fontes externas, favicon e rotas de API', () => {
    const html = INDEX + '<img src="/api/assets/9/file"><a href="https://exemplo.com/assets/x.js">x</a>';
    expect(assetSignature(html)).toBe('/assets/index-AAA111.js|/assets/index-BBB222.css');
  });

  it('não depende da ordem das tags nem de repetições', () => {
    const invertido = INDEX.replace(/(<script.*?<\/script>)\s*(<link rel="stylesheet" crossorigin.*?>)/s, '$2\n$1') + INDEX;
    expect(assetSignature(invertido)).toBe(assetSignature(INDEX));
  });

  it('descarta ?query e #hash do nome do arquivo', () => {
    expect(assetSignature('<script src="/assets/a.js?v=2"></script><link href="/assets/b.css#x">'))
      .toBe('/assets/a.js|/assets/b.css');
  });

  it('versão nova muda a assinatura', () => {
    const nova = INDEX.replace('AAA111', 'CCC333');
    expect(assetSignature(nova)).not.toBe(assetSignature(INDEX));
  });

  it('página sem arquivos de /assets/ (tela de PIN, erro, vazio) dá vazio: o componente não avisa', () => {
    expect(assetSignature('<!doctype html><title>PIN</title><form>pin</form>')).toBe('');
    expect(assetSignature('')).toBe('');
    expect(assetSignature(undefined)).toBe('');
    expect(assetSignature(null)).toBe('');
  });
});
