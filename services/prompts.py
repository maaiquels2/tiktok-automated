"""Local, deterministic drafts. No paid generation or external API calls."""
import difflib
import re
import unicodedata

from services import formats, persuasion, speech_bank


def _phrase(value):
    return ' '.join(str(value or '').strip().rstrip('.').split())


def _clean_punct(value):
    """Junta falas sem criar pontuacao dupla ('movimento?.' vira 'movimento?')."""
    text = ' '.join(str(value or '').split())
    text = re.sub(r'([!?])\s*\.', r'\1', text)
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)
    text = re.sub(r'\.{2,}', '.', text)
    return text.strip()


def _pt_br(value):
    """Normalize common production/marketing English before spoken copy is built."""
    text = _phrase(value)
    if not text:
        return ''
    replacements = (
        (r'\bworkout\b', 'treino de academia'),
        (r'\bactivewear\b', 'roupa de treino'),
        (r'\bbeachwear\b', 'moda praia'),
        (r'\bstreetwear\b', 'moda urbana'),
        (r'\bwalk[- ]and[- ]talk\b', 'caminhada falando com a câmera'),
        (r'\blow[- ]angle\b', 'ângulo baixo'),
        (r'\bclose[- ]up\b', 'detalhe de perto'),
        (r'\bclose\b', 'detalhe de perto'),
        (r'\blook\b', 'visual'),
        (r'\bshop\b', 'loja'),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.I)
    return text


_PRODUCT_FEATURES = (
    ('bolso lateral', ('bolso lateral', 'bolsos laterais')),
    ('bolso interno', ('bolso interno', 'bolsos internos')),
    ('bolso', ('bolso', 'bolsos')),
    ('botões', ('botões', 'botoes')),
    ('cós largo', ('cós largo', 'cos largo')),
    ('cintura alta', ('cintura alta',)),
    ('cintura média', ('cintura média', 'cintura media')),
    ('cintura baixa', ('cintura baixa',)),
    ('tecido leve', ('tecido leve',)),
    ('tecido macio', ('tecido macio',)),
    ('tecido encorpado', ('tecido encorpado',)),
    ('secagem rápida', ('secagem rápida', 'secagem rapida')),
    ('compressão', ('compressão', 'compressao')),
    ('sem transparência', ('sem transparência', 'sem transparencia')),
    ('bojo', ('bojo', 'bojos')),
    ('renda', ('renda',)),
    ('cetim', ('cetim',)),
    ('viscose', ('viscose',)),
    ('canelado', ('canelado', 'canelada', 'ribana')),
    ('amarração', ('amarração', 'amarracao', 'de amarrar', 'lacinho')),
    ('fenda', ('fenda',)),
    ('crochê', ('crochê', 'croche')),
    ('tule', ('tule',)),
    ('decote nas costas', ('decote nas costas', 'costas abertas', 'costas nuas')),
    ('decote', ('decote',)),
    # Detalhe decorativo vende mais que a alca: vem antes dela (teste real do
    # maio: "argolas douradas" e "recortes" sumiam e o close ia para a alca).
    ('argolas', ('argola', 'argolas')),
    ('recorte', ('recorte', 'recortes', 'vazado', 'vazados')),
    ('franzido', ('franzido', 'franzida', 'drapeado', 'drapeada')),
    ('alça regulável', ('alça regulável', 'alca regulavel', 'alças reguláveis', 'alcas regulaveis')),
    ('alça', ('alça', 'alca')),
    ('manga', ('manga',)),
    ('barra', ('barra',)),
    ('costura', ('costura',)),
    ('estampa', ('estampa',)),
    ('acabamento', ('acabamento',)),
    ('forro', ('forro',)),
    ('zíper', ('zíper', 'ziper')),
    ('botão', ('botão', 'botao')),
    ('cordão', ('cordão', 'cordao')),
    ('elástico', ('elástico', 'elastico')),
    ('capuz', ('capuz',)),
    ('gola', ('gola',)),
    ('punho', ('punho',)),
    ('poliamida', ('poliamida',)),
    ('courino', ('courino', 'couro sintético', 'couro sintetico')),
    ('algodão', ('algodão', 'algodao')),
    ('lã', ('lã',)),
    ('elastano', ('elastano',)),
    ('poliéster', ('poliéster', 'poliester')),
)

_MATERIAL_LABELS = {'poliamida', 'courino', 'algodão', 'lã', 'elastano', 'poliéster', 'viscose', 'cetim'}


_NICHE_TEXTS = None


def _niche_default_texts():
    """Textos padrao dos nichos (detalhes, beneficio, angulo...). Sao direcao
    de cena preenchida pelo formulario, nao fato do produto."""
    global _NICHE_TEXTS
    if _NICHE_TEXTS is None:
        try:
            from services.model_library import NICHE_DEFAULTS
            _NICHE_TEXTS = sorted({_phrase(v).casefold() for d in NICHE_DEFAULTS.values() if isinstance(d, dict)
                                   for v in d.values() if isinstance(v, str) and len(_phrase(v)) > 12},
                                  key=len, reverse=True)
        except Exception:
            _NICHE_TEXTS = []
    return _NICHE_TEXTS


def without_niche_defaults(text):
    """Tira do texto os trechos padrao do nicho. No teste das 6 modas, o
    padrao "Priorizar sensacao de tecido macio" virava o fato confirmado
    "tecido macio" (e "renda" na moda intima, "alca" na praia) sem o operador
    ter dito nada."""
    low = _phrase(text).casefold()
    for default in _niche_default_texts():
        low = low.replace(default, ' ')
    return low


def _is_niche_default(value):
    v = re.sub(r'^(tem|possui)\s+', '', _phrase(value).casefold())
    return bool(v) and any(v == re.sub(r'^(tem|possui)\s+', '', d) for d in _niche_default_texts())


def _product_features(c, limit=3):
    """Return only attributes literally present in the user's brief.

    This is deliberately conservative: a local generator is more useful when it
    omits an unconfirmed selling point than when it invents one.
    """
    source = ' '.join(without_niche_defaults(c.get(key)) for key in
                      ('product', 'outfit', 'details', 'angle', 'benefit'))
    # The product description and benefit are authoritative. An angle such as
    # "mostrar bolso" must not turn "legging sem bolso" into a fake feature.
    negative_source = ' '.join(without_niche_defaults(c.get(key)) for key in
                               ('product', 'outfit', 'details', 'benefit'))
    found = []
    for label, needles in _PRODUCT_FEATURES:
        # Do not report a broad feature after its more precise form ("bolso"
        # after "bolso lateral"). It wastes words and weakens the hook.
        if label == 'bolso' and any(item.startswith('bolso ') for item in found):
            continue
        negative_needles = list(needles)
        if ' ' in label:
            negative_needles.append(label.split()[0])
        if label != 'sem transparência' and any(
            re.search(rf'\b(?:sem|não|nao)(?:\s+(?:possui|tem|oferece))?\s+(?:um|uma|o|a)?\s*{re.escape(needle)}\b', negative_source, re.I)
            for needle in negative_needles
        ):
            continue
        if any(_feature_present(source, needle, label) for needle in needles) and label not in found:
            found.append(label)
        if len(found) >= limit:
            break
    return found


def _material_facts(c):
    """Keep composition visible even when several other features fill the focus list."""
    return [item for item in _product_features(c, limit=50) if item in _MATERIAL_LABELS]


def _feature_present(source: str, needle: str, label: str = '') -> bool:
    """Match an attribute while ignoring explicit negations such as 'sem bolso'."""
    escaped = re.escape(needle)
    if not re.search(rf'\b{escaped}\b', source, re.I):
        return False
    if label.startswith('sem '):
        # "sem transparencia" pode aparecer dentro de uma duvida ou negacao
        # do proprio usuario ("nao e sem transparencia", "nao sei se e sem
        # transparencia") -- nesse caso nao confirma o atributo.
        doubt = rf'\b(?:não|nao)\b(?:\s+(?:sei\s+se|tenho\s+certeza\s+se|sei))?(?:\s+\w+){{0,2}}\s*{escaped}\b'
        return not re.search(doubt, source, re.I)
    negative = rf'\b(?:sem|não|nao)(?:\s+(?:possui|tem|oferece))?\s+(?:um|uma|o|a)?\s*{escaped}\b'
    return not re.search(negative, source, re.I)


_FALLBACK_DETAIL = 'o caimento e os detalhes visíveis'


def _focus_parts(c):
    """Turn the angle and explicit product attributes into readable focus text."""
    features = _product_features(c, limit=2)
    angle = _pt_br(c.get('angle'))
    cleaned = re.sub(r'^(mostrar|mostre|destacar|destaque|focar em)\s+', '', angle,
                     flags=re.I).strip(' .,:;')
    directional = re.search(
        r'\b(demonstrar|demonstra|mostrar|mostre|prova social|antes/depois|rotina|revela|revelar|movimento real)\b',
        cleaned, re.I,
    )
    # Long angle paragraphs are production direction, not a product detail to
    # repeat in a hook. Prefer verified features from the brief in that case.
    if cleaned and not directional and len(cleaned.split()) <= 9 and not _focus_is_contradictory(c, cleaned) and cleaned.casefold() not in {
        'detalhes', 'os detalhes', 'o caimento e os detalhes', 'caimento e detalhes',
        'qualidade', 'versatilidade', 'economia', 'autoestima', 'confiança',
        'confianca', 'custo-benefício', 'custo beneficio', 'bom custo-benefício',
        'bom custo beneficio'
    }:
        return cleaned, features
    if features:
        if len(features) == 1:
            return features[0], features
        if len(features) == 2:
            return f'{features[0]} e {features[1]}', features
        return f'{features[0]}, {features[1]} e {features[2]}', features
    return _FALLBACK_DETAIL, []


def _focus_is_contradictory(c, focus: str) -> bool:
    """Reject a short angle that asks for an attribute explicitly negated in the brief."""
    source = ' '.join(_phrase(c.get(key)).casefold() for key in
                      ('product', 'outfit', 'details', 'benefit'))
    target = _phrase(focus).casefold()
    for label, needles in _PRODUCT_FEATURES:
        if label.startswith('sem '):
            continue
        negative_needles = list(needles)
        if ' ' in label:
            negative_needles.append(label.split()[0])
        negated = any(re.search(rf'\b(?:sem|não|nao)(?:\s+(?:possui|tem|oferece))?\s+(?:um|uma|o|a)?\s*{re.escape(needle)}\b', source, re.I)
                      for needle in negative_needles)
        if negated and any(re.search(rf'\b{re.escape(needle)}\b', target, re.I) for needle in needles):
            return True
    return False


def _persuasion_signals(c):
    """Return selling angles explicitly present in the operator's brief.

    These signals make the copy persuasive without turning a niche default or
    a generic adjective into an invented product promise.
    """
    blob = ' '.join(_phrase(c.get(key)).casefold() for key in
                    ('product', 'outfit', 'benefit', 'angle', 'details'))
    occasion_blob = f"{blob} {_phrase(c.get('audience')).casefold()}"
    signals = []
    if re.search(r'\b(econom|custo|preço|preco|barat|rende|bom negócio|bom negocio)\w*', blob):
        signals.append('economia')
    if re.search(r'\b(qualidade|premium|duráv|durav|resistent)\w*', blob):
        signals.append('qualidade')
    if re.search(r'\b(versátil|versatil|multiuso|várias formas|varias formas|2 em 1|combina com tudo)\b', blob):
        signals.append('versatilidade')
    if re.search(r'\b(autoestima|confiança|confianca|valoriza o corpo|se sentir bem)\b', blob):
        signals.append('autoestima')
    if (re.search(r'\b(trabalho|escritório|escritorio|home office)\b', occasion_blob)
            and re.search(r'\b(amigas|sair|saída|saida|dia a dia|cotidiano|encontro)\b', occasion_blob)):
        signals.append('ocasiões')
    return signals


def _is_unisex(c) -> bool:
    """Detect an explicitly unisex product so spoken articles stay neutral."""
    blob = ' '.join(_phrase(c.get(key)).casefold() for key in
                    ('product', 'outfit', 'audience', 'details'))
    return bool(re.search(r'\bunissex\b|\bunisex\b', blob, re.I))


def _with_article(value):
    """Make a short attribute usable after verbs such as 'veja' or 'mostre'.

    Atributo em forma negativa ("sem transparencia") nao aceita artigo: "Repara
    na sem transparencia" nao e portugues. Ele volta a funcionar quando e
    atribuido ao elemento a que pertence - "o tecido sem transparencia" -, sem
    inventar nenhuma propriedade nova.
    """
    value = _phrase(value)
    if re.match(r'^sem\s+', value, re.I):
        return f'o tecido {value}'
    if not value or re.match(r'^(o|a|os|as)\b', value, re.I):
        return value
    articles = {
        'bolso': 'o', 'bolso lateral': 'o', 'bolso interno': 'o',
        'cós': 'o', 'cós largo': 'o', 'caimento': 'o', 'tecido leve': 'o',
        'tecido macio': 'o', 'tecido encorpado': 'o', 'recorte': 'o',
        'acabamento': 'o', 'decote': 'o', 'detalhe': 'o', 'estampa': 'a',
        'alça': 'a', 'manga': 'a', 'barra': 'a', 'costura': 'a',
        'compressão': 'a', 'cintura alta': 'a', 'cintura média': 'a',
        'cintura baixa': 'a', 'secagem rápida': 'a', 'sem transparência': 'a',
        'forro': 'o', 'zíper': 'o', 'botão': 'o', 'cordão': 'o',
        'elástico': 'o', 'capuz': 'o', 'gola': 'a', 'punho': 'o',
        'botões': 'os', 'argolas': 'as', 'franzido': 'o', 'poliamida': 'a', 'courino': 'o', 'algodão': 'o',
        'lã': 'a', 'elastano': 'o', 'poliéster': 'o',
        'bojo': 'o', 'renda': 'a', 'cetim': 'o', 'viscose': 'a', 'canelado': 'o',
        'amarração': 'a', 'fenda': 'a', 'crochê': 'o', 'tule': 'o',
        'decote nas costas': 'o', 'alça regulável': 'a',
    }
    if value.casefold() in articles:
        return f"{articles[value.casefold()]} {value}"
    if ' e ' in value or ',' in value:
        # "bolso lateral e cintura alta" precisa de artigo em cada item, senao a
        # fala sai como "Olha bolso lateral e cintura alta".
        parts = [p.strip() for p in re.split(r'\s+e\s+|,\s*', value) if p.strip()]
        marked = []
        for part in parts:
            if re.match(r'^sem\s+', part, re.I):
                marked.append(f'o tecido {part}')
                continue
            article = articles.get(part.casefold())
            marked.append(f'{article} {part}' if article else part)
        if len(marked) == 1:
            return marked[0]
        return ', '.join(marked[:-1]) + ' e ' + marked[-1]
    return f'o detalhe de {value}'


def _with_em(value):
    """Put a visible attribute after ``em`` with the correct contraction."""
    value = _with_article(value)
    if not value:
        return value
    return re.sub(r'^(o|a|os|as)\b', lambda m: {'o': 'no', 'a': 'na', 'os': 'nos', 'as': 'nas'}[m.group(1).casefold()], value, flags=re.I)


def _benefit_clause(c):
    """Create a grammatical, bounded benefit clause without adding claims."""
    raw = _pt_br(c.get('benefit')).rstrip('.').strip()
    if _is_niche_default(c.get('benefit')):
        # "Caimento e ajuste visiveis nos movimentos da rotina" e direcao de
        # cena; lido em voz alta soava catalogo.
        return ''
    if not raw or _is_meta_field(raw):
        # Preserve concrete claims when a default also contains one noisy
        # platform promise (for example "caimento firme ... e visual que
        # motiva postar no FYP"). Remove only the noisy clause.
        raw = re.sub(
            r'\s+e\s+(?:o\s+)?(?:visual|look)(?:\s+\w+){0,3}\s+que\s+(?:motiva postar|chama atenção|chama atencao).*$',
            '', raw, flags=re.I,
        ).strip(' ,;')
        clauses = [part.strip(' ,;') for part in raw.split(',') if part.strip(' ,;')]
        clauses = [part for part in clauses if not _is_meta_field(part)]
        raw = ', '.join(clauses)
    if not raw:
        return ''
    # A negative product statement is useful as a constraint, not as a benefit
    # to repeat in a sales line (e.g. "não possui bolso").
    if (re.match(r'^(não|nao)\s+(possui|tem|oferece)', raw, re.I)
            or (re.match(r'^sem\s+', raw, re.I) and not re.match(r'^sem transparência\b', raw, re.I))):
        return ''
    # Keep the spoken middle inside the 15-second budget even when a niche
    # default contains a long marketing paragraph.
    words = raw.split()
    if len(words) > 16:
        # Prefer complete comma-separated claims over cutting a sentence in the
        # middle of a verb ("motiva postar…").
        clauses = [part.strip(' ,;:') for part in raw.split(',') if part.strip(' ,;:')]
        compact = []
        for clause in clauses:
            candidate = ', '.join(compact + [clause])
            if len(candidate.split()) > 16:
                break
            compact.append(clause)
        raw = ', '.join(compact) if compact else ' '.join(words[:16]).rstrip(' ,;:')
        # Nunca terminar em preposicao/artigo ("um visual marcante para").
        raw = re.sub(r'(\s+(?:para|pra|de|da|do|com|em|no|na|e|o|a|os|as|um|uma|que))+$', '', raw, flags=re.I)
    raw = re.sub(r'^produto de qualidade\b', 'qualidade', raw, flags=re.I)
    raw = re.sub(r'\s+e\s+versát(?:il|eis)\b', ' e é versátil', raw, flags=re.I)
    raw = raw[0].lower() + raw[1:] if raw else raw
    # Benefits commonly arrive as a noun phrase ("caimento firme") or as a
    # sentence ("veste muito bem..."). Handle both without guessing facts.
    verb_start = re.match(
        r'^(é|são|tem|têm|possui|oferece|veste|valoriza|ajuda|permite|seca|fica|deixa|traz|renova|combina|economiza|melhora|entrega|não\b)',
        raw, re.I)
    if re.match(r'^versát(?:il|eis)\b', raw, re.I) or re.match(r'^versat(?:il|eis)\b', raw, re.I):
        return f'A peça é {raw}'
    if verb_start:
        return f'A peça {raw}'
    if _own_subject(raw):
        return raw[0].upper() + raw[1:]
    return f'A peça tem {raw}'


_OWN_SUBJECT_VERBS = re.compile(
    r'\b(valoriza|valorizam|deixa|deixam|fica|ficam|é|são|tem|têm|ajuda|ajudam|dá|dão|realça|realçam|'
    r'marca|marcam|cai|caem|veste|vestem|combina|combinam|traz|trazem|mostra|mostram|acompanha|acompanham|'
    r'cria|criam|garante|garantem|destaca|destacam|alonga|alongam|afina|afinam|levanta|levantam|'
    r'chama|chamam|transforma|transformam|define|definem)\b',
    re.I)


def _own_subject(text):
    """'os drapeados laterais valorizam a silhueta': frase com sujeito proprio."""
    return bool(re.match(r'^(o|a|os|as|seu|sua|seus|suas)\s+\w+', text, re.I)) and bool(_OWN_SUBJECT_VERBS.search(text))


def _sentence(value):
    value = _phrase(value)
    if not value:
        return ''
    return value if value.endswith(('.', '!', '?')) else value + '.'


_SCENE_COMPOSITION_RE = re.compile(
    r'\b(?:camera\w*|enquadramento\w*|planos?|corpo\s+inteiro|'
    r'cenario\w*|fundos?|ambiente\w*|locacao|academia|praia|rua|'
    r'sala|quarto|estudio|cozinha|janela\w*|piscina|luz|luzes|'
    r'ilumin\w*|sombras?|reflexos?|nitid\w*|desfo\w*|bokeh|'
    r'perspectiva|pose\w*|expressao|olhar|rosto|cabelo|pele|'
    r'maos?|bracos?|pernas?|dedos?|sorria|sorriso|'
    r'contraste|saturacao|exposicao|filtros?|resolucao)\b|'
    r'\b\d+\s*:\s*\d+\b|\b(?:720|1080|2160)p\b'
)


