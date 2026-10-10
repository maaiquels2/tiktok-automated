import { Check } from 'lucide-react';
import { nextStage, stageInfo } from './api';
import { PHASES, phaseOfStage } from './ui';

// Mapa da producao em 4 fases (Preparar, Imagem, Video, Publicar), cada uma
// com sua cor. Abaixo, as subetapas da fase aberta. Antes eram 9 cartoes do
// mesmo peso lado a lado, e no celular a maioria ficava fora da tela.
export default function Canvas({ campaign, selected, onSelect, busy, stages = stageInfo }) {
  const order = stages.map(s => s.id);
  const published = campaign?.status === 'published';
  const currentId = nextStage(campaign);
  const currentIdx = order.indexOf(currentId);
  const stateOf = id => {
    const i = order.indexOf(id);
    return published || i < currentIdx ? 'done' : i === currentIdx ? 'current' : 'waiting';
  };
  const openPhase = phaseOfStage(selected);
  const phases = PHASES.map(p => ({ ...p, stages: p.stages.filter(id => order.includes(id)) })).filter(p => p.stages.length);

  return (
    <nav className="rd-stepper" aria-label="Fases da produção">
      <ol className="rd-phases">
        {phases.map((p, i) => {
          const states = p.stages.map(stateOf);
          const done = states.every(s => s === 'done');
          const current = states.includes('current');
          const open = PHASES.indexOf(PHASES.find(x => x.id === p.id)) === openPhase;
          // Abrir uma fase leva a etapa em andamento dela; numa fase ja
          // concluida, a primeira etapa; numa futura, a primeira tambem.
          const target = p.stages.find(id => stateOf(id) === 'current') || p.stages[0];
          return (
            <li key={p.id}>
              <button
                type="button"
                className={`rd-phase is-${p.id}${done ? ' is-done' : ''}${current ? ' is-current' : ''}${open ? ' is-open' : ''}`}
                aria-current={open ? 'step' : undefined}
                disabled={busy}
                onClick={() => onSelect(target)}
              >
                <span className="rd-phase-mark" aria-hidden="true">{done ? <Check size={14} strokeWidth={3} /> : i + 1}</span>
                {p.title}
              </button>
            </li>
          );
        })}
      </ol>
      <div className="rd-substeps" role="tablist" aria-label="Etapas desta fase">
        {(phases[openPhase] || phases[0]).stages.map(id => {
          const s = stages.find(x => x.id === id);
          const state = stateOf(id);
          return (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={selected === id}
              className={`rd-substep is-${state}${selected === id ? ' is-selected' : ''}`}
              disabled={busy}
              onClick={() => onSelect(id)}
            >
              {state === 'done' && <Check size={14} strokeWidth={3} aria-hidden="true" />}
              {s?.title}
              {state === 'current' && <span className="rd-substep-now">agora</span>}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
