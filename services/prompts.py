"""Local, deterministic drafts. No paid generation or external API calls."""
import re
import unicodedata


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
    ('decote', ('decote',)),
    ('alça', ('alça', 'alca')),
    ('manga', ('manga',)),
    ('barra', ('barra',)),
    ('recorte', ('recorte',)),
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

_MATERIAL_LABELS = {'poliamida', 'courino', 'algodão', 'lã', 'elastano', 'poliéster'}


def _product_features(c, limit=3):
    """Return only attributes literally present in the user's brief.

    This is deliberately conservative: a local generator is more useful when it
    omits an unconfirmed selling point than when it invents one.
    """
    source = ' '.join(_phrase(c.get(key)).casefold() for key in
                      ('product', 'outfit', 'details', 'angle', 'benefit'))
    # The product description and benefit are authoritative. An angle such as
    # "mostrar bolso" must not turn "legging sem bolso" into a fake feature.
    negative_source = ' '.join(_phrase(c.get(key)).casefold() for key in
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
        return True
    negative = rf'\b(?:sem|não|nao)(?:\s+(?:possui|tem|oferece))?\s+(?:um|uma|o|a)?\s*{escaped}\b'
    return not re.search(negative, source, re.I)


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
    return 'o caimento e os detalhes visíveis', []


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
        'botões': 'os', 'poliamida': 'a', 'courino': 'o', 'algodão': 'o',
        'lã': 'a', 'elastano': 'o', 'poliéster': 'o',
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
    if len(words) > 12:
        # Prefer complete comma-separated claims over cutting a sentence in the
        # middle of a verb ("motiva postar…").
        clauses = [part.strip(' ,;:') for part in raw.split(',') if part.strip(' ,;:')]
        compact = []
        for clause in clauses:
            candidate = ', '.join(compact + [clause])
            if len(candidate.split()) > 12:
                break
            compact.append(clause)
        raw = ', '.join(compact) if compact else ' '.join(words[:12]).rstrip(' ,;:')
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
    return f'A peça tem {raw}'


def _sentence(value):
    value = _phrase(value)
    if not value:
        return ''
    return value if value.endswith(('.', '!', '?')) else value + '.'


def _image_details(details: str) -> str:
    """Keep only visual notes; never leak a shot list or spoken-video brief."""
    text = _pt_br(details)
    if not text:
        return ''
    # Timing beats and action directions belong to the video prompt. Keep the
    # image prompt about the visible subject, product and set only.
    timing = re.compile(r'^\s*\d+(?:[.,]\d+)?\s*[–—-]\s*\d+(?:[.,]\d+)?\s*s?\s*:', re.I)
    video_hints = (
        'vídeo', 'video', '15 segundos', '15s', 'ugc', 'fala', 'frases',
        'jogo de câmera', 'jogo de cameras', 'enquadramento', 'movimentos de ia',
        'movimento', 'agachar', 'caminhar', 'alongar', 'girar', 'senta', 'sentar',
        'shot list', 'câmera fixa', 'camera fixa', 'câmera', 'camera', 'frame',
        'quadro', 'take', 'clipe', 'duração', 'duracao', 'roteiro', 'ação:', 'acao:',
        'prova no corpo', 'produto no frame', 'cta', 'hook', 'fyp', 'query quente',
        'legenda', 'caption', 'loja', 'chamada para ação', 'chamada para acao',
    )
    metadata_hints = ('caption_seed', 'checklist:', 'hook falado', 'howto:', '1 cor =')
    chunks = [part.strip(' .;') for part in re.split(r'(?<=[.!?])\s+|\s*;\s*|\n+|\|', text)]
    kept = [
        part for part in chunks
        if part
        and not timing.search(part)
        and not part.casefold().startswith(('detalhes do briefing:', 'detalhes do briefing'))
        and not any(h in part.casefold() for h in video_hints + metadata_hints)
    ]
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
    """Keep useful operator notes, excluding playbook metadata and shot lists."""
    text = _pt_br(details)
    if not text:
        return ''
    chunks = [part.strip(' .;') for part in re.split(r'(?<=[.!?])\s+|\s*;\s*|\n+|\|', text) if part.strip(' .;')]
    meta = ('howto', 'checklist:', 'shot list:', 'caption_seed:', 'hook falado',
            'legenda sugerida:', 'query quente', '1 cor = 1 mp4')
    timing = re.compile(r'^\s*\d+(?:[.–-]\d+)?s?\s*:', re.I)
    kept = [part for part in chunks if not any(h in part.casefold() for h in meta) and not timing.search(part)]
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
    'estampa': 'abre a peça com as duas mãos, de frente para a lente',
    'alça': 'ajusta a alça com um dedo e solta',
    'decote': 'ajusta a peça no ombro, sem puxar',
    'barra': 'segura a barra da peça e solta',
    'zíper': 'abre e fecha o zíper uma vez',
    'botão': 'toca o botão com a ponta do dedo',
    'botões': 'passa o dedo pelos botões, de cima para baixo',
    'forro': 'afasta a peça levemente do corpo para o forro aparecer',
    'elástico': 'estica a peça rapidamente para um lado e solta',
    'compressão': 'passa a mão na peça já no corpo, sem esticar',
    'secagem rápida': 'passa a mão no tecido, na altura da cintura',
    'gola': 'ajusta a gola com um dedo',
    'punho': 'aproxima o punho da lente',
    'cordão': 'puxa o cordão e solta',
    'capuz': 'ajusta o capuz com uma das mãos, sem erguer os dois braços',
}


