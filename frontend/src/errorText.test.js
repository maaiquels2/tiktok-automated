import { describe, expect, it } from 'vitest';
import { errorText } from './errorText';

describe('texto do aviso de erro', () => {
  it('texto passa como esta e vazio limpa o aviso', () => {
    expect(errorText('Falhou')).toBe('Falhou');
    expect(errorText('')).toBe('');
    expect(errorText(null)).toBe('');
    expect(errorText(undefined)).toBe('');
  });

  it('um Error vira a mensagem dele (nunca o objeto)', () => {
    expect(errorText(new Error('Gere os prompts de imagem de todas as cores antes.'))).toBe('Gere os prompts de imagem de todas as cores antes.');
  });

  it('qualquer outro objeto vira uma mensagem generica', () => {
    expect(errorText({ status: 500 })).toBe('Algo deu errado. Tente de novo.');
    expect(typeof errorText({})).toBe('string');
  });
});