def _image_details(details: str, *, preserve_base=False) -> str:
    """Keep static notes, with an extra continuity guard for localized edits.

    Match words rather than substrings ("alfaiataria" is not a spoken line).
    Static camera notes remain valid for extraction, but cannot override the
    existing camera/scene when editing an established photograph.
    """
    text = '\n'.join(_pt_br(line) for line in str(details or '').splitlines())
    if not text:
        return ''
    # Timing beats and action directions belong to the video prompt. Keep the
    # image prompt about the visible subject, product and set only.
    video = re.compile(
        r'\b(?:video\w*|ugc|fala\w*|dizer|diga|frases?|roteiro\w*|'
        r'agach\w*|caminh\w*|alongar|alongue|alongando|girar|gire|giro|girando|sentar|sente|sentando|'
        r'levantar|levante|andando|movimento\w*|mover|mova|acenar|acene|'
        r'takes?|clipes?|frames?|duracao|ritmo|zoom|tracking|panoramica|'
        r'cta|hook|fyp|query|legenda\w*|caption(?:_seed)?|checklist|howto)\b|'
        r'\b(?:shot\s+list|jogo\s+de\s+cameras?|prova\s+no\s+corpo|'
        r'chamada\s+para\s+acao|produto\s+marcado|primeiro\s+quadro|'
        r'cortes?\s+(?:de\s+camera|invisiveis|entre|rapidos)|'
        r'alternar\s+planos|aproxim\w*\s+(?:a\s+)?camera|'
        r'no\s+(?:inicio|final)|depois\s+de\s+\d+)\b|'
        r'\b\d+(?:[.,]\d+)?\s*(?:s\b|segundos?\b)|'
        r'\b\d+(?:[.,]\d+)?\s*[–—-]\s*\d+(?:[.,]\d+)?\s*s?\s*:'
    )
    composition = _SCENE_COMPOSITION_RE
    chunks = [part.strip(' .;') for part in re.split(r'(?<=[.!?])\s+|\s*;\s*|\n+|\|', text)]
    kept = []
    for part in chunks:
        normalized = ''.join(ch for ch in unicodedata.normalize('NFKD', part.casefold())
                             if not unicodedata.combining(ch))
        if not part or normalized.startswith('detalhes do briefing') or video.search(normalized):
            continue
        if preserve_base and composition.search(normalized):
            continue
        kept.append(part)
    return '. '.join(kept).strip()


def _image_angle(value: str) -> str:
    """Convert a video-oriented sales angle into a static visual angle."""
    text = _pt_br(value)
    if not text:
        return ''
    video_markers = (
        'movimento', 'agachar', 'caminhar', 'alongar', 'girar', 'vídeo', 'video',
        'ugc', 'fala', 'hook', 'cta', 'frame', 'take', 'prova no corpo',
    )
    if any(marker in text.casefold() for marker in video_markers):
        return 'mostrar a peça no corpo, o caimento e os detalhes visíveis'
    return text


def _video_details(details: str) -> str:
    """Keep useful operator notes, excluding playbook metadata, shot lists and
    scene/composition boilerplate (the video prompt's CENARIO FIXO already
    locks the environment to the approved/reference photo; a leftover niche
    sentence here would just contradict that anchor)."""
    text = _pt_br(details)
    if not text:
        return ''
    chunks = [part.strip(' .;') for part in re.split(r'(?<=[.!?])\s+|\s*;\s*|\n+|\|', text) if part.strip(' .;')]
    meta = ('howto', 'checklist:', 'shot list:', 'caption_seed:', 'hook falado',
            'legenda sugerida:', 'query quente', '1 cor = 1 mp4')
    timing = re.compile(r'^\s*\d+(?:[.–-]\d+)?s?\s*:', re.I)
    kept = []
    for part in chunks:
        normalized = ''.join(ch for ch in unicodedata.normalize('NFKD', part.casefold())
                             if not unicodedata.combining(ch))
        if any(h in part.casefold() for h in meta) or timing.search(part):
            continue
        if _SCENE_COMPOSITION_RE.search(normalized):
            continue
        kept.append(part)
    return '. '.join(kept).strip()


def _spoken_line(value, fallback='') -> str:
    """Extract a sentence the presenter can say, dropping silent directions."""
    text = _pt_br(value)
    if not text:
        return _phrase(fallback)
    chunks = [part.strip(' .;,:') for part in re.split(r'(?<=[.!?])\s+|\s*;\s*|\n+|\|', text) if part.strip(' .;,:')]
    silent_start = re.compile(
        r'^(mostre|mostrar|mostra|demonstre|demonstrar|aproxime|aproximar|gire|girar|ajuste|ajustar|'
        r'faça|faca|use a direção|use a direcao|câmera|camera|plano|shot list|checklist|instruções|instrucoes)\b',
        re.I,
    )
    meta = ('hook falado:', 'fala (pt-br):', 'desenvolvimento:', 'cta:', 'caption_seed:', 'shot list:')
    kept = [part for part in chunks if not silent_start.search(part) and not any(m in part.casefold() for m in meta)]
    cleaned = ''
    for part in kept:
        if not cleaned:
            cleaned = part
        elif cleaned.endswith(('.', '!', '?')):
            cleaned = f'{cleaned} {part}'
        else:
            cleaned = f'{cleaned}. {part}'
    cleaned = _clean_punct(cleaned)
    if not cleaned:
        return _phrase(fallback)
    return cleaned


# Acoes que terminam com os bracos no alto. Se uma delas cair no fim da
# coreografia, ela acontece exatamente na janela do CTA - foi o que produziu o
# aceno involuntario no primeiro video de teste.
_PROOF_GESTURES = {
    'sem transparência': 'gira de costas para a câmera com a luz de frente, para a cobertura do tecido aparecer',
    'tecido leve': 'movimenta a peça com a mão e deixa o tecido responder sozinho ao movimento',
    'tecido macio': 'passa a mão na superfície devagar, bem perto da lente',
    'tecido encorpado': 'segura a barra da peça e solta, deixando o tecido cair sozinho',
    'cós largo': 'puxa o cós para a frente e solta',
    'cintura alta': 'passa a mão na cintura mostrando onde a peça termina',
    'bolso lateral': 'coloca a mão dentro do bolso e tira',
    'bolso interno': 'abre o bolso com a mão e mostra o interior',
    'bolso': 'coloca a mão dentro do bolso e tira',
    'costura': 'aproxima a peça da lente e passa o dedo na costura',
    'acabamento': 'aproxima a peça da lente e passa o dedo no acabamento',
    'recorte': 'gira de lado devagar até o recorte ficar visível',
    'argolas': 'toca a argola com a ponta do dedo, deixando o dourado brilhar',
    'franzido': 'passa o dedo pelo franzido, sem puxar o tecido',
    'estampa': 'abre a peça com as duas mãos, de frente para a lente',
    'alça': 'ajusta a alça com um dedo e solta',
    'decote': 'ajusta a peça no ombro, sem puxar',
    'barra': 'segura a barra da peça e solta',
    'zíper': 'abre e fecha o zíper uma vez',
    'botão': 'toca o botão com a ponta do dedo',
    'botões': 'passa o dedo pelos botões, de cima para baixo',
    'forro': 'afasta a peça levemente do corpo para o forro aparecer',
    'elástico': 'puxa a peça com firmeza e solta, o tecido volta exatamente no lugar',
    'compressão': 'passa a mão na peça já no corpo, sem esticar',
    'secagem rápida': 'passa a mão no tecido, na altura da cintura',
    'gola': 'ajusta a gola com um dedo',
    'punho': 'aproxima o punho da lente',
    'cordão': 'puxa o cordão e solta',
    'capuz': 'ajusta o capuz com uma das mãos, sem erguer os dois braços',
    'bojo': 'ajusta a alça com um dedo, deixando o bojo à vista',
    'renda': 'passa o dedo devagar pela renda',
    'cetim': 'passa a mão no tecido e deixa ele cair, mostrando o brilho do cetim',
    'canelado': 'passa a mão no tecido canelado, de cima para baixo',
    'amarração': 'ajusta o laço da amarração e solta',
    'fenda': 'dá um passo à frente, deixando a fenda aparecer',
    'crochê': 'abre levemente a peça com as mãos, mostrando o crochê',
    'tule': 'levanta um pouco o tule com a ponta dos dedos e solta',
    'alça regulável': 'ajusta a alça regulável com um dedo e solta',
    'decote nas costas': 'vira o ombro de leve, deixando o decote das costas aparecer',
}


def _proof_gestures(features, limit=3, turns=()):
    """Converte cada fato confirmado no gesto que o demonstra na camera."""
    turns = set(turns or ())
    plan = []
    for label in features or []:
        gesture = _PROOF_GESTURES.get(label)
        # Prova visual também respeita a orientação escolhida. Antes, o fato
        # "sem transparência" reintroduzia uma virada de costas mesmo quando a
        # lista de movimentos não pedia giro algum.
        if label == 'sem transparência' and 'costas' not in turns:
            if 'lado' in turns:
                gesture = ('vira somente até o perfil e faz um agachamento curto sob a mesma luz, '
                           'sem mostrar as costas')
            elif 'leve_lado' in turns:
                gesture = ('inclina o corpo até 30 graus e faz um agachamento curto sob a mesma luz, '
                           'mantendo a frente da peça visível')
            else:
                gesture = ('faz um agachamento curto de frente sob a mesma luz, sem girar o corpo')
        elif label == 'recorte' and not turns:
            gesture = 'aponta o recorte com um dedo mantendo o corpo de frente'
        if gesture and gesture not in plan:
            plan.append(f'{label} → {gesture}')
        if len(plan) >= limit:
            break
    return plan


# No POV a camera e o olho de quem veste: nao da para "girar de costas para a
# camera" nem "manter o corpo de frente" -- o corpo nao aparece de fora. Estes
# gestos provam o mesmo fato visto de cima, pelas maos.
_POV_PROOF_GESTURES = {
    'sem transparência': ('afasta o tecido do corpo com a ponta dos dedos, sob a mesma luz, e mostra que '
                          'a pele não aparece através dele'),
    'recorte': 'a câmera desce até o recorte e o dedo contorna a linha dele',
    'estampa': 'alisa a estampa com a mão livre, bem perto da lente',
    'capuz': 'puxa a borda do capuz para a frente com a mão livre até ele entrar no quadro',
}


def _pov_proof_gestures(features, limit=3):
    plan = []
    for label in features or []:
        gesture = _POV_PROOF_GESTURES.get(label) or _PROOF_GESTURES.get(label)
        if gesture and not _POV_SKIP_RE.search(gesture):
            item = f'{label} → {gesture}'
            if item not in plan:
                plan.append(item)
        if len(plan) >= limit:
            break
    return plan


# Acoes do nicho que so existem vistas de fora (rosto, sorriso, pose, caminhar
# ate a camera, girar). No POV elas contradizem "nunca mostrar o rosto".
_POV_SKIP_RE = re.compile(
    r'\b(?:olh\w*|sorri\w*|sorriso|pose|posar|caminh\w*\s+(?:lent\w*\s+)?at[ée]\s+(?:a\s+)?c[âa]mera|'
    r'entrar\s+no\s+frame|gir\w*|vir\w*|rota(?:ç|c)[ãa]o|de\s+costas|perfil|express\w*|rosto|'
    r'cta|gesto\s+caracter\w*)\b',
    re.I,
)
# Sem fala nao ha CTA falado: "CTA final animado" do nicho so confundia o gerador.
_CTA_ACTION_RE = re.compile(r'\bcta\b', re.I)


def _filter_actions(value: str, pattern) -> str:
    raw = _phrase(value)
    if not raw:
        return ''
    chunks = [part.strip(' .,:;') for part in re.split(r'\s*;\s*|\n+', raw) if part.strip(' .,:;')]
    return '; '.join(part for part in chunks if not pattern.search(part))


_ARM_ACTIONS = ('alongar', 'along', 'braco', 'braço', 'levantar', 'erguer',
                'acenar', 'aceno', 'maos para cima', 'mãos para cima', 'comemor')


def _is_arm_action(chunk: str) -> bool:
    return any(word in chunk.casefold() for word in _ARM_ACTIONS)


def _movement_plan(value: str, limit: int = 6) -> str:
    """Keep the action list executable without flooding a video model.

    Duas regras que parecem detalhe e nao sao:
    1. A ULTIMA acao e o encerramento do video. Cortar a lista pelo comeco
       apagava justamente ela (o padrao de academia perdia "pose confiante
       final" e terminava em "alongar os bracos").
    2. Acao de braco nunca fica nas duas ultimas posicoes: ali ela coincide com
       o CTA e o video fecha com a modelo acenando.
    """
    raw = _phrase(value)
    if not raw:
        return ''
    chunks = [part.strip(' .,:;') for part in re.split(r'\s*;\s*|\n+', raw) if part.strip(' .,:;')]
    if len(chunks) <= 1:
        return raw[:600]
    if len(chunks) > limit:
        # Mantem o inicio e preserva o encerramento escolhido pelo operador.
        chunks = chunks[:limit - 1] + [chunks[-1]]
    if len(chunks) > 2:
        tail = chunks[-2:]
        arms = [c for c in tail if _is_arm_action(c)]
        if arms:
            head = [c for c in chunks if c not in arms]
            insert_at = min(2, max(1, len(head) - 1))
            for action in arms:
                head.insert(insert_at, action)
                insert_at += 1
            chunks = head
    return '; '.join(chunks)[:900]


_TURN_ACTION_RE = re.compile(
    r'\b(?:girar?|giro|virar?|virada|rota(?:ç|c)[ãa]o|volta\s+completa|de\s+costas|perfil|por\s+cima\s+do\s+ombro)\b',
    re.I,
)


def _body_turns(c: dict) -> list[str]:
    """Return only body rotations explicitly authorized in the brief."""
    raw = str(c.get('body_turns') or '')
    selected = {part.strip() for part in raw.split(',') if part.strip()}
    return [key for key in ('leve_lado', 'lado', 'costas') if key in selected]


def _movement_without_unapproved_turns(value: str) -> str:
    """Remove inherited niche rotations; the dedicated selector owns them."""
    raw = _phrase(value)
    if not raw:
        return ''
    action_separator = (
        r'\s*;\s*|\n+|,\s*|\s+e\s+'
        r'(?=(?:ajust|caminh|gir|vir|pux|mostr|entr|sorr|agach|sent|levant|along|acen|toc|segur|apont|pose|inclin))'
    )
    chunks = [part.strip(' .,:;') for part in re.split(action_separator, raw, flags=re.I)
              if part.strip(' .,:;')]
    return '; '.join(part for part in chunks if not _TURN_ACTION_RE.search(part))


def _turn_direction(c: dict) -> tuple[str, str]:
    """Prompt rule and action for the largest rotation the operator allowed."""
    selected = _body_turns(c)
    if 'costas' in selected:
        return (
            'ORIENTAÇÃO CORPORAL: uma única virada contínua de costas, por no máximo 1 segundo, e retorno '
            'imediato de frente; sem pose nem olhar por cima do ombro.',
            'virar brevemente de costas e voltar de frente sem pausar',
        )
    if 'lado' in selected:
        return (
            'ORIENTAÇÃO CORPORAL: uma única virada de 90 graus até o perfil e retorno de frente; '
            'não ultrapassar o perfil nem mostrar as costas.',
            'virar uma vez de lado até o perfil e voltar de frente',
        )
    if 'leve_lado' in selected:
        return (
            'ORIENTAÇÃO CORPORAL: uma única inclinação de 20 a 30 graus, mantendo rosto e frente da peça '
            'visíveis; sem perfil ou costas.',
            'inclinar levemente o corpo de lado e voltar de frente',
        )
    return (
        'ORIENTAÇÃO CORPORAL: sempre de frente, com ombros e frente da peça voltados à lente; '
        'não mostrar perfil, costas ou olhar por cima do ombro.',
        '',
    )


def shows_unconfirmed_feature(action: str, c: dict) -> bool:
    """'mostrar bolso' numa peca sem bolso confirmado: o padrao do nicho casual
    pedia isso para qualquer produto e o gerador podia inventar o bolso.
    So conta acao de mostrar/destacar; "ajustar o cos" e gesto, nao promessa."""
    low = _phrase(action).casefold()
    if not re.search(r'\b(mostr|exib|destac|revel)', low):
        return False
    confirmed = set(_product_features(c, limit=50))
    return any(label not in confirmed and any(re.search(rf'\b{re.escape(n)}\b', low) for n in needles)
               for label, needles in _PRODUCT_FEATURES)


def _configured_movement_plan(value: str, c: dict, limit: int = 6) -> str:
    """Combine safe product actions with the one explicitly allowed rotation."""
    value = '; '.join(part for part in re.split(r'\s*;\s*|\n+', _phrase(value))
                      if part.strip() and not shows_unconfirmed_feature(part, c))
    cleaned = _movement_without_unapproved_turns(value)
    _direction, turn_action = _turn_direction(c)
    combined = '; '.join(part for part in (cleaned, turn_action) if part)
    return _movement_plan(combined, limit=limit)


def _slug_tag(value, limit=28):
    # "maio" sem acento e o mes: o maio de praia mantem o circunflexo.
    if re.fullmatch(r'mai[ôo]s?', _phrase(value), re.I):
        return ('Maiôs' if _phrase(value).lower().endswith('s') else 'Maiô')[:limit]
    tag = ''.join(ch for ch in unicodedata.normalize('NFKD', _phrase(value)) if not unicodedata.combining(ch))
    tag = re.sub(r'[^a-zA-Z0-9]', '', tag)
    return tag[:limit]


def _camel_tag(text, limit=18):
    """'calça de courino' -> 'CalcaDeCourino'. Palavras inteiras: cortar no
    limite gerava #Calcadecourinofemi e #Fantasiadecoelhinh."""
    tag = ''
    for word in _phrase(text).split():
        part = _slug_tag(word, 40)
        part = part[:1].upper() + part[1:]
        if tag and len(tag + part) > limit:
            break
        tag += part
    return tag[:limit]


def _niche_hashtags(c, color):
    """Build product-aware hashtags (TikTok Shop / UGC style, pt-BR)."""
    blob = ' '.join(_phrase(c.get(k)).casefold() for k in ('product', 'outfit', 'audience', 'angle', 'benefit', 'details'))
    color = _phrase(color)
    specific = []
    rules = [
        (('legging',), ['Legging', 'LeggingFitness', 'LookAcademia']),
        (('calça', 'calca'), ['CalcaFeminina', 'LookDoDia']),
        (('top', 'cropped', 'crop'), ['TopFitness', 'Cropped', 'LookTreino']),
        (('short',), ['ShortFitness', 'LookAcademia']),
        (('academia', 'treino', 'fitness', 'gym', 'esporte'), ['LookAcademia', 'FitnessBrasil', 'TreinoFeminino']),
        (('yoga', 'pilates'), ['YogaLook', 'Pilates']),
        (('jeans', 'denim'), ['Jeans', 'LookCasual']),
        (('vestido',), ['Vestido', 'LookDoDia']),
        (('saia',), ['Saia', 'LookFeminino']),
        (('bolso',), ['Pratico', 'Funcional']),
        (('cintura alta', 'cós', 'cos'), ['CinturaAlta']),
        (('mulher', 'feminina', 'feminino'), ['ModaFeminina']),
        (('verão', 'verao', 'praia'), ['LookVerão', 'ModaPraia']),
        (('inverno', 'frio'), ['LookInverno']),
        (('promo', 'oferta', 'barat'), ['AchadinhoBarato', 'Promocao']),
    ]
    for needles, extra in rules:
        if 'calça' in needles and 'legging' in blob:
            continue
        if any(n in blob for n in needles):
            for t in extra:
                if t not in specific:
                    specific.append(t)
    # Use the readable product nickname, otherwise long catalogue names become
    # broken-looking tags such as #Leggingcinturaaltacombol.
    product_tag = _camel_tag(_product_nick(c.get('product')), 18)
    color_tag = _slug_tag(color, 16)
    if product_tag and product_tag not in specific:
        specific.insert(0, product_tag)
    # A cauda generica nao pode assumir publico feminino: um produto unissex,
    # masculino, infantil, de casa ou pet recebia #ModaFeminina e era entregue
    # para o publico errado.
    tail = ['TikTokShop', 'Achadinhos']
    if (_product_family(c) == 'moda' and not _is_unisex(c)
            and re.search(r'\b(mulher|feminin|elas|meninas|garotas)\w*', blob)):
        tail.append('ModaFeminina')
    tail.append('ForYou')
    ordered = specific + ([color_tag] if color_tag else []) + tail
    # Keep caption readable: 5 tags max, prioritizing searchable product terms.
    uniq = []
    seen = set()
    for t in ordered:
        key = t.casefold() if t else ''
        if t and key not in seen:
            uniq.append(t)
            seen.add(key)
    return uniq[:5]



def _is_meta_field(value: str) -> bool:
    """True when a brief field looks like UI placeholder / production note, not sell copy."""
    v = _phrase(value).casefold()
    if not v:
        return True
    needles = (
        "definir 1", "1-3 cores", "1–3 cores", "empurrar search", "replicar query",
        "shot list", "checklist:", "howto", "caption_seed", "problema →", "problema ->",
        "playbook", "query '", "fyp", "for you", "parece caro", "chama atenção",
        "chama atencao", "motiva postar",
    )
    if any(n in v for n in needles):
        return True
    if ("→" in (value or "")) or ("->" in (value or "")):
        if any(k in v for k in ("peca", "peça", "search", "query", "vibe", "prova")):
            return True
    # Category crumbs that are not a real benefit sentence
    thin = {"maio feminino", "moda praia", "moda academia", "moda casual", "feminino", "masculino"}
    if v in thin or (len(v.split()) <= 2 and not any(ch in v for ch in ".!?")):
        # two-word labels without punctuation are usually tags, not benefits
        if v in thin or v.startswith("maio ") or v.startswith("moda "):
            return True
    return False


