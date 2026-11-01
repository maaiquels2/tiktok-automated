import {describe, expect, it} from 'vitest';
import {warningsFor} from './mediaChecks';

describe('warningsFor', () => {
  const list = [
    {kind: 'image', slot: 'Azul', message: 'a'},
    {kind: 'video', slot: 'Azul', message: 'b'},
    {kind: 'video', slot: '', message: 'c'},
  ];
  it('filtra por tipo e cor', () => {
    expect(warningsFor(list, {kind: 'image'}).map(w => w.message)).toEqual(['a']);
    expect(warningsFor(list, {kind: 'video', slot: ''}).map(w => w.message)).toEqual(['c']);
    expect(warningsFor(list, {slot: 'Azul'}).map(w => w.message)).toEqual(['a', 'b']);
  });
  it('aceita lista ausente', () => {
    expect(warningsFor(undefined, {kind: 'image'})).toEqual([]);
    expect(warningsFor(null)).toEqual([]);
  });
});
