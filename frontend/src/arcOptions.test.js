import { describe, expect, it } from 'vitest';
import { CLIP_TURN_OPTIONS, arcOptions, resizeTurns } from './arcOptions';

describe('opcoes da sequencia (giro por clipe e close de textura)', () => {
  it('desligadas nao mandam nada: o pedido fica igual ao de antes', () => {
    expect(arcOptions([], 3, false)).toEqual({ clip_turns: undefined, texture: undefined });
    expect(arcOptions(['', '', ''], 3, false)).toEqual({ clip_turns: undefined, texture: undefined });
    expect(JSON.stringify(arcOptions(['', ''], 2, false))).toBe('{}');
  });

  it('um giro por clipe, no tamanho da sequencia', () => {
    expect(arcOptions(['', 'costas_pausa', 'lado'], 2, false).clip_turns).toEqual(['', 'costas_pausa']);
    expect(arcOptions(['lado'], 3, true)).toEqual({ clip_turns: ['lado', '', ''], texture: true });
    expect(resizeTurns(undefined, 2)).toEqual(['', '']);
  });

  it('as opcoes da tela sao as do servidor', () => {
    expect(CLIP_TURN_OPTIONS.map(([id]) => id)).toEqual(['', 'frente', 'leve_lado', 'lado', 'costas', 'costas_pausa']);
  });
});
