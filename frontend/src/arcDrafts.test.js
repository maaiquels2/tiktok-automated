import { describe, expect, it } from 'vitest';
import { anyDirty, baseDrafts, dirtyClips, draftKey, restoreDrafts } from './arcDrafts';

const clips = [{ lines: ['a1', 'a2', 'a3'] }, { lines: ['b1', 'b2', 'b3'] }];

describe('falas editadas da sequencia que ainda nao viraram prompt', () => {
  it('sem edicao, nada esta pendente e os prompts copiados valem', () => {
    expect(dirtyClips(clips, baseDrafts(clips))).toEqual([false, false]);
    expect(dirtyClips(clips, [])).toEqual([false, false]);
    expect(anyDirty(clips, baseDrafts(clips))).toBe(false);
  });

  it('colar a fala do ChatGPT numa caixa deixa so aquele clipe pendente', () => {
    const drafts = baseDrafts(clips);
    drafts[1] = 'fala nova\nmeio novo\nfecho novo';
    expect(dirtyClips(clips, drafts)).toEqual([false, true]);
    expect(anyDirty(clips, drafts)).toBe(true);
  });

  it('voltar ao texto montado limpa a pendencia', () => {
    const drafts = baseDrafts(clips);
    drafts[0] = 'x';
    drafts[0] = 'a1\na2\na3';
    expect(anyDirty(clips, drafts)).toBe(false);
  });

  it('guarda o rascunho por cor, arco e numero de clipes', () => {
    expect(draftKey(7, 12, 'motivos', 2)).toBe('7|12|motivos|2');
    expect(draftKey(7, null, 'motivos', 2)).toBe('7|base|motivos|2');
    expect(draftKey(7, 12, 'mito', 2)).not.toBe(draftKey(7, 12, 'motivos', 2));
  });

  it('o rascunho guardado volta so se a sequencia tem o mesmo numero de clipes', () => {
    expect(restoreDrafts(clips, ['x', 'y'])).toEqual(['x', 'y']);
    expect(restoreDrafts(clips, ['x'])).toEqual(baseDrafts(clips));
    expect(restoreDrafts(clips, undefined)).toEqual(baseDrafts(clips));
  });
});