def _caption_seed_from_details(details: str) -> str:
    text = str(details or "")

    def _ok(seed: str) -> bool:
        seed = _phrase(seed)
        if not seed or len(seed) < 24:
            return False
        if _is_meta_field(seed):
            return False
        # Reject tag-only / crumb seeds ("maio feminino #x")
        plain = re.sub(r"#\S+", "", seed).strip()
        if len(plain.split()) < 5:
            return False
        return True

    m = re.search(r"caption_seed:\s*(.+?)(?:\s+Checklist:|\s+Hook falado|\s+Shot list:|$)", text, re.I | re.S)
    if m and _ok(m.group(1)):
        return _phrase(m.group(1))
    m = re.search(r"Legenda sugerida:\s*(.+?)(?:\s+Checklist:|$)", text, re.I | re.S)
    if m and _ok(m.group(1)):
        return _phrase(m.group(1))
    return ""



def _product_nick(product: str) -> str:
    """Readable product name for captions (drop slash aliases / catalogue noise)."""
    p = _phrase(product)
    if not p:
        return "essa peça"
    # "Maiô autoestima / mamãe" -> prefer left side, then soft nick
    if "/" in p:
        p = p.split("/", 1)[0].strip() or p
    cat = speech_bank.category(speech_bank.detect({'product': p}))
    if cat:
        # "Calça de courino feminina" -> "calça de courino"; "Legging cintura
        # alta" -> "legging" (o rotulo "calça legging" nao esta no produto).
        label = cat['label'].casefold()
        return label if label in p.casefold() else cat['piece']
    low = p.casefold()
    if "maiô" in low or "maio" in low:
        return "maiô"
    if "legging" in low:
        return "legging"
    if "vestido" in low:
        return "vestido"
    if "conjunto" in low:
        return "conjunto"
    if "biquíni" in low or "biquini" in low:
        return "biquíni"
    if len(p) > 36:
        return p[:34].rstrip(" ,-") + "…"
    return p


def _caption_cta(i: int = 0) -> str:
    options = [
        "O link tá no carrinho aqui embaixo.",
        "Corre no carrinho laranja e confere de perto.",
        "Toca no carrinho laranja e vê os detalhes.",
        "Tá no carrinho, é só tocar.",
        "Confere tamanhos e cores no carrinho.",
        "Tá no carrinho laranja aqui embaixo.",
    ]
    return options[int(i) % len(options)]


def build_caption(c, color=None, cta=None, variation_index=0):
    """Build a factual, product-aware TikTok caption using local rules only.

    The old rotating copy used unverifiable first-person claims, price claims and
    scenery that did not come from the brief. Captions now have a clear promise,
    one observable detail and a Shop action; every assertion comes from a field
    the operator supplied.
    """
    full_product = _pt_br(c.get('product')) or 'essa peça'
    nick = _product_nick(full_product)
    # A legenda e lida pelo cliente final: concordancia errada ("uma vestido")
    # derruba a credibilidade da peca inteira.
    nick_gender = _PIECE_GENDER.get(nick.casefold()) or _piece_forms(c)['art'].replace('a', 'f').replace('o', 'm')
    fem = nick_gender == 'f'
    uma, esta, essa, art = ('uma', 'esta', 'essa', 'a') if fem else ('um', 'este', 'esse', 'o')
    mesma = 'mesma' if fem else 'mesmo'
    color_raw = _phrase(color or c.get('color'))
    parts = color_variants(color_raw)
    color = parts[0] if parts else color_raw
    color_word = f' na versão {color}' if color else ''
    benefit = _benefit_clause(c)
    # _benefit_clause already limits this to complete words. Avoid slicing by
    # characters, which used to produce broken endings such as "posta..".
    focus, features = _focus_parts(c)
    detail = _with_article(features[0] if features else focus)
    i = int(variation_index or 0)
    all_colors = color_variants(c.get('color'))
    shop_cta = _pt_br(cta) if cta else ''
    if not shop_cta:
        shop_cta = ('Escolhe a tua cor no carrinho aqui embaixo.'
                    if len(all_colors) > 1 else _caption_cta(i))

    seed = _caption_seed_from_details(c.get('details') or '')
    if seed and i % 7 == 0:
        body = seed
        if not re.search(r'\b(toque|confira|veja|escolha|acesse|compre|salve|marcado|shop)\b', body, re.I):
            body += f' {shop_cta}'
    else:
        openings = [
            f'Quer escolher {uma} {nick} pelo caimento? Olha {esta} {nick}{color_word}.',
            f'Antes de decidir {"pela" if fem else "pelo"} {nick}, veja este detalhe{color_word}: {detail}.',
            f'{uma.capitalize()} {mesma} {nick} muda muito no corpo conforme a cor. Esta é a versão {color}.',
            f'Você usaria {esta} {nick}{color_word}? Repara {_with_em(detail)}.',
            f'Para quem procura {nick}{color_word}, o ponto principal é observar {detail}.',
            f'Olha {art} {nick}{color_word} em movimento e confere {detail}.',
        ] if color else [
            f'Quer escolher {uma} {nick} pelo caimento? Repara {_with_em(detail)}.',
            f'Antes de decidir {"pela" if fem else "pelo"} {nick}, veja este detalhe: {detail}.',
            f'Você usaria {esta} {nick}? Olha como {"ela" if fem else "ele"} veste no corpo.',
            f'Para quem procura {nick}, o ponto principal é observar {detail}.',
            f'Olha {art} {nick} em movimento e confere {detail}.',
            f'{essa.capitalize()} {nick} merece um olhar de perto: {detail}.',
        ]
        persuasion_captions = {
            'economia': f'Quer economizar sem abrir mão do visual? Olha {esta} {nick}{color_word}.',
            'qualidade': f'Quer ver qualidade nos detalhes? Repara {"nesta" if fem else "neste"} {nick}{color_word}: {detail}.',
        'versatilidade': f'{uma.capitalize()} {nick}, vários momentos: olha {esta} {nick}{color_word} em movimento.',
            'autoestima': f'Quando o caimento ajuda na confiança, o detalhe aparece: olha {esta} {nick}{color_word}.',
            'ocasiões': f'Do trabalho ao encontro com as amigas, {esta} {nick}{color_word} acompanha o movimento.',
        }
        for signal in reversed(_persuasion_signals(c)):
            if signal in persuasion_captions:
                openings.insert(0, persuasion_captions[signal])
        opening = openings[i % len(openings)]
        body = opening
        if benefit and i % 2 == 0:
            body += f' {benefit}.'
        body += f' {shop_cta}'

    body = re.sub(r'\s+', ' ', body).replace(' .', '.').strip()
    body = re.sub(r'\bna cor\s+\.', '.', body)
    tags = ' '.join(f'#{t}' for t in _niche_hashtags(c, color or nick))
    return f'{body} {tags}'.strip()


def color_variants(value):
    """Split a color field into stable, unique variants in user-entered order."""
    variants=[]
    for item in re.split(r'[,;\n|]+', str(value or '')):
        item=_phrase(item)
        if item and item.casefold() not in {old.casefold() for old in variants}:
            variants.append(item)
    return variants


# ---------------------------------------------------------------------------
# Motor de copy: familia de produto, motor de persuasao e orcamento por trecho.
# Regra de honestidade: necessidade so existe com objecao informada; escassez so
# existe com oferta real informada. Sem esses campos, o gerador usa desejo, que
# nao afirma nada alem do que esta no briefing.
# ---------------------------------------------------------------------------

_FAMILY_WORDS = (
    ('beleza', ('batom', 'base', 'sérum', 'serum', 'creme', 'hidratante', 'protetor solar',
                'máscara de cílios', 'maquiagem', 'skincare', 'shampoo', 'perfume', 'esmalte', 'gloss')),
    ('casa', ('organizador', 'cesto', 'pote', 'suporte de parede', 'luminária', 'luminaria',
              'tapete', 'cortina', 'panela', 'utensílio', 'utensilio', 'almofada', 'edredom')),
    ('gadget', ('fone', 'carregador', 'cabo usb', 'smartwatch', 'caixa de som', 'teclado', 'mouse', 'power bank')),
    ('pet', ('coleira', 'comedouro', 'arranhador', 'caminha para', 'brinquedo para cachorro', 'brinquedo para gato')),
    ('infantil', ('infantil', 'bebê', 'bebe', 'criança', 'crianca', 'kids')),
)

_FAMILY_VOCAB = {
    'moda': dict(noun='peça', gender='f', on='no corpo', quality='caimento'),
    'beleza': dict(noun='produto', gender='m', on='na pele', quality='textura'),
    'casa': dict(noun='item', gender='m', on='em uso', quality='acabamento'),
    'gadget': dict(noun='aparelho', gender='m', on='em uso', quality='acabamento'),
    'pet': dict(noun='item', gender='m', on='no pet', quality='acabamento'),
    'infantil': dict(noun='peça', gender='f', on='na criança', quality='caimento'),
}

_PIECE_GENDER = {
    'legging': 'f', 'calça': 'f', 'saia': 'f', 'blusa': 'f', 'camiseta': 'f', 'camisa': 'f',
    'peça': 'f', 'bermuda': 'f', 'regata': 'f', 'jaqueta': 'f',
    'vestido': 'm', 'conjunto': 'm', 'short': 'm', 'top': 'm', 'maiô': 'm', 'biquíni': 'm',
    'produto': 'm', 'item': 'm', 'aparelho': 'm', 'cropped': 'm', 'macacão': 'm',
}

_PIECE_WORDS = ('legging', 'vestido', 'conjunto', 'camiseta', 'camisa', 'blusa', 'calça', 'saia',
                'short', 'top', 'maiô', 'biquíni', 'macacão', 'cropped', 'regata', 'jaqueta', 'bermuda')

# Objecao informada -> dor (usada no hook) e verificacao (usada na prova do meio).
# A dor e sempre da CATEGORIA, nunca uma afirmacao sobre este produto.
_OBJECTION_PRESETS = (
    ('transparencia', ('transparente', 'transparência', 'transparencia', 'aparece a calcinha'),
     'ficar transparente', 'Olha contra a luz e confira a cobertura'),
    ('desce', ('desce', 'escorrega', 'não fica no lugar', 'nao fica no lugar', 'cai o tempo todo'),
     'a peça descer no movimento', 'No movimento dá para ver se o cós segura'),
    ('tamanho', ('tamanho', 'serve em mim', 'manequim', 'medida', 'numeração', 'numeracao'),
     'não saber se serve', 'Aqui aparece a peça no corpo inteiro'),
    ('qualidade', ('qualidade', 'acabamento', 'parece barat', 'frágil', 'fragil'),
     'parecer barata de perto', 'Repara no acabamento e na costura'),
    ('durabilidade', ('durabilidade', 'estraga', 'desbota', 'lavagem', 'não dura', 'nao dura'),
     'não durar muito', 'Olha a costura e o acabamento de perto'),
    ('conforto', ('conforto', 'incomoda', 'aperta', 'coça', 'coca'),
     'incomodar no uso', 'Em movimento dá para ver como ela acompanha'),
    ('preco', ('preço', 'preco', 'caro', 'custo', 'valor'),
     'pagar caro por uma peça só', 'Olha quantas combinações saem da mesma peça'),
    ('marca', ('marca o corpo', 'marca tudo', 'sobra', 'aperta demais'),
     'marcar o corpo', 'De frente e de lado dá para conferir'),
)

_NICHE_OCCASION = {
    'academia': 'no treino e depois na rua',
    'praia': 'na praia e na piscina',
    'casual': 'no dia a dia',
    'dia-a-dia': 'em casa e para sair rápido',
    'intima': 'no dia a dia',
    'fantasia': 'na festa',
}


def _product_family(c):
    blob = ' '.join(_phrase(c.get(k)).casefold() for k in ('product', 'outfit', 'details', 'audience'))
    for family, needles in _FAMILY_WORDS:
        if any(n in blob for n in needles):
            return family
    return 'moda'


def _piece_noun(c):
    # Substantivo real do produto, usado tanto na fala quanto no prompt de imagem.
    cat = speech_bank.category(speech_bank.detect(c))
    if cat:
        return cat['piece']
    product = _pt_br(c.get('product')).casefold()
    outfit = _pt_br(c.get('outfit')).casefold()
    # O campo "produto" manda: o "outfit" costuma descrever o look inteiro
    # ("vestido com legging por baixo") e nao a peca que esta sendo vendida.
    for source in (product, outfit):
        for name in _PIECE_WORDS:
            if re.search(r'\b' + re.escape(name) + r'\b', source):
                return name
    # So cai no generico "peça" quando nenhum substantivo especifico foi
    # encontrado -- unissex nao deve apagar "camisa", so evita generizar.
    if _is_unisex(c):
        return 'peça'
    return _FAMILY_VOCAB[_product_family(c)]['noun']


def _piece_forms(c):
    piece = _piece_noun(c)
    cat = speech_bank.category(speech_bank.detect(c))
    gender = (cat['gender'] if cat else '') or _PIECE_GENDER.get(piece) or _FAMILY_VOCAB[_product_family(c)]['gender']
    if gender == 'f':
        return dict(piece=piece, art='a', de='da', dem='essa', prep='nessa', pron='ela')
    return dict(piece=piece, art='o', de='do', dem='esse', prep='nesse', pron='ele')


def _objection_parts(c):
    # Retorna (dor, verificacao) a partir do campo de objecao do briefing.
    raw = _phrase(c.get('objection'))
    if not raw or _is_meta_field(raw):
        return '', ''
    hit = speech_bank.objection(speech_bank.category(speech_bank.detect(c)), raw)
    if hit:
        return hit['pain'], hit['proof']
    low = raw.casefold()
    for _key, needles, pain, check in _OBJECTION_PRESETS:
        if any(n in low for n in needles):
            return pain, check
    # Texto livre: usa como dor, sem inventar verificacao.
    words = raw.split()
    pain = ' '.join(words[:7]).rstrip('.,;:').casefold()
    return pain, ''


def _offer_text(c):
    raw = _phrase(c.get('offer'))
    if not raw or _is_meta_field(raw):
        return ''
    return ' '.join(raw.split()[:10]).rstrip('.,;:')


_MOTOR_ALIASES = {
    'necessidade': 'necessidade',
    'escassez': 'escassez', 'escassez_contexto': 'escassez', 'escassez-contexto': 'escassez',
    'escassez de contexto': 'escassez',
    'desejo': 'desejo', 'desejo_posse': 'desejo', 'desejo-posse': 'desejo', 'desejo de posse': 'desejo',
}


def _chosen_motor(c):
    """Motor escolhido explicitamente pelo operador no formulario, se houver."""
    return _MOTOR_ALIASES.get(_phrase(c.get('motor')).casefold(), '')


def _dominant_motor(c):
    escolhido = _chosen_motor(c)
    if escolhido:
        return escolhido
    if _objection_parts(c)[0]:
        family = _product_family(c)
        if family != 'moda':
            return 'necessidade'
        if (c.get('niche') or '') in ('academia', 'dia-a-dia'):
            return 'necessidade'
        return 'necessidade'
    return 'desejo'


_VIDEO_MODE_ALIASES = {
    'pov': 'pov', 'pov_produto': 'pov', 'pov-produto': 'pov', 'pov produto': 'pov',
    'produto': 'pov',
    'movimento': 'movimento', 'movimentos': 'movimento', 'so_movimento': 'movimento',
    'so-movimento': 'movimento', 'só movimento': 'movimento', 'so movimento': 'movimento',
    'fit': 'movimento', 'fit_check': 'movimento', 'fit check': 'movimento',
    'espelho': 'espelho', 'celular': 'espelho', 'selfie': 'espelho', 'selfie_espelho': 'espelho',
    'celular no espelho': 'espelho',
    # Formatos que rodam sobre outra base (services/formats.py).
    'unboxing': 'pov', 'asmr': 'movimento',
}


def _video_mode(c):
    """Formato de video escolhido explicitamente pelo operador, se houver."""
    return _VIDEO_MODE_ALIASES.get(_phrase(c.get('video_mode')).casefold(), '')


def _count_words(text):
    return len([w for w in _phrase(text).split() if w])


def _line_key(text):
    """Impressao digital de uma fala, usada para reconhecer repeticao."""
    txt = unicodedata.normalize('NFKD', _phrase(text).casefold())
    txt = ''.join(ch for ch in txt if not unicodedata.combining(ch))
    return re.sub(r'[^a-z0-9]+', ' ', txt).strip()


# Duas falas com o mesmo molde ("Olha o bolso com a legging..." e "Olha o forro
# com o vestido...") sao quase identicas caractere a caractere, porque o molde
# ocupa a maior parte da frase. Acima deste limite tratamos como repeticao --
# e o que impede a conta de publicar a mesma abertura cinco vezes por semana.
_REPEAT_RATIO = 0.72


def _too_similar(candidate, used_keys, fuzzy=True):
    """Ja usamos esta fala, ou uma com o mesmo molde?

    ``fuzzy`` fica desligado no CTA de proposito: chamada para acao repete
    vocabulario por natureza ("no carrinho aqui embaixo" aparece em quase
    todas), entao a semelhanca de texto ali nao significa molde repetido --
    significa so que as duas sao um CTA. No hook e no desenvolvimento, que e
    onde a repeticao cansa o espectador, a semelhanca vale.
    """
    key = _line_key(candidate)
    if not key:
        return False
    if key in used_keys:
        return True
    if not fuzzy:
        return False
    return any(difflib.SequenceMatcher(None, old, key).ratio() > _REPEAT_RATIO
               for old in used_keys if old)


def _used_keys(c, field):
    """Falas ja publicadas, entregues pelo app em 'recent_lines'.

    O app le as ultimas falas gravadas no banco e manda junto com o briefing.
    Sem esse campo o gerador funciona como antes -- a memoria e um reforco,
    nunca um requisito.
    """
    data = c.get('recent_lines')
    if not isinstance(data, dict):
        return set()
    return {k for k in (_line_key(t) for t in (data.get(field) or [])) if k}


def _pick_in_budget(candidates, index, low, high, used_keys=(), fuzzy=True):
    """Escolhe uma fala dentro do orcamento falado, evitando molde repetido.

    ``candidates`` aceita texto solto ou pares (molde, texto). O molde nao muda
    a escolha por si so: ele existe para deduplicar e para deixar claro, na
    leitura do codigo, que cada familia e uma estrutura de frase diferente --
    nao a mesma frase com outra palavra no meio.
    """
    pairs, seen = [], set()
    for item in candidates:
        tid, text = item if isinstance(item, tuple) else ('', item)
        text = _phrase(text)
        if not text or text in seen:
            continue
        seen.add(text)
        pairs.append((tid, text))
    if not pairs:
        return ''
    fits = [p for p in pairs if low <= _count_words(p[1]) <= high]
    if not fits:
        # Nenhum candidato coube: usa os mais proximos da faixa, nao os mais
        # curtos - um hook curto demais vira rotulo e nao prende ninguem.
        def distance(item):
            n = _count_words(item[1])
            return low - n if n < low else (n - high if n > high else 0)
        fits = sorted(pairs, key=distance)[:3]
    fresh = [p for p in fits if not _too_similar(p[1], used_keys, fuzzy)] if used_keys else fits
    pool = fresh or fits
    return pool[int(index or 0) % len(pool)][1]


