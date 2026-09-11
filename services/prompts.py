"""Local, deterministic drafts. No paid generation or external API calls."""
import re
import unicodedata


def _phrase(value):
    return ' '.join(str(value or '').strip().rstrip('.').split())


def _focus(c):
    """Pick concrete attributes that are actually present in the briefing."""
    source = ' '.join(_phrase(c.get(key)).casefold() for key in ('product', 'outfit', 'details', 'angle'))
    angle = _phrase(c.get('angle')).casefold()
    angle = re.sub(r'^(mostrar|mostre|destacar|destaque|focar em)\s+', '', angle)
    if angle and angle not in {'detalhes', 'os detalhes', 'o caimento e os detalhes', 'caimento e detalhes'}:
        return angle
    known = ('cintura alta', 'cintura média', 'cintura baixa', 'bolso lateral', 'bolso interno',
             'tecido leve', 'tecido macio', 'tecido encorpado', 'caimento', 'cós largo',
             'recorte', 'costura', 'alça', 'decote', 'manga', 'barra', 'secagem rápida',
             'compressão', 'sem transparência', 'estampa', 'acabamento')
    found=[]
    for item in known:
        if item in source and item not in found:
            found.append(item)
    if found:
        return ' e '.join(found[:3])
    if angle:
        return angle
    return 'o caimento e os detalhes da peça'



def _slug_tag(value, limit=28):
    tag = ''.join(ch for ch in unicodedata.normalize('NFKD', _phrase(value)) if not unicodedata.combining(ch))
    tag = re.sub(r'[^a-zA-Z0-9]', '', tag)
    return tag[:limit]


def _niche_hashtags(c, color):
    """Build product-aware hashtags (TikTok Shop / UGC style, pt-BR)."""
    blob = ' '.join(_phrase(c.get(k)).casefold() for k in ('product', 'outfit', 'audience', 'angle', 'benefit', 'details'))
    color = _phrase(color)
    tags = ['Achadinhos', 'TikTokShop', 'AchadinhoTikTok', 'ForYou']
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
                if t not in tags:
                    tags.append(t)
    product_tag = _slug_tag(c.get('product'), 24)
    color_tag = _slug_tag(color, 16)
    if product_tag and product_tag not in tags:
        tags.insert(0, product_tag)
    if color_tag:
        tags.append(color_tag)
    # Keep caption readable: 5 tags max
    uniq = []
    for t in tags:
        if t and t not in uniq:
            uniq.append(t)
    return uniq[:5]


def build_caption(c, color=None, cta=None, variation_index=0):
    """Natural TikTok caption aligned to product + color + benefit."""
    product = _phrase(c.get('product'))
    benefit = _phrase(c.get('benefit')).rstrip('.')
    audience = _phrase(c.get('audience'))
    focus = _focus(c)
    color = _phrase(color or c.get('color')) or 'essa cor'
    cta = _phrase(cta) or 'Toque no produto marcado e confira.'
    openings = [
        f'{product} na cor {color}  -  {benefit}.',
        f'Olha o caimento dessa {product.lower()} {color}: {benefit}.',
        f'Pra quem busca {focus}: {product} {color}.',
        f'{color} ficou incrível nessa {product.lower()}. {benefit}.',
        f'Achadinho: {product} ({color}). {benefit}.',
        f'Se você é {audience.lower()}, essa {product.lower()} {color} é pra você.' if audience else f'{product} {color} no corpo real. {benefit}.',
    ]
    bridges = [
        f'Destaque em {focus}.',
        'Testei no corpo real, sem filtro de catálogo.',
        'UGC direto do dia a dia.',
        f'Ideal para {audience.lower()}.' if audience else 'Fácil de combinar no dia a dia.',
    ]
    i = int(variation_index or 0)
    body = f'{openings[i % len(openings)]} {bridges[i % len(bridges)]} {cta}'
    tags = ' '.join(f'#{t}' for t in _niche_hashtags(c, color))
    return f'{body} {tags}'.replace('  ', ' ').strip()


def color_variants(value):
    """Split a color field into stable, unique variants in user-entered order."""
    variants=[]
    for item in re.split(r'[,;\n|]+', str(value or '')):
        item=_phrase(item)
        if item and item.casefold() not in {old.casefold() for old in variants}:
            variants.append(item)
    return variants


