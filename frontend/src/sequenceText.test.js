import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { FEW_FACTS, isFewFacts, pointToFacts } from './sequenceText.js';

describe('aviso de poucos fatos', () => {
  it('o servidor ainda usa o texto que a tela troca', () => {
    const src = readFileSync(new URL('../../services/story_arcs.py', import.meta.url), 'utf-8');
    expect(src).toContain(FEW_FACTS);
  });
  it('aponta para o campo de fatos do painel, nunca para o Detalhes', () => {
    const msg = 'Só encontrei 1 (capuz). Escreva pelo menos 3 no campo Detalhes, separados por vírgula.';
    expect(isFewFacts(msg)).toBe(true);
    const out = pointToFacts(msg, 'abaixo');
    expect(out).toContain('no campo Fatos da peça abaixo');
    expect(out).not.toContain('Detalhes');
    expect(pointToFacts('Outro erro', 'acima')).toBe('Outro erro');
  });
});
