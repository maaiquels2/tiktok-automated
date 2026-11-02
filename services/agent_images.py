"""Mensagem unica para o Grok Agente gerar a imagem de TODAS as cores de uma vez.

Hoje o operador cola um prompt de imagem por cor. Os prompts das cores so diferem no nome da cor
(services/prompts.py gera o mesmo texto trocando a cor), entao uma mensagem so com o prompt da 1a cor e a lista
das outras cores pede as N imagens. So leitura: nada e gravado. Se o operador editou a mao o prompt de uma cor (da 2a em
diante) e ele deixou de ser igual ao das outras (fora o nome da cor), o pacote nao e montado, para nao apagar a edicao em silencio.
"""
from services import generators

AGENT_LIMIT = generators.GROK.max_prompt_chars   # o limite de 4.000 caracteres do agente vem do relato do operador

INTRO = ('Vou te passar UM prompt-base e uma lista de cores. Gere {n} imagens SEPARADAS, uma por cor, na ordem da '
         'lista, todas com o MESMO prompt, a mesma modelo, a mesma pose, o mesmo cenário e a mesma luz, trocando '
         'SOMENTE a cor da peça. Nunca misture cores na mesma imagem e não crie versões extras. Use os anexos desta '
         'conversa (referência da modelo e fotos do produto) em todas as imagens.')


class ImagesError(Exception):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def _same_but_color(base_color, base, color, prompt):
    return base.replace(base_color, color) == prompt


def build_agent_images(variants):
    """``variants``: lista de {color, prompts:{image}} na ordem. Devolve a mensagem e o tamanho."""
    items = [(str(v.get('color') or '').strip(), str((v.get('prompts') or {}).get('image') or '').strip())
             for v in variants]
    if len(items) < 2:
        raise ImagesError('O pacote do agente serve para duas ou mais cores.')
    if any(not color or not prompt for color, prompt in items):
        raise ImagesError('Gere os prompts de imagem de todas as cores antes.')
    base_color, base = items[0]
    # O prompt da 1a cor parte da foto de referencia da modelo; os das cores seguintes editam a imagem aprovada (o app gera
    # os dois de formas diferentes, de proposito). Entao so as cores a partir da 2a se comparam entre si: um prompt editado a
    # mao entre elas bloqueia o pacote. O prompt-base da mensagem e o da 1a cor, que vale como esta (inclusive editado).
    if len(items) > 2:
        ref_color, ref = items[1]
        for color, prompt in items[2:]:
            if not _same_but_color(ref_color, ref, color, prompt):
                raise ImagesError(f'O prompt de imagem de {color} foi editado e difere do das outras cores além do nome '
                                  'da cor. Use um prompt por cor.')
    colors = '\n'.join(f'{i}. {color}' + (' (a cor do prompt-base)' if i == 1 else '') for i, (color, _) in enumerate(items, 1))
    text = (f'{INTRO.format(n=len(items))}\n\nPROMPT-BASE (cor: {base_color}):\n{base}\n\n'
            f'CORES, uma imagem para cada, nesta ordem:\n{colors}')
    return dict(text=text, chars=len(text), limit=AGENT_LIMIT, fits=len(text) <= AGENT_LIMIT, colors=[c for c, _ in items])