def _proof_gestures(features, limit=3):
    """Converte cada fato confirmado no gesto que o demonstra na camera."""
    plan = []
    for label in features or []:
        gesture = _PROOF_GESTURES.get(label)
        if gesture and gesture not in plan:
            plan.append(f'{label} → {gesture}')
        if len(plan) >= limit:
            break
    return plan


_ARM_ACTIONS = ('alongar', 'along', 'braco', 'braço', 'levantar', 'erguer',
                'acenar', 'maos para cima', 'mãos para cima', 'comemor')


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


def _scene_lock(c, fallback='a mesma locação da imagem aprovada'):
    """Extract one positive scene cue and turn it into a continuity constraint."""
    text = _pt_br('. '.join(_phrase(c.get(key)) for key in ('details', 'style') if _phrase(c.get(key))))
    chunks = [part.strip(' .;,:') for part in re.split(r'(?<=[.!?])\s+|\s*;\s*|\n+', text) if part.strip(' .;,:')]
    scene_words = ('cenário', 'cenario', 'fundo', 'ambiente', 'locação', 'locacao',
                   'quarto', 'sala', 'cozinha', 'rua', 'café', 'cafe', 'praia',
                   'piscina', 'academia', 'estúdio', 'estudio', 'varanda', 'deck')
    blocked = ('evitar', 'não usar', 'nao usar', 'sem fundo', 'não desfocar', 'nao desfocar',
               'caption_seed', 'checklist:', 'shot list:', 'hook falado', 'howto')
    for chunk in chunks:
        low = chunk.casefold()
        if any(word in low for word in scene_words) and not any(word in low for word in blocked):
            candidate = ' '.join(chunk.split()[:24])
            # Niche defaults often list alternatives; lock to the first one so
            # each generated colour cannot choose a different location.
            candidate = re.split(r'\s+ou\s+', candidate, maxsplit=1, flags=re.I)[0].strip(' ,;')
            return candidate
    candidate = _phrase(fallback)
    return re.split(r'\s+ou\s+', candidate, maxsplit=1, flags=re.I)[0].strip(' ,;')



def _slug_tag(value, limit=28):
    tag = ''.join(ch for ch in unicodedata.normalize('NFKD', _phrase(value)) if not unicodedata.combining(ch))
    tag = re.sub(r'[^a-zA-Z0-9]', '', tag)
    return tag[:limit]