def _hook_pool(c, detail, forms):
    """Ganchos de 9 a 14 palavras, em primeira pessoa e sem inventar fato.

    Primeira pessoa aqui e sempre sobre o que da para ver ou fazer na hora da
    gravacao -- olhei, vesti, reparei, testei, me surpreendi. Nunca sobre
    historia que ninguem pode verificar ("lavei vinte vezes", "comprei mes
    passado"): isso seria inventar fato, exatamente o que o projeto inteiro
    existe para evitar. Opiniao ("foi o que mais gostei") e livre, porque e
    opiniao declarada e nao promessa de desempenho.

    Cada familia abaixo e uma ESTRUTURA diferente de abertura, nao uma troca de
    palavra dentro do mesmo molde -- e a estrutura que o espectador reconhece
    quando ve o quarto video da semana.
    """
    dem, prep, piece, art = forms['dem'], forms['prep'], forms['piece'], forms['art']
    de = forms['de']
    det = _phrase(detail)
    det_em = _with_em(det)
    # "foi os botoes" -> "foram os botoes"
    plural = bool(re.match(r'^(os|as)\s', det) or re.search(r'\se\s', det))
    foi, eh = ('foram', 'são') if plural else ('foi', 'é')
    pain, _check = _objection_parts(c)
    offer = _offer_text(c)

    # Descoberta: eu vi algo que nao esperava ver.
    descoberta = [
        ('desc-achei', f'Achei {dem} {piece} e não esperava {det}.'),
        ('desc-naosabia', f'Não sabia que {dem} {piece} tinha {det} até ver de perto.'),
        ('desc-peguei', f'Peguei {dem} {piece} pra olhar de perto e encontrei {det}.'),
        ('desc-vesti', f'Vesti {dem} {piece} e só então reparei {det_em}.'),
    ]
    # Contraste: minha expectativa era uma, o que vi foi outra.
    contraste = [
        ('cont-igual', f'Achei que {dem} {piece} fosse igual {"às outras" if art == "a" else "aos outros"}. Aí vi {det}.'),
        ('cont-batido', f'Quase passei batido {prep} {piece}, mas {det} me segurou.'),
        ('cont-esperava', f'Esperava pouco {de} {piece} e me surpreendi com {det}.'),
    ]
    # Criterio: o detalhe que decidiu por mim.
    decide = [
        ('dec-escolhi', f'O que me fez escolher {dem} {piece} {foi} {det}.'),
        ('dec-mudou', f'Reparei {det_em} e mudou o que eu achava {de} {piece}.'),
        ('dec-criterio', f'Pra mim o que decide {prep} {piece} {eh} {det}.'),
    ]
    # Uso: eu com a peca, agora.
    uso = [
        ('uso-gostei', f'Vesti {dem} {piece} e {det} foi o que mais gostei.'),
    ]
    # Necessidade: a dor que o briefing declarou, na minha voz.
    necessidade = []
    if pain:
        necessidade = [
            ('nec-medo', f'Meu medo {de} {piece} sempre foi {pain}. Olha {dem} aqui.'),
            ('nec-segurava', f'O que me segurava {prep} {piece} era {pain}, até eu testar {dem}.'),
            ('nec-desisti', f'Eu já desisti {de} {piece} quando o problema era {pain}.'),
            ('nec-testei', f'Testei {dem} {piece} justamente porque meu medo era {pain}.'),
        ]
    # Escassez com oferta real declarada no briefing.
    # Cada fala de urgencia usa um fato da oferta com o numero exato
    # (services/persuasion); o texto cru da oferta so entra se nada casou.
    escassez = []
    if offer:
        escassez = persuasion.scarcity_hooks(persuasion.offer_facts(c.get('offer')), forms) or [
            ('esc-oferta', f'{_sentence(offer[0].upper() + offer[1:])} E eu reparei {det_em}.'),
            ('esc-antes', f'{_sentence(offer[0].upper() + offer[1:])} Olha {det} antes.'),
        ]
    # Prova social so quando declarada no briefing.
    prova = persuasion.social_hooks(persuasion.social_facts(c.get('social_proof')), forms)

    # Banco de falas: moldes da categoria, separados pelo que sustentam.
    cat = speech_bank.category(speech_bank.detect(c))
    cat_dor, cat_fato, cat_livre = [], [], []
    for tid, text in (_category_lines(c, 'hooks', forms, det) if not offer else []):
        item = cat['hooks'][int(tid.rsplit('-', 1)[1])]
        item = item if isinstance(item, dict) else {}
        (cat_dor if item.get('pain') else cat_fato if item.get('req') else cat_livre).append((tid, text))
    if det == _FALLBACK_DETAIL:
        # Sem atributo nem angulo, os moldes genericos so repetiriam o texto
        # de reserva; a voz da categoria vem antes deles.
        descoberta, contraste, decide, uso = cat_livre + descoberta, [], [], uso + decide + contraste
        cat_livre = []

    motor = _dominant_motor(c)
    order = {
        'necessidade': [cat_dor, necessidade, cat_fato, contraste, decide, descoberta, cat_livre, uso],
        'desejo': [cat_fato, decide, cat_livre, uso, descoberta, contraste, cat_dor, necessidade],
        'escassez': [escassez, descoberta, cat_fato, contraste, decide, cat_livre, uso],
    }[motor]
    order.insert(2 if motor == 'necessidade' else 1, prova)
    if offer and motor != 'escassez':
        order.insert(1, escassez)
    pool = []
    for group in order:
        for item in group:
            if item and item not in pool:
                pool.append(item)
    return pool


# Prova falada de cada objecao: primeira pessoa, presente, sobre o que o
# video mostra. As versoes de _OBJECTION_PRESETS sao direcao de camera
# ("Olha contra a luz e confira a cobertura") e, lidas em voz alta, viravam
# ordem de locutor.
_SPOKEN_CHECK = {
    'transparencia': 'Por isso tô aqui contra a luz, pra você conferir.',
    'desce': 'Por isso tô me mexendo aqui, pra você ver se o cós segura.',
    'tamanho': 'Por isso quis mostrar ela inteira no corpo.',
    'qualidade': 'Por isso quis te mostrar o acabamento e a costura.',
    'durabilidade': 'Por isso quis te mostrar a costura e o acabamento.',
    'conforto': 'Por isso tô em movimento, pra você ver como ela acompanha.',
    'preco': 'E olha quantas combinações saem da mesma peça.',
    'marca': 'Por isso mostro de frente e de lado, pra você conferir.',
}


def _objection_key(c):
    low = _phrase(c.get('objection')).casefold()
    for key, needles, _pain, _check in _OBJECTION_PRESETS:
        if low and any(n in low for n in needles):
            return key
    return ''


# Ocasioes como se fala (as de _NICHE_OCCASION seguem no briefing da IA).
_SPOKEN_OCCASION = {
    'academia': 'no treino e depois na rua',
    'praia': 'na praia e na piscina',
    'casual': 'no dia a dia',
    'dia-a-dia': 'em casa ou pra sair correndo',
    'intima': 'no dia a dia',
    'fantasia': 'na festa',
}


# Variacoes das frases de prova do banco de falas. A frase original saia
# igual em toda campanha da mesma objecao. As variantes de "contra a luz"
# mantem a expressao, porque ela aciona a cena de contraluz no prompt.
_PROOF_VARIANTS = (
    (r'quis te mostrar (ela|ele) no corpo, de frente e de lado',
     ('quis te mostrar {p} no corpo, de frente e de lado', 'tô usando {p} aqui pra você ver de frente e de lado',
      'vesti {p} pra você ver de frente e de lado')),
    (r'quis te mostrar (ela|ele) no corpo, de frente',
     ('quis te mostrar {p} no corpo, de frente', 'tô com {p} no corpo, pra você ver de frente',
      'vesti {p} pra você ver como fica de frente')),
    (r'tô aqui contra a luz, pra você conferir',
     ('tô aqui contra a luz, pra você conferir', 'vim pra frente da janela, contra a luz, pra você conferir',
      'olha aqui contra a luz, pode conferir')),
    (r'tô aqui na luz, pra você ver o tecido',
     ('tô aqui na luz, pra você ver o tecido', 'chega mais perto, olha o tecido aqui na luz',
      'trouxe pra perto da luz pra você ver o tecido')),
    (r'quis te mostrar (ela|ele) aqui na luz, pra você ver o acabamento',
     ('quis te mostrar {p} aqui na luz, pra você ver o acabamento', 'olha o acabamento aqui na luz, de pertinho',
      'trouxe {p} pra luz pra você ver o acabamento')),
)


def _vary_proof(text, index=0):
    """Troca a frase de prova por uma variante equivalente (mesmo sentido)."""
    if not text:
        return text
    for pattern, variants in _PROOF_VARIANTS:
        m = re.search(pattern, text, re.I)
        if m:
            pron = m.group(1) if m.groups() else ''
            escolha = variants[int(index or 0) % len(variants)].replace('{p}', pron or 'ela')
            novo = text[:m.start()] + escolha + text[m.end():]
            return novo[:1].upper() + novo[1:] if text[:1].isupper() else novo
    return text


def _development_line(c, detail, features, forms, index, used_keys=(), hook=''):
    """O meio da fala, como gente fala: uma reacao em primeira pessoa que
    continua o gancho, e nao tres ordens soltas.

    A versao anterior colava "Repara no X com calma." + a instrucao de camera
    da objecao + "Da para usar ...". O primeiro video gerado com ela soou como
    locucao: o atributo do gancho repetido, direcao de camera lida em voz alta
    e "com calma" so para alcancar um minimo de palavras.

    Ordem do que ela fala: a objecao do briefing (com a prova que o video
    mostra), senao o beneficio escolhido, senao outro atributo. Depois, o
    detalhe do angulo de venda que o gancho ainda nao disse, ou a ocasiao de
    uso. Nada fora dos fatos do briefing; opiniao declarada e livre.
    """
    feats = list(features or [])
    hook_fact = (feats[0] if feats else '').casefold()
    dem, piece, pron = forms['dem'], forms['piece'], forms['pron']
    pain, _check = _objection_parts(c)
    cat_hit = speech_bank.objection(speech_bank.category(speech_bank.detect(c)), _phrase(c.get('objection')))
    spoken_check = cat_hit['proof'] if cat_hit else _SPOKEN_CHECK.get(_objection_key(c), '')
    benefit = _benefit_clause(c)
    benefit_text = re.sub(r'^A peça\s+', '', benefit, flags=re.I).strip().rstrip('.')
    if benefit_text and hook_fact and hook_fact.split()[-1] in benefit_text.casefold():
        benefit_text = ''
    second = _with_article(feats[1]) if len(feats) > 1 else ''

    reacoes = []
    motor = _dominant_motor(c)
    # A dor so e retomada ("por isso", agitacao) quando o gancho falou dela;
    # depois de um gancho de oferta ou de detalhe, a prova entra direta.
    dor_no_gancho = bool(pain) and pain.casefold() in (hook or '').casefold()
    if pain:
        prova_falada = _vary_proof(spoken_check, index) or 'Por isso fiz questão de te mostrar aqui.'
        if not dor_no_gancho and hook:
            prova_falada = re.sub(r'^Por isso\s+', '', prova_falada)
            prova_falada = prova_falada[:1].upper() + prova_falada[1:]
        if motor == 'necessidade' and (dor_no_gancho or not hook):
            # Dor -> agitacao -> prova: uma frase curta do incomodo antes da prova.
            agita = persuasion.AGITATION[int(index or 0) % len(persuasion.AGITATION)]
            reacoes.append(('re-agita', f'{agita} {prova_falada}'))
        # O gancho ja disse a dor; o meio continua dali, sem repeti-la.
        reacoes.append(('re-porisso', prova_falada))
    social = persuasion.social_facts(c.get('social_proof'))
    reacoes += [r for r in persuasion.social_reactions(social, forms)
                if not any(v and v in (hook or '') for v in (social.get('sold'), social.get('rating')))]
    if benefit_text:
        verbo = '' if re.match(r'^(é|são|tem|têm|possui|oferece|veste|valoriza|ajuda|permite|seca|fica|deixa|traz|combina|entrega)\b',
                               benefit_text, re.I) else 'tem '
        if _own_subject(benefit_text):
            reacoes.append(('re-melhor', f'E o melhor é que {benefit_text[0].lower() + benefit_text[1:]}.'))
        else:
            reacoes.append(('re-melhor', f'E o melhor é que {pron} {verbo}{benefit_text}.'))
    # Depois do que o briefing declarou, a voz da categoria.
    reacoes += _category_lines(c, 'reactions', forms)
    if second and not re.match(r'^(o tecido )?sem\b', second, re.I):
        reacoes.append(('re-tambem', f'E ainda tem {second}, que era bem o que eu procurava.'))
    cat = speech_bank.category(speech_bank.detect(c))
    reacoes += [
        ('re-veste', f'E olha como {pron} veste, fiquei com vontade de usar todo dia.'),
        ('re-gostei', 'Sinceramente, gostei muito mais do que eu imaginava.'),
    ]

    # Detalhe do angulo de venda que o gancho ainda nao citou ("o cós").
    partes = [p.strip() for p in re.split(r'\s+e\s+|,\s*', _phrase(detail)) if p.strip()]
    hook_words = set(re.findall(r'\w{3,}', hook_fact))
    novas = [p for p in partes if not (hook_words & set(re.findall(r'\w{3,}', p.casefold())))
             and not re.match(r'^(o tecido )?sem\b|^o caimento|^os detalhes', p, re.I)]
    fechos = []
    if novas:
        alvo = _with_em(novas[0])
        fechos.append(('fe-repara', f'E repara {alvo}, ficou um charme.'))
    if cat:
        for n, occ in enumerate(cat['occasions'][:2]):
            fechos += _category_lines(c, 'closers', forms, occ=occ)
    occasion = _SPOKEN_OCCASION.get((c.get('niche') or '').strip(), '')
    if occasion and not cat:
        fechos += [
            ('fe-usar', f'Dá pra usar {occasion} numa boa.'),
            ('fe-serve', f'Serve {occasion}, sem pensar muito.'),
        ]
    if motor == 'desejo':
        # Desejo: quem assiste se imagina usando a peca na ocasiao.
        # O detalhe do angulo de venda (o que o operador pediu para mostrar)
        # continua na frente.
        imagina = persuasion.future_pacing((cat['occasions'][0] if cat else occasion), forms)
        frente = 1 if fechos and fechos[0][0] == 'fe-repara' else 0
        fechos = fechos[:frente] + imagina + fechos[frente:]
    oferta = persuasion.offer_facts(c.get('offer')) if _offer_text(c) else {}
    if oferta:
        # Escassez real lembrada no meio: prazo, estoque, frete ou cupom.
        fechos = persuasion.scarcity_closers(oferta, forms) + fechos
    if not fechos:
        fechos.append(('fe-cara', 'Achei a cara do meu dia a dia.'))

    hook_low = (hook or '').casefold()
    ja_ditos = [f for f in _product_features(c, limit=50) if f.casefold() in hook_low]
    if ja_ditos:
        def repete(texto):
            return any(f.casefold() in texto.casefold() for f in ja_ditos)
        reacoes = [r for r in reacoes if not repete(r[1])] or reacoes
        fechos = [f for f in fechos if not repete(f[1])] or fechos
    candidates = []
    for ri, (rid, reacao) in enumerate(reacoes):
        for fi, (fid, fecho) in enumerate(fechos):
            # "E o melhor e que ela tem tecido macio. E repara no tecido macio"
            if fid == 'fe-repara' and novas and novas[0].split()[-1].casefold() in reacao.casefold():
                continue
            texto = f'{reacao} {fecho}'
            if _count_words(texto) > 36:
                texto = reacao
            candidates.append(((ri + fi, ri), (f'{rid}+{fid}', texto)))
    # Com objecao, a prova abre todas as variantes; sem ela, cada variante
    # troca reacao e fechamento juntos, e nao so o fim da frase.
    if not pain:
        candidates.sort(key=lambda item: item[0])
    candidates = [item[1] for item in candidates]
    # Sem piso alto: frase natural curta vale mais que enchimento.
    return _pick_in_budget(candidates, index, 10, 36, used_keys)


def _cta_pool(c, forms):
    # Orcamento do CTA: 6 a 10 palavras.
    #
    # Vocabulario real do TikTok Shop: o botao e o carrinho laranja e o link
    # fica embaixo do video. "Produto marcado" e linguagem de painel, nao de
    # quem fala com a camera - por isso o CTA soava de aviso institucional.
    piece, art = forms['piece'], forms['art']
    possessive = 'a tua' if art == 'a' else 'o teu'
    colors = color_variants(c.get('color'))
    pain, _check = _objection_parts(c)
    offer = _offer_text(c)
    direto = [
        ('cta-corre', 'Corre pro carrinho laranja e confere os detalhes agora.'),
        ('cta-abre', 'Abre o carrinho laranja e escolhe a sua versão.'),
        ('cta-aproveita', 'Aproveita e garante a sua versão no carrinho laranja.'),
        ('cta-agora', 'Não deixa pra depois: confere no carrinho laranja agora.'),
        ('cta-toca', 'Toca no carrinho laranja e vê todos os detalhes.'),
        ('cta-tala', 'Tá no carrinho laranja, corre lá e vê de pertinho.'),
        ('cta-deixei', 'Deixei no carrinho laranja pra você, corre lá.'),
    ]
    if len(colors) > 1:
        direto = [
            ('cta-cores', 'Escolhe a tua cor agora no carrinho laranja.'),
            ('cta-vercores', 'Corre pro carrinho laranja e compara as cores agora.'),
        ] + direto
    condicional = [
        ('cta-resolve', 'Resolve essa dúvida agora: abre o carrinho laranja.'),
        ('cta-confere', 'Confere essa solução agora no carrinho laranja.'),
    ] if pain else []
    offer_short = ' '.join(offer.split()[:5]).rstrip('.,;:')
    escassez = (persuasion.scarcity_ctas(persuasion.offer_facts(c.get('offer')), {**forms, 'teu': possessive})
                if offer else [])
    if offer and not escassez:
        escassez = [('cta-oferta', f'Aproveita {offer_short} no carrinho laranja.')]
    posse = [
        ('cta-garante', f'Corre pro carrinho laranja e garante {possessive} agora.'),
        ('cta-escolhe', f'Abre o carrinho laranja e escolhe {possessive}.'),
    ]
    categoria = _category_lines(c, 'ctas', forms) if not offer else []
    descoberta = [
        ('cta-achado', 'Salva esse achado agora no carrinho laranja.'),
        ('cta-detalhes', 'Toca no carrinho laranja e confere os detalhes.'),
    ]
    motor = _dominant_motor(c)
    if motor == 'escassez':
        order = [descoberta, direto, posse, condicional]
    elif motor == 'necessidade':
        order = [condicional, direto, posse, descoberta]
    else:
        order = [posse, direto, descoberta, condicional]
    if offer:
        order.insert(0, escassez)
    pool = list(categoria)
    for group in order:
        for item in group:
            if item and item not in pool:
                pool.append(item)
    return pool


def _bank_slots(c, forms):
    pain, _check = _objection_parts(c)
    return {**forms, 'teu': 'a tua' if forms['art'] == 'a' else 'o teu', 'pain': pain}


def _category_lines(c, kind, forms, det='', occ=''):
    """Moldes da categoria (banco de falas) que os fatos do briefing sustentam."""
    cat = speech_bank.category(speech_bank.detect(c))
    if not cat:
        return []
    feats = set(_product_features(c, limit=50))
    slots = _bank_slots(c, forms)
    lines = []
    for i, item in enumerate(cat.get(kind, [])):
        item = item if isinstance(item, dict) else {'t': item}
        req = item.get('req')
        if req and req not in feats:
            continue
        if item.get('pain') and not slots['pain']:
            continue
        values = {**slots, 'det': _with_article(req) if req else det, 'occ': occ,
                  'feat': req or re.sub(r'^(o|a|os|as)\s+', '', det or '')}
        if '{det}' in item['t'] and not values['det']:
            continue
        text = speech_bank.fill(item['t'], values)
        if '{' not in text:
            lines.append((f'cat-{kind}-{i}', text))
            if item.get('for_pain') and item['for_pain'] == slots['pain']:
                # Molde feito para a objecao do briefing vai para a frente.
                lines.insert(0, lines.pop())
    return lines


def _sem_artigo(value):
    """Tira o artigo inicial: 'o bolso lateral' -> 'bolso lateral'."""
    return re.sub(r'^(o|a|os|as)\s+', '', _phrase(value), flags=re.I)


def _infinitive(phrase):
    """'ficar transparente', 'não segurar em cima' -> True; 'amassa fácil' -> False."""
    palavras = re.sub(r'^(não|nao)\s+', '', _phrase(phrase), flags=re.I).split()
    return any(re.search(r'(ar|er|ir)$', w, re.I) for w in palavras[:3])


def _cover_text(c, forms, detail, index=0):
    """Texto da capa: 3 a 6 palavras, lido no feed ANTES de alguem dar play.

    Existe porque o prompt de video proibe (com razao) texto dentro do quadro:
    gerador de IA escreve letra torta e inventa marca. A proibicao vale para o
    video gerado -- nao para a postagem. Este campo e para colar no CapCut ou
    no editor do TikTok, onde a letra sai correta.

    Vale a mesma regra de honestidade do resto: so entra fato que o briefing
    sustenta.
    """
    det = _phrase(detail)
    nu = _sem_artigo(det)
    piece = forms['piece']
    opcoes = [
        f'{nu.capitalize()}?',
        f'{piece.capitalize()} com {nu}',
        f'Repara {_with_em(det)}',
        f'Repara {_with_em(det)}' if re.match(r'^(os|as)\s', det) else f'O detalhe é {det}',
    ]
    opcoes = [o for o in opcoes if 2 <= _count_words(o) <= 6]
    if not opcoes:
        return f'{piece.capitalize()}'
    return opcoes[int(index or 0) % len(opcoes)]


