"""Curadoria dos moldes de fala (banco de falas): contexto para os geradores, checagens automaticas e junção.

Um MOLDE e um dicionario {'t': texto com espacos {dem} {piece} {art} {de} {prep} {pron} {teu} {det} {occ} {pain}, e
opcionalmente 'req' (atributo que o briefing precisa confirmar), 'pain' (usa {pain}), 'for_pain' (feito para essa dor)}.
Tipos: hooks, reactions, closers (texto puro com {occ}) e ctas.
"""
import difflib
import json
import re
import string
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services import copywriter, prompts, script_budget, speech_bank  # noqa: E402

KINDS = ('hooks', 'reactions', 'closers', 'ctas')
SLOTS = {'dem', 'piece', 'art', 'de', 'prep', 'pron', 'teu', 'det', 'occ', 'pain', 'feat'}
FEATURES = [label for label, _needles in prompts.PRODUCT_FEATURES]
# (minimo, maximo) de palavras do molde ja preenchido.
BUDGET = {'hooks': (8, 15), 'reactions': (5, 22), 'closers': (4, 14), 'ctas': (5, 11)}

BANNED = [
    r'\b(hoje|agora mesmo|última[s]?|ultimas?|acabando|estoque|promo[cç][aã]o|desconto|oferta|barat\w+|r\$|%|frete|cupom|'
    r'só até|por tempo|corre que)\b',
    r'\b(câmera|camera|close|enquadr\w+|zoom|plano|filmand\w+|gravand\w+)\b',
    r'\b(não amassa|nao amassa|não desbota|nao desbota|não escurece|nao escurece|não esquenta|nao esquenta|'
    r'não marca|nao marca|não transparece|nao transparece|modela|durável|duravel|resistente|à prova|a prova|'
    r'hipoalerg\w+|dermatol\w+|clareia|hidrata\w*|anti-?idade|elimina|resolve tudo|garantia|garantid\w+|'
    r'melhor do brasil|número 1|numero 1|todo mundo|todas as mulheres|viciante|milagr\w+|tabela)\b',
    r'[#@\U0001F300-\U0001FAFF]',
    r'["“”]',
]


def norm(text):
    text = unicodedata.normalize('NFKD', str(text or '').casefold())
    return ''.join(ch for ch in text if not unicodedata.combining(ch))


def words(text):
    return len(re.findall(r'\w+', str(text or '')))


def slots_for(cat, req='', pain='ficar transparente', occ=None):
    forms = speech_bank._forms(cat)
    occ = occ or (cat['occasions'][0] if cat['occasions'] else 'no dia a dia')
    det = prompts.with_article(req) if req else ''
    return {**forms, 'pain': pain, 'det': det, 'occ': occ, 'feat': req}


