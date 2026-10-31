import SCRIPT_RULES from './scriptRules.json';

// Orcamento de palavras das tres falas (services/script_budget.py tem os mesmos numeros). Os dois editores de
// roteiro (uma cor e varias cores) usam este arquivo, para a faixa alvo aparecer nos dois.
const PART_LABELS = { hook: 'abertura', development: 'meio', cta: 'fechamento' };

export function countWords(value) {
  const clean = String(value || '').trim();
  return clean ? clean.split(/\s+/).length : 0;
}

// Acima do alvo nao e erro: fica neutro. Vazio ou curto demais e que pede atencao.
function partState(key, words) {
  const [low] = SCRIPT_RULES.target[key];
  return words >= low ? 'ok' : (words >= low - 2 ? 'near' : 'off');
}

export function ScriptBudget({ draft, caption }) {
  const rows = Object.entries(SCRIPT_RULES.target).map(([key, [low, high]]) => {
    const words = countWords(draft[key]);
    return { key, words, low, high, time: PART_LABELS[key], state: partState(key, words) };
  });
  const total = rows.reduce((sum, row) => sum + row.words, 0);
  const [fillLow, fillHigh] = SCRIPT_RULES.fill;
  const [warnLow, warnHigh] = SCRIPT_RULES.warn;
  const totalState = total < warnLow || total > warnHigh ? 'near' : 'ok';
  return <div className="script-budget" aria-label="Palavras por trecho">
    {caption && <small className="help budget-caption">{caption}</small>}
    {rows.map(row => <span key={row.key} className={'budget-chip is-' + row.state} title={`${row.time}: alvo ${row.low} a ${row.high} palavras`}>
      <em>{row.time}</em>{row.words}<small>/{row.low}–{row.high}</small>
    </span>)}
    <span className={'budget-chip is-total is-' + totalState} title={`De ${fillLow} a ${fillHigh} palavras ocupam os 15 s sem silêncio; acima de ${warnHigh}, use a sequência de clipes`}>
      <em>total</em>{total}<small>{total > warnHigh ? ' · sequência' : total < warnLow ? ' · vai sobrar silêncio' : ' palavras'}</small>
    </span>
  </div>;
}

// Contagem ao vivo logo abaixo de cada fala, contra a faixa alvo daquele trecho.
export function FieldCount({ field, value }) {
  const target = SCRIPT_RULES.target[field];
  if (!target) return null;
  const words = countWords(value);
  return <small className={'field-count is-' + partState(field, words)}>
    {words} {words === 1 ? 'palavra' : 'palavras'} · alvo {target[0]}–{target[1]}
  </small>;
}