def _screen_text(c, forms, detail, index=0):
    """Texto de tela dos primeiros 3 segundos, para quem assiste sem som.

    Boa parte do TikTok roda mudo. Sem texto na tela, esse publico nao recebe o
    gancho -- ve uma modelo se mexendo em silencio. Aqui a ideia do gancho vira
    escrita, curta o bastante para caber num frame.
    """
    det = _phrase(detail)
    nu = _sem_artigo(det)
    piece = forms['piece']
    pain, _check = _objection_parts(c)
    opcoes = []
    if pain:
        # A objecao escrita e o que mais segura o dedo de quem tem essa duvida.
        # Dor do banco vem no infinitivo ("ficar transparente"); texto livre
        # vem do jeito que a pessoa escreveu ("amassa fácil"). "Desistiu por
        # amassa fácil" nao e portugues: cada forma ganha a frase que cabe.
        pain = re.sub(r'^(tenho\s+)?medo\s+de\s+', '', pain, flags=re.I)
        if _infinitive(pain):
            opcoes.append(f'Medo de {pain}?')
            opcoes.append(f'Você também tem medo de {pain}?')
        else:
            opcoes.append(f'{pain[:1].upper() + pain[1:]}?')
            opcoes.append(f'A dúvida: {pain}?')
    opcoes.extend([
        f'{piece.capitalize()}: {nu}',
        f'Não sabia que tinha {det}',
        f'Repara {_with_em(det)}',
        f'{nu.capitalize()} de perto',
    ])
    opcoes = [o for o in opcoes if 3 <= _count_words(o) <= 8]
    if not opcoes:
        return f'{piece.capitalize()}: {nu}'
    return opcoes[int(index or 0) % len(opcoes)]


# Frase de imaginacao de uso por moda: so ocasiao, nenhum atributo. Tres por
# moda, escolhidas pelo indice da variacao, para nao repetir entre roteiros.
_FUTURE_LINES = {
    'praia': ('Já tô me imaginando {com} na praia no próximo fim de semana, sem pensar duas vezes.',
              'Imagina chegar na piscina {com} e todo mundo perguntando de onde é.',
              'Já separei {com} pra viagem de verão, sério, nem vou esperar.'),
    'academia': ('Já quero ir treinar {com} amanhã cedo, sério, nem vou esperar.',
                 'Imagina chegar na academia {com} e já se sentir pronta pro treino.',
                 'É daquelas que dá vontade de usar no treino e depois sair direto.'),
    'casual': ('Já tô pensando em sair {com} no fim de semana, com uma blusinha básica.',
               'Imagina chegar no barzinho {com} e já resolver o look da noite.',
               'É daquelas peças que salvam quando eu não sei o que vestir pra sair.'),
    'dia-a-dia': ('É daquelas peças que eu usaria a semana inteira, do trabalho ao fim de semana.',
                  'Imagina abrir o guarda-roupa e já ter o look do dia resolvido.',
                  'Já tô pensando em usar {com} amanhã mesmo, com um tênis branco.'),
    'intima': ('Já me imagino {com} numa manhã preguiçosa de domingo, com um café do lado.',
               'Imagina acordar {com} e já se sentir arrumada dentro de casa.',
               'É aquele mimo que dá vontade de usar todo dia antes de dormir.'),
    'fantasia': ('Já tô me vendo chegando na festa {com}, e todo mundo perguntando de onde é.',
                 'Imagina entrar na festa {com} e já virar assunto da noite.',
                 'Já tô pensando nas fotos da festa {com}, vai ficar lindo.'),
}


def _future_line(c, forms, index=0):
    lines = _FUTURE_LINES.get(_niche_key(c)) or _FUTURE_LINES['casual']
    line = lines[int(index or 0) % len(lines)]
    return line.replace('{com}', 'com ela' if forms.get('art') == 'a' else 'com ele')


def _script_variation(c, color, index=0):
    # Constroi as tres falas a partir de evidencia explicita do briefing.
    # A cor NAO entra no hook: o espectador ja a ve na tela, e cada palavra do
    # hook vale ~0,36s. Ela permanece na legenda e no prompt de imagem.
    forms = _piece_forms(c)
    focus, features = _focus_parts(c)
    hook_detail = _with_article(features[0] if features else (focus or 'o caimento'))
    detail = _with_article(focus if focus else 'o caimento')
    i = int(index or 0)

    selected_hook = _pick_in_budget(_hook_pool(c, hook_detail, forms), i, 10, 13,
                                    _used_keys(c, 'hook'))
    selected_development = _development_line(c, detail, features, forms, i,
                                             _used_keys(c, 'development'), hook=selected_hook)
    selected_cta = _pick_in_budget(_cta_pool(c, forms), i, 6, 10,
                                   _used_keys(c, 'cta'), fuzzy=False)
    # Formato escolhido (responder comentario, teste...): o gancho anuncia o
    # formato; no 3 jeitos o desenvolvimento lista os looks.
    selected_hook = formats.script_hook(c, forms, _objection_parts(c)[0]) or selected_hook
    selected_development = (formats.script_development(c, forms, [_with_article(f) for f in features[:2]])
                            or selected_development)

    # Teto absoluto de 45 palavras faladas (~15s). Se estourar, encurta o
    # desenvolvimento pela ultima batida, nunca pela prova.
    def total():
        return _count_words(' '.join((selected_hook, selected_development, selected_cta)))
    # Teste real: com 33 a 46 palavras sobraram 2 a 3 s de silencio no fim
    # dos 15 s. Fala de quem vende ocupa o clipe inteiro: abaixo de 46
    # palavras entra uma frase de imaginacao de uso (sem afirmar nada novo).
    if _count_words(selected_development) < 26 and formats.video_format(c) != 'tres_jeitos':
        extra = _future_line(c, forms, i)
        if extra and extra.casefold() not in selected_development.casefold():
            selected_development = f'{selected_development.rstrip(". ")}. {extra}'
    # Segundo teste: com ~57 palavras ficou um pouco acelerado; teto de 57.
    if total() > 57:
        sentences = [p.strip() for p in re.split(r'(?<=[.!?])\s+', selected_development) if p.strip()]
        while len(sentences) > 1 and total() > 57:
            sentences.pop()
            selected_development = ' '.join(sentences)

    if selected_development and selected_development[0].islower():
        selected_development = selected_development[0].upper() + selected_development[1:]
    selected_development = re.sub(
        r'(?<=\.\s)([a-záàâãéêíóôõúç])',
        lambda m: m.group(1).upper(),
        selected_development,
    )
    selected_hook = _clean_punct(selected_hook)
    selected_development = _clean_punct(selected_development)
    selected_cta = _clean_punct(selected_cta)
    return selected_hook, selected_development, selected_cta


def script_budget(hook, development, cta):
    # Orcamento falado por trecho, usado pela interface e pelo prompt de video.
    return {
        'hook': dict(words=_count_words(hook), low=10, high=18),
        'development': dict(words=_count_words(development), low=20, high=40),
        'cta': dict(words=_count_words(cta), low=7, high=14),
        'total': dict(words=_count_words(' '.join((hook, development, cta))), low=38, high=70),
    }


_SPOKEN_LINE_RE = re.compile(r'Fala \(PT-BR\): "([^"]*)"')
_WORD_COUNT_RE = re.compile(r'(Total das falas fornecidas: )\d+( palavras)')


def _replace_spoken_lines(video_text, hook, development, cta):
    """Atualiza somente as tres falas entre aspas dentro de um prompt de video
    ja existente, preservando qualquer ajuste manual de camera, coreografia ou
    encerramento que o usuario tenha feito. Retorna None quando o texto nao
    tem exatamente as 3 marcacoes esperadas (ex.: prompt vazio ou reescrito de
    forma que a substituicao segura nao pode ser garantida) -- nesse caso o
    chamador deve regenerar o prompt inteiro como antes.
    """
    if not video_text:
        return None
    matches = list(_SPOKEN_LINE_RE.finditer(video_text))
    if len(matches) != 3:
        return None
    parts = []
    last = 0
    for match, new_line in zip(matches, (hook, development, cta)):
        parts.append(video_text[last:match.start(1)])
        parts.append(new_line)
        last = match.end(1)
    parts.append(video_text[last:])
    updated = ''.join(parts)
    total = len((hook + ' ' + development + ' ' + cta).split())
    return _WORD_COUNT_RE.sub(rf'\g<1>{total}\g<2>', updated)


def sync_video_spoken_lines(video_text, hook, development, cta):
    """Public entry point for updating only the spoken copy in a video prompt.

    API-written scripts must not discard camera, choreography or ending edits
    that the operator already reviewed.  ``None`` means the prompt does not
    contain the three safe markers and the caller should rebuild it.
    """
    return _replace_spoken_lines(video_text, hook, development, cta)


def refresh_script_fields(c, color, current_prompts, fields=None, bump=1):
    """Cycle script variation for selected fields (hook/caption/etc.)."""
    fields = fields or ['hook', 'development', 'cta', 'caption']
    allowed = {'hook', 'development', 'cta', 'caption'}
    fields = [f for f in fields if f in allowed]
    if not fields:
        raise ValueError('Nenhum campo de fala para atualizar.')
    index = int((current_prompts or {}).get('variation_index') or 0) + int(bump)
    fresh = generate({**c, 'color': color}, variant_index=index)
    merged = dict(current_prompts or {})
    for f in fields:
        merged[f] = fresh[f]
    if 'caption' in fields:
        merged['caption'] = build_caption({**c, 'color': color}, color=color, cta=None, variation_index=index)
    # Refreshing only the spoken lines must preserve any manual visual
    # direction (camera, coreography, ending) already saved in the video
    # prompt. Try a targeted substitution first; only rebuild the whole
    # video prompt from scratch when that is not safely possible.
    if set(fields) & {'hook', 'development', 'cta'}:
        patched = _replace_spoken_lines(
            (current_prompts or {}).get('video'),
            merged.get('hook', ''), merged.get('development', ''), merged.get('cta', ''),
        )
        if patched is not None:
            merged['video'] = patched
        else:
            merged['video'] = generate({**c, 'color': color}, script=merged, variant_index=index)['video']
    if 'image' not in merged and fresh.get('image'):
        merged['image'] = fresh['image']
    merged['variation_index'] = index
    return merged



# Niche-specific video direction for Flow/Grok (concrete beats, not vague adjectives).
_VIDEO_NICHE = {
    "praia": {
        "setting": "praia, deck de piscina ou varanda ensolarada; fundo com luz natural e leve movimento de vento",
        "camera": "câmera na mão em estilo UGC leve; plano médio na abertura; detalhe de perto no tecido ao vento; giro curto no corpo; final em plano médio frontal",
        "must_show": "movimento natural do tecido ao caminhar na areia/deck e detalhe visível da peça sob luz natural",
        "avoid": "estudio frio, pose estatica demais, morphing de rosto, logos inventados",
    },
    "academia": {
        "setting": "academia limpa ou outdoor fitness crivel; luz clara e energetica",
        "camera": "plano médio dinâmico; ângulo baixo curto no agachamento; detalhe de perto no cós e no tecido; acompanhamento ao caminhar até a câmera",
        "must_show": "agachar, alongar e caminhar para revelar o caimento; suor somente se aparecer naturalmente",
        "avoid": "maquina vazia sem acao, deformacao anatomica, rosto mudando entre cortes",
    },
    "casual": {
        "setting": "rua, cafe ou quarto com luz natural; visual street realista",
        "camera": "aproximação suave; detalhe de perto na barra, bolso ou textura; acompanhamento frontal em dois passos",
        "must_show": "como a peça cai no corpo em movimento urbano, textura e detalhe que estejam visíveis (barra, costura ou bolso)",
        "avoid": "fundo genérico borrado sem contexto, gestos roboticos, troca de identidade",
    },
    "dia-a-dia": {
        "setting": "casa real (quarto/cozinha/sala) com luz de janela suave",
        "camera": "plano médio caseiro; detalhe de perto na textura ao sentar e levantar; deslocamento curto pela casa; final frontal calmo",
        "must_show": "sentar, levantar e caminhar para revelar o caimento; textura e ajuste somente quando visíveis",
        "avoid": "cena de studio fashion, exagero de poses, mudanca de rosto/cabelo",
    },
    "intima": {
        "setting": "quarto premium ou canto de estudio com luz quente suave; clima elegante",
        "camera": "plano médio frontal; panorâmica lenta para o lado; detalhe de perto no tecido, renda ou ajuste; retorno ao rosto confiante",
        "must_show": "caimento elegante, textura e ajuste de alça/fecho somente se estiverem presentes na peça",
        "avoid": "nudez, zoom agressivo, poses explicitas, troca de identidade, filtros plasticos",
    },
    "fantasia": {
        "setting": "cenario tematico coerente com a fantasia (quarto preparado, luz colorida ou festa simples)",
        "camera": "revelação em plano médio; giro dramático; detalhe de perto em acessório (asa, cinto ou peruca); pose marcante final",
        "must_show": "transformacao visual clara, acessorios da fantasia, detalhe do traje, energia teatral controlada",
        "avoid": "cenario generico sem tema, morphing de rosto, logos de franquias proibidas",
    },
}


def _niche_key(c):
    niche = (c.get("niche") or "").strip()
    if niche in _VIDEO_NICHE:
        return niche
    # fallback from style/outfit keywords
    blob = f"{c.get('style','')} {c.get('outfit','')} {c.get('angle','')}".casefold()
    for key, words in (
        ("praia", ("praia", "beach", "biquini", "verao")),
        ("academia", ("academia", "fitness", "legging", "treino", "active")),
        ("intima", ("intima", "íntima", "lingerie", "sensual")),
        ("fantasia", ("fantasia", "cosplay", "halloween", "personagem")),
        ("dia-a-dia", ("rotina", "dia a dia", "lounge", "casa")),
        ("casual", ("casual", "street")),
    ):
        if any(w in blob for w in words):
            return key
    return "casual"


# Limite de caracteres do campo de prompt em cada gerador. O Grok corta em
# 4000 sem avisar: ate aqui todo prompt de video saia com 4600 a 6800
# caracteres, entao o FINAL (honestidade, audio, "fale so as falas") era
# descartado em silencio -- as travas que o projeto inteiro existe para manter.
_LIMITE_PROMPT = {'grok': 4000}
# Margem: nome de produto, cor e movimentos vem do briefing e variam de tamanho.
_MARGEM_PROMPT = 60


def _limite_video(c):
    limite = _LIMITE_PROMPT.get((c.get('generator') or '').strip().casefold())
    return (limite - _MARGEM_PROMPT) if limite else None


def _montar_video(blocos, limite=None):
    """Junta as partes do prompt e, havendo limite, corta pelas menos essenciais.

    Cada parte vem como (prioridade, texto): 0 e intocavel (identidade, cenario,
    falas, honestidade) e numeros maiores sao dispensaveis (contexto opcional de
    nicho, angulo de venda, contagem de palavras). Cortar um bloco inteiro e
    melhor que deixar o gerador truncar no meio de uma frase, que era o que
    vinha acontecendo.
    """
    partes = [(p, t) for p, t in blocos if t]
    texto = ''.join(t for _p, t in partes)
    if not limite or len(texto) <= limite:
        return texto
    # Corta um bloco de cada vez, começando pelo menos essencial e, dentro do
    # mesmo nível, pelo mais comprido: assim sobra o máximo de instrução que
    # cabe, em vez de perder um nível inteiro por causa de poucos caracteres.
    descartaveis = sorted(
        (i for i, (p, _t) in enumerate(partes) if p > 0),
        key=lambda i: (partes[i][0], len(partes[i][1])), reverse=True)
    fora = set()
    for indice in descartaveis:
        fora.add(indice)
        texto = ''.join(t for i, (_p, t) in enumerate(partes) if i not in fora)
        if len(texto) <= limite:
            return texto
    return texto


def _build_movement_video_prompt(c, *, resolution, color, product, benefit, movements, details, hook, development, cta, base_image=False):
    """Video so de movimento: a peca no corpo, sem nenhuma fala.

    E o formato "fit check": ninguem fala, a modelo mostra como a peca cai --
    puxa de leve, segue somente a orientacao corporal autorizada e ajusta como
    quem arruma. O som vira por conta da trend escolhida no TikTok e a mensagem
    fica na legenda do post, entao o quadro fica limpo: sem locucao, sem legenda
    automatica e sem texto na tela.

    hook/development/cta chegam aqui e NAO sao usados de proposito: continuam
    existindo na campanha (alimentam a legenda, o orcamento falado e a troca
    para os outros formatos), mas neste video ninguem fala.
    """
    niche = _niche_key(c)
    dirn = _VIDEO_NICHE.get(niche) or _VIDEO_NICHE["casual"]
    outfit = _pt_br(c.get("outfit")) or "visual do produto"
    style = _pt_br(c.get("style")) or "natural e realista"
    model = _phrase(c.get("model_name")) or "a modelo"
    color_l = _phrase(color) or "a cor escolhida"
    product_l = product or "o produto"
    benefit_l = _phrase(benefit)
    benefit_l = re.sub(r'^A peça\s+', '', benefit_l, flags=re.I).strip()
    benefit_l = benefit_l or "somente fatos visíveis da peça"
    moves = _movement_plan(_filter_actions(_movement_without_unapproved_turns(movements), _CTA_ACTION_RE))
    turn_direction, _turn_action = _turn_direction(c)
    video_notes = _video_details(details)
    extras = f" Notas adicionais do operador (não são falas nem texto na tela): {video_notes}." if video_notes else ""
    focus, features = _focus_parts(c)
    facts = ', '.join(features) if features else 'nenhum além do que aparece na imagem aprovada'
    materials = ', '.join(_material_facts(c)) or 'não especificada'
    gender_note = ' Modelagem unissex: manter a peça neutra e fiel à referência.' if _is_unisex(c) else ''
    scene_lock = ('o mesmo ambiente mostrado na imagem aprovada desta campanha' if base_image
                  else 'o mesmo ambiente mostrado na foto de referência da modelo')
    forms = _piece_forms(c)
    anchor = 'o cós' if forms['piece'] in ('legging', 'calça', 'short', 'saia', 'bermuda') else 'a barra'
    selected_turns = _body_turns(c)
    if 'costas' in selected_turns:
        rotation_motion = ('faz uma única rotação contínua e breve até mostrar as costas por no máximo 1 segundo, '
                           'e volta imediatamente de frente; ')
        rotation_shot = ('faz uma única rotação contínua até as costas aparecerem por no máximo 1 segundo e '
                         'retorna de frente, sem posar')
    elif 'lado' in selected_turns:
        rotation_motion = 'vira uma única vez até o perfil, sem mostrar as costas, e volta de frente; '
        rotation_shot = 'vira uma única vez até o perfil e retorna de frente, sem ultrapassar 90 graus'
    elif 'leve_lado' in selected_turns:
        rotation_motion = 'inclina o corpo uma única vez de 20 a 30 graus e volta de frente; '
        rotation_shot = 'inclina o corpo de 20 a 30 graus e retorna de frente, mantendo a frente da peça visível'
    else:
        rotation_motion = 'permanece de frente enquanto caminha dois passos curtos no próprio eixo; '
        rotation_shot = 'caminha dois passos curtos de frente e mostra o caimento sem girar o corpo'
    # Cada fato confirmado ganha o gesto que o prova -- isso nunca e descartado.
    # O que se ajusta e a QUANTIDADE: onde o gerador tem limite de caracteres,
    # dois gestos bem escolhidos cabem e provam; quatro estouram o campo e o
    # gerador corta o final do prompt sozinho.
    gestures = _proof_gestures(
        _product_features(c, limit=2 if _limite_video(c) else 4),
        turns=_body_turns(c))
    proof_block = (
        'PROVA VISUAL — cada fato abaixo precisa do seu gesto correspondente, executado entre 3s e 11s: '
        + '; '.join(gestures) + '.\n'
    ) if gestures else ''
    extra_moves = f" Se couber no ritmo, inclua também: {moves}." if moves else ''
    # A direcao de camera do nicho pode mencionar fala ("caminhada frontal
    # falando com a camera"). Neste formato ninguem fala: deixar a frase
    # passar seria mandar o gerador fazer as duas coisas ao mesmo tempo.
    camera = re.sub(r',?\s*falando com a c[âa]mera', '', dirn['camera'], flags=re.I).strip(' ;,')
    if formats.asmr(c):
        camera = f"{camera}; {formats.ASMR_CAMERA}"
    abertura = formats.opening(c, '', 'movimento')
    lead = formats.lead_moves(c)
    fim = formats.ending(c)

    return _montar_video([
        (0, f"UGC TikTok Shop vertical 9:16, exatamente 15 segundos, {resolution}. "
            "VÍDEO SEM FALA: ninguém fala, ninguém narra e não existe voz em nenhum momento. "
            "O vídeo é só a modelo mostrando como a peça fica no corpo. "
            f"ANEXE a IMAGEM APROVADA da cor {color_l} como primeiro quadro e referência contínua. "
            f"A modelo é {model}: preserve 100% o mesmo rosto, cabelo, pele e corpo em TODOS os quadros, "
            f"sem troca de identidade ou redesenho. "
            f"Produto em cena: {product_l} na cor {color_l}. Visual: {outfit}.{gender_note} "
            f"FATOS CONFIRMADOS: {facts}. MATERIAL CONFIRMADO: {materials}. "
            f"Benefício a mostrar visualmente, só se for demonstrável: {benefit_l}.\n"),
        (0, f"CENÁRIO FIXO (todos os frames e cores): {scene_lock}. "
            "Fundo, objetos e luz vêm só dessa foto; descrição genérica de nicho não autoriza substituir. "
            "Não trocar a locação nem desfocar o fundo; a câmera pode aproximar, voltando ao enquadramento inicial no fim. "),
        (2, f"CÂMERA: {camera}. "),
        (0, _main_detail(focus, facts)),
        (4, f"CONTEXTO VISUAL OPCIONAL (não é fato do produto; não inventar): {dirn['must_show']}. "),
        (3, f"EVITAR: {dirn['avoid']}; "),
        (0, "EVITAR TAMBÉM: qualquer fala, narração ou voz; legenda automática; textos, ícones ou carrinho na tela; marcas inventadas; "
            "cortes que quebrem a continuidade; pose parada de catálogo.\n"),
        (0, proof_block),
        (0, "MOVIMENTO (é o conteúdo inteiro do vídeo, com calma e naturalidade, na ordem do SHOT LIST): a modelo puxa "
            f"{anchor} {forms['de']} {forms['piece']} DE LEVE, só o suficiente para o tecido mostrar como assenta, e solta — "
            f"a peça volta exatamente ao lugar; {rotation_motion}"
            f"e ajusta {forms['art']} {forms['piece']} como quem arruma algo fora do lugar (alinhar a barra, subir o cós, "
            f"acertar uma alça, endireitar uma dobra).{extra_moves}{extras} "
            "Nunca esticar a peça com força para os lados: o tecido deforma e o vídeo fica falso. "),
        (0, "MÃOS: uma sempre em contato com a peça; as duas só ficam livres juntas num gesto que exija isso, "
            "por no máximo 1 segundo. "),
        (1, "CABELO: se solto, acompanha o movimento de forma natural e fluida, sem travar nem tremular. "),
        (0, turn_direction + "\n"),
        (0, "SHOT LIST 15s — um único take contínuo ou cortes invisíveis, sem nenhuma fala:\n"
            f"0–3s ABERTURA: {abertura + '; ' if abertura else ''}plano médio frontal, a peça inteira visível no corpo; um ajuste curto e natural, como quem "
            "acabou de se arrumar; expressão tranquila.\n"
            f"3–7s CAIMENTO: {'; '.join(lead) + '; ' if lead else ''}puxa a peça de leve com a ponta dos dedos e solta, deixando o tecido responder sozinho; "
            f"a câmera aproxima do detalhe que vende ({focus}) e volta.\n"
            f"7–11s ORIENTAÇÃO: {rotation_shot}.\n"
            "11–15s AJUSTE FINAL: ajusta a peça como quem arruma (barra, cós, alça ou dobra), volta ao enquadramento "
            f"inicial e sustenta o olhar calmo na lente até o fim. {fim}\n"),
        (0, _unconfirmed_line(c)),
        (0, "ENQUADRAMENTO: manter a mesma cena entre os beats; a câmera pode aproximar e afastar na mesma locação. "
            "Sem movimento artificial de IA: o ritmo é de quem se olha no espelho, não de coreografia ensaiada. "),
        (2, f"Estilo visual: {style}. "),
        (0, (formats.ASMR_AUDIO if formats.asmr(c) else
             "ÁUDIO: nenhuma voz, nenhuma narração e nenhuma música — apenas som ambiente natural e discreto. "
             "A trilha entra depois, na edição, com o áudio escolhido na hora de publicar. ")
            + "Sem promessas não demonstradas no vídeo."),
    ], _limite_video(c))