def used_slots(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def fill(cat, mold, kind, occ=None):
    item = mold if isinstance(mold, dict) else {'t': mold}
    return speech_bank.fill(item['t'], slots_for(cat, item.get('req', ''), occ=occ))


def base_brief(cat, with_req=''):
    """Briefing realista da categoria; com `with_req` o atributo esta confirmado nos detalhes."""
    forms = speech_bank._forms(cat)
    return dict(model_name='Micaela', product=cat['piece'].capitalize(), outfit=cat['piece'], color='Preto',
                niche='casual', audience='mulheres adultas', benefit='', angle='', tone='', style='', movements='',
                objection='', offer='', generator='grok', video_mode='', details=with_req or '',
                **{'_forms': forms})


def check(cat, mold, kind, existing_texts=()):
    """Motivos de reprovacao de um molde (lista vazia = passou nas checagens automaticas)."""
    why = []
    if not isinstance(mold, dict) and not isinstance(mold, str):
        return ['formato invalido']
    item = mold if isinstance(mold, dict) else {'t': mold}
    text = str(item.get('t') or '').strip()
    if not text:
        return ['vazio']
    unknown = used_slots(text) - SLOTS
    if unknown:
        why.append(f'espaco desconhecido: {sorted(unknown)}')
    req = item.get('req') or ''
    if req and req not in FEATURES:
        why.append(f'req invalido: {req}')
    if ('{det}' in text or '{feat}' in text) and not req:
        why.append('{det}/{feat} sem req')
    if '{pain}' in text and not item.get('pain'):
        why.append('{pain} sem pain: true')
    if item.get('pain') and '{pain}' not in text:
        why.append('pain: true sem {pain}')
    if item.get('for_pain') and kind != 'ctas':
        why.append('for_pain so vale em CTA')
    if why:
        return why
    filled = fill(cat, item, kind)
    if '{' in filled or '}' in filled:
        return ['espaco sem preenchimento']
    low = norm(filled)
    lo, hi = BUDGET[kind]
    n = words(filled)
    if not lo <= n <= hi:
        why.append(f'{n} palavras (faixa {lo}-{hi})')
    if kind == 'ctas' and 'carrinho laranja' not in low:
        why.append('CTA sem "carrinho laranja"')
    if kind == 'ctas' and copywriter._weak_cta(filled):
        why.append('CTA fraco para a auditoria (pede permissao ou termina fraco)')
    if kind in ('hooks', 'ctas') and not re.search(r'[.?!]$', filled):
        why.append('sem pontuacao final')
    for pattern in BANNED:
        hit = re.search(norm(pattern) if pattern.startswith('\\b') else pattern, low)
        if hit:
            why.append(f'termo proibido: {hit.group(0)}')
    # Atributo citado sem declarar `req`: promessa sem fato.
    own = norm(item.get('req') or '')
    for label in FEATURES:
        l = label.casefold()
        if l and norm(label) != own and re.search(rf'(?<!\w){re.escape(l)}(?!\w)', text.casefold()) \
                and l not in cat['piece'].casefold():
            why.append(f'cita "{label}" sem declarar req')
    # Concordancia com o genero da categoria (colete e masculino).
    fem = cat['gender'] == 'f'
    wrong = r'\b(ele|esse|nesse|o teu|dele)\b' if fem else r'\b(ela|essa|nessa|a tua|dela)\b'
    if re.search(wrong, norm(text)):
        why.append('pronome ou demonstrativo do genero errado')
    # Voz de catalogo / locutor.
    if re.search(r'\b(adquira|confira nossa|nossa loja|nosso produto|descubra|conheça|conheca|aproveite)\b', low):
        why.append('voz de catalogo')
    # Quase igual a outro molde (ja existente ou candidato anterior).
    for other in existing_texts:
        if difflib.SequenceMatcher(None, low, norm(other)).ratio() >= 0.80:
            why.append(f'quase igual a: {other[:50]}')
            break
    return why


def audit_in_context(cat, mold, kind):
    """Preenche o molde num roteiro conhecido e roda a auditoria do app. Devolve a lista de problemas."""
    item = mold if isinstance(mold, dict) else {'t': mold}
    req = item.get('req') or ''
    brief = {k: v for k, v in base_brief(cat, req).items() if not k.startswith('_')}
    if item.get('pain') or item.get('for_pain'):
        brief['objection'] = 'ficar transparente'
    filled = fill(cat, item, kind, occ=cat['occasions'][0] if cat['occasions'] else None)
    pack = {
        'hook': 'Vesti essa peça e olha como o look ficou pronto na hora, sério mesmo',
        'development': 'E o caimento dela é lindo no corpo, eu gostei muito mais do que imaginava. Dá pra usar no dia a dia numa boa.',
        'cta': 'Corre pro carrinho laranja e escolhe a tua',
    }
    field = {'hooks': 'hook', 'reactions': 'development', 'closers': 'development', 'ctas': 'cta'}[kind]
    if kind == 'reactions':
        pack['development'] = f'{filled} Dá pra usar no dia a dia numa boa.'
    elif kind == 'closers':
        pack['development'] = f'E o caimento dela é lindo no corpo, eu gostei muito. {filled}'
    else:
        pack[field] = filled
    # strict_style=True: e a regua da geracao individual, a mais exigente (CTA fraco, contagem minima, formato).
    return copywriter.audit(pack, brief, require_caption=False, strict_style=True)


def category_context(cat):
    """Resumo da categoria para o pedido de geracao (o que ja existe, para nao repetir)."""
    out = {'id': cat['id'], 'label': cat['label'], 'piece': cat['piece'],
           'genero': 'feminino' if cat['gender'] == 'f' else 'masculino', 'tom': cat['tone'], 'evitar': cat['avoid'],
           'ocasioes': cat['occasions'], 'dores_tipicas': [o['pain'] for o in cat['objections']],
           'familia': cat.get('family') or 'roupa'}
    for kind in KINDS:
        out[f'{kind}_existentes'] = [(m['t'] if isinstance(m, dict) else m) for m in cat.get(kind, [])]
    return out


def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')


# ---------------------------------------------------------------------------------------------- pedido de geracao
QUANTIDADE = {'hooks': 14, 'reactions': 14, 'closers': 8, 'ctas': 8}

REGRAS = """Você escreve MOLDES de fala para vídeos UGC de 15 segundos do TikTok Shop, em português do Brasil, em primeira pessoa, como uma cliente real que comprou a peça e está mostrando para a câmera. Fala de conversa, natural, com as emendas de quem fala de verdade ("sério", "olha", "e aí", "gente"); nunca voz de catálogo, de locutor ou de anúncio.

Um vídeo tem 3 trechos: GANCHO (0-4 s), DESENVOLVIMENTO (4-12 s: uma reação e um fechamento) e CHAMADA (12-15 s). Você escreve peças soltas (moldes) que o gerador combina. Cada molde é um texto com ESPAÇOS entre chaves, que o gerador preenche:
{dem} = essa/esse · {piece} = o nome da peça · {art} = a/o · {de} = da/do · {prep} = nessa/nesse · {pron} = ela/ele · {teu} = a tua/o teu · {occ} = uma ocasião de uso (ex.: "no trabalho", "na praia") · {pain} = a dor do cliente (ex.: "ficar transparente") · {det} = o atributo confirmado, já com artigo (ex.: "a renda") · {feat} = o atributo sem artigo.
Use os espaços em vez de escrever "essa", "ela", "a tua" direto: a mesma frase tem que servir para a peça no feminino e no masculino.

TIPOS e o que cada um precisa:
- hooks: abre o vídeo, 9 a 14 palavras já preenchido. Termina com . ? ou !. Estruturas diferentes entre si: pergunta, confissão, descoberta, teste, comparação, reação, dúvida resolvida.
- reactions: a primeira parte do desenvolvimento, 6 a 20 palavras, uma ou duas frases curtas, o que a pessoa sente ou vê ao usar.
- closers: a segunda parte do desenvolvimento, SEMPRE com {occ}, 5 a 12 palavras (ex.: "Dá pra usar {occ} numa boa.").
- ctas: 6 a 10 palavras, SEMPRE com "carrinho laranja", sem pressão de tempo.

ATRIBUTOS: um molde que cita um atributo da peça (tecido, renda, bolso, cós, decote, zíper, forro...) só pode aparecer quando o briefing confirma esse atributo. Declare-o em "req" com EXATAMENTE um destes rótulos: __FEATURES__. O mesmo atributo tem que estar no texto (por {det}, {feat} ou pela palavra). Molde que NÃO tem "req" não pode citar nenhum atributo específico: fala só de sensação, de uso, de look e de ocasião.
DOR: um molde que usa a dor do cliente leva {pain} no texto e "pain": true. Um CTA feito para uma dor específica leva "for_pain": "<a dor>" (use só uma das dores típicas da categoria).

HONESTIDADE (reprovam o molde): nada de urgência, estoque, "últimas peças", preço, desconto, frete, promoção, "só hoje"; nada de promessa de desempenho (não amassa, não desbota, não esquenta, não marca, modela, durável, resistente, hidrata, resolve tudo, garantia); nada de superlativo ou comparação com concorrente; nada de "todo mundo" ou "todas as mulheres"; nada de câmera, enquadramento, close ou zoom dentro da fala; sem emoji, hashtag, aspas nem nome de marca. Opinião pessoal pode ("me senti linda"); desempenho, não.

VARIEDADE: cada molde tem que ter estrutura de frase própria, e não ser outro com uma palavra trocada. Não repita nem pareça com os moldes que já existem (lista abaixo).

SAÍDA: SOMENTE um JSON, sem texto antes nem depois: {"hooks":[{"t":"..."}], "reactions":[...], "closers":["...", ...], "ctas":[{"t":"..."}]}. Em closers use só strings. Os campos opcionais ("req", "pain", "for_pain") só nos moldes que precisam deles."""


def pedido_geracao(cat, quantidades=None):
    """(sistema, usuario) para pedir candidatos a uma categoria. Serve para a IA e para os agentes do Claude."""
    q = quantidades or QUANTIDADE
    system = REGRAS.replace('__FEATURES__', ', '.join(f'"{f}"' for f in FEATURES))
    ctx = category_context(cat)
    user = (f"CATEGORIA: {ctx['label']} (peça: \"{ctx['piece']}\", gênero {ctx['genero']}, família: {ctx['familia']}).\n"
            f"TOM: {ctx['tom']}\nEVITAR: {ctx['evitar']}\n"
            f"OCASIÕES TÍPICAS ({{occ}}): {'; '.join(ctx['ocasioes'])}\n"
            f"DORES TÍPICAS ({{pain}}): {'; '.join(ctx['dores_tipicas'])}\n\n"
            "MOLDES QUE JÁ EXISTEM (não repita nem imite):\n"
            + '\n'.join(f"[{kind}] " + ' | '.join(ctx[f'{kind}_existentes']) for kind in KINDS)
            + f"\n\nEscreva {q['hooks']} hooks, {q['reactions']} reactions, {q['closers']} closers e {q['ctas']} ctas NOVOS para esta categoria."
            " Metade dos hooks e das reactions deve ser livre de atributo (sem req); o resto pode usar req quando fizer sentido."
            " Pelo menos 3 hooks usam {pain} com \"pain\": true.")
    return system, user


def parse_candidatos(texto):
    """Extrai o JSON da resposta (com ou sem cerca de codigo). Devolve dict por tipo ou None."""
    raw = str(texto or '').strip()
    raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw, flags=re.S)
    a, b = raw.find('{'), raw.rfind('}')
    if a < 0 or b <= a:
        return None
    try:
        data = json.loads(raw[a:b + 1])
    except ValueError:
        return None
    out = {}
    for kind in KINDS:
        items = data.get(kind) if isinstance(data, dict) else None
        out[kind] = items if isinstance(items, list) else []
    return out


