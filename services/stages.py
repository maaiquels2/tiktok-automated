"""Etapas da campanha: ordem, o que falta para avancar e o que uma edicao desfaz.

Funcoes puras sobre o detalhe da campanha (o mesmo dicionario que a tela
recebe). A transicao no app barra com estas regras e ``readiness`` vai junto
com o detalhe, para a tela parar de re-derivar as regras por indice e liberar
um botao que o servidor depois recusa.
"""
from services import variants

STATES = ['briefing', 'image_ready', 'image_approved', 'script_ready', 'video_ready',
          'video_approved', 'ready_to_publish', 'published']

SCRIPT_FIELDS = {'image': 'prompt de imagem', 'video': 'prompt de vídeo', 'hook': 'gancho',
                 'development': 'desenvolvimento', 'cta': 'chamada', 'caption': 'legenda'}
SPOKEN = {'hook', 'development', 'cta'}


def rules():
    """O que a tela precisa (frontend/src/stageRules.json; um teste confere)."""
    return dict(states=list(STATES))


def index(status):
    return STATES.index(status)


def is_next(status, target):
    return target in STATES and index(target) == index(status) + 1


def script_gaps(c):
    """[(cor, campo)] que faltam para concluir o roteiro.

    Com varias cores cada uma precisa de falas, legenda e prompt de video; com
    uma cor, de todos os textos da campanha.
    """
    if c.get('variants'):
        need = ('hook', 'development', 'cta', 'caption', 'video')
        return [(v['color'], k) for v in c['variants'] for k in need
                if not str((v.get('prompts') or {}).get(k) or '').strip()]
    prompts = c.get('prompts') or {}
    return [('', k) for k in SCRIPT_FIELDS if not str(prompts.get(k) or '').strip()]


def media_by_slot(c, kind):
    """{cor: midia ``kind`` (image ou video)} na ordem das cores; None onde falta.

    Video conta o arquivo enviado e o que ficou so no aparelho (o enviado vale
    primeiro). Campanha sem cor aceita a primeira midia, qualquer que seja o slot.
    """
    slots = variants.slots(c.get('color'))
    rows = [a for a in c.get('assets') or [] if a.get('kind', kind) == kind]
    if kind == 'video':
        rows += c.get('device_videos') or []
    by_slot = {}
    for row in rows:
        by_slot.setdefault(row.get('slot') or '', row)
    if slots == [''] and '' not in by_slot and rows:
        by_slot[''] = rows[0]
    return {slot: by_slot.get(slot) for slot in slots}


def media_gaps(c, kind, approved=False):
    """Cores sem midia (``kind`` image ou video), ou sem aprovacao se ``approved``."""
    return [slot for slot, row in media_by_slot(c, kind).items()
            if not row or (approved and not row.get('approved_at'))]


def readiness(c):
    """O que ainda bloqueia cada aprovacao, em texto para a tela."""
    def media(kind, approved, word):
        return [f'{word} de {slot}' if slot else word
                for slot in media_gaps(c, kind, approved)]
    has_reference = any(a.get('kind') == 'reference' for a in c.get('assets') or [])
    return {
        'image_approved': ([] if has_reference else ['foto da modelo']) + media('image', False, 'imagem'),
        'script_ready': media('image', True, 'imagem aprovada')
        + [f'{color}: falta {SCRIPT_FIELDS[k]}' if color else f'falta {SCRIPT_FIELDS[k]}'
           for color, k in script_gaps(c)],
        'video_approved': media('video', False, 'vídeo'),
        'ready_to_publish': media('video', True, 'vídeo aprovado'),
    }


def rewind_after_edit(status, fields):
    """(etapa para onde voltar, midias a descartar) depois de editar ``fields``.

    Prompt de imagem novo invalida imagens e videos; falas ou prompt de video
    novos, depois das imagens, invalidam so os videos. Legenda nao volta etapa.
    """
    fields = set(fields)
    if 'image' in fields:
        return 'briefing', ['image', 'video']
    if fields & (SPOKEN | {'video'}) and index(status) >= index('image_approved'):
        return 'image_approved', ['video']
    return None, []