def _build_pov_video_prompt(c, *, resolution, color, product, benefit, movements, details, hook, development, cta, base_image=False):
    """Video POV (primeira pessoa, produto em foco, rosto nunca aparece).

    Reaproveita o mesmo conteudo falado (hook/development/cta) e as mesmas
    garantias de honestidade do video UGC padrao -- so muda a direcao de
    camera, identidade e performance para o formato POV.
    """
    niche = _niche_key(c)
    dirn = _VIDEO_NICHE.get(niche) or _VIDEO_NICHE["casual"]
    outfit = _pt_br(c.get("outfit")) or "visual do produto"
    style = _pt_br(c.get("style")) or "natural e realista"
    tone = _pt_br(c.get("tone")) or "conversacional"
    model = _phrase(c.get("model_name")) or "a pessoa"
    color_l = _phrase(color) or "a cor escolhida"
    product_l = product or "o produto"
    benefit_l = _phrase(benefit)
    benefit_l = re.sub(r'^A peça\s+', '', benefit_l, flags=re.I).strip()
    benefit_l = benefit_l or "somente fatos visíveis do produto"
    moves = (_movement_plan(_filter_actions(movements, _POV_SKIP_RE))
             or "manuseio natural que mostre o produto de perto")
    pov_lead = formats.pov_lead_moves(c)
    if pov_lead:
        moves = '; '.join(pov_lead + [moves])
    video_notes = _video_details(details)
    extras = f" Notas adicionais do operador (não são falas): {video_notes}." if video_notes else ""
    focus, features = _focus_parts(c)
    facts = ', '.join(features) if features else 'nenhum além do que aparece na imagem aprovada'
    materials = ', '.join(_material_facts(c)) or 'não especificada'
    gender_note = ' Modelagem unissex: manter o produto neutro e fiel à referência.' if _is_unisex(c) else ''
    scene_lock = ('o mesmo ambiente mostrado na imagem aprovada desta campanha' if base_image
                  else 'o mesmo ambiente mostrado na foto de referência da modelo')
    # Cada fato confirmado ganha o gesto que o prova -- isso nunca e descartado.
    # O que se ajusta e a QUANTIDADE: onde o gerador tem limite de caracteres,
    # dois gestos bem escolhidos cabem e provam; quatro estouram o campo e o
    # gerador corta o final do prompt sozinho.
    gestures = _pov_proof_gestures(
        _product_features(c, limit=2 if _limite_video(c) else 4))
    proof_block = (
        'PROVA VISUAL — cada fato abaixo precisa do seu gesto correspondente, executado entre 4s e 11s, sempre visto pelas mãos em primeira pessoa: '
        + '; '.join(gestures) + '.\n'
    ) if gestures else ''

    return _montar_video([
        (0, f"VÍDEO POV (primeira pessoa) TikTok Shop vertical 9:16, exatamente 15 segundos, {resolution}, "
            "filmado no celular por uma pessoa real testando o produto. "
            f"ANEXE a IMAGEM APROVADA da cor {color_l} como primeiro quadro e referência contínua. "
            f"PONTO DE VISTA: câmera em primeira pessoa o tempo todo, como os olhos de {model} segurando o celular. "
            "NUNCA mostrar rosto, pescoço ou reflexo (espelho, vidro, tela) que revele a pessoa: aparecem só as mãos "
            "e o produto, com o mesmo tom de pele e mãos da imagem aprovada. "),
        (0, f"Produto em cena: {product_l} na cor {color_l}. Visual: {outfit}.{gender_note} "
            f"FATOS CONFIRMADOS: {facts}. MATERIAL CONFIRMADO: {materials}. "
            f"Benefício a provar visualmente, só se for demonstrável: {benefit_l}.\n"),
        (0, f"CENÁRIO FIXO (todos os frames e cores): {scene_lock}. "
            "Fundo, objetos e luz vêm só dessa foto; descrição genérica de nicho não autoriza substituir. "
            "Não trocar a locação; o fundo pode ficar fora de foco quando a mão se aproxima da lente, "
            "como numa gravação real de celular. "),
        (0, "CÂMERA: na mão, em primeira pessoa, com micro-tremores sutis e ritmo de respiração natural; pequenos "
            "ajustes de enquadramento, como quem reposiciona o celular; sem movimento cinematográfico, sem ângulo "
            "dramático, sem estabilização artificial. "),
        (4, f"CONTEXTO VISUAL OPCIONAL (não é fato do produto; não inventar): {dirn['must_show']}. "),
        (3, f"EVITAR: {dirn['avoid']}; "),
        (0, "EVITAR TAMBÉM: pose de apresentador; comportamento de influenciador; sensação de anúncio; textos, "
            "ícones, carrinho ou botões na tela (o carrinho só é falado); marcas inventadas; deformação do produto.\n"),
        (0, proof_block),
        (0, "MÃOS: são o único ponto de identidade visível; manuseiam o produto com naturalidade (pegar, virar de leve, testar, "
            "mostrar), com pressão coerente com o tipo de produto; sem gesto ensaiado, pausas e imperfeições bem-vindas. "),
        (0 if pov_lead else 1, f"AÇÕES (escolha 2 a 3, na ordem, entre 0s e 11s; não precisa usar todas): {moves}. "),
        (0, "ENCERRAMENTO (12–15s): a câmera se aproxima com calma de um detalhe final do produto nas mãos, ainda com o "
            "leve tremor de quem segura o celular, enquanto a fala de fechamento acontece."
            + (" No último quadro, o enquadramento volta ao do primeiro, para o vídeo recomeçar sem emenda."
               if 'loop' in formats.techniques(c) else '')),
        (1, extras),
        (0, "\nSHOT LIST 15s — um único take contínuo ou cortes invisíveis:\n"
            f"0–4s ABERTURA: {formats.pov_opening(c, product_l)}. "
            f"Fala (PT-BR), tom espontâneo, como quem pensa em voz alta: \"{hook}\"\n"
            f"4–12s TESTE — uma fala só, contínua, emendada sem pausa na anterior (mesma respiração); não repetir nem "
            f"dividir em dois trechos. Fala (PT-BR): \"{development}\"\n"),
        (3, f"   · 4–6s PROVA 1 (ação silenciosa, sem fala): a mão mostra de perto o detalhe que vende; a câmera segue a mão.\n"
            f"   · 6–11s PROVA 2 (ação silenciosa, sem fala): manuseio completo que demonstra o benefício ({benefit_l}) — "
            f"girar, abrir, testar. Manter cor {color_l} e acabamento fiéis.\n"),
        (4, "   · 11–12s REAÇÃO (ação silenciosa, sem fala): pequena pausa natural, como quem aprova o que viu.\n"),
        (0, f"12–15s FECHAMENTO: o produto em destaque nas mãos. Emendar sem pausa à fala anterior, num tom leve, "
            f"nunca de vendedor. Fala (PT-BR): \"{cta}\"\n"),
        (0, _unconfirmed_line(c)),
        (1, "ENQUADRAMENTO: pequenos reenquadramentos naturais são esperados; não são cortes nem troca de cena. "
            "Nada de propaganda ou atuação: o momento deve parecer real, levemente imperfeito e espontâneo. "),
        (0, "As três falas são UM discurso contínuo: mesma respiração, sem pausa entre os trechos, como quem fala "
            "sozinho ou com um amigo, nunca roteiro decorado. "),
        (2, f"Estilo visual: {style}, com qualidade de câmera de celular real (sem filtros). Tom: espontâneo e casual, "
            f"nunca de vendedor. "),
        (0, "Áudio: voz clara em português do Brasil, ritmo de conversa real. Fale somente as três falas entre aspas, "
            "palavra por palavra; nunca leia títulos, instruções, câmera, shot list ou notas. "),
        (4, f"Total das falas: {len((hook + ' ' + development + ' ' + cta).split())} palavras; "
            f"se passar de 15s em leitura natural, sinalize em vez de acelerar. "),
        (0, "Sem promessas não demonstradas no vídeo."),
    ], _limite_video(c))

# Gestos que pedem "perto da lente" puxam a camera para um close e tiram o
# rosto do quadro enquanto ela fala. Com a modelo em cena, a prova acontece
# no plano (o POV e o produto sem modelo continuam usando o close).
_STAY_IN_FRAME = {
    'tecido macio': 'passa a mão no tecido, na altura da coxa',
    'costura': 'passa o dedo na costura, sem se aproximar da câmera',
    'acabamento': 'passa o dedo no acabamento, sem se aproximar da câmera',
    'punho': 'estende o braço e mostra o punho, sem se aproximar da câmera',
}

# Atributo que nao pode ser inventado -> fato confirmado que o libera.
_UNCONFIRMED = (
    ('compressão', ('compressão', 'compressao')),
    ('elasticidade', ('elastano', 'elástic', 'elastic')),
    ('conforto', ('confort',)),
    ('maciez', ('tecido macio', 'macio', 'macia')),
    ('tecido premium', ('premium',)),
    ('secagem', ('secagem', 'seca rápido', 'seca rapido')),
    ('suporte', ('suporte', 'sustenta')),
    ('composição', ()),
)


# Gestos de prova com a peca FORA do corpo (abrindo o pacote).
_UNBOX_GESTURES = (
    (('bolso',), 'aponta o bolso e passa o dedo pela costura dele'),
    (('botão', 'botões', 'botao', 'botoes'), 'passa o dedo pelos botões, um por um'),
    (('cintura alta', 'cós', 'elástico', 'elastico'), 'segura o cós aberto com as duas mãos, de frente para a lente'),
    (('estampa', 'tie dye', 'floral', 'listra'), 'abre a peça de frente para a estampa aparecer inteira'),
    (('argola', 'dourad', 'fivela', 'metal'), 'aproxima o detalhe metálico da lente e mostra de perto'),
    (('cetim', 'seda'), 'deixa o tecido escorregar entre os dedos, mostrando o brilho'),
    (('courino', 'couro'), 'passa a ponta dos dedos no courino, mostrando a textura'),
    (('renda',), 'aproxima a renda da lente, sem esticar'),
    (('laço', 'laco', 'capuz', 'gola', 'lapela'), 'ajeita esse detalhe com os dedos e aproxima da lente'),
)


def _unbox_gesture(feature):
    low = feature.casefold()
    for words, gesture in _UNBOX_GESTURES:
        if any(w in low for w in words):
            return f'{feature} → {gesture}'
    return f'{feature} → aproxima esse detalhe da lente e mostra de perto'


def _build_unboxing_video_prompt(c, *, resolution, color, product, benefit, movements, details, hook, development,
                                 cta, base_image=False):
    """Abrindo o pacote: a peca FORA do corpo, vista de cima.

    A primeira versao herdava o POV de quem veste: celular na mao (uma mao a
    menos), "girar" a peca e provas no corpo. No teste real o Grok inventou
    uma terceira mao, girou a calca no ar (ela "pulava" para o verso) e
    demorou a abrir a caixa. Aqui o celular esta apoiado (duas maos livres),
    a peca sai da caixa logo no inicio e o verso aparece virando a peca
    sobre a caixa, nunca girando no ar.

    Segundo teste real: qualquer pedido de mostrar o verso virou salto de um
    quadro para o outro, e "apoiar sobre a caixa" fez a peca pular de volta
    para dentro dela. Agora so a frente aparece e a peca fica nas maos."""
    model = _phrase(c.get('model_name')) or 'a pessoa'
    color_l = _phrase(color) or 'a cor escolhida'
    product_l = product or 'o produto'
    _focus, features = _focus_parts(c)
    facts = ', '.join(features) if features else 'nenhum além do que aparece na imagem aprovada'
    materials = ', '.join(_material_facts(c))
    scene_lock = ('o mesmo ambiente mostrado na imagem aprovada desta campanha' if base_image
                  else 'o mesmo ambiente mostrado na foto de referência da modelo')
    gestures = [_unbox_gesture(f) for f in _product_features(c, limit=2)]
    extra = formats.pov_lead_moves(c)
    loop = ('No último quadro, a peça e as mãos voltam à posição do primeiro, para o vídeo recomeçar sem emenda. '
            if 'loop' in formats.techniques(c) else '')
    return _montar_video([
        (0, f"VÍDEO ABRINDO O PACOTE, em primeira pessoa, TikTok Shop vertical 9:16, exatamente 15 segundos, "
            f"{resolution}. ANEXE a IMAGEM APROVADA da cor {color_l} como primeiro quadro e referência contínua. "
            f"Produto: {product_l} na cor {color_l}. FATOS CONFIRMADOS: {facts}. "
            + (f"MATERIAL CONFIRMADO: {materials}. " if materials else '') + "\n"),
        (0, "CÂMERA: o celular está apoiado acima da superfície, apontado para baixo, quase parado (só um leve "
            "tremor natural), um único take contínuo, sem cortes nem zoom. Por isso as DUAS mãos ficam livres. "),
        (0, f"MÃOS: exatamente duas mãos, a esquerda e a direita de {model}, entrando pela parte de baixo do quadro, "
            "com o mesmo tom de pele, unhas e acessórios da imagem; nunca uma terceira mão, nunca braço ou dedo a "
            "mais; as duas ficam no quadro o tempo todo e nenhuma mão nova entra; nunca aparece rosto, pescoço "
            "ou reflexo. "),
        (0, f"CENÁRIO FIXO: {scene_lock}; fundo, caixa, papel de seda e luz só dessa imagem. "),
        (0, "A PEÇA: sempre fora do corpo, ninguém veste. Ela começa à vista na caixa aberta, como na imagem, e já "
            "sai da caixa nos 2 primeiros segundos (nada de caixa fechada nem de abrir devagar). As mãos seguram a "
            "peça aberta, de frente para a lente. Só a FRENTE da peça aparece, do começo ao fim: nunca mostrar o "
            "verso, nunca virar nem girar a peça. Movimentos lentos e contínuos: a peça nunca muda de posição de um "
            "quadro para o outro (nada de salto, corte ou peça que reaparece em outro lugar) e não volta para a "
            "caixa. "),
        (0, ('PROVA VISUAL — com a peça nas mãos, entre 3s e 11s: ' + '; '.join(gestures) + '. ') if gestures else ''),
        (0, f"Também: {'; '.join(extra)}. " if extra else ''),
        (0, "EVITAR: terceira mão, dedos deformados, peça girando ou virando de costas, peça pulando de posição ou "
            "voltando para a caixa, peça mudando de forma ou de cor, vestir a peça, rosto ou corpo, textos, ícones, "
            "carrinho, botões ou stickers na tela, marcas na caixa, cortes.\n"),
        (0, "SHOT LIST 15s — um único take contínuo, sem pausas entre os trechos:\n"
            f"0–3s ABERTURA: {formats.pov_opening(c, product_l)}. Fala (PT-BR), tom espontâneo: \"{hook}\"\n"
            "3–11s DETALHES: as mãos mostram os detalhes de perto, um de cada vez, emendados, enquanto a fala "
            f"continua na mesma respiração. Fala (PT-BR): \"{development}\"\n"
            "11–15s FECHAMENTO: uma mão continua segurando a peça aberta, de frente, e a outra aponta uma vez para "
            f"baixo; a peça não volta para a caixa. {loop}Fala (PT-BR): \"{cta}\"\n"),
        (0, _unconfirmed_line(c)),
        (0, " As três falas são UM discurso contínuo, sem pausa entre os trechos. Áudio: voz feminina em português "
            "do Brasil, espontânea, ritmo de conversa real, som do papel e do tecido ao fundo, sem música; fale só as "
            "falas entre aspas, palavra por palavra; nunca leia títulos, instruções, câmera, shot list ou notas. "),
        (0, "Sem promessas não demonstradas no vídeo."),
    ], _limite_video(c))


def _unconfirmed_line(c):
    """Lista do que nao inventar, sem o que o briefing confirmou: com
    "tecido macio" confirmado, proibir "maciez" contradizia o proprio prompt."""
    facts = ' '.join([*_product_features(c, limit=50), _phrase(c.get('benefit'))]).casefold()
    if _material_facts(c):
        facts += ' composição'
    banned = [name for name, keys in _UNCONFIRMED if not any(k in facts for k in keys)
              and not (name == 'composição' and _material_facts(c))]
    lista = ', '.join(banned[:-1]) + (' ou ' + banned[-1] if len(banned) > 1 else (banned[0] if banned else ''))
    return ((f"ATRIBUTOS NÃO CONFIRMADOS: não inventar {lista} — " if banned else "ATRIBUTOS: ")
            + "nada fora dos FATOS CONFIRMADOS. Com material confirmado, preservar textura e brilho. ")


