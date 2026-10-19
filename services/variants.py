"""Variacao por cor: o que e uma cor da campanha e como o prompt dela e refeito.

Antes estas regras estavam copiadas pelas rotas, e uma delas se perdeu: com a
escrita por IA ligada, a 2a cor em diante era refeita sem a trava de cena e o
prompt pedia o ambiente da foto de referencia da modelo, nao o da imagem
aprovada desta campanha.

A gravacao (variacao no banco e a 1a cor espelhando a campanha principal) fica
em ``app.slots``/``app.save_slot``, que usam estas regras.
"""
from services.prompts import color_variants, generate


def colors(value):
    """Cores na ordem digitada, sem repetir (maiusculas e ponto final nao contam)."""
    return color_variants(value)


def slots(value):
    """Uma entrada por cor; campanha sem cor tem um unico slot vazio."""
    return colors(value) or ['']


def uses_approved_base(index):
    """A 1a cor edita a foto de referencia da modelo; as seguintes editam a imagem aprovada."""
    return index > 0


def video_prompt(campaign, color, index, script):
    """Prompt de video da cor ``index`` com as falas de ``script``.

    Usa a variacao de texto ja gravada no pacote (``variation_index``) para o
    resto do prompt nao mudar de molde a cada regravacao.
    """
    variation = script.get('variation_index')
    return generate({**campaign, 'color': color}, script=script,
                    variant_index=int(index if variation is None else variation),
                    base_image=uses_approved_base(index))['video']