# ---------------------------------------------------------------------------------------------- dores reais
GRAMATICA = re.compile(r'\b(em ele|em ela|de o|de a|pra o|pra a|em o|em a|a o|por o|por a)\b', re.I)


def check_pains(cat, mold, kind):
    """Um molde com {pain} entra no app com a objecao REAL do briefing, nao so com uma de exemplo: confere cada dor tipica
    da categoria (preenchimento, gramatica e a auditoria do app com essa objecao no briefing)."""
    item = mold if isinstance(mold, dict) else {'t': mold}
    if '{pain}' not in item['t']:
        return []
    problemas = []
    for objection in cat['objections']:
        dor = objection['pain']
        slots = {**slots_for(cat, item.get('req', ''), pain=dor), 'pain': dor}
        filled = speech_bank.fill(item['t'], slots)
        if '{' in filled:
            problemas.append(f'{dor}: espaco sem preenchimento')
            continue
        if GRAMATICA.search(filled):
            problemas.append(f'{dor}: gramatica ({GRAMATICA.search(filled).group(0)})')
        brief = {k: v for k, v in base_brief(cat, item.get('req', '')).items() if not k.startswith('_')}
        brief['objection'] = dor
        pack = {'hook': filled if kind == 'hooks' else 'Vesti essa peça e olha como o look ficou pronto na hora, sério mesmo',
                'development': 'E o caimento dela é lindo no corpo, eu gostei muito mais do que imaginava. Dá pra usar no dia a dia numa boa.',
                'cta': 'Corre pro carrinho laranja e escolhe a tua'}
        if kind == 'reactions':
            pack['development'] = f'{filled} Dá pra usar no dia a dia numa boa.'
        problemas += [f'{dor}: {p}' for p in copywriter.audit(pack, brief, require_caption=False, strict_style=True)]
    return problemas
