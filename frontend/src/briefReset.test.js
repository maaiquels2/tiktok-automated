import { describe, expect, it } from 'vitest';
import { briefResetMessage, changedFields } from './briefReset';

const campaign = {
  name: 'Blusa', video_mode: '', color: 'Preto, Amarelo', product: 'Blusa', status: 'image_approved',
  assets: [{ kind: 'reference' }, { kind: 'image', slot: 'Preto' }, { kind: 'image', slot: 'Amarelo' }],
  device_videos: [], variants: [{ color: 'Preto' }, { color: 'Amarelo' }], prompts: { hook: 'x' },
};

describe('o que salvar o briefing apaga', () => {
  it('so o nome mudou: nada a avisar', () => {
    expect(changedFields(campaign, { name: 'Outro', video_mode: '' })).toEqual([]);
    expect(briefResetMessage(campaign, { name: 'Outro', video_mode: '' })).toBeNull();
  });

  it('trocar o formato avisa das falas editadas, das imagens e do que mudou', () => {
    const msg = briefResetMessage(campaign, { video_mode: 'espelho' });
    expect(msg).toContain('Formato do vídeo');
    expect(msg).toContain('falas de 2 cores');
    expect(msg).toContain('inclusive as que você editou');
    expect(msg).toContain('2 imagens');
    expect(msg).not.toContain('vídeo,');
  });

  it('conta os videos, inclusive os que ficaram no aparelho', () => {
    const c = { ...campaign, assets: [...campaign.assets, { kind: 'video' }], device_videos: [{ slot: 'Amarelo' }] };
    expect(briefResetMessage(c, { color: 'Preto' })).toContain('2 vídeos');
  });

  it('com fala para so movimento: indica o botao que nao apaga', () => {
    expect(briefResetMessage(campaign, { video_mode: 'movimento' })).toContain('etapa Criar vídeo');
    expect(briefResetMessage(campaign, { video_mode: 'espelho' })).not.toContain('etapa Criar vídeo');
  });

  it('sem nada produzido ainda, nao ha o que perder', () => {
    const vazio = { ...campaign, assets: [{ kind: 'reference' }], variants: [], prompts: {} };
    expect(briefResetMessage(vazio, { video_mode: 'espelho' })).toBeNull();
  });

  it('trocar as fotos do produto tambem apaga', () => {
    expect(briefResetMessage(campaign, { video_mode: '' }, { photos: 1 })).toContain('apaga');
  });
});
