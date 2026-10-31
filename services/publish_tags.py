"""Etiquetas de uma publicacao: o que foi ao ar, para depois comparar venda por formato.

O formato fica na campanha e pode mudar depois da publicacao; a versao do prompt (completo ou Guia do Grok) so
existe no texto salvo. Por isso a etiqueta e gravada no slot no momento do registro e nunca reescrita.
Funcoes puras: a rota entrega a campanha (detail) e o que o operador escolheu na tela.
"""
from datetime import datetime, timezone

from services import formats

# Formato que nao fica gravado na campanha: e montado a partir dela (services/home_reveal.py).
EXTRA_FORMATS = ('recebi_em_casa',)
BASES = ('espelho', 'pov', 'movimento')
FORMAT_IDS = ('fala',) + BASES + tuple(formats.FORMATS) + EXTRA_FORMATS
VERSIONS = ('completo', 'guia')
# Como o video foi montado: um clipe so, sequencia de clipes (story_arcs), partes com Extend do Grok
# (story_sequence) ou as duas cenas do "Recebi em casa" (home_reveal). Nenhum dos tres ultimos fica gravado na
# campanha (so sequence_clips), entao o operador pode dizer qual foi.
KINDS = ('unico', 'sequencia', 'extend', 'recebi_em_casa')
# O Guia do Grok (services/prompt_improve.py) abre assim; o prompt completo nao (a tela usa a mesma regra).
GUIDE_START = 'Vídeo vertical'
TAG_KEYS = ('format', 'format_source', 'video_kind', 'video_kind_source', 'duration_s', 'prompt_version',
            'prompt_version_source', 'sequence_clips', 'sequence_arc', 'generator', 'tagged_at', 'tagged_via')


class TagError(ValueError):
    """Valor escolhido na tela que nao existe (a mensagem e para o operador)."""


def campaign_format(c):
    """Id do formato da campanha. video_format cobre os formatos com nome e a mesa; as bases (espelho, pov,
    movimento) so aparecem em video_mode; sem nenhum dos dois e o 'Com fala'."""
    return formats.video_format(c) or formats.video_mode(c) or 'fala'


def prompt_version(video_prompt):
    """'guia', 'completo' ou None quando nao ha prompt de video salvo."""
    text = str(video_prompt or '').strip()
    if not text:
        return None
    return 'guia' if text.startswith(GUIDE_START) else 'completo'


def _choice(value, allowed, label):
    value = str(value or '').strip()
    if value and value not in allowed:
        raise TagError(f'{label} inválido.')
    return value


def video_duration(row):
    """Duracao medida do video aprovado (segundos), ou None. ``row`` e o registro do video da cor: arquivo enviado
    ou so do aparelho; os dois guardam a duracao em ``metadata``."""
    meta = (row or {}).get('metadata')
    try:
        seconds = float((meta or {}).get('duration') or 0)
    except (TypeError, ValueError):
        return None
    return round(seconds, 1) if seconds > 0 else None


def build(c, video_prompt='', chosen_format='', chosen_version='', via='publish_slot', now=None,
          chosen_kind='', duration=None):
    """Etiquetas do slot. ``c`` e a campanha (detail); ``video_prompt`` o prompt de video da cor publicada;
    ``duration`` a duracao medida do video (``video_duration``)."""
    chosen_format = _choice(chosen_format, FORMAT_IDS, 'Formato')
    chosen_version = _choice(chosen_version, VERSIONS, 'Versão do prompt')
    chosen_kind = _choice(chosen_kind, KINDS, 'Tipo de vídeo')
    if chosen_format == 'recebi_em_casa' and chosen_kind and chosen_kind != 'recebi_em_casa':
        raise TagError('Recebi em casa é um tipo de vídeo próprio: escolha o mesmo nos dois campos ou deixe o tipo em automático.')
    clips = str(c.get('sequence_clips') or '').strip()
    if chosen_kind:
        kind, kind_source = chosen_kind, 'operador'
    elif chosen_format == 'recebi_em_casa':
        kind, kind_source = 'recebi_em_casa', 'operador'
    else:
        kind, kind_source = ('sequencia' if clips else 'unico'), 'campanha'
    if chosen_version:
        version, version_source = chosen_version, 'operador'
    elif kind != 'unico':
        # Sequencia e Extend: cada parte tem o seu prompt. Recebi em casa: as duas cenas vem de
        # services/home_reveal.py. Em todos o prompt de video salvo nao e o que foi ao ar.
        version, version_source = None, None
    else:
        version = prompt_version(video_prompt)
        version_source = 'prompt_salvo' if version else None
    moment = (now or datetime.now(timezone.utc)).strftime('%Y-%m-%dT%H:%M:%SZ')
    return {
        'format': chosen_format or campaign_format(c),
        'format_source': 'operador' if chosen_format else 'campanha',
        'video_kind': kind,
        'video_kind_source': kind_source,
        'duration_s': duration,
        'prompt_version': version,
        'prompt_version_source': version_source,
        'sequence_clips': clips,
        'sequence_arc': str(c.get('sequence_arc') or '').strip() if clips else '',
        'generator': str(c.get('generator') or '').strip(),
        'tagged_at': moment,
        'tagged_via': via,
    }


def merge_into_slot(old, new_fields, tags):
    """Slot atualizado: campos novos por cima do que ja existia (nao perde published_at) e etiquetas gravadas
    uma vez so (a primeira vale; o formato pode mudar entre uma cor e outra).

    Slot que ja estava publicado sem etiqueta (registrado antes destas etiquetas) continua sem: o formato de hoje
    da campanha nao e, necessariamente, o que foi ao ar, e a etiqueta de agora pareceria uma publicacao nova.
    """
    old = old if isinstance(old, dict) else {}
    slot = {**old, **new_fields}
    if 'format' not in slot and not old.get('published'):
        slot.update(tags)
    elif old.get('tagged_at'):
        # Ja etiquetado: formato, momento e origem nunca mudam, mas o que ficou em branco (duracao do video que
        # ainda nao estava aprovado quando o link foi salvo, tipo de video) pode ser completado depois.
        for key in ('duration_s', 'video_kind', 'video_kind_source'):
            if slot.get(key) is None and tags.get(key) is not None:
                slot[key] = tags[key]
    return slot
