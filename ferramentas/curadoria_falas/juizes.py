"""Pacotes para os juizes (agentes do Claude, 3 modelos) e consolidacao dos vereditos.

    python ferramentas/curadoria_falas/juizes.py pacote blusa calca_jeans     # monta curadoria/juizes/<cat>.json + pedido
    python ferramentas/curadoria_falas/juizes.py consolidar blusa calca_jeans # le os vereditos e grava curadoria/finais/<cat>.json

O juiz nao sabe quem escreveu cada molde (GPT ou Claude): a origem fica so no arquivo de controle.
Regra: hooks e reactions ficam se pelo menos 2 dos 3 juizes dao nota 4 ou mais e NENHUM marca risco; closers e ctas (funcionais)
ficam sem risco, com pelo menos 2 juizes em 3 ou mais e media de 3,0 ou mais (ranking pela media, ate o limite).
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

BASE = lib.ROOT / 'testes-estresse-2026-11-02' / 'curadoria'
MODELOS = ('opus', 'sonnet', 'haiku')
LIMITE = {'hooks': 12, 'reactions': 12, 'closers': 6, 'ctas': 6}

RUBRICA = """Você é juiz de falas UGC para vídeos de TikTok Shop em português do Brasil. Avalie cada molde como se fosse falado por uma cliente real, olhando para a câmera, num vídeo de 15 segundos.

Para cada item dê:
- "score" de 1 a 5:
  5 = soa como gente de verdade, tem personalidade e prende ou convence; eu aprovaria sem mexer.
  4 = natural e útil, bom o suficiente para entrar no banco.
  3 = comum, genérico ou meio rígido; não acrescenta nada ao que já existe.
  2 = estranho, forçado, com cara de texto de IA ou de catálogo.
  1 = errado, confuso ou constrangedor.
- "risco": true se a fala promete, insinua ou inventa algo que o vendedor não confirmou (desempenho do tecido, tabela de medidas, frete, estoque, preço, resultado, durabilidade), se tem pressão de tempo, se ofende ou compara com concorrente, se tem direção de câmera dentro da fala, se inventa experiência ou reação de terceiros (elogios recebidos, irmã ou amiga que aprovou, "há meses uso", "todo mundo pergunta"), ou se a gramática/o sentido quebra com o espaço preenchido. Opinião e sensação da própria pessoa ("me senti linda", "gostei") NÃO são risco. Na dúvida, marque true.
- "nota": no máximo 12 palavras, só quando score < 4 ou risco for true.

Cada item traz "filled" (a fala já preenchida para uma peça de exemplo). Julgue o que a pessoa DIRIA em voz alta. Os espaços entre chaves ({dem}, {occ}...) são preenchidos pelo gerador e não são defeito. Seja exigente: 3 é a nota normal, 4 e 5 são para o que realmente se destaca.