def _script_variation(c, color, index=0):
    """Build hook/development/CTA that feel different per color."""
    product = _phrase(c['product'])
    benefit = _phrase(c['benefit'])
    audience = _phrase(c.get('audience'))
    focus = _focus(c)
    color = _phrase(color) or _phrase(c.get('color')) or 'essa cor'
    # Keep catalogue titles out of the opening sentence: a hook has about 4s.
    piece = next((name for name in ('legging', 'vestido', 'conjunto', 'camiseta', 'blusa', 'calça', 'saia', 'short', 'top')
                  if re.search(r'\b'+name+r'\b', product.casefold())), 'look')
    feminine = piece in {'legging', 'camiseta', 'blusa', 'calça', 'saia'}
    demonstrative = 'essa' if feminine else 'esse'
    contracted = 'nessa' if feminine else 'nesse'
    possessive = 'sua' if feminine else 'seu'
    hooks = [
        f'Quer ver {demonstrative} {piece} no corpo? Repara no caimento em {color}.',
        f'Como fica {demonstrative} {piece} em movimento? Olha a versão em {color}.',
        f'Pensando {contracted} {piece}? Veja de perto como fica na cor {color}.',
        f'Você usaria {demonstrative} {piece} em {color}? Olha os detalhes no corpo.',
        f'Antes de escolher {possessive} {piece}, confira o caimento desta versão em {color}.',
        f'O que observar {contracted} {piece}? Veja o acabamento e a cor {color}.',
    ]
    developments = [
        f'Em {color}, ela {benefit.lower()}. Veja {focus} e o caimento em movimento.',
        f'A versão {color} destaca {focus}. Ela {benefit.lower()}.',
        f'Olha o movimento em {color}: {focus}, sem marcar demais.',
        (f'Para {audience.lower()}, o {color} {benefit.lower()}. Veja {focus}.'
         if audience else f'O {color} {benefit.lower()}. Veja {focus}.'),
        f'Detalhe a detalhe na peça {color}: {focus}. Ela {benefit.lower()}.',
        f'Giro completo na {color}: caimento, bolso e acabamento. Ela {benefit.lower()}.',
    ]
    ctas = [
        'Gostou? Toque no produto marcado e confira essa cor.',
        f'Quer a {color}? Toque no produto marcado.',
        'Salva e toca no produto marcado pra ver as cores.',
        'Comenta a cor favorita e toca no produto marcado.',
        'Toque no produto marcado e escolhe a sua cor.',
        'Link no produto marcado  -  tem essa e outras cores.',
    ]
    i = index % len(hooks)
    return hooks[i], developments[i], ctas[i]


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
        merged['caption'] = build_caption({**c, 'color': color}, color=color, cta=merged.get('cta'), variation_index=index)
    # Always rebuild video prompt from the new falas
    merged['video'] = generate({**c, 'color': color}, script=merged, variant_index=index)['video']
    if 'image' not in merged and fresh.get('image'):
        merged['image'] = fresh['image']
    merged['variation_index'] = index
    return merged



