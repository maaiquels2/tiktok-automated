import { UserRound, Shirt, Image, Check, Clapperboard, Type, Upload, Sparkles, Wand2 } from 'lucide-react';
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
    <div className="stage-stepper" role="list" aria-label="Etapas da producao">
      {stages.map((s, i) => {
        const Icon = icons[s.icon] || Image;
        const state = published || i < currentIdx ? 'done' : i === currentIdx ? 'current' : 'waiting';
        const active = selected === s.id;
        const gen = s.id === 'image' || s.id === 'video'
          ? (campaign.generator === 'flow' ? 'Flow' : 'Grok')
          : s.id.includes('approval')
            ? 'Voce'
            : s.id === 'studio'
              ? 'Studio'
              : null;
        return (
          <button
            key={s.id}
            type="button"
            role="listitem"
            className={`stage-step ${state}${active ? ' selected' : ''}`}
            disabled={busy}
            aria-pressed={active}
            onClick={() => onSelect(s.id)}
          >
            <span className="stage-step-index">{String(i + 1).padStart(2, '0')}</span>
            <span className="stage-step-icon"><Icon size={16} /></span>
            <span className="stage-step-body">
              <strong>{s.title}</strong>
              <small>{state === 'done' ? 'Concluido' : state === 'current' ? 'Agora' : 'A seguir'}{gen ? ` · ${gen}` : ''}</small>
            </span>
            {i < stages.length - 1 && <span className="stage-step-rail" aria-hidden="true" />}
          </button>
        );
      })}
    </div>
  );
}