Responda SOMENTE com um JSON: {"<id>": {"score": 4, "risco": false, "nota": ""}, ...} com todos os ids, sem texto antes nem depois."""


def candidatos_aprovados(nome):
    """Aprovados nas checagens automaticas, de todas as origens (GPT e Claude), embaralhados e sem origem visivel."""
    itens, controle = [], {}
    for origem in ('candidatas_gpt', 'candidatas_claude'):
        dados = lib.load_json(BASE / 'auto' / f'{origem}__{nome}.json')
        if not dados:
            continue
        for kind, lista in dados['aprovados'].items():
            for mold in lista:
                itens.append((kind, mold, origem))
    random.Random(nome).shuffle(itens)
    cat = {c['id']: c for c in lib.speech_bank.CATEGORIES}[nome]
    pacote = []
    for n, (kind, mold, origem) in enumerate(itens, 1):
        item = mold if isinstance(mold, dict) else {'t': mold}
        ident = f'{kind[:2]}{n:03d}'
        pacote.append({'id': ident, 'tipo': kind, 'molde': item['t'], 'filled': lib.fill(cat, item, kind),
                       **({'req': item['req']} if item.get('req') else {})})
        controle[ident] = {'kind': kind, 'mold': mold, 'origem': origem}
    return pacote, controle


def pacote(nomes):
    cats = {c['id']: c for c in lib.speech_bank.CATEGORIES}
    for nome in nomes:
        itens, controle = candidatos_aprovados(nome)
        cat = cats[nome]
        cabecalho = (f'CATEGORIA: {cat["label"]} (peça: "{cat["piece"]}", {"feminino" if cat["gender"] == "f" else "masculino"}). '
                     f'Tom: {cat["tone"]} Evitar: {cat["avoid"]}')
        lib.save_json(BASE / 'juizes' / f'{nome}.json', {'categoria': cabecalho, 'itens': itens})
        lib.save_json(BASE / 'juizes' / f'{nome}.controle.json', controle)
        print(nome, len(itens), 'itens para julgar')


def consolidar(nomes):
    total_ok = 0
    for nome in nomes:
        controle = lib.load_json(BASE / 'juizes' / f'{nome}.controle.json')
        vereditos = {m: lib.load_json(BASE / 'juizes' / f'veredito_{m}__{nome}.json') for m in MODELOS}
        faltam = [m for m, v in vereditos.items() if not v]
        if faltam:
            print(nome, 'faltam vereditos:', faltam)
            continue
        finais = {k: [] for k in lib.KINDS}
        placar = []
        for ident, info in controle.items():
            notas = [vereditos[m].get(ident) for m in MODELOS]
            if any(n is None for n in notas):
                continue
            scores = [int(n.get('score') or 0) for n in notas]
            risco = any(bool(n.get('risco')) for n in notas)
            if info['kind'] in ('closers', 'ctas'):
                # Fechamento e chamada sao funcionais: "comum" (3) serve. Entram sem risco, com pelo menos 2 juizes em 3
                # ou mais e media de 3,0 ou mais; o ranking pela media escolhe os melhores ate o limite.
                aprovado = (not risco) and sum(1 for s in scores if s >= 3) >= 2 and sum(scores) / len(scores) >= 3.0
            else:
                aprovado = sum(1 for s in scores if s >= 4) >= 2 and not risco
            placar.append((info['origem'], aprovado))
            if aprovado:
                finais[info['kind']].append((sum(scores) / len(scores), info['mold'], info['origem']))
        saida = {}
        for kind, lista in finais.items():
            lista.sort(key=lambda x: -x[0])
            saida[kind] = [{'mold': m, 'media': round(s, 2), 'origem': o} for s, m, o in lista[:LIMITE[kind]]]
        lib.save_json(BASE / 'finais' / f'{nome}.json', saida)
        por_origem = {}
        for origem, ok in placar:
            a, b = por_origem.get(origem, (0, 0))
            por_origem[origem] = (a + ok, b + 1)
        total_ok += sum(len(v) for v in saida.values())
        print(nome, {k: len(v) for k, v in saida.items()}, 'aprovados por origem:', por_origem)
    print('TOTAL finais', total_ok)


def escrever_rubrica():
    (BASE / 'juizes').mkdir(parents=True, exist_ok=True)
    (BASE / 'juizes' / 'RUBRICA.md').write_text(RUBRICA + chr(10), encoding='utf-8')


# ---------------------------------------------------------------------------------------------- moldes com {pain}
def pacote_dor():
    """Moldes com {pain}, preenchidos com as dores REAIS da categoria (os 2 primeiros), para os juizes."""
    cats = {c['id']: c for c in lib.speech_bank.CATEGORIES}
    itens, controle = [], {}
    n = 0
    for nome, cat in cats.items():
        for origem in ('candidatas_gpt', 'candidatas_claude'):
            dados = lib.load_json(BASE / 'auto' / f'{origem}__{nome}.json')
            if not dados:
                continue
            for kind in ('hooks', 'reactions'):
                for mold in dados['aprovados'].get(kind, []):
                    item = mold if isinstance(mold, dict) else {'t': mold}
                    if '{pain}' not in item['t']:
                        continue
                    n += 1
                    ident = f'dr{n:03d}'
                    dores = [o['pain'] for o in cat['objections']][:2]
                    preenchidos = [lib.speech_bank.fill(item['t'], {**lib.slots_for(cat, item.get('req', ''), pain=d), 'pain': d})
                                   for d in dores]
                    itens.append({'id': ident, 'categoria': f'{cat["label"]} ({"feminino" if cat["gender"] == "f" else "masculino"})',
                                  'tipo': kind, 'molde': item['t'], 'dores_reais': dores, 'filled': preenchidos,
                                  **({'req': item['req']} if item.get('req') else {})})
                    controle[ident] = {'cat': nome, 'kind': kind, 'mold': mold, 'origem': origem}
    random.Random('dores').shuffle(itens)
    lib.save_json(BASE / 'juizes' / 'dores.json', {'itens': itens})
    lib.save_json(BASE / 'juizes' / 'dores.controle.json', controle)
    print(len(itens), 'moldes com {pain} para julgar')


def consolidar_dor():
    controle = lib.load_json(BASE / 'juizes' / 'dores.controle.json')
    vereditos = {m: lib.load_json(BASE / 'juizes' / f'veredito_{m}__dores.json') for m in MODELOS}
    if any(not v for v in vereditos.values()):
        print('faltam vereditos:', [m for m, v in vereditos.items() if not v])
        return
    cats = {c['id']: c for c in lib.speech_bank.CATEGORIES}
    aceitos = {}
    for ident, info in controle.items():
        notas = [vereditos[m].get(ident) for m in MODELOS]
        if any(n is None for n in notas):
            continue
        scores = [int(n.get('score') or 0) for n in notas]
        if any(bool(n.get('risco')) for n in notas) or sum(1 for s in scores if s >= 4) < 2:
            continue
        if lib.check(cats[info['cat']], info['mold'], info['kind']) or lib.check_pains(cats[info['cat']], info['mold'], info['kind']):
            continue
        aceitos.setdefault((info['cat'], info['kind']), []).append((sum(scores) / 3, info['mold'], info['origem']))
    total = 0
    for (nome, kind), lista in aceitos.items():
        lista.sort(key=lambda x: -x[0])
        finais = lib.load_json(BASE / 'finais' / f'{nome}.json') or {k: [] for k in lib.KINDS}
        ja = {(x['mold']['t'] if isinstance(x['mold'], dict) else x['mold']) for x in finais.get(kind, [])}
        for media, mold, origem in lista[:4]:
            t = mold['t'] if isinstance(mold, dict) else mold
            if t not in ja:
                finais.setdefault(kind, []).append({'mold': mold, 'media': round(media, 2), 'origem': origem})
                total += 1
        lib.save_json(BASE / 'finais' / f'{nome}.json', finais)
    print(total, 'moldes com {pain} acrescentados aos finais')


if __name__ == '__main__':
    escrever_rubrica()
    comando, nomes = sys.argv[1], sys.argv[2:]
    if '--todas' in nomes:
        nomes = [c['id'] for c in lib.speech_bank.CATEGORIES]
    if comando == 'pacote-dor':
        pacote_dor()
    elif comando == 'consolidar-dor':
        consolidar_dor()
    else:
        {'pacote': pacote, 'consolidar': consolidar}[comando](nomes)
