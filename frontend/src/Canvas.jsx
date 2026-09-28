import { UserRound, Shirt, Image, Check, Clapperboard, Type, Upload } from 'lucide-react';
import { nextStage, stageInfo } from './api';

const icons = {
  user: UserRound,
  shirt: Shirt,
  image: Image,
  check: Check,
  video: Clapperboard,
  text: Type,
  upload: Upload,
};

export default function Canvas({ campaign, selected, onSelect, busy, stages = stageInfo }) {
  const currentIdx = stages.findIndex((s) => s.id === nextStage(campaign));
  const published = campaign?.status === 'published';

  return (
    <nav className="stage-stepper" aria-label="Etapas da produção">
      {stages.map((s, i) => {
        const state = published || i < currentIdx ? 'done' : i === currentIdx ? 'current' : 'waiting';
        // Etapa concluida mostra um visto: antes o icone era o mesmo e so a
        // cor de fundo mudava, dificil de perceber o que ja foi feito.
        const Icon = state === 'done' ? Check : icons[s.icon] || Image;
        const active = selected === s.id;
        const gen = s.id === 'image' || s.id === 'video'
          ? (campaign.generator === 'flow' ? 'Flow' : 'Grok')
          : s.id.includes('approval')
            ? 'Você'
            : s.id === 'studio'
              ? 'Studio'
              : null;
        return (
          <button
            key={s.id}
            type="button"
            className={`stage-step ${state}${active ? ' selected' : ''}`}
            disabled={busy}
            aria-current={active ? 'step' : undefined}
            title={s.title}
            onClick={() => onSelect(s.id)}
          >
            <span className="stage-step-index">{String(i + 1).padStart(2, '0')}</span>
            <span className="stage-step-icon"><Icon size={16} /></span>
            <span className="stage-step-body">
              <strong>{s.title}</strong>
              <small>{state === 'done' ? 'Concluído' : state === 'current' ? 'Agora' : 'A seguir'}{gen ? ` · ${gen}` : ''}</small>
            </span>
            {i < stages.length - 1 && <span className="stage-step-rail" aria-hidden="true" />}
          </button>
        );
      })}
    </nav>
  );
}
