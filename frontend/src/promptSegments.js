// Divide o prompt de video em pedacos so para exibir: titulos de secao e falas entre aspas ganham destaque.
// Nao altera o texto: juntar todos os pedacos devolve o prompt original, e o que vai para a area de
// transferencia e sempre o prompt cru (veja promptSegments.test.js).
//
// Titulo de secao: palavras em maiusculas seguidas de ":" ou "—" ("FATOS CONFIRMADOS:", "ENCERRAMENTO (12–15s):",
// "0–4s HOOK:"). Maiuscula no meio da frase ("ANEXE a IMAGEM APROVADA da cor") nao e titulo.
const WORD = '(?:[A-ZÀ-Ú][A-ZÀ-Ú0-9/–-]*|\\d+(?:[–-]\\d+)?s?)';
const LABEL_RE = new RegExp(`(^|[^\\p{L}\\p{N}])(${WORD}(?: ${WORD})*(?:\\s*\\([^)\\n]{0,60}\\))?\\s*(?::|—))`, 'gu');
const SAY_RE = /"[^"\n]{2,500}"|“[^”\n]{2,500}”/g;

export function segmentPrompt(text) {
  const src = String(text ?? '');
  const marks = [];
  for (const m of src.matchAll(LABEL_RE)) {
    // "9:16" nao e titulo: precisa de uma palavra em maiusculas, nao so numeros.
    if (!/[A-ZÀ-Ú]{2,}/.test(m[2])) continue;
    const start = m.index + m[1].length;
    marks.push([start, start + m[2].length, 'label']);
  }
  for (const m of src.matchAll(SAY_RE)) marks.push([m.index, m.index + m[0].length, 'say']);
  marks.sort((a, b) => a[0] - b[0]);
  const out = [];
  let pos = 0;
  for (const [start, end, kind] of marks) {
    if (start < pos) continue;
    if (start > pos) out.push({ kind: 'text', text: src.slice(pos, start) });
    out.push({ kind, text: src.slice(start, end) });
    pos = end;
  }
  if (pos < src.length) out.push({ kind: 'text', text: src.slice(pos) });
  return out;
}
