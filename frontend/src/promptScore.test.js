import { describe, expect, it } from 'vitest';
import { scorePrompt } from './promptScore.js';

// Fala de n palavras (palavras neutras: nenhuma casa com as listas de ações ou peças do avaliador).
const fala = n => Array.from({ length: n }, () => 'bom').join(' ');

// Prompt no formato do app completo: três falas marcadas, câmera e luz nomeadas.
function completo({ hook = 15, dev = 20, cta = 15, extra = '', camera = 'Câmera: na mão, dolly-in suave.', luz = 'Luz: a mesma da imagem.' } = {}) {
  return [
    camera, luz, extra,
    `0–4s HOOK. Fala (PT-BR): "${fala(hook)}"`,
    `4–12s DESENVOLVIMENTO. Fala (PT-BR): "${fala(dev)}"`,
    `12–15s CTA. Fala (PT-BR): "${fala(cta)}"`,
  ].join('\n');
}

// Prompt no formato do Guia do Grok: uma única fala entre aspas.
function guia(n, extra = '') {
  return `Câmera: na mão, dolly-in suave. Luz: a mesma da imagem. ${extra}\nO que ela diz, do começo ao fim do vídeo, num fôlego só: "${fala(n)}"\nIMPORTANTE: mesmo rosto.`;
}

const issues = r => r.issues.join(' | ');

describe('scorePrompt: base', () => {
  it('devolve null para texto vazio', () => {
    expect(scorePrompt('')).toBeNull();
    expect(scorePrompt('   \n ')).toBeNull();
    expect(scorePrompt(undefined)).toBeNull();
  });

  it('prompt limpo com 50 palavras, câmera e luz nomeadas dá 10', () => {
    const r = scorePrompt(completo());
    expect(r.score).toBe(10);
    expect(r.tone).toBe('good');
    expect(r.label).toBe('Bom');
    expect(r.issues).toEqual([]);
  });

  it('passa de 4.000 caracteres: -2 e avisa do corte', () => {
    const r = scorePrompt(completo({ extra: 'x'.repeat(4000) }));
    expect(r.score).toBe(8);
    expect(issues(r)).toContain('limite do Grok');
  });

  it('câmera e luz sem nome custam 1 ponto cada', () => {
    expect(scorePrompt(completo({ camera: 'Câmera: sem nome.' })).score).toBe(9);
    expect(scorePrompt(completo({ luz: 'Nada citado aqui.' })).score).toBe(9);
    expect(scorePrompt(completo({ camera: 'x', luz: 'y' })).score).toBe(8);
  });

  it('nota mínima é 1 e o tom acompanha a faixa', () => {
    const r = scorePrompt(completo({ hook: 30, dev: 1, cta: 1, camera: 'x', luz: 'y',
      extra: 'regulagem lateral. com as duas mãos e segura o celular. ' + 'x'.repeat(4000) }));
    expect(r.score).toBeGreaterThanOrEqual(1);
    expect(r.score).toBeLessThanOrEqual(5);
    expect(['warn', 'bad']).toContain(r.tone);
  });
});

describe('scorePrompt: tamanho da fala', () => {
  it.each([
    [39, 6, 'Fala curta'],            // < 40 palavras: -4
    [42, 8, 'um pouco curta'],        // 40 a 43: -2
    [44, 10, ''],                     // 44 a 58: sem desconto
    [58, 10, ''],
    [60, 9, 'um pouco acelerada'],    // 59 a 64: -1
    [66, 8, 'longa demais'],          // > 64: -2
  ])('%i palavras -> nota %i', (total, nota, trecho) => {
    const hook = 15;
    const r = scorePrompt(completo({ hook, dev: total - hook - 10, cta: 10 }));
    expect(r.score).toBe(nota);
    if (trecho) expect(issues(r)).toContain(trecho);
  });

  it('gancho com mais de 20 palavras custa 1 ponto, mas só quando há mais de uma fala', () => {
    const r = scorePrompt(completo({ hook: 22, dev: 14, cta: 14 }));
    expect(r.score).toBe(9);
    expect(issues(r)).toContain('gancho');
  });

  it('Guia do Grok: a fala única é lida, conta palavras e não vira "gancho longo"', () => {
    expect(scorePrompt(guia(50)).score).toBe(10);
    const curta = scorePrompt(guia(30));
    expect(curta.score).toBe(6);
    expect(issues(curta)).toContain('Fala curta');
    expect(issues(curta)).not.toContain('gancho');
  });
});