def _visual_outfit(c, product):
    """O 'Visual' do prompt: a roupa do briefing, ou o produto quando o campo
    ficou com o texto padrao do nicho ("lounge, basic tee, calca moletom..."),
    que contradiz a peca vendida."""
    outfit = _pt_br(c.get('outfit'))
    try:
        from services.model_library import NICHE_DEFAULTS
        genericos = {_pt_br(d.get('outfit')).casefold() for d in NICHE_DEFAULTS.values() if isinstance(d, dict)}
    except Exception:
        genericos = set()
    if not outfit or outfit.casefold() in genericos:
        return product or 'visual do produto'
    return outfit


def video_style(c):
    """Opcoes de estilo escolhidas pelo operador: 'closes' (a camera pode
    sair do rosto para closes curtos no material) e 'ousado' (movimento
    maior, conforme a peca)."""
    return {part.strip() for part in str(c.get('video_style') or '').split(',') if part.strip()}


# Movimento ousado por tipo de peca. "giro" marca os que passam pelas costas.
_BOLD_MOVES = (
    (('vestido', 'saia', 'saída de praia', 'saida de praia', 'kimono', 'macacão', 'macacao'),
     'dá um giro completo e rápido, deixando a peça abrir e acompanhar o movimento', True),
    (('fantasia',), 'faz um gesto característico da fantasia e dá um giro completo e rápido', True),
    (('legging', 'short', 'bermuda', 'top', 'conjunto fitness'),
     'faz um agachamento firme e uma passada larga, com energia de treino', False),
    (('biquíni', 'biquini', 'maiô', 'maio'),
     'caminha confiante, joga o cabelo para trás e leva a mão à cintura', False),
    (('calça', 'calca', 'jeans', 'courino', 'colete', 'jaqueta', 'blazer'),
     'caminha com passos firmes até a câmera, com a mão na cintura', False),
    (('blusa', 'regata', 'camisa', 'body', 'cropped'),
     'joga o cabelo para trás e vira o ombro para a lente', False),
    (('pijama', 'baby doll', 'robe'),
     'se espreguiça e dá uma voltinha leve', False),
)


def bold_move(c, espelho=False):
    """(acao, giro_completo) do movimento ousado para esta peca."""
    text = ' '.join(_phrase(c.get(k)).casefold() for k in ('product', 'outfit'))
    move, spin = 'faz um movimento amplo e confiante que mostre a peça inteira', False
    for words, candidate, giro in _BOLD_MOVES:
        if any(w in text for w in words):
            move, spin = candidate, giro
            break
    if espelho:
        move = move.replace('até a câmera', 'até o espelho').replace('para a lente', 'para o espelho')
    return move, spin


def close_target(c):
    """O que a camera mostra de perto nos closes: material ou fato confirmado."""
    feats = _product_features(c, limit=3)
    materials = [f for f in feats if f in _MATERIAL_LABELS]
    alvo = materials[0] if materials else (feats[0] if feats else '')
    # "no cetim", "nos botões": ja com a contracao de "em".
    return _with_em(_with_article(alvo)) if alvo else 'no tecido e nos detalhes da peça'


def mirror_hands(text):
    """No espelho uma mao segura o celular: gesto "com as duas maos" vira da
    mao livre (senao o Grok inventa uma terceira mao) e a lente vira o espelho."""
    t = re.sub(r'\bcom as duas mãos\b', 'com a mão livre', text or '')
    return (t.replace('de frente para a lente', 'de frente para o espelho')
             .replace('perto da lente', 'perto do espelho').replace('da lente', 'do espelho'))


def _main_detail(focus, facts):
    """Bloco DETALHE PRINCIPAL so quando acrescenta algo aos FATOS CONFIRMADOS
    (varredura: ele repetia os fatos com "e" no lugar da virgula e gastava
    espaco do limite do Grok)."""
    palavras = re.findall(r'\w{3,}', (focus or '').casefold())
    if palavras and all(w in (facts or '').casefold() for w in palavras):
        return ''
    return f"DETALHE PRINCIPAL: {focus}. "


def _light_scene(falas, espelho=False):
    """Acao de contraluz quando a fala promete mostrar a peca contra a luz."""
    if not re.search(r'contra a luz', ' '.join(f or '' for f in falas), re.I):
        return ''
    if espelho:
        return 'vira de leve para a janela, com a luz batendo atrás do tecido, e volta para o espelho'
    return 'vira de leve para a janela, com a luz batendo atrás do tecido, e volta de frente'


def _build_video_prompt(c, *, resolution, color, product, benefit, movements, details, hook, development, cta,
                        base_image=False, formato='ugc'):
    """Prompt unico do Grok para a modelo falando: as travas do prompt completo
    (que gerou o video bom no teste real: identidade, cenario, fatos, prova,
    o que nao inventar, falas marcadas no tempo) somadas ao que o Guia do
    Grok trouxe de melhor no teste seguinte (clima por referencia, plano do
    joelho para cima com o rosto grande, maos que gesticulam, acoes emendadas
    sem parar, arco de expressao e ritmo natural, sem camera lenta)."""
    from services.prompt_improve import mood, push_target, speech_framing
    dirn = _VIDEO_NICHE.get(_niche_key(c)) or _VIDEO_NICHE["casual"]
    outfit = _visual_outfit(c, product)
    angle = _pt_br(c.get("angle")) or "mostrar o produto em uso"
    angle_context = ' '.join(angle.split()[:16]) + ('…' if len(angle.split()) > 16 else '')
    style = _pt_br(c.get("style")) or "natural e realista"
    model = _phrase(c.get("model_name")) or "a modelo"
    color_l = _phrase(color) or "a cor escolhida"
    product_l = product or "o produto"
    benefit_l = re.sub(r'^A peça\s+', '', _phrase(benefit), flags=re.I).strip() or "somente fatos visíveis da peça"
    moves = _configured_movement_plan(movements, c)
    # Pose, close e "CTA final" do padrao do nicho contradiziam o rosto sempre
    # no quadro e o encerramento sem pose; ficam so as acoes.
    moves = '; '.join(m for m in moves.split('; ') if m and not re.search(
        r'\bpose\b|\bposar\b|\bclose\b|\bcta\b', m, re.I)) or "movimentos frontais e naturais que mostrem o caimento"
    turn_direction, _turn_action = _turn_direction(c)
    video_notes = _video_details(details)
    focus, features = _focus_parts(c)
    facts = ', '.join(features) if features else 'nenhum além do que aparece na imagem aprovada'
    materials = ', '.join(_material_facts(c)) or 'não especificada'
    gender_note = ' Modelagem unissex: manter a peça neutra e fiel à referência.' if _is_unisex(c) else ''
    scene_lock = ('o mesmo ambiente mostrado na imagem aprovada desta campanha' if base_image
                  else 'o mesmo ambiente mostrado na foto de referência da modelo')
    forms = _piece_forms(c)
    anchor = 'o cós' if forms['piece'] in ('legging', 'calça', 'short', 'saia', 'bermuda') else 'a barra'
    # Cada fato confirmado ganha o gesto que o prova; onde o gerador tem
    # limite de caracteres, dois gestos bem escolhidos cabem e provam.
    gestures = _proof_gestures(_product_features(c, limit=2 if _limite_video(c) else 4), turns=_body_turns(c))
    estilo = video_style(c)
    if 'closes' not in estilo:
        # Sem closes autorizados, a prova acontece no plano, com o rosto no quadro.
        gestures = [f'{lab} → {_STAY_IN_FRAME.get(lab, ges)}' for lab, ges in (g.split(' → ', 1) for g in gestures)]
    # Motor de persuasao no corpo; tempos proporcionais as falas (4s/12s no padrao).
    cena = persuasion.scene_direction(persuasion.script_motor(_dominant_motor(c), hook),
                                      f"{anchor} {forms['de']} {forms['piece']}")
    t1, t2 = persuasion.timeline(hook, development, cta)
    espelho = formato == 'espelho'
    if espelho:
        turn_direction = turn_direction.replace('à lente', 'ao espelho').replace('a lente', 'o espelho')
        gestures = [mirror_hands(g) for g in gestures]
        moves = mirror_hands(moves)
        # O quadro e o reflexo: mostrar de perto = se aproximar do espelho.
        moves = re.sub(r'\bmostrar de perto\b', 'aproximar-se do espelho e mostrar de perto', moves)
        if 'espelho' not in moves:
            alvo = _with_article(features[0]) if features else 'os detalhes da peça'
            moves = f"aproximar-se do espelho para mostrar {alvo} de perto e voltar; {moves}"
        # Celular no espelho: o quadro e o reflexo; uma mao segura o celular o
        # tempo todo e a outra faz tudo (gesto, prova, carrinho).
        clima = 'fit check no espelho gravado com o celular e postado no TikTok'
        camera = ("o vídeo é o que o celular dela grava no espelho de corpo inteiro: o quadro é o reflexo, com o "
                  "celular sempre na mão dela, na altura do peito, sem cobrir o rosto; leve balanço natural de mão, "
                  "um único take contínuo, sem cortes nem zoom. O rosto fica sempre inteiro no reflexo enquanto ela "
                  "fala, olhando para a tela do celular. ")
        maos = ("MÃOS: uma segura o celular o tempo todo; a outra gesticula enquanto ela fala — toca a peça, ajusta, "
                "aponta o detalhe — e volta para a peça; nada de braço duro. Sem movimento artificial de IA. ")
        abre = cena['hook'].replace('em direção à câmera', 'em direção ao espelho').replace('até a câmera', 'até o espelho')
        fecha = ("já de frente para o espelho, com o celular na mão; a mão livre aponta UMA vez para baixo com o "
                 "indicador e volta para a peça, sorrindo, sem parar de falar e sem pose final. ")
    else:
        clima = mood(c)
        camera = (f"na mão, estável, {speech_framing(c)}, frontal, um único take contínuo, sem cortes; "
                  f"dolly-in suave e contínuo até {push_target(c)} e volta suave ao plano inicial no final. "
                  "O rosto fica sempre inteiro no quadro enquanto ela fala. ")
        maos = ("MÃOS: ela gesticula enquanto fala, como quem conversa com uma amiga — abre a mão, aponta a peça, toca o "
                "tecido quando fala dele e volta a mão para a peça; nada de mãos paradas nem braços duros. "
                "Sem movimento artificial de IA. ")
        abre = cena['hook']
        fecha = (f"já de frente para a lente, com uma das mãos tocando {anchor} {forms['de']} {forms['piece']}, como "
                 "quem ajusta a peça; a outra aponta UMA vez para baixo com o indicador e volta, "
                 "sorrindo, sem parar de falar e sem pose final. ")
    if 'ousado' in estilo:
        ousado, giro = bold_move(c, espelho=espelho)
        moves = f"{ousado}; {moves}"
        if giro and 'costas' not in _body_turns(c):
            turn_direction = ('ORIENTAÇÃO CORPORAL: de frente para a ' + ('espelho' if espelho else 'lente')
                              + ', com um giro completo e rápido no meio; as costas só passam, ela nunca para de costas.')
            turn_direction = turn_direction.replace('para a espelho', 'para o espelho')
    if 'closes' in estilo:
        alvo = close_target(c)
        if espelho:
            camera = camera.replace(
                "O rosto fica sempre inteiro no reflexo enquanto ela fala, olhando para a tela do celular. ",
                f"No gancho e no fim o rosto fica inteiro no reflexo, olhando para a tela do celular; no meio, ela "
                f"aproxima o celular da peça para 1 ou 2 closes curtos (1 a 2 s) {alvo}, enquanto a voz continua, "
                "e volta ao reflexo. ")
        else:
            camera = camera.replace(
                "O rosto fica sempre inteiro no quadro enquanto ela fala. ",
                f"No gancho e no fim o rosto fica inteiro no quadro; no meio, a câmera faz 1 ou 2 closes curtos "
                f"(1 a 2 s cada) {alvo}, enquanto a voz dela continua, e volta ao rosto. ")
            # Os closes ja aproximam a camera: o dolly-in vira redundancia e
            # ocupa o espaco das acoes no limite do Grok.
            camera = re.sub(r'dolly-in suave e contínuo até .*? no final\. ', '', camera)
    # Formato e tecnicas de retencao (services/formats.py): entram dentro da
    # abertura, das acoes e do encerramento, sem bloco novo (o prompt esta
    # perto do limite do Grok).
    lugar = 'espelho' if espelho else ''
    abre = formats.opening(c, abre, lugar)
    jeitos = formats.three_looks(c, f"{forms['art']} {forms['piece']}")
    lead = formats.lead_moves(c, lugar)
    if jeitos:
        moves = '; '.join(lead + [jeitos])
    elif lead:
        moves = '; '.join(lead + [moves])
    # A fala cita contraluz ("tô aqui contra a luz"): a cena precisa existir,
    # senao o Grok ignora ou improvisa (varredura: 100% das leggings).
    luz = _light_scene((hook, development, cta), espelho)
    if luz:
        moves = f'{luz}; {moves}'
        lead = lead or [luz]
    if jeitos or lead or 'ousado' in estilo:
        # Com acao especifica, a acao generica do padrao so ocupa espaco.
        moves = '; '.join(m for m in moves.split('; ') if not m.startswith('movimentos sutis')) or moves
    fecha += formats.ending(c, lugar)
    cortes = formats.allows_cuts(c)
    if cortes:
        camera = camera.replace('sem cortes', 'sem cortes além das 2 trocas de look')
        # O meio do 3 jeitos e das trocas de look: gesto de prova ali
        # disputaria o mesmo tempo e estouraria o limite do Grok.
        gestures = []
    acoes = (f"AÇÕES (na ordem, a primeira é obrigatória, entre 0s e {t2 - 1}s, emendadas, sem parar nem posar): {moves}. "
             if jeitos or lead else
             f"AÇÕES (escolha 2 a 3, na ordem, entre 0s e {t2 - 1}s, emendadas, sem parar nem posar): {moves}. ")
    shot_head = ("\nSHOT LIST 15s — um take com 2 trocas de look pela mão na lente, sem pausas na fala:\n" if cortes
                 else "\nSHOT LIST 15s — um único take contínuo, sem pausas entre os trechos:\n")
    proof_block = (
        f'PROVA VISUAL — cada fato abaixo precisa do seu gesto correspondente, executado entre {t1}s e {t2 - 1}s, '
        'sem interromper a fala: ' + '; '.join(gestures) + '.\n'
    ) if gestures else ''
    words = len((hook + ' ' + development + ' ' + cta).split())

    blocos = [
        (0, f"UGC TikTok Shop vertical 9:16, exatamente 15 segundos, {resolution}. Clima: {clima}. "
            f"ANEXE a IMAGEM APROVADA da cor {color_l} como primeiro quadro e referência contínua. "
            f"A modelo é {model}: preserve 100% o mesmo rosto, cabelo, pele e corpo em TODOS os quadros, "
            f"sem troca de identidade ou redesenho. "
            f"Produto em cena: {product_l} na cor {color_l}. Visual: {outfit}.{gender_note} "),
        (4, f"Ângulo de venda (contexto, não criar atributos): {angle_context}. "),
        (0, f"FATOS CONFIRMADOS: {facts}. "
            + (f"MATERIAL CONFIRMADO: {materials}. " if materials != 'não especificada' else '')
            + (f"Benefício a provar visualmente, só se for demonstrável: {benefit_l}." if _phrase(benefit) else '')
            + "\n"),
        (0, f"CENÁRIO FIXO (todos os frames e cores): {scene_lock}; fundo, objetos e luz só dessa foto, sem trocar "
            "a locação, escurecer ou desfocar; descrição genérica de nicho não autoriza substituir. "
            "ENQUADRAMENTO: manter a mesma cena entre os beats. "),
        (0, f"CÂMERA: {camera}"),
        (0, _main_detail(focus, facts)),
        # So no Flow (sem limite apertado): no Grok o espaco vai para o essencial.
        (4, f"CONTEXTO VISUAL OPCIONAL (não é fato do produto; não inventar): {dirn['must_show']}. "
            if not _limite_video(c) else ''),
        (0, "EVITAR: textos, ícones, carrinho, botões, setas ou stickers na tela (o carrinho só é falado, "
            f"nunca desenhado); marcas inventadas; {'cortes fora das trocas de look' if cortes else 'cortes'}; câmera lenta.\n"),
        (0, proof_block),
        (0, turn_direction + "\n"),
        (0, maos),
        (1, "CABELO: se solto, acompanha o movimento de forma natural e fluida, sem travar nem tremular. "),
        # As acoes nunca saem: sem elas o video ficou estatico no teste real.
        (0, acoes),
        (0, f"ENCERRAMENTO ({t2}–15s): {fecha}"),
        (1, f"EXPRESSÃO: {cena['arc']}. "),
        (2, f"Notas adicionais do operador (não são falas): {video_notes}. " if video_notes else ''),
        (0, shot_head +
            f"0–{t1}s HOOK: olhar {'na tela do celular' if espelho else 'na lente'}, produto visível no corpo; "
            f"a modelo {abre}. "
            f"Fala (PT-BR): \"{hook}\"\n"
            f"{t1}–{t2}s DESENVOLVIMENTO — mesma respiração, enquanto faz a prova e as ações. "
            f"Fala (PT-BR): \"{development}\"\n"
            f"{t2}–15s CTA: apontando para baixo uma vez, concluindo o mesmo pensamento. Fala (PT-BR): \"{cta}\"\n"),
        (0, _unconfirmed_line(c)),
        (0, "As três falas são UM discurso contínuo, sem pausa entre os trechos, como quem conta uma descoberta "
            "para uma amiga. Áudio: voz feminina em português do Brasil, espontânea, sorriso na voz, a fala ocupa "
            "os 15 s até o fim, sem silêncio, lábios sincronizados, nada de locução; fale só as falas entre aspas, palavra por palavra; "
            "nunca leia títulos, instruções, câmera, shot list ou notas. Som ambiente baixo, sem música. "),
        (2, f"Estilo visual: {style}. "),
        (4, f"Total das falas: {words} palavras; se passar de 15s em leitura natural, sinalize em vez de acelerar. "),
        (0, "Sem promessas não demonstradas no vídeo."),
    ]
    limite = _limite_video(c)
    texto = _montar_video(blocos, limite)
    if limite and len(texto) > limite and len(gestures) > 1:
        # Formato com muitas tecnicas: um gesto de prova bem feito cabe; dois
        # passariam do limite do Grok, que corta o fim do prompt sozinho.
        curto = (f'PROVA VISUAL — o fato abaixo precisa do seu gesto, executado entre {t1}s e {t2 - 1}s, '
                 f'sem interromper a fala: {gestures[0]}.\n')
        texto = _montar_video([(p, curto if t == proof_block else t) for p, t in blocos], limite)
    if limite and len(texto) > limite and proof_block:
        # Ultimo recurso (espelho com closes, ousado e duas tecnicas): os
        # closes e as acoes ja mostram a peca; sem isso o Grok cortaria o fim.
        texto = _montar_video([(p, '' if t == proof_block else t) for p, t in blocos], limite)
    if limite and len(texto) > limite:
        # Ultimo recurso 2 (3 jeitos com tecnicas e beneficio longo): o
        # beneficio e contexto; fatos, acoes e falas ficam.
        sem_beneficio = [(p, '' if proof_block and t == proof_block else
                          re.sub(r'Benefício a provar visualmente, só se for demonstrável: [^\n]*', '', t))
                         for p, t in blocos]
        texto = _montar_video(sem_beneficio, limite)
    return texto


def generate_variants(c, audit=None):
    colors = color_variants(c.get('color'))
    # A primeira cor edita a referencia; as seguintes editam a base aprovada,
    # mantendo cenario, pose e enquadramento identicos.
    #
    # As falas ja escolhidas entram na memoria da propria rodada: sem isso as
    # cores de uma mesma campanha saem com o mesmo molde de frase, que e
    # justamente o que o espectador percebe quando ve dois posts seguidos.
    memoria = {k: list(v) for k, v in (c.get('recent_lines') or {}).items() if isinstance(v, list)}
    saida = []
    for index, color in enumerate(colors):
        pacote = generate({**c, 'color': color, 'recent_lines': memoria},
                          variant_index=index, base_image=index > 0, audit=audit)
        for campo in ('hook', 'development', 'cta'):
            if pacote.get(campo):
                memoria.setdefault(campo, []).append(pacote[campo])
        saida.append({'color': color, 'prompts': pacote})
    return saida