def _niche_hashtags(c, color):
    """Build product-aware hashtags (TikTok Shop / UGC style, pt-BR)."""
    blob = ' '.join(_phrase(c.get(k)).casefold() for k in ('product', 'outfit', 'audience', 'angle', 'benefit', 'details'))
    color = _phrase(color)
    specific = []
    rules = [
        (('legging', 'calça', 'calca', 'legging'), ['Legging', 'LeggingFitness', 'LookAcademia']),
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
        if any(n in blob for n in needles):
            for t in extra:
                if t not in specific:
                    specific.append(t)
    # Use the readable product nickname, otherwise long catalogue names become
    # broken-looking tags such as #Leggingcinturaaltacombol.
    product_tag = _slug_tag(_product_nick(c.get('product')), 18)
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
        "Produto marcado aqui embaixo.",
        "Confira os detalhes no produto marcado.",
        "Quer? Toque no produto marcado.",
        "Veja a peça no produto marcado.",
        "Confira tamanhos e disponibilidade na loja.",
        "Toque no produto e confira.",
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
        shop_cta = ('Toque no produto marcado e escolha a sua cor.'
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
    product = _pt_br(c.get('product')).casefold()
    outfit = _pt_br(c.get('outfit')).casefold()
    if _is_unisex(c):
        return 'peça'
    # O campo "produto" manda: o "outfit" costuma descrever o look inteiro
    # ("vestido com legging por baixo") e nao a peca que esta sendo vendida.
    for source in (product, outfit):
        for name in _PIECE_WORDS:
            if re.search(r'\b' + re.escape(name) + r'\b', source):
                return name
    return _FAMILY_VOCAB[_product_family(c)]['noun']


def _piece_forms(c):
    piece = _piece_noun(c)
    gender = _PIECE_GENDER.get(piece) or _FAMILY_VOCAB[_product_family(c)]['gender']
    if gender == 'f':
        return dict(piece=piece, art='a', de='da', dem='essa', prep='nessa', pron='ela')
    return dict(piece=piece, art='o', de='do', dem='esse', prep='nesse', pron='ele')


def _objection_parts(c):
    # Retorna (dor, verificacao) a partir do campo de objecao do briefing.
    raw = _phrase(c.get('objection'))
    if not raw or _is_meta_field(raw):
        return '', ''
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


def _dominant_motor(c):
    if _objection_parts(c)[0]:
        family = _product_family(c)
        if family != 'moda':
            return 'necessidade'
        if (c.get('niche') or '') in ('academia', 'dia-a-dia'):
            return 'necessidade'
        return 'necessidade'
    return 'desejo'


def _count_words(text):
    return len([w for w in _phrase(text).split() if w])


def _pick_in_budget(candidates, index, low, high):
    # Prefere as opcoes dentro do orcamento falado; se nenhuma couber, usa a mais curta.
    clean = [c for c in candidates if _phrase(c)]
    if not clean:
        return ''
    fits = [c for c in clean if low <= _count_words(c) <= high]
    if not fits:
        # Nenhum candidato coube: usa os mais proximos da faixa, nao os mais
        # curtos - um hook curto demais vira rotulo e nao prende ninguem.
        def distance(item):
            n = _count_words(item)
            return low - n if n < low else (n - high if n > high else 0)
        fits = sorted(clean, key=distance)[:3]
    return fits[int(index or 0) % len(fits)]


def _hook_pool(c, detail, forms):
    # Orcamento do hook: 10 a 12 palavras (4s a 2,8 palavras por segundo).
    dem, prep, piece, art = forms['dem'], forms['prep'], forms['piece'], forms['art']
    det = _phrase(detail)
    det_em = _with_em(det)
    pain, _check = _objection_parts(c)
    offer = _offer_text(c)
    desejo = [
        f'Olha {det} com {art} {piece} em movimento, bem de perto.',
        f'É {det} que muda o visual inteiro {prep} {piece}.',
        f'Antes de escolher {dem} {piece}, repara {det_em} com calma.',
        f'Vale olhar {det} bem de perto antes de decidir.',
        f'O que decide {prep} {piece} é {det}. Olha só.',
        f'Poucas pessoas reparam {det_em}, e é o que muda tudo.',
    ]
    necessidade = []
    if pain:
        necessidade = [
            f'Se você já desistiu {forms["de"]} {piece} por {pain}, olha isto.',
            f'O que mais segura a compra costuma ser {pain}. Olha isto.',
            f'Como saber se vai {pain}? Repara {det_em} agora.',
            f'Cansou de {pain}? Então olha {det} com atenção.',
        ]
    escassez = []
    if offer:
        escassez = [
            f'{_sentence(offer[0].upper() + offer[1:])} Olha {det} antes de acabar.',
            f'Antes de acabar: {offer}. Repara {det_em}.',
        ]
    motor = _dominant_motor(c)
    order = {
        'necessidade': [necessidade, desejo, escassez],
        'desejo': [desejo, necessidade, escassez],
    }[motor]
    if offer:
        order.insert(1, escassez)
    pool = []
    for group in order:
        for item in group:
            if item and item not in pool:
                pool.append(item)
    return pool


def _development_line(c, detail, features, forms, index):
    # Tres batidas: prova (4-6s), objecao quebrada (6-10s), posse (10-12s).
    # Orcamento total: 20 a 24 palavras. Se estourar, cai a posse primeiro -
    # a prova nunca e descartada.
    feats = list(features or [])
    benefit_preview = _benefit_clause(c).casefold()
    # Se o beneficio ja cita o primeiro fato, a prova usa o segundo. Repetir a
    # mesma palavra em duas batidas queima segundos sem acrescentar argumento.
    if feats and len(feats) > 1 and feats[0].casefold() in benefit_preview:
        det = _with_article(feats[1])
    else:
        det = _phrase(detail)
    det_em = _with_em(det)
    provas = [
        f'Olha {det} de perto.',
        f'Repara {det_em} com calma.',
        f'Aqui aparece {det}.',
        f'Começa {det_em}.',
    ]
    prova = provas[int(index or 0) % len(provas)]
    _pain, check = _objection_parts(c)
    benefit = _benefit_clause(c)
    benefit_text = re.sub(r'^A peça\s+', '', benefit, flags=re.I).strip().rstrip('.')
    if check:
        meio = _sentence(check)
    elif benefit_text:
        if re.match(r'^(é|são|tem|têm|possui|oferece|veste|valoriza|ajuda|permite|seca|fica|deixa|traz|renova|combina|economiza|melhora|entrega)\b', benefit_text, re.I):
            meio = _sentence(f'{forms["dem"].capitalize()} {forms["piece"]} {benefit_text}')
        else:
            meio = _sentence(f'{forms["dem"].capitalize()} {forms["piece"]} tem {benefit_text}')
    else:
        meio = ''
    occasion = _NICHE_OCCASION.get((c.get('niche') or '').strip(), '')
    posse = _sentence(f'Dá para usar {occasion}') if occasion else ''
    beats = [b for b in (_sentence(prova), meio, posse) if b]
    while len(beats) > 1 and _count_words(' '.join(beats)) > 24:
        beats.pop()
    return ' '.join(beats)


def _cta_pool(c, forms):
    # Orcamento do CTA: 7 a 9 palavras.
    piece, dem, art = forms['piece'], forms['dem'], forms['art']
    colors = color_variants(c.get('color'))
    pain, _check = _objection_parts(c)
    offer = _offer_text(c)
    direto = [
        'Toque no produto marcado e confira os detalhes.',
        'Toque no produto marcado e veja os tamanhos.',
        f'Quer {art} {piece}? Está no produto marcado.',
    ]
    if len(colors) > 1:
        direto = [
            'Toque no produto marcado e escolha a sua cor.',
            'As cores estão todas no produto marcado.',
            'Escolha a sua cor no produto marcado.',
        ] + direto
    condicional = [f'Se isso te incomoda, está no produto marcado.'] if pain else []
    escassez = [_sentence(f'{offer}. Confira no produto marcado')] if offer else []
    posse = [
        'Pega a sua no produto marcado.',
        f'Leve {dem} {piece} pelo produto marcado.',
    ]
    motor = _dominant_motor(c)
    order = ([condicional, direto, posse] if motor == 'necessidade' else [posse, direto, condicional])
    if offer:
        order.insert(0, escassez)
    pool = []
    for group in order:
        for item in group:
            if item and item not in pool:
                pool.append(item)
    return pool


def _script_variation(c, color, index=0):
    # Constroi as tres falas a partir de evidencia explicita do briefing.
    # A cor NAO entra no hook: o espectador ja a ve na tela, e cada palavra do
    # hook vale ~0,36s. Ela permanece na legenda e no prompt de imagem.
    forms = _piece_forms(c)
    focus, features = _focus_parts(c)
    hook_detail = _with_article(features[0] if features else (focus or 'o caimento'))
    detail = _with_article(focus if focus else 'o caimento')
    i = int(index or 0)

    selected_hook = _pick_in_budget(_hook_pool(c, hook_detail, forms), i, 10, 13)
    selected_development = _development_line(c, detail, features, forms, i)
    selected_cta = _pick_in_budget(_cta_pool(c, forms), i, 6, 10)

    # Teto absoluto de 45 palavras faladas (~15s). Se estourar, encurta o
    # desenvolvimento pela ultima batida, nunca pela prova.
    def total():
        return _count_words(' '.join((selected_hook, selected_development, selected_cta)))
    if total() > 45:
        sentences = [p.strip() for p in re.split(r'(?<=[.!?])\s+', selected_development) if p.strip()]
        while len(sentences) > 1 and total() > 45:
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
        'hook': dict(words=_count_words(hook), low=10, high=12),
        'development': dict(words=_count_words(development), low=20, high=24),
        'cta': dict(words=_count_words(cta), low=7, high=9),
        'total': dict(words=_count_words(' '.join((hook, development, cta))), low=38, high=45),
    }


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
    # Refreshing only the caption must preserve an edited video prompt. Rebuild
    # video only when a spoken line actually changed.
    if set(fields) & {'hook', 'development', 'cta'}:
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
        "camera": "aproximação suave; giro de 180 graus; detalhe de perto na barra, bolso ou textura; caminhada frontal falando com a câmera",
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


def _build_video_prompt(c, *, resolution, color, product, benefit, movements, details, hook, development, cta):
    niche = _niche_key(c)
    dirn = _VIDEO_NICHE.get(niche) or _VIDEO_NICHE["casual"]
    outfit = _pt_br(c.get("outfit")) or "visual do produto"
    angle = _pt_br(c.get("angle")) or "mostrar o produto em uso"
    angle_context = ' '.join(angle.split()[:16])
    if len(angle.split()) > 16:
        angle_context += '…'
    style = _pt_br(c.get("style")) or "natural e realista"
    tone = _pt_br(c.get("tone")) or "conversacional"
    model = _phrase(c.get("model_name")) or "a modelo"
    color_l = _phrase(color) or "a cor escolhida"
    product_l = product or "o produto"
    benefit_l = _phrase(benefit)
    benefit_l = re.sub(r'^A peça\s+', '', benefit_l, flags=re.I).strip()
    benefit_l = benefit_l or "somente fatos visíveis da peça"
    moves = _movement_plan(movements) or "movimentos naturais que mostrem o caimento"
    video_notes = _video_details(details)
    extras = f" Notas adicionais do operador (não são falas): {video_notes}." if video_notes else ""
    focus, features = _focus_parts(c)
    facts = ', '.join(features) if features else focus
    materials = ', '.join(_material_facts(c)) or 'não especificada'
    gender_note = ' Modelagem unissex: manter a peça neutra e fiel à referência.' if _is_unisex(c) else ''
    scene_lock = _scene_lock(c, fallback=dirn['setting'])
    forms = _piece_forms(c)
    anchor = 'o cós' if forms['piece'] in ('legging', 'calça', 'short', 'saia', 'bermuda') else 'a barra'
    gestures = _proof_gestures(_product_features(c, limit=4))
    proof_block = (
        'PROVA VISUAL — cada fato abaixo precisa do seu gesto correspondente, executado entre 4s e 11s: '
        + '; '.join(gestures) + '.\n'
    ) if gestures else ''
    closing_hands = (
        f"com as duas mãos tocando {anchor} {forms['de']} {forms['piece']}, "
        "como quem ajusta a peça, ou apoiadas na cintura"
    )

    return (
        f"UGC TikTok Shop vertical 9:16, exatamente 15 segundos, {resolution}. "
        f"ANEXE a IMAGEM APROVADA da cor {color_l} como primeiro quadro e referência contínua. "
        f"A modelo é {model}: preserve 100% o mesmo rosto, cabelo, pele e corpo em TODOS os quadros "
        f"(sem transformação de rosto, troca de identidade ou redesenho). "
        f"Produto em cena: {product_l} na cor {color_l}. Visual: {outfit}.{gender_note} "
        f"Ângulo de venda (contexto, não criar atributos): {angle_context}. FATOS CONFIRMADOS: {facts}. "
        f"MATERIAL / COMPOSIÇÃO CONFIRMADA: {materials}. "
        f"Benefício a provar visualmente, somente se estiver demonstrável: {benefit_l}.\n"
        f"CENÁRIO FIXO ({niche}, todos os frames e variações de cor): {scene_lock}. "
        f"Repetir exatamente fundo, objetos, posição da câmera, distância, perspectiva e iluminação; não trocar a locação nem desfocar o fundo. "
        f"CÂMERA: {dirn['camera']}. "
        f"DETALHE PRINCIPAL: {focus}. CONTEXTO VISUAL OPCIONAL (não é fato do produto; não inventar): {dirn['must_show']}. "
        f"EVITAR: {dirn['avoid']}; textos na tela; marcas inventadas; cortes que quebrem continuidade.\n"
        f"{proof_block}"
        "MÃOS: uma das mãos mantém contato com a peça o tempo todo (na cintura, no cós ou na barra) e a outra é a que mostra os detalhes. "
        "As duas nunca ficam soltas ao mesmo tempo. "
        f"COREOGRAFIA / AÇÕES (executar nesta ordem, TODAS entre 0s e 11s; no máximo uma ação por beat, ritmo natural): {moves}. "
        f"ENCERRAMENTO (12–15s), posição obrigatória: a modelo está de frente para a lente, {closing_hands}. "
        "As mãos permanecem ocupadas nessa posição até o último quadro, na altura da cintura ou abaixo dela. "
        "O corpo fica parado e estável; apenas o rosto e o olhar se movem."
        f"{extras}\n"
        f"SHOT LIST 15s — executar como um único take contínuo ou cortes invisíveis:\n"
        f"0–4s HOOK: a modelo se aproxima um passo da câmera, como quem vai contar um segredo; plano médio frontal, "
        f"olhar na lente, produto já visível no corpo e a mão apontando a peça. Fala (PT-BR): \"{hook}\"\n"
        f"4–12s DESENVOLVIMENTO — uma única fala, dita de forma contínua e natural neste intervalo; "
        f"não repetir, não antecipar e não dividir em dois trechos. Fala (PT-BR): \"{development}\"\n"
        f"   · 4–6s PROVA 1 (somente câmera, sem nova fala): aproxima OU mostra de perto o detalhe que vende "
        f"(tecido, cós, alça, barra, acessório); mãos tocam o produto de forma natural.\n"
        f"   · 6–11s PROVA 2 (somente câmera, sem nova fala): movimento completo que demonstra o benefício ({benefit_l}) — "
        f"caminhar/girar/sentar/agachar conforme a coreografia. Manter cor {color_l} e caimento fiéis.\n"
        f"   · 11–12s DESEJO (somente câmera, sem nova fala): plano médio, sorriso confiante, 1 detalhe hero em destaque.\n"
        f"12–15s CTA: manter a posição de encerramento descrita acima, olhar firme na lente; o produto marcado é indicado apenas com o olhar. Fala (PT-BR): \"{cta}\"\n"
        f"ATRIBUTOS NÃO CONFIRMADOS: não inventar compressão, elasticidade, conforto, maciez, tecido premium, secagem, suporte, impermeabilidade, composição ou qualquer benefício ausente nos FATOS CONFIRMADOS. Se houver material confirmado, preservar textura, brilho e comportamento; não substituí-lo por outro. "
        "ENQUADRAMENTO: não altere o enquadramento entre os beats; use jogo de câmeras apenas se for necessário, mantendo a mesma cena. "
        "Realize movimentos laterais quando precisar mostrar o produto completo no corpo. "
        "Evite movimentos artificiais de IA: as expressões e os gestos acompanham as falas, no ritmo delas. "
        "As três falas formam um único discurso contínuo, dito pela mesma pessoa sem pausa artificial entre os trechos. "
        f"Estilo visual: {style}. Tom de performance: {tone}. "
        f"Áudio: voz clara em português do Brasil, ritmo de leitura em voz alta (sem correr). "
        f"Fale somente as três falas entre aspas, palavra por palavra; nunca leia títulos, instruções, movimentos, câmera, shot list, notas ou textos de interface. "
        f"Total das falas fornecidas: {len((hook + ' ' + development + ' ' + cta).split())} palavras; se ultrapassar 15s em leitura natural, sinalize para revisão em vez de acelerar. "
        f"Sem promessas não demonstradas no vídeo. "
        f"Se o gerador entregar clipes curtos, una na ordem acima e exporte 1 MP4 de 15s antes de anexar."
    )


def generate_variants(c):
    colors = color_variants(c.get('color'))
    # A primeira cor cria a fotografia-base; as seguintes sao edicao localizada
    # dessa base, o que mantem cenario, pose e enquadramento identicos.
    return [{'color': color, 'prompts': generate({**c, 'color': color}, variant_index=index, base_image=index > 0)}
            for index, color in enumerate(colors)]


def generate(c, script=None, variant_index=0, base_image=False):
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
    identity = (
        f"Use a imagem anexada de {c['model_name']} como referência visual fixa. "
        'Preserve rigorosamente rosto, cabelo, tom de pele, corpo, idade aparente e proporções. '
        'Somente a roupa e sua cor podem mudar na aparência da modelo. '
        'Não substitua a pessoa nem redesenhe sua identidade. '
    )
    photos=c.get('product_assets',[])
    product_reference=''
    if photos:
        photo_word = 'foto' if len(photos) == 1 else 'fotos'
        product_reference=(
            f"Anexe primeiro a referência fixa de {c['model_name']} e depois {len(photos)} {photo_word} do produto. "
            f'As fotos do produto representam: {product}. Use-as para reproduzir o corte, '
            'o caimento, as costuras, os acabamentos e os detalhes visíveis da peça. '
            'Pessoas presentes nas fotos do produto NÃO são referências de identidade: '
            'não copie seu rosto, cabelo, corpo, pose ou tom de pele. '
            f"A cor final solicitada é {c['color']}; ela prevalece sobre fotos com outras cores. "
            "Não reproduza fundos, textos sobrepostos nem marcas d'água das fotos de catálogo. "
        )
    details = _pt_br(c.get('details'))
    confirmed_features = _product_features(c)
    facts_for_image = ', '.join(confirmed_features) if confirmed_features else 'somente os detalhes visíveis nas fotos do produto'
    materials_for_image = ', '.join(_material_facts(c)) or 'não especificada'
    details_for_image = _image_details(details)
    angle_context = _image_angle(c.get('angle'))
    angle_context_words = angle_context.split()
    if len(angle_context_words) > 16:
        angle_context = ' '.join(angle_context_words[:16]) + '…'
    scene_lock = _scene_lock(c)
    forms = _piece_forms(c)
    piece_ref = f"{forms['art']} {forms['piece']}"
    # Dois modos incompativeis nao podem conviver no mesmo prompt. Na primeira
    # cor ainda nao existe imagem aprovada: pedir "edicao localizada" de uma
    # foto-base inexistente derruba a adesao do modelo a todas as instrucoes.
    if base_image:
        mode_block = (
            "EDIÇÃO LOCALIZADA: trate a imagem aprovada desta campanha como a fotografia-base final, não como inspiração para uma nova cena. "
            "Preserve exatamente a mesma modelo, pose, expressão, posição das mãos, cabelo, rosto, corpo, peças complementares, calçados, enquadramento, distância da câmera, perspectiva, cenário, objetos, sombras, reflexos, profundidade, iluminação, granulação e qualidade fotográfica. "
            f"Altere somente a área ocupada por {piece_ref}, mantendo todo o restante da imagem visualmente idêntico. "
            "Não redesenhe a pessoa, não mude a pose, não reposicione membros, não altere as peças complementares, não crie outro ângulo e não gere uma nova fotografia. "
        )
    else:
        mode_block = (
            "FOTOGRAFIA NOVA A PARTIR DA REFERÊNCIA: esta é a primeira imagem da campanha. "
            "Gere uma fotografia inédita usando a referência anexada apenas como fonte de identidade da modelo. "
            f"Enquadre a pessoa inteira ou até os joelhos, com {piece_ref} claramente visível e bem iluminada. "
            "Pose natural e estável, mãos corretas, olhar na câmera ou levemente para o lado. "
            "Esta imagem será a base fotográfica das outras cores: escolha um enquadramento que possa ser repetido. "
        )
    image = (
        identity + product_reference + f"Roupa: {_pt_br(c['outfit'])}. Cor: {c['color']}. Produto: {product}. "
        + mode_block
        + f"VARIAÇÃO ÚNICA: gere somente esta cor ({c['color']}); não misture cores nem crie outras versões na mesma imagem. "
        f"FATOS DO PRODUTO A PRESERVAR: {facts_for_image}. "
        f"MATERIAL / COMPOSIÇÃO CONFIRMADA: {materials_for_image}; preservar textura, brilho e caimento sem substituir por outro material. "
        f"FOCO VISUAL: {_focus_parts(c)[0]}. "
        + ('MODELAGEM: unissex. ' if _is_unisex(c) else '')
        + f"CENÁRIO FIXO: {scene_lock}. Repetir exatamente o mesmo fundo, objetos, enquadramento, perspectiva e iluminação em todas as cores; fundo nítido, sem desfoque e sem substituição. "
        + ("Use a imagem aprovada da campanha como referência do cenário, sem copiar a cor da roupa. " if base_image else "")
        + ("INTEGRAÇÃO FOTOGRÁFICA: a peça substituída deve acompanhar exatamente a anatomia e a pose já existentes, com caimento, dobras, tensão do tecido, oclusão correta pelas mãos e pelo corpo, sombras de contato, reflexos e luz coerentes com a fotografia-base. A borda da roupa deve estar natural, sem aparência de recorte, colagem ou pintura por cima. " if base_image else "")
        + "Contexto de comunicação (não inserir texto nem inventar atributo): "
        f"público {_pt_br(c['audience']) or 'geral'}; ângulo {angle_context or 'mostrar detalhes do produto'}. "
        f"Estilo: {_pt_br(c['style']) or 'natural e realista'}. Tom: {_pt_br(c['tone']) or 'conversacional'}. "
        'Fotografia vertical 9:16, luz suave, anatomia natural, mãos corretas. '
        'Mantenha o produto fiel à referência; sem textos, marcas inventadas ou deformações. '
        + (f'Detalhes do briefing: {details_for_image}.' if details_for_image else
           'Apenas uma imagem estática; não descreva vídeo, falas nem duração.')
    )
    resolution = '1080 × 1920 (1080p)' if c['generator'] == 'flow' else '720 × 1280 (720p)'
    video = _build_video_prompt(
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
    )
    caption = build_caption(c, color=color, cta=None, variation_index=variant_index)
    return dict(image=image, video=video, hook=hook, development=development, cta=cta, caption=caption, variation_index=variant_index)


def package_text(c):
    p = c['prompts']
    blocks = [f"FÁBRICA TIKTOK — CAMPANHA {c['id']:04d}", c['name'],
              f"Modelo: {c['model_name']}\nProduto: {c['product']}\nLook: {c['outfit']} · {c['color']}",
              f"Destino: {c['generator'].upper()} · 9:16 · 15 segundos\nEstado: {c['status']}"]
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
                       ('cta', 'CTA · 12–15s'), ('caption', 'LEGENDA')]:
        blocks.append(f"{title}\n{p.get(key, '(ainda não gerado)')}")
    blocks.append('REVISÃO HUMANA\n[ ] Conferir conta da Micaela\n[ ] Subir o MP4 aprovado\n'
                  '[ ] Selecionar o produto manualmente no TikTok Shop\n[ ] Colar e revisar a legenda\n'
                  '[ ] Revisar vídeo, áudio e direitos de uso\n[ ] Publicar manualmente no Studio')
    return '\n\n'.join(blocks) + '\n'