describe('scorePrompt: fidelidade da peça (teste real do biquíni)', () => {
  it('"regulagem lateral" fora da fala custa 3 pontos', () => {
    const r = scorePrompt(completo({ extra: 'Benefício: a calcinha com regulagem lateral ajusta ao corpo.' }));
    expect(r.score).toBe(7);
    expect(r.tone).toBe('warn');
    expect(issues(r)).toContain('regulagem');
  });

  it('"ajustar a calcinha" e "desamarrar" também são pegos', () => {
    expect(scorePrompt(completo({ extra: 'ajustar a calcinha' })).score).toBe(7);
    expect(scorePrompt(completo({ extra: 'ela vai desamarrar o laço' })).score).toBe(7);
  });

  it('a mesma expressão DENTRO da fala não pune (a fala é só conversa)', () => {
    const texto = completo().replace('Fala (PT-BR): "' + fala(20) + '"', 'Fala (PT-BR): "a regulagem lateral ajuda no ajuste ' + fala(14) + '"');
    expect(scorePrompt(texto).score).toBe(10);
  });

  it('fala que cita outras peças fora do "3 jeitos" custa 2 pontos', () => {
    const texto = completo().replace(fala(20), 'uso com saída de praia e short jeans ' + fala(14));
    const r = scorePrompt(texto);
    expect(r.score).toBe(8);
    expect(issues(r)).toContain('saída de praia');
  });

  it('no formato "3 jeitos de usar" citar outras peças é o conteúdo: sem desconto', () => {
    const texto = '3 jeitos de usar. ' + completo().replace(fala(20), 'uso com saída de praia e short jeans ' + fala(14));
    expect(scorePrompt(texto).score).toBe(10);
  });
});

describe('scorePrompt: peça com bordado, pérola ou pendente', () => {
  const deco = 'FATOS CONFIRMADOS: bordados, conchas e pérolas.';

  it('teste de prova (pulo) com peça decorada custa 3 pontos', () => {
    const r = scorePrompt(completo({ extra: `${deco} Ação: o teste do pulo, dá dois pulinhos.` }));
    expect(r.score).toBe(7);
    expect(issues(r)).toContain('Teste de prova');
  });

  it('agachamento com peça decorada também', () => {
    expect(scorePrompt(completo({ extra: `${deco} Ação: faz um agachamento curto.` })).score).toBe(7);
  });

  it('3 jeitos com peça decorada custa 3 pontos', () => {
    const r = scorePrompt('3 jeitos de usar. ' + completo({ extra: deco }));
    expect(r.score).toBe(7);
    expect(issues(r)).toContain('3 jeitos de usar');
  });

  it('peça decorada sem pulo nem troca de look não perde ponto', () => {
    expect(scorePrompt(completo({ extra: deco })).score).toBe(10);
  });

  it('pulo sem peça decorada (calça jeans) não perde ponto', () => {
    expect(scorePrompt(completo({ extra: 'Calça jeans. Ação: o teste do pulo, dá dois pulinhos.' })).score).toBe(10);
  });
});

describe('scorePrompt: contradições', () => {
  it('pede para mostrar compressão e depois proíbe inventar compressão: -2', () => {
    const r = scorePrompt(completo({ extra: 'Mostrar a compressão da peça. ATRIBUTOS: não inventar compressão nem elasticidade.' }));
    expect(r.score).toBe(8);
    expect(issues(r)).toContain('Contradição');
  });

  it('uma mão no celular e ação com as duas mãos: -2 (terceira mão)', () => {
    const r = scorePrompt(completo({ extra: 'Uma mão segura o celular. Ação: abre o top com as duas mãos.' }));
    expect(r.score).toBe(8);
    expect(issues(r)).toContain('terceira mão');
  });

  it('muitas ações e ângulos para 15 s: 4 a 5 custam 1, 6 ou mais custam 3', () => {
    const quatro = scorePrompt(completo({ extra: 'aproxima, caminha, agacha, alonga.' }));
    expect(quatro.score).toBe(9);
    const seis = scorePrompt(completo({ extra: 'aproxima, caminha, agacha, alonga, de costas, gira, pula.' }));
    expect(seis.score).toBe(7);
  });
});
