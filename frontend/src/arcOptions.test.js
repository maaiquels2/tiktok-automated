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

describe('clipe de 10 s e ganchos visuais', () => {
  it('so manda seconds e hook_visual quando escolhidos', async () => {
    const { arcOptions: opts } = await import('./arcOptions');
    expect(JSON.stringify(opts([], 3, false, 15, ''))).toBe('{}');
    expect(opts([], 3, false, 10, 'corre')).toEqual({ clip_turns: undefined, texture: undefined, seconds: 10, hook_visual: 'corre' });
  });
  it('o arco Dor e FOMO so existe em 10 s e sempre com 3 clipes', async () => {
    const { arcsFor, arcFor, clipsFor, windowsLabel, HOOK_VISUAL_OPTIONS } = await import('./arcOptions');
    const base = [['motivos', 'Motivos', '']];
    expect(arcsFor(15, base).map(([id]) => id)).toEqual(['motivos']);
    expect(arcsFor(10, base).map(([id]) => id)).toEqual(['motivos', 'dor']);
    expect(arcFor(15, 'dor')).toBe('motivos');
    expect(arcFor(10, 'dor')).toBe('dor');
    expect(clipsFor('dor', 2)).toBe(3);
    expect(clipsFor('motivos', 2)).toBe(2);
    expect(windowsLabel(10)).toContain('8–10 s');
    expect(windowsLabel(15)).toContain('12–15 s');
    expect(HOOK_VISUAL_OPTIONS.map(([id]) => id)).toEqual(['', 'espia', 'corre', 'dedo']);
  });
});
