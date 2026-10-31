import { describe, it, expect } from 'vitest';
import { segmentPrompt } from './promptSegments';

const join = parts => parts.map(p => p.text).join('');
const of = (parts, kind) => parts.filter(p => p.kind === kind).map(p => p.text);

// Trechos do prompt completo de verdade (calça jeans, espelho): titulos de secao, ênfase no meio da frase e falas.
const COMPLETO = [
  'UGC TikTok Shop vertical 9:16, exatamente 15 segundos, 720 × 1280 (720p). ANEXE a IMAGEM APROVADA da cor Azul claro como primeiro quadro. FATOS CONFIRMADOS: bolso, cintura alta.',
  'CENÁRIO FIXO (todos os frames e cores): o mesmo ambiente. ENQUADRAMENTO: manter a mesma cena. EVITAR: textos, ícones.',
  'PROVA VISUAL — cada fato abaixo precisa do seu gesto, executado entre 4s e 11s.',
  'MÃOS: ela gesticula. AÇÕES (na ordem, a primeira é obrigatória, entre 0s e 11s): gira só o tronco. ENCERRAMENTO (12–15s): já de frente.',
  'SHOT LIST 15s — um único take contínuo:',
  '0–4s HOOK: olhar na lente. Fala (PT-BR): "Meu problema com calça jeans sempre foi ficar transparente. Olha essa aqui"',
  '4–12s DESENVOLVIMENTO — mesma respiração. Fala (PT-BR): "E quem já passou por isso sabe como é chato"',
  'ATRIBUTOS NÃO CONFIRMADOS: não inventar compressão. Áudio: voz feminina; fale só as falas entre aspas.',
].join('\n');

describe('segmentPrompt', () => {
  it('juntar os pedaços devolve o prompt original, sem perder nem mudar nada', () => {
    expect(join(segmentPrompt(COMPLETO))).toBe(COMPLETO);
    for (const sample of ['', 'texto simples', '   \n  ', 'FATOS:', '"fala"', 'A: B: C —', 'SEM TÍTULO']) {
      expect(join(segmentPrompt(sample))).toBe(sample);
    }
  });

  it('destaca títulos de seção, com o parêntese e os dois pontos', () => {
    const labels = of(segmentPrompt(COMPLETO), 'label');
    expect(labels).toContain('FATOS CONFIRMADOS:');
    expect(labels).toContain('CENÁRIO FIXO (todos os frames e cores):');
    expect(labels).toContain('PROVA VISUAL —');
    expect(labels).toContain('ENCERRAMENTO (12–15s):');
    expect(labels).toContain('SHOT LIST 15s —');
    expect(labels).toContain('0–4s HOOK:');
    expect(labels).toContain('4–12s DESENVOLVIMENTO —');
    expect(labels).toContain('ATRIBUTOS NÃO CONFIRMADOS:');
  });

  it('não confunde maiúscula no meio da frase com título', () => {
    const labels = of(segmentPrompt(COMPLETO), 'label').join('|');
    expect(labels).not.toMatch(/ANEXE/);
    expect(labels).not.toMatch(/IMAGEM APROVADA/);
    expect(labels).not.toMatch(/Áudio/);
  });

  it('proporção e horário com números não são título', () => {
    expect(of(segmentPrompt('Vídeo vertical 9:16, 15 segundos. Entre 0:30 e 1:10.'), 'label')).toEqual([]);
  });

  it('destaca as falas entre aspas retas ou curvas e não mexe nas aspas', () => {
    const say = of(segmentPrompt('Fala: "Oi, gente. Olha isso" e depois “segunda fala”.'), 'say');
    expect(say).toEqual(['"Oi, gente. Olha isso"', '“segunda fala”']);
  });

  it('título dentro de uma fala fica como fala', () => {
    const parts = segmentPrompt('Fala: "ATENÇÃO: corre pro carrinho"');
    expect(of(parts, 'say')).toEqual(['"ATENÇÃO: corre pro carrinho"']);
    expect(of(parts, 'label')).toEqual([]);
  });
});
