"""Gerador de video: o que muda entre o Grok Imagine e o Google Flow.

Limite do campo de prompt e resolucao estavam repetidos em seis arquivos, e
dois deles discordavam sobre campanha sem gerador. Quem monta prompt, valida
video ou mostra a tela pergunta aqui: ``of(campanha)`` devolve o adapter.
"""
from dataclasses import dataclass

# Folga sob o limite: nome de produto, cor e movimentos vem do briefing e variam.
_MARGIN = 60


@dataclass(frozen=True)
class Generator:
    name: str
    width: int
    height: int
    # O Grok corta o prompt em 4000 caracteres sem avisar; o Flow nao tem limite conhecido.
    max_prompt_chars: int | None

    @property
    def resolution(self):
        return (self.width, self.height)

    @property
    def resolution_label(self):
        return f'{self.width} × {self.height} ({self.width}p)'

    @property
    def prompt_target(self):
        """Tamanho para o qual o montador encolhe o prompt (limite menos a folga)."""
        return self.max_prompt_chars - _MARGIN if self.max_prompt_chars else None

    def fits(self, text):
        return not self.max_prompt_chars or len(text or '') <= self.max_prompt_chars

    def info(self):
        return dict(name=self.name, max_prompt_chars=self.max_prompt_chars,
                    width=self.width, height=self.height)


GROK = Generator('grok', 720, 1280, 4000)
FLOW = Generator('flow', 1080, 1920, None)


def of(campaign):
    """Adapter do gerador da campanha. Sem gerador vale o padrao do banco (Flow)."""
    name = str((campaign or {}).get('generator') or 'flow').strip().casefold()
    return GROK if name == 'grok' else FLOW