# Niche-specific video direction for Flow/Grok (concrete beats, not vague adjectives).
_VIDEO_NICHE = {
    "praia": {
        "setting": "praia, deck de piscina ou varanda ensolarada; fundo com luz natural e leve movimento de vento",
        "camera": "handheld UGC leve; plano medio na abertura; close no tecido ao vento; orbit curta no corpo; final em plano medio frontal",
        "must_show": "caimento molhado/leve do tecido, brilho do sol na peca, movimento real ao caminhar na areia/deck",
        "avoid": "estudio frio, pose estatica demais, morphing de rosto, logos inventados",
    },
    "academia": {
        "setting": "academia limpa ou outdoor fitness crivel; luz clara e energetica",
        "camera": "plano medio dinamico; low-angle curto no agachamento; close no cos/tecido stretch; tracking ao caminhar ate a camera",
        "must_show": "compressao/elasticidade em movimento (agachar, alongar, caminhar), suporte do top/legging, suor leve natural",
        "avoid": "maquina vazia sem acao, deformacao anatomica, rosto mudando entre cortes",
    },
    "casual": {
        "setting": "rua, cafe ou quarto com luz natural; visual street realista",
        "camera": "push-in suave; giro 180 graus; close na barra/bolso/textura; walk-and-talk frontal",
        "must_show": "como a peca cai no corpo em movimento urbano, textura do tecido, detalhe que vende (barra, costura, bolso)",
        "avoid": "fundo genérico borrado sem contexto, gestos roboticos, troca de identidade",
    },
    "dia-a-dia": {
        "setting": "casa real (quarto/cozinha/sala) com luz de janela suave",
        "camera": "plano medio caseiro; close na textura ao sentar/levantar; travelling curto pela casa; final frontal calmo",
        "must_show": "conforto real (sentar, levantar, caminhar), tecido macio em close, rotina crivel em 15s",
        "avoid": "cena de studio fashion, exagero de poses, mudanca de rosto/cabelo",
    },
    "intima": {
        "setting": "quarto premium ou canto de estudio com luz quente suave; clima elegante",
        "camera": "plano medio frontal; pan lento para o lado; close no tecido/renda/ajuste; retorno ao rosto confiante",
        "must_show": "caimento que valoriza sem vulgaridade, textura do tecido, ajuste de alca/fecho, poses seguras",
        "avoid": "nudez, zoom agressivo, poses explicitas, troca de identidade, filtros plasticos",
    },
    "fantasia": {
        "setting": "cenario tematico coerente com a fantasia (quarto preparado, luz colorida ou festa simples)",
        "camera": "revelacao em plano medio; giro dramatico; close em acessorio (asa, cinto, peruca); pose iconica final",
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
    outfit = _phrase(c.get("outfit")) or "look do produto"
    angle = _phrase(c.get("angle")) or "mostrar o produto em uso"
    style = _phrase(c.get("style")) or "natural e realista"
    tone = _phrase(c.get("tone")) or "conversacional"
    model = _phrase(c.get("model_name")) or "a modelo"
    color_l = _phrase(color) or "a cor escolhida"
    product_l = product or "o produto"
    benefit_l = benefit or "o beneficio principal"
    moves = movements or "movimentos naturais que mostrem o caimento"
    extras = f" Instruções extras do briefing: {details}." if details else ""

    return (
        f"UGC TikTok Shop vertical 9:16, exatamente 15 segundos, {resolution}. "
        f"ANEXE a IMAGEM APROVADA da cor {color_l} como primeiro frame / referência contínua. "
        f"A modelo é {model}: preserve 100% o mesmo rosto, cabelo, pele e corpo em TODOS os frames "
        f"(sem morphing, sem face swap, sem redesign). "
        f"Produto em cena: {product_l} na cor {color_l}. Look: {outfit}. "
        f"Ângulo de venda: {angle}. Benefício a provar visualmente: {benefit_l}.\n"
        f"CENÁRIO ({niche}): {dirn['setting']}. "
        f"CÂMERA: {dirn['camera']}. "
        f"OBRIGATÓRIO mostrar: {dirn['must_show']}. "
        f"EVITAR: {dirn['avoid']}; textos na tela; marcas inventadas; cortes que quebrem continuidade.\n"
        f"COREOGRAFIA / AÇÕES (usar nesta ordem, ritmo natural): {moves}.{extras}\n"
        f"SHOT LIST 15s — executar como um único take contínuo ou cortes invisíveis:\n"
        f"0–4s HOOK: plano médio frontal, olhar na lente, produto já visível no corpo; "
        f"micro-gesto que aponta/mostra a peça. Fala (PT-BR): \"{hook}\"\n"
        f"4.0–6.0s PROVA 1: câmera se aproxima OU close no detalhe que vende (tecido, cós, alça, barra, acessório). "
        f"Mãos tocam o produto de forma natural. Iniciar a fala do desenvolvimento, distribuída entre 4 e 12s.\n"
        f"6.0–11.0s PROVA 2: movimento completo que demonstra o benefício ({benefit_l}) — "
        f"caminhar/girar/sentar/agachar conforme a coreografia. Manter cor {color_l} e caimento fiéis. "
        f"Fala (PT-BR): \"{development}\"\n"
        f"11.0–12.0s DESEJO: plano médio de novo, sorriso confiante, 1 detalhe hero do produto em destaque.\n"
        f"12–15s CTA: gesto leve para a câmera / produto marcado. Fala (PT-BR): \"{cta}\"\n"
        f"Estilo visual: {style}. Tom de performance: {tone}. "
        f"Áudio: voz clara em português do Brasil, ritmo de leitura em voz alta (sem correr). "
        f"Sem promessas não demonstradas no vídeo. "
        f"Se o gerador entregar clipes curtos, una na ordem acima e exporte 1 MP4 de 15s antes de anexar."
    )


def generate_variants(c):
    colors = color_variants(c.get('color'))
    return [{'color': color, 'prompts': generate({**c, 'color': color}, variant_index=index)}
            for index, color in enumerate(colors)]


def generate(c, script=None, variant_index=0):
    # Always treat color as a single variant for one image/video package.
    colors = color_variants(c.get('color'))
    if len(colors) > 1:
        c = {**c, 'color': colors[0]}
    product = _phrase(c['product'])
    benefit = _phrase(c['benefit'])
    movements = _phrase(c.get('movements')) or 'movimentos sutis e naturais que mostrem o caimento da peça'
    color = _phrase(c.get('color'))
    hook, development, cta = _script_variation(c, color, variant_index)
    if script:
        hook = _phrase(script.get('hook', hook))
        development = _phrase(script.get('development', development))
        cta = _phrase(script.get('cta', cta))
    identity = (
        f"Use a imagem anexada de {c['model_name']} como referência visual fixa. "
        'Preserve rigorosamente rosto, cabelo, tom de pele, corpo, idade aparente e proporções. '
        'Somente a roupa e sua cor podem mudar na aparência da modelo. '
        'Não substitua a pessoa nem redesenhe sua identidade. '
    )
    photos=c.get('product_assets',[])
    product_reference=''
    if photos:
        product_reference=(
            f"Anexe primeiro a referência fixa de {c['model_name']} e depois as {len(photos)} fotos do produto. "
            f'As fotos do produto representam: {product}. Use-as para reproduzir o corte, '
            'o caimento, as costuras, os acabamentos e os detalhes visíveis da peça. '
            'Pessoas presentes nas fotos do produto NÃO são referências de identidade: '
            'não copie seu rosto, cabelo, corpo, pose ou tom de pele. '
            f"A cor final solicitada é {c['color']}; ela prevalece sobre fotos com outras cores. "
            "Não reproduza fundos, textos sobrepostos nem marcas d'água das fotos de catálogo. "
        )
    details = _phrase(c.get('details'))
    video_detail_hints = ('vídeo', 'video', '15 segundos', '15s', 'ugc', 'fala', 'frases',
                          'jogo de câmera', 'jogo de cameras', 'enquadramento', 'movimentos de ia')
    details_for_image = details
    if details and any(h in details.casefold() for h in video_detail_hints):
        details_for_image = ''
    image = (
        identity + product_reference + f"Roupa: {c['outfit']}. Cor: {c['color']}. Produto: {product}. "
        f"Público: {c['audience']}. Ângulo de comunicação: {c['angle'] or 'mostrar detalhes do produto'}. "
        f"Estilo: {c['style'] or 'natural e realista'}. Tom: {c['tone'] or 'conversacional'}. "
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
        benefit=benefit,
        movements=movements,
        details=details,
        hook=hook,
        development=development,
        cta=cta,
    )
    caption = build_caption(c, color=color, cta=cta, variation_index=variant_index)
    return dict(image=image, video=video, hook=hook, development=development, cta=cta, caption=caption, variation_index=variant_index)


def package_text(c):
    p = c['prompts']
    blocks = [f"FÁBRICA TIKTOK  -  CAMPANHA {c['id']:04d}", c['name'],
              f"Modelo: {c['model_name']}\nProduto: {c['product']}\nLook: {c['outfit']} · {c['color']}",
              f"Destino: {c['generator'].upper()} · 9:16 · 15 segundos\nEstado: {c['status']}"]
    if c.get('product_assets'):
        blocks.append('FOTOS DO PRODUTO  -  anexar após a referência da modelo\n'+'\n'.join(
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
        blocks.append(f"VARIAÇÃO DE COR  -  {variant['color']}\n"
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
