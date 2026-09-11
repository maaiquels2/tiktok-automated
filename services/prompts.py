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
    hooks = [
        f'{color} no corpo: olha esse caimento.',
        f'Essa {product.lower()} em {color} mudou meu treino.',
        f'Close no detalhe: {product.lower()} {color}.',
        f'Se você curte {color}, presta atenção nisso.',
        f'Antes eu duvidava do {color}. Olha agora.',
        f'{focus.capitalize()} na versão {color}.',
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
    video = (
        f'Vídeo final vertical 9:16, 15 segundos, {resolution}. '
        f"Use a IMAGEM APROVADA da cor {c['color']} anexada como quadro de referência. Preserve a identidade, "
        'o look, as cores e o produto durante todo o vídeo. Movimentos sutis, gestos naturais, '
        'continuidade visual, sem morphing ou alteração do rosto. '
        f'Direção de movimentos para este produto: {movements}. '
        + (f'Instruções extras do briefing: {details}. ' if details and not details_for_image else '')
        + f"Estilo: {c['style'] or 'natural e realista'}. Tom: {c['tone'] or 'conversacional'}. "
        f'0–2s: olhar para a câmera e apresentar o produto. Fala: {hook} '
        f'2–12s: mostrar os detalhes e o benefício informado. Fala: {development} '
        f'12–15s: encerrar com gesto leve. Fala: {cta} '
        'Falas em português do Brasil. Ajuste o ritmo após leitura em voz alta. '
        'Sem promessas adicionais ou resultados não demonstrados. '
        'Se o serviço gerar clipes menores, monte os trechos e exporte 15 segundos antes de anexar.'
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
                       ('hook', 'HOOK · 0–2s'), ('development', 'DESENVOLVIMENTO · 2–12s'),
                       ('cta', 'CTA · 12–15s'), ('caption', 'LEGENDA')]:
        blocks.append(f"{title}\n{p.get(key, '(ainda não gerado)')}")
    blocks.append('REVISÃO HUMANA\n[ ] Conferir conta da Micaela\n[ ] Subir o MP4 aprovado\n'
                  '[ ] Selecionar o produto manualmente no TikTok Shop\n[ ] Colar e revisar a legenda\n'
                  '[ ] Revisar vídeo, áudio e direitos de uso\n[ ] Publicar manualmente no Studio')
    return '\n\n'.join(blocks) + '\n'