def _build_pov_image_prompt(c, *, product, color, piece_ref, photos, product_reference,
                            facts, materials, notes, base_image=False):
    """Imagem-base do video POV: o primeiro quadro ja em primeira pessoa.

    O video POV anexa esta imagem como primeiro quadro e proibe mostrar o
    rosto. Ate aqui a imagem era a mesma do UGC (a modelo de frente, com
    rosto), entao o gerador recebia um primeiro quadro que ele mesmo estava
    proibido de mostrar. Na primeira cor a imagem muda o ponto de vista a
    partir da foto de referencia; nas outras cores ela ja nasce da imagem
    POV aprovada e vira uma edicao localizada, como no UGC.
    """
    model = c['model_name']
    worn = _product_family(c) in ('moda', 'infantil')
    in_view = (f"{piece_ref} vestida no corpo, vista de cima pelos olhos de quem veste, "
               "com uma das mãos tocando a peça" if worn else
               f"{piece_ref} em uma das mãos, perto da lente, visto pelos olhos de quem segura")
    if formats.video_format(c) == 'unboxing':
        in_view = formats.UNBOXING_VIEW.format(piece=piece_ref)
    pov_rules = (
        "PONTO DE VISTA: primeira pessoa (POV), câmera do celular na altura dos olhos apontada para baixo. "
        "A outra mão segura o celular e fica fora do quadro. "
        "NUNCA mostrar rosto, pescoço, cabelo na frente da lente nem reflexo em espelho, vidro ou tela. "
    )
    if base_image:
        attachments = "ORDEM DOS ANEXOS: anexe primeiro a imagem aprovada desta campanha (primeiro quadro POV)"
        if photos:
            attachments += f" e depois {len(photos)} {'foto' if len(photos) == 1 else 'fotos'} do produto"
        attachments += '. O primeiro anexo é a única base de ponto de vista, mãos, cenário e enquadramento. '
        return (
            attachments
            + "EDIÇÃO LOCALIZADA: trate a imagem aprovada como a fotografia-base final. "
            + f"Produto: {product}. Cor: {color}. "
            + f"Altere somente a área ocupada por {piece_ref}, mantendo todo o restante visualmente idêntico: "
            + "mesmas mãos, mesmo tom de pele, mesma posição dos dedos, mesmo ângulo de câmera. "
            + pov_rules
            + product_reference
            + f"VARIAÇÃO ÚNICA: gere somente esta cor ({color}); não misture cores nem crie outras versões na mesma imagem. "
            + f"FATOS DO PRODUTO A PRESERVAR: {facts}. "
            + f"MATERIAL / COMPOSIÇÃO CONFIRMADA: {materials}. "
            + "CENÁRIO FIXO: preserve exatamente fundo, chão, objetos, iluminação, sombras e balanço de branco. "
            + "INTEGRAÇÃO FOTOGRÁFICA: caimento, dobras, oclusão pelos dedos e sombras de contato coerentes; "
            + "sem aparência de recorte ou colagem. Sem textos nem marcas inventadas. "
            + (f"DETALHES ESTÁTICOS DO PRODUTO: {notes}. " if notes else '')
            + "Apenas uma imagem estática; não descreva vídeo, falas nem duração."
        )
    attachments = f"ORDEM DOS ANEXOS: anexe primeiro a foto de referência da modelo (fotografia-base de {model})"
    if photos:
        attachments += f" e depois {len(photos)} {'foto' if len(photos) == 1 else 'fotos'} do produto"
    attachments += ('. O primeiro anexo é a base de tom de pele, mãos, unhas, corpo e cenário — mas NÃO de '
                    'enquadramento: esta imagem muda o ponto de vista para a primeira pessoa. ')
    return (
        attachments
        + "PRIMEIRO QUADRO DE UM VÍDEO POV: fotografia vertical 9:16 feita com o celular de "
        + f"{model}, como se a câmera fossem os olhos dela. "
        + f"Produto: {product}. Cor: {color}. "
        + f"O QUE APARECE: {in_view}. "
        + pov_rules
        + f"IDENTIDADE PELAS MÃOS: mesmo tom de pele, mesmas mãos, unhas e proporções do corpo de {model} "
        + "na foto de referência; nada de mãos ou pele de outra pessoa. "
        + product_reference
        + f"VARIAÇÃO ÚNICA: gere somente esta cor ({color}); não misture cores nem crie outras versões na mesma imagem. "
        + f"FATOS DO PRODUTO A PRESERVAR: {facts}. "
        + f"MATERIAL / COMPOSIÇÃO CONFIRMADA: {materials}; mantenha a textura e o caimento compatíveis com a referência do produto. "
        + ('MODELAGEM: unissex. ' if _is_unisex(c) else '')
        + "CENÁRIO: o mesmo ambiente da foto de referência, agora visto de cima — mesmo chão, objetos, "
        + "iluminação, balanço de branco e granulação. Não trocar a locação nem inventar um estúdio. "
        + "REALISMO: fotografia comum de celular, sem filtro, leve perspectiva de grande-angular; "
        + "caimento, dobras, oclusão pelos dedos e sombras de contato coerentes; sem pose de catálogo. "
        + "Mantenha o produto fiel à referência; sem textos, marcas inventadas ou deformações. "
        + (f"DETALHES ESTÁTICOS DO PRODUTO: {notes}. " if notes else '')
        + "Apenas uma imagem estática; não descreva vídeo, falas nem duração."
    )


def _build_mirror_image_prompt(c, *, product, color, piece_ref, photos, product_reference,
                               facts, materials, notes, base_image=False):
    """Primeiro quadro do formato "Celular no espelho": o fit check que a
    propria creator grava com o celular no espelho de corpo inteiro. O video
    anexa esta imagem como primeiro quadro, entao ela ja nasce com o celular
    na mao e o reflexo; nas outras cores vira edicao localizada da aprovada."""
    model = c['model_name']
    mirror_rules = (
        "SELFIE NO ESPELHO: a imagem é o reflexo num espelho de corpo inteiro. Ela segura o próprio celular com "
        "uma das mãos, na altura do peito, com a câmera traseira voltada para o espelho; o celular aparece no "
        "reflexo sem cobrir o rosto, que fica inteiro e visível acima do aparelho. A outra mão toca a peça. "
        f"Corpo de frente para o espelho, com {piece_ref} inteira visível no reflexo. "
    )
    if base_image:
        attachments = "ORDEM DOS ANEXOS: anexe primeiro a imagem aprovada desta campanha (selfie no espelho)"
        if photos:
            attachments += f" e depois {len(photos)} {'foto' if len(photos) == 1 else 'fotos'} do produto"
        attachments += '. O primeiro anexo é a única base de pose, celular, espelho, cenário e enquadramento. '
        return (
            attachments
            + "EDIÇÃO LOCALIZADA: trate a imagem aprovada como a fotografia-base final. "
            + f"Produto: {product}. Cor: {color}. "
            + f"Altere somente a área ocupada por {piece_ref}; mantenha idênticos rosto, cabelo, corpo, pose, "
            + "o celular na mão, o espelho, o fundo e a luz. "
            + product_reference
            + f"VARIAÇÃO ÚNICA: gere somente esta cor ({color}); não misture cores nem crie outras versões na mesma imagem. "
            + f"FATOS DO PRODUTO A PRESERVAR: {facts}. MATERIAL / COMPOSIÇÃO CONFIRMADA: {materials}. "
            + "INTEGRAÇÃO FOTOGRÁFICA: caimento, dobras, oclusão pela mão e reflexo coerentes; sem recorte ou colagem. "
            + "Sem textos nem marcas inventadas; a tela do celular não mostra texto legível. "
            + (f"DETALHES ESTÁTICOS DO PRODUTO: {notes}. " if notes else '')
            + "Apenas uma imagem estática; não descreva vídeo, falas nem duração."
        )
    attachments = f"ORDEM DOS ANEXOS: anexe primeiro a foto de referência da modelo (fotografia-base de {model})"
    if photos:
        attachments += f" e depois {len(photos)} {'foto' if len(photos) == 1 else 'fotos'} do produto"
    attachments += ('. O primeiro anexo é a base de identidade, corpo, cenário e luz — mas NÃO de pose nem de '
                    'enquadramento: esta imagem vira uma selfie no espelho. ')
    return (
        attachments
        + "PRIMEIRO QUADRO DE UM VÍDEO DE FIT CHECK NO ESPELHO: fotografia vertical 9:16, como a foto que a própria "
        + f"{model} tira de si mesma no espelho com o celular. "
        + f"Produto: {product}. Cor: {color}. "
        + mirror_rules
        + f"IDENTIDADE: preserve 100% o rosto, cabelo, tom de pele, corpo, idade aparente e proporções de {model}. "
        + product_reference
        + f"VARIAÇÃO ÚNICA: gere somente esta cor ({color}); não misture cores nem crie outras versões na mesma imagem. "
        + f"FATOS DO PRODUTO A PRESERVAR: {facts}. "
        + f"MATERIAL / COMPOSIÇÃO CONFIRMADA: {materials}; mantenha a textura e o caimento compatíveis com a referência do produto. "
        + ('MODELAGEM: unissex. ' if _is_unisex(c) else '')
        + "CENÁRIO: o mesmo ambiente da foto de referência, refletido no espelho — mesmos objetos, luz, balanço de "
        + "branco e granulação. Não trocar a locação nem inventar um estúdio; a moldura do espelho pode aparecer na borda. "
        + "REALISMO: foto comum de celular, sem filtro, leve perspectiva de grande-angular; reflexo coerente; "
        + "sem pose de catálogo. Mantenha o produto fiel à referência; sem textos, marcas inventadas ou deformações; "
        + "a tela do celular não mostra texto legível. "
        + (f"DETALHES ESTÁTICOS DO PRODUTO: {notes}. " if notes else '')
        + "Apenas uma imagem estática; não descreva vídeo, falas nem duração."
    )


def generate(c, script=None, variant_index=0, base_image=False, audit=None, attempts=6):
    """Monta o pacote (imagem, video, falas, legenda) de uma cor.

    ``audit`` e opcional e recebe ``(pacote, campanha)``, devolvendo a lista de
    problemas. Quando vem preenchido, o gerador percorre as variacoes seguintes
    ate achar uma que passe -- e a forma de a mesma regua que julga o texto da
    IA valer tambem para o texto local. Sem ele o comportamento e o de antes.
    Texto escrito pelo operador (``script``) nunca e trocado por este caminho.
    """
    if audit is not None and not script:
        melhor, melhor_problemas = None, None
        for passo in range(max(1, int(attempts))):
            pacote = generate(c, variant_index=int(variant_index or 0) + passo, base_image=base_image)
            problemas = list(audit(pacote, c) or [])
            if not problemas:
                return pacote
            if melhor_problemas is None or len(problemas) < len(melhor_problemas):
                melhor, melhor_problemas = pacote, problemas
        return melhor
    # Always treat color as a single variant for one image/video package.
    colors = color_variants(c.get('color'))
    if len(colors) > 1:
        c = {**c, 'color': colors[0]}
    product = _pt_br(c['product'])
    benefit = _phrase(c['benefit'])
    movements = _phrase(c.get('movements')) or 'movimentos sutis e naturais que mostrem o caimento da peça'
    color = _phrase(c.get('color'))
    hook, development, cta = _script_variation(c, color, variant_index)
    if script:
        hook = _spoken_line(script.get('hook'), hook)
        development = _spoken_line(script.get('development'), development)
        cta = _spoken_line(script.get('cta'), cta)
    # Localized image edits use the photograph as the only scene/camera source.
    # Niche style, audience and sales direction belong to the video/copy path;
    # reinserting them here used to contradict the preserved background.
    details = _pt_br(c.get('details'))
    photos = c.get('product_assets') or []
    forms = _piece_forms(c)
    piece_ref = f"{forms['art']} {forms['piece']}"
    base = ('a imagem aprovada desta campanha' if base_image
            else 'a foto de referência da modelo')
    attachments = f"ORDEM DOS ANEXOS: anexe primeiro {base} (fotografia-base de {c['model_name']})"
    if photos:
        attachments += f" e depois {len(photos)} {'foto' if len(photos) == 1 else 'fotos'} do produto"
    attachments += '. O primeiro anexo é a única base de identidade, pose, cenário e enquadramento. '
    product_reference = (
        "REFERÊNCIA DO PRODUTO: reproduza na peça o corte, o caimento, as costuras, "
        "os acabamentos e os detalhes visíveis nas fotos do produto. "
        "Pessoas presentes nas fotos do produto NÃO são referências de identidade: "
        "não copie seu rosto, cabelo, corpo, pose ou tom de pele. "
        f"A cor final solicitada é {color}; ela prevalece sobre fotos com outras cores. "
        "Não reproduza fundos, textos sobrepostos nem marcas d'água das fotos de catálogo. "
    ) if photos else (
        "Não há foto de catálogo anexada: use somente os detalhes informados e os já visíveis "
        "na fotografia-base, sem inventar acabamentos, costuras ou acessórios. "
    )
    features = _product_features(c)
    facts = ', '.join(features) if features else 'somente os detalhes visíveis nas referências do produto'
    if not features and not photos:
        facts = 'somente os detalhes já visíveis na fotografia-base'
    materials = ', '.join(_material_facts(c)) or 'não especificada'
    notes = _image_details(c.get('details'), preserve_base=True)
    scene = ('o mesmo ambiente mostrado na imagem aprovada desta campanha' if base_image
             else 'o mesmo ambiente mostrado na foto de referência da modelo')
    image = (
        attachments
        + f"EDIÇÃO LOCALIZADA: trate {base} como a fotografia-base final, não como inspiração para uma nova cena. "
        + f"Produto: {product}. Cor: {color}. "
        + f"Altere somente a área ocupada por {piece_ref}, mantendo todo o restante da imagem visualmente idêntico. "
        + f"IDENTIDADE: a modelo é {c['model_name']}. Preserve rosto, cabelo, tom de pele, corpo, idade aparente e proporções. "
        + "Preserve também pose, expressão, posição das mãos, peças complementares e calçados. "
        + "Não redesenhe a pessoa, não reposicione membros e não altere outras peças do visual. "
        + product_reference
        + f"VARIAÇÃO ÚNICA: gere somente esta cor ({color}); não misture cores nem crie outras versões na mesma imagem. "
        + f"FATOS DO PRODUTO A PRESERVAR: {facts}. "
        + f"MATERIAL / COMPOSIÇÃO CONFIRMADA: {materials}; mantenha a textura e o caimento compatíveis com a referência do produto. "
        + ('MODELAGEM: unissex. ' if _is_unisex(c) else '')
        + f"CENÁRIO FIXO: {scene}. Preserve exatamente fundo, objetos, iluminação, sombras, reflexos, "
        + "perspectiva, exposição, balanço de branco, granulação e o nível de nitidez ou desfoque já existente na fotografia-base. "
        + "O cenário e a luz vêm exclusivamente dessa fotografia; descrições genéricas de nicho não autorizam sua substituição. "
        + "ENQUADRAMENTO: mantenha os limites originais da foto, a proporção, a distância e a altura da câmera. "
        + "Não recorte, não amplie o campo de visão e não invente partes da pessoa ou do ambiente fora do quadro. "
        + "Se a peça estiver cortada na fotografia-base, preserve esses limites; não reconstrua a área ausente. "
        + "INTEGRAÇÃO FOTOGRÁFICA: a peça substituída deve acompanhar exatamente a anatomia e a pose já existentes, "
        + "com caimento, dobras, tensão do tecido, oclusão correta pelas mãos e pelo corpo, sombras de contato, "
        + "reflexos e luz coerentes com a fotografia-base. A borda da roupa deve estar natural, sem aparência de recorte, "
        + "colagem ou pintura por cima. Mantenha o produto fiel à referência; sem textos, marcas inventadas ou deformações. "
        + (f"DETALHES ESTÁTICOS DO PRODUTO (sem alterar a composição da fotografia-base): {notes}. " if notes else '')
        + "Apenas uma imagem estática; não descreva vídeo, falas nem duração."
    )
    if _video_mode(c) == 'pov':
        image = _build_pov_image_prompt(
            c, product=product, color=color, piece_ref=piece_ref, photos=photos,
            product_reference=product_reference, facts=facts, materials=materials,
            notes=notes, base_image=base_image)
    elif _video_mode(c) == 'espelho':
        image = _build_mirror_image_prompt(
            c, product=product, color=color, piece_ref=piece_ref, photos=photos,
            product_reference=product_reference, facts=facts, materials=materials,
            notes=notes, base_image=base_image)
    resolution = '1080 × 1920 (1080p)' if c['generator'] == 'flow' else '720 × 1280 (720p)'
    build_video = {
        'pov': _build_pov_video_prompt,
        'movimento': _build_movement_video_prompt,
        'espelho': lambda *a, **k: _build_video_prompt(*a, formato='espelho', **k),
    }.get(_video_mode(c), _build_video_prompt)
    if formats.video_format(c) == 'unboxing':
        build_video = _build_unboxing_video_prompt
    video = build_video(
        c,
        resolution=resolution,
        color=c.get('color'),
        product=product,
        benefit=_benefit_clause(c),
        movements=movements,
        details=details,
        hook=hook,
        development=development,
        cta=cta,
        base_image=base_image,
    )
    caption = build_caption(c, color=color, cta=None, variation_index=variant_index)
    # Texto de capa e texto de tela: ficam FORA do video gerado de proposito
    # (o prompt continua proibindo letra dentro do quadro) e sao colados na
    # postagem, onde a tipografia sai correta.
    forms_txt = _piece_forms(c)
    focus_txt, features_txt = _focus_parts(c)
    detail_txt = _with_article(features_txt[0] if features_txt else (focus_txt or 'o caimento'))
    cover_text = _cover_text(c, forms_txt, detail_txt, variant_index)
    # Deslocado de proposito: capa e texto de tela aparecem juntos na postagem,
    # entao repetir a mesma frase nos dois desperdica o unico frame que quem
    # assiste sem som realmente le.
    screen_text = _screen_text(c, forms_txt, detail_txt, variant_index + 1)
    if _line_key(screen_text) == _line_key(cover_text):
        screen_text = _screen_text(c, forms_txt, detail_txt, variant_index + 2)
    screen_text = formats.screen_text(c, forms_txt, _objection_parts(c)[0]) or screen_text
    return dict(image=image, video=video, hook=hook, development=development, cta=cta,
                caption=caption, cover_text=cover_text, screen_text=screen_text,
                variation_index=variant_index)


def package_text(c):
    p = c['prompts']
    blocks = [f"FÁBRICA TIKTOK — CAMPANHA {c['id']:04d}", c['name'],
              f"Modelo: {c['model_name']}\nProduto: {c['product']}\nLook: {c['outfit']} · {c['color']}",
              f"Destino: {c['generator'].upper()} · 9:16 · 15 segundos\nEstado: {c['status']}"]
    if formats.edit_tip(c):
        fmt = formats.FORMATS.get(formats.video_format(c), {}).get('label', 'Técnicas de retenção')
        blocks.append(f"FORMATO: {fmt}\n{formats.edit_tip(c)}")
    if c.get('product_assets'):
        blocks.append('FOTOS DO PRODUTO — anexar após a referência da modelo\n'+'\n'.join(
            f"{i}. {a['original_name']}" for i,a in enumerate(c['product_assets'],1)))
    if c.get('movements'):
        blocks.append(f"MOVIMENTOS DO PRODUTO\n{c['movements']}")
    images = [a for a in c.get('assets', []) if a.get('kind') == 'image']
    if images:
        blocks.append('IMAGENS POR COR\n'+'\n'.join(
            f"- {a.get('slot') or (a.get('metadata') or {}).get('color') or 'sem cor'}: {a.get('original_name')}"
            + (' (aprovada)' if a.get('approved_at') else '')
            for a in images))
    for variant in c.get('variants',[]):
        vp=variant.get('prompts',{})
        blocks.append(f"VARIAÇÃO DE COR — {variant['color']}\n"
                      f"PROMPT DE IMAGEM\n{vp.get('image','')}\n"
                      f"PROMPT DE VÍDEO\n{vp.get('video','')}\n"
                      f"ROTEIRO\n{vp.get('hook','')}\n{vp.get('development','')}\n{vp.get('cta','')}\n"
                      f"LEGENDA\n{vp.get('caption','')}")
    for key, title in [('image', 'PROMPT DE IMAGEM (cor principal)'), ('video', 'PROMPT DE VÍDEO (cor principal)'),
                       ('hook', 'HOOK · 0–4s'), ('development', 'DESENVOLVIMENTO · 4–12s'),
                       ('cta', 'CTA · 12–15s'), ('caption', 'LEGENDA'),
                       ('cover_text', 'TEXTO DA CAPA (colar no CapCut / editor do TikTok)'),
                       ('screen_text', 'TEXTO NA TELA · 0–3s (colar no CapCut / editor do TikTok)')]:
        blocks.append(f"{title}\n{p.get(key, '(ainda não gerado)')}")
    blocks.append('REVISÃO HUMANA\n[ ] Conferir conta da Micaela\n[ ] Subir o MP4 aprovado\n'
                  '[ ] Unir clipes e exportar 1 único MP4 de 15s, se o gerador entregar em partes\n'
                  '[ ] Selecionar o produto manualmente no TikTok Shop\n[ ] Colar e revisar a legenda\n'
                  '[ ] Revisar vídeo, áudio e direitos de uso\n[ ] Publicar manualmente no Studio')
    return '\n\n'.join(blocks) + '\n'
