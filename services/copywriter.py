# -*- coding: utf-8 -*-
"""Escrita das falas por modelo de linguagem, com auditoria local.

Por que esta camada existe
--------------------------
O gerador deterministico (services/prompts.py) e correto, consistente e nunca
inventa atributo -- mas tem teto: ele monta a frase a partir do rotulo do
briefing, entao produz coisas como "Repara no tecido sem transparencia".
Hook vive de surpresa, e regra fixa nao surpreende.

A troca nao e "modelo no lugar do codigo". E:

    modelo escreve  ->  codigo local audita  ->  falhou? volta pro deterministico

Assim ganha-se a qualidade da escrita sem abrir mao da regra que sustenta o
projeto inteiro: nao afirmar nada que nao esteja no briefing. Sem chave
configurada, ou sem internet, o app continua funcionando exatamente como antes.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from services.prompts import (
    _count_words, _objection_parts, _offer_text, _product_features,
    _dominant_motor, color_variants,
)

SETTINGS_FILE = 'llm.json'
PROVIDERS = ('openai', 'gemini')
DEFAULT_MODELS = {'openai': 'gpt-4o-mini', 'gemini': 'gemini-2.0-flash'}
TIMEOUT = 25

# Afirmacoes de desempenho que so podem aparecer se estiverem no briefing.
# Entusiasmo subjetivo ("linda", "maravilhosa") fica liberado: e opiniao, nao
# promessa verificavel.
CLAIM_TERMS = (
    'compressão', 'compressao', 'elasticidade', 'elástico', 'elastico',
    'premium', 'secagem', 'antibacteriano', 'impermeável', 'impermeavel',
    'respirável', 'respiravel', 'modelador', 'redutor', 'emagrece',
    'hipoalergênico', 'hipoalergenico', 'dermatologicamente', 'anti-odor',
    'proteção uv', 'protecao uv', 'térmico', 'termico', 'sustentável',
    'sustentavel', 'orgânico', 'organico', 'certificado',
)

URGENCY_PATTERNS = (
    r'\búltim[ao]s?\s+(?:chance|unidades|peças|pecas)\b',
    r'\búltimas\b', r'\bultimas\b',
    r'\bacab(?:a|ou|ando|ar)\b',
    r'\besgot\w*\b',
    r'\bs[óo]\s+hoje\b',
    r'\brel[âa]mpago\b',
    r'\bpor\s+tempo\s+limitado\b',
    r'\bdesconto\w*\b',
    r'\bpromo(?:ção|cao|ções|coes)\b',
    r'\bfrete\s+gr[áa]tis\b',
    r'\boferta\w*\b',
    r'\b\d{1,3}\s*%\s*(?:off|de\s+desconto)\b',
)

BUDGET = {'hook': (9, 14), 'development': (18, 26), 'cta': (6, 10)}
TOTAL_MAX = 45

STAGE_DIRECTION_PATTERNS = (
    r'\bc[âa]mera\b', r'\benquadramento\b', r'\bclose(?:-up)?\b',
    r'\bplano\s+(?:m[ée]dio|aberto|fechado|detalhe)\b',
    r'\baproxim(?:o|a|e|ando)\s+(?:a|da)\s+c[âa]mera\b',
    r'\bmostrando\s+(?:o|a|os|as)\b', r'\bfa[çc]a\s+um\s+giro\b',
    r'\bmostre\b', r'\bfoco\s+(?:no|na|em)\b',
)

GENERIC_HOOK_PATTERNS = (
    r'^quer\s+ver\b', r'^como\s+fica\b', r'^pensando\s+ness[ae]\b',
    r'^voc[êe]\s+usaria\b', r'^antes\s+de\s+escolher\b',
    r'^o\s+que\s+vale\s+observar\b', r'^de\s+perto,?\s+ser[áa]\s+que\b',
    r'^olha\s+(?:só\s+)?ess[ae]\b', r'^essa\s+pe[çc]a\s+[ée]\b',
)

FIRST_PERSON_PATTERNS = (
    r'\beu\b', r'\bme\b', r'\bminh[ao]s?\b', r'\bcomigo\b',
    r'\bachei\b', r'\bvesti\b', r'\busei\b', r'\buso\b',
    r'\btestei\b', r'\bexperimentei\b', r'\bpercebi\b',
)

SYSTEM_PROMPT = """Você é uma roteirista sênior de resposta direta para vídeos UGC de 15 segundos no TikTok Shop, em português do Brasil.

Escreva como uma pessoa real contando uma descoberta para uma amiga. A fala precisa soar espontânea quando lida em voz alta, vender por identificação e prova, e nunca parecer anúncio, catálogo, locução ou instrução de filmagem.

OBJETIVO CRIATIVO
- Escolha UMA ideia central forte por opção: quebra de objeção, descoberta inesperada, versatilidade/ocasião, percepção de qualidade, economia real ou autoestima. Use somente o que o briefing sustenta.
- Abra uma pequena história: expectativa ou receio -> descoberta concreta -> uso na vida real -> ação.
- A cor é informação visual. Só a mencione quando ela for a razão da história; nunca gaste hook e CTA repetindo a cor.
- O público orienta o vocabulário, mas idade, gênero e segmentação jamais são recitados.
- A direção de câmera e os movimentos acontecem na imagem. A pessoa NÃO fala "aproximo a câmera", "mostrando o caimento", "faço um giro", "close" ou qualquer instrução de produção.

ESTRUTURA (obrigatória)
- hook (0–4s, 10 a 12 palavras): uma confissão, receio, contraste ou descoberta específica. Abre tensão sem usar perguntas genéricas como "quer ver?", "como fica?", "você usaria?" ou "será que parece bonita?".
- development (4–12s, 20 a 24 palavras): linguagem falada em primeira pessoa. Traz uma prova concreta, resolve a objeção e conecta a peça a uma ocasião real. Descreva a experiência, nunca a câmera.
- cta (12–15s, 7 a 9 palavras): uma ação só, no vocabulário real do TikTok Shop — "carrinho", "o link tá aqui embaixo", "garante a tua". Exemplos do tom certo: "Se você também gostou, dá uma conferida no carrinho." / "Corre garantir a tua, o link tá aqui embaixo." Nunca diga "produto marcado": isso é linguagem de painel, não de quem fala com a câmera.
- caption: uma frase de gancho + o que é o produto, e no máximo 5 hashtags no fim.

EXEMPLO DE TRANSFORMAÇÃO (aprenda o princípio, não copie as palavras)
Fraco: "De perto, será que essa legging parece bonita?" / "Aproximo a câmera do acabamento." / "Confira a cor no carrinho."
Forte: "Eu achei que ela ia parecer barata, até olhar de perto." / "O acabamento me surpreendeu e, quando vesti, o caimento ficou muito mais bonito do que eu esperava." / "Se você gostou, dá uma conferida no carrinho."

REGRAS INEGOCIÁVEIS
1. Só pode afirmar o que estiver em FATOS CONFIRMADOS. Nada de compressão, elasticidade, durabilidade, secagem, proteção ou qualquer desempenho que não esteja lá.
2. Urgência (últimas peças, corre, acaba hoje, desconto) só se houver OFERTA REAL no briefing. Sem oferta, nenhuma palavra de urgência.
3. Nunca repita a mesma expressão em duas batidas. Se o hook usou uma palavra-chave, o desenvolvimento usa outra.
4. Nunca leia o rótulo do atributo em voz alta. "sem transparência" é uma ficha técnica; a pessoa fala "dá pra agachar sem medo", "não aparece nada", "pode usar legging clarinha".
5. Nada de saudação ("oi gente", "vem comigo") nem de "nesse vídeo eu vou te mostrar".
6. Fale na primeira pessoa, com a naturalidade de quem comprou e está recomendando. Não narre gestos nem movimentos que o público já está vendo.
7. "Corre", "garante a tua" e afins são entusiasmo e podem ser usados sempre. O que a regra 2 proíbe é afirmar FATO falso sobre estoque, prazo ou preço: "últimas peças", "acaba hoje", "50% off", "promoção relâmpago".
8. As três opções devem usar ângulos narrativos e palavras diferentes. Não entregue paráfrases da mesma ideia.

Responda SOMENTE com um objeto JSON válido, sem markdown, sem comentário:
{"options": [{"hook": "...", "development": "...", "cta": "...", "caption": "..."}, {"hook": "...", "development": "...", "cta": "...", "caption": "..."}, {"hook": "...", "development": "...", "cta": "...", "caption": "..."}]}"""


# --------------------------------------------------------------------------- config
STORAGE_KEY = 'app-settings/llm.json'


def load_settings(data_dir, storage_get=None) -> dict:
    """Le as configuracoes de escrita por IA (Supabase Storage na nuvem,
    arquivo local no modo padrao - mesma convencao usada em
    services/model_library.py). Sem chave configurada, ou sem internet, o
    app continua funcionando exatamente como antes (gerador deterministico)."""
    raw = {}
    if storage_get is not None:
        try:
            raw = json.loads(storage_get(STORAGE_KEY).decode('utf-8'))
        except Exception:
            raw = {}
    else:
        path = Path(data_dir)/SETTINGS_FILE
        try:
            raw = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            raw = {}
    if not isinstance(raw, dict):
        raw = {}
    provider = raw.get('provider') if raw.get('provider') in PROVIDERS else ''
    return {
        'provider': provider,
        'api_key': str(raw.get('api_key') or ''),
        'model': str(raw.get('model') or DEFAULT_MODELS.get(provider, '')),
        'enabled': bool(raw.get('enabled')) and bool(provider) and bool(raw.get('api_key')),
    }


def save_settings(data_dir, values: dict, storage_get=None, storage_put=None) -> dict:
    current = load_settings(data_dir, storage_get=storage_get)
    provider = values.get('provider')
    if provider in PROVIDERS:
        current['provider'] = provider
    elif provider == '':
        current['provider'] = ''
    # Chave vazia no payload significa "mantem a que ja esta gravada".
    key = values.get('api_key')
    if isinstance(key, str) and key.strip():
        current['api_key'] = key.strip()
    if values.get('clear_key'):
        current['api_key'] = ''
    model = values.get('model')
    if isinstance(model, str) and model.strip():
        current['model'] = model.strip()
    elif current['provider'] and not current.get('model'):
        current['model'] = DEFAULT_MODELS[current['provider']]
    if 'enabled' in values:
        current['enabled'] = bool(values['enabled'])
    current['enabled'] = bool(current['enabled'] and current['provider'] and current['api_key'])
    if storage_put is not None:
        storage_put(STORAGE_KEY, json.dumps(current, ensure_ascii=False, indent=2).encode('utf-8'), 'application/json')
    else:
        path = Path(data_dir)/SETTINGS_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding='utf-8')
    return current


def public_settings(data_dir, storage_get=None) -> dict:
    s = load_settings(data_dir, storage_get=storage_get)
    key = s['api_key']
    return {
        'provider': s['provider'],
        'model': s['model'],
        'enabled': s['enabled'],
        'has_key': bool(key),
        'key_hint': f'…{key[-4:]}' if len(key) >= 4 else '',
        'providers': list(PROVIDERS),
        'default_models': DEFAULT_MODELS,
    }


# --------------------------------------------------------------------------- brief
def build_brief(c: dict) -> str:
    facts = _product_features(c, limit=6)
    pain, check = _objection_parts(c)
    offer = _offer_text(c)
    colors = color_variants(c.get('color'))
    linhas = [
        f"PRODUTO: {c.get('product') or '(não informado)'}",
        f"COR DESTE VÍDEO: {c.get('color') or '(única)'}",
        f"FATOS CONFIRMADOS: {', '.join(facts) if facts else '(nenhum além do que aparece nas fotos)'}",
        f"BENEFÍCIO DEMONSTRÁVEL: {c.get('benefit') or '(não informado)'}",
        f"ÂNGULO DE VENDA: {c.get('angle') or '(descoberta e prova no corpo)'}",
        f"PÚBLICO: {c.get('audience') or '(geral)'}",
        f"NICHO: {c.get('niche') or 'casual'}",
        f"TOM: {c.get('tone') or 'conversacional'}",
        f"MOTOR DOMINANTE: {_dominant_motor(c)}",
    ]
    if pain:
        linhas.append(f"OBJEÇÃO Nº 1 DO CLIENTE: {pain}")
    if check:
        linhas.append(f"COMO A CÂMERA DERRUBA ESSA OBJEÇÃO: {check}")
    if offer:
        linhas.append(f"OFERTA REAL (pode usar urgência): {offer}")
    else:
        linhas.append("OFERTA REAL: não existe — PROIBIDO usar qualquer palavra de urgência.")
    if len(colors) > 1:
        linhas.append(f"O produto tem outras cores ({', '.join(colors)}), mas este vídeo é só da cor {c.get('color')}.")
    previous = c.get('previous_script') or {}
    if isinstance(previous, dict) and any(previous.get(k) for k in ('hook','development','cta')):
        linhas.extend([
            'ROTEIRO ATUAL (não repetir estrutura nem frases; crie uma ideia realmente nova):',
            f"- hook atual: {previous.get('hook') or ''}",
            f"- desenvolvimento atual: {previous.get('development') or ''}",
            f"- CTA atual: {previous.get('cta') or ''}",
        ])
    return '\n'.join(linhas)


# --------------------------------------------------------------------------- auditoria
def audit(pack: dict, c: dict) -> list[str]:
    """Devolve a lista de violacoes. Lista vazia = texto aprovado."""
    problemas = []
    for campo, (low, high) in BUDGET.items():
        texto = (pack.get(campo) or '').strip()
        if not texto:
            problemas.append(f'{campo} veio vazio')
            continue
        n = _count_words(texto)
        if n < low:
            problemas.append(f'{campo} tem {n} palavras, precisa de pelo menos {low}')
        elif n > high:
            problemas.append(f'{campo} tem {n} palavras, o teto é {high}')
    total = sum(_count_words(pack.get(k) or '') for k in BUDGET)
    if total > TOTAL_MAX:
        problemas.append(f'as três falas somam {total} palavras; o teto para 15 segundos é {TOTAL_MAX}')

    falado = ' '.join((pack.get(k) or '') for k in ('hook', 'development', 'cta')).casefold()
    hook = (pack.get('hook') or '').strip().casefold()
    development = (pack.get('development') or '').strip().casefold()
    cta = (pack.get('cta') or '').strip().casefold()
    briefing = ' '.join(str(c.get(k) or '') for k in
                        ('product', 'outfit', 'details', 'benefit', 'angle', 'objection')).casefold()
    for termo in CLAIM_TERMS:
        if termo in falado and termo not in briefing:
            problemas.append(f'"{termo}" não está no briefing e não pode ser afirmado')

    if not _offer_text(c):
        for padrao in URGENCY_PATTERNS:
            achado = re.search(padrao, falado)
            if achado:
                problemas.append(f'"{achado.group(0)}" é urgência e não existe oferta real no briefing')
                break

    for padrao in STAGE_DIRECTION_PATTERNS:
        achado = re.search(padrao, falado)
        if achado:
            problemas.append(f'"{achado.group(0)}" é direção de cena e não pode ser pronunciada')
            break

    for padrao in GENERIC_HOOK_PATTERNS:
        if re.search(padrao, hook):
            problemas.append('o hook é uma pergunta ou abertura genérica; use uma experiência, receio ou descoberta específica')
            break

    if not any(re.search(padrao, f'{hook} {development}') for padrao in FIRST_PERSON_PATTERNS):
        problemas.append('hook e desenvolvimento não soam como experiência pessoal em primeira pessoa')

    if re.search(r'\b(?:mulheres|homens|pessoas)\s+(?:de\s+)?\d{2}\s*(?:a|-|–)\s*\d{2}\b', falado):
        problemas.append('a fala recita a faixa etária do público')

    colors = color_variants(c.get('color'))
    color = (c.get('color') or '').strip().casefold()
    if color and len(colors) <= 1 and color in cta:
        problemas.append('o CTA repete a cor sem acrescentar uma razão para agir')

    previous = c.get('previous_script') or {}
    if isinstance(previous, dict):
        for field in ('hook','development','cta'):
            old = re.sub(r'\W+', ' ', str(previous.get(field) or '').casefold()).strip()
            new = re.sub(r'\W+', ' ', str(pack.get(field) or '').casefold()).strip()
            if old and new and old == new:
                problemas.append(f'{field} repetiu exatamente o roteiro atual')

    caption = (pack.get('caption') or '')
    if not caption.strip():
        problemas.append('caption veio vazia')
    elif len(re.findall(r'#\w+', caption)) > 5:
        problemas.append('a legenda passou de 5 hashtags')

    if re.search(r'\[[^\]]+\]|\{\{|\bXXX\b', ' '.join(str(v) for v in pack.values())):
        problemas.append('o texto ficou com um espaço reservado por preencher')
    return problemas


# --------------------------------------------------------------------------- provedores
class ProviderError(Exception):
    """Erro vindo do provedor, ja com o corpo da resposta lido.

    HTTPError so deixa ler o corpo uma vez; sem isto a mensagem util se perde
    no caminho e sobra um numero seco na tela.
    """

    def __init__(self, message: str, status: int = 0, param: str = ''):
        super().__init__(message)
        self.message = message
        self.status = status
        self.param = param


def _describe_error(status: int, corpo: str) -> ProviderError:
    mensagem, param = '', ''
    try:
        dados = json.loads(corpo)
        erro = dados.get('error') if isinstance(dados, dict) else None
        if isinstance(erro, dict):
            mensagem = str(erro.get('message') or '')
            param = str(erro.get('param') or '')
        elif isinstance(erro, str):
            mensagem = erro
    except ValueError:
        pass
    if not mensagem:
        mensagem = (corpo or '').strip()[:400]
    if not param:
        # Alguns provedores nomeiam o parametro so na frase.
        achado = re.search(r"'([A-Za-z_][A-Za-z0-9_]*)'\s*(?:does not support|is not supported|nao suportado)", mensagem)
        if achado:
            param = achado.group(1)
    return ProviderError(mensagem, status=status, param=param)


def _post_json(url: str, payload: dict, headers: dict) -> dict:
    data = json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json', **headers})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        try:
            corpo = exc.read().decode('utf-8', 'ignore')
        except Exception:
            corpo = ''
        raise _describe_error(exc.code, corpo) from exc


# Parametros que um modelo pode recusar. Os modelos de raciocinio mais novos,
# por exemplo, so aceitam temperature no padrao. Em vez de exigir que o operador
# adivinhe qual modelo aceita o que, o codigo tira o parametro recusado e tenta
# de novo -- o essencial e o texto, nao o ajuste fino.
_OPTIONAL_OPENAI = ('temperature', 'response_format', 'top_p')


def _image_data_url(image_bytes: bytes, mime: str) -> str:
    import base64
    return f"data:{mime or 'image/jpeg'};base64,{base64.b64encode(image_bytes).decode('ascii')}"


def _call_openai(settings: dict, system: str, user: str, images: list[tuple[bytes, str]] | None = None) -> str:
    if images:
        content = [{'type': 'text', 'text': user}]
        for image_bytes, mime in images:
            content.append({'type': 'image_url', 'image_url': {'url': _image_data_url(image_bytes, mime)}})
        user_message = {'role': 'user', 'content': content}
    else:
        user_message = {'role': 'user', 'content': user}
    body = {
        'model': settings['model'] or DEFAULT_MODELS['openai'],
        'messages': [{'role': 'system', 'content': system}, user_message],
        'temperature': 0.9,
        'response_format': {'type': 'json_object'},
    }
    for _ in range(len(_OPTIONAL_OPENAI) + 1):
        try:
            out = _post_json('https://api.openai.com/v1/chat/completions', body,
                             {'Authorization': f"Bearer {settings['api_key']}"})
            return out['choices'][0]['message']['content']
        except ProviderError as exc:
            alvo = exc.param if exc.param in body else next(
                (nome for nome in _OPTIONAL_OPENAI
                 if nome in body and nome in (exc.message or '').casefold()), '')
            if exc.status == 400 and alvo:
                body.pop(alvo, None)
                continue
            raise
    raise ProviderError('o modelo recusou todos os parametros enviados', status=400)


def _call_gemini(settings: dict, system: str, user: str, images: list[tuple[bytes, str]] | None = None) -> str:
    import base64
    model = settings['model'] or DEFAULT_MODELS['gemini']
    url = (f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
           f"?key={settings['api_key']}")
    parts = [{'text': user}]
    for image_bytes, mime in (images or []):
        parts.append({'inlineData': {'mimeType': mime or 'image/jpeg', 'data': base64.b64encode(image_bytes).decode('ascii')}})
    body = {
        'systemInstruction': {'parts': [{'text': system}]},
        'contents': [{'role': 'user', 'parts': parts}],
        'generationConfig': {'temperature': 0.9, 'responseMimeType': 'application/json'},
    }
    for tentativa in range(3):
        try:
            out = _post_json(url, body, {})
            return out['candidates'][0]['content']['parts'][0]['text']
        except ProviderError as exc:
            baixo = (exc.message or '').casefold()
            if exc.status == 400 and 'responsemimetype' in baixo and 'responseMimeType' in body.get('generationConfig', {}):
                body['generationConfig'].pop('responseMimeType')
                continue
            if exc.status == 400 and 'systeminstruction' in baixo and 'systemInstruction' in body:
                body.pop('systemInstruction')
                body['contents'][0]['parts'][0]['text'] = system + '\n\n' + user
                continue
            if exc.status == 400 and 'temperature' in baixo:
                body.get('generationConfig', {}).pop('temperature', None)
                continue
            raise
    raise ProviderError('o modelo recusou todos os parametros enviados', status=400)


CALLERS = {'openai': _call_openai, 'gemini': _call_gemini}


def _clean_pack(dados: dict) -> dict:
    return {k: str(dados.get(k) or '').strip() for k in ('hook', 'development', 'cta', 'caption')}


def _parse_candidates(raw: str) -> list[dict]:
    texto = (raw or '').strip()
    texto = re.sub(r'^```(?:json)?|```$', '', texto, flags=re.M).strip()
    inicio, fim = texto.find('{'), texto.rfind('}')
    if inicio >= 0 and fim > inicio:
        texto = texto[inicio:fim + 1]
    dados = json.loads(texto)
    if not isinstance(dados, dict):
        raise ValueError('resposta não é um objeto')
    options = dados.get('options')
    if isinstance(options, list):
        packs = [_clean_pack(item) for item in options if isinstance(item, dict)]
        if packs:
            return packs[:5]
    # Compatibilidade com provedores/modelos que ainda devolvem o formato
    # antigo. A auditoria continua valendo, portanto isto nao reduz a seguranca.
    return [_clean_pack(dados)]


def _creative_score(pack: dict, c: dict) -> int:
    """Desempata candidatos validos pela naturalidade e especificidade."""
    hook = (pack.get('hook') or '').casefold()
    development = (pack.get('development') or '').casefold()
    score = 0
    if any(word in hook for word in ('achei', 'confesso', 'quase', 'medo', 'dúvida', 'duvida', 'surpreend', 'esperava', 'até ')):
        score += 4
    if any(re.search(p, f'{hook} {development}') for p in FIRST_PERSON_PATTERNS):
        score += 3
    pain, check = _objection_parts(c)
    evidence = f'{pain} {check}'.casefold()
    evidence_words = {w for w in re.findall(r'[a-záàâãéêíóôõúç]{5,}', evidence) if w not in {'mostrar', 'aparece', 'movimento'}}
    score += min(4, sum(1 for word in evidence_words if word in f'{hook} {development}'))
    if any(word in development for word in ('quando vesti', 'no treino', 'no trabalho', 'no dia a dia', 'para sair', 'pra sair', 'na rua')):
        score += 2
    repeated = set(re.findall(r'\b\w{5,}\b', hook)) & set(re.findall(r'\b\w{5,}\b', development))
    score -= len(repeated)
    return score


def _parse(raw: str) -> dict:
    """Formato antigo usado por testes e integracoes locais."""
    return _parse_candidates(raw)[0]


def write_script(c: dict, settings: dict, attempts: int = 2) -> tuple[dict | None, str]:
    """Escreve as falas com o modelo. Devolve (pacote, motivo_da_falha)."""
    caller = CALLERS.get(settings.get('provider'))
    if not caller or not settings.get('api_key'):
        return None, 'sem provedor configurado'
    user = build_brief(c)
    ultimo = ''
    for tentativa in range(max(1, attempts)):
        try:
            bruto = caller(settings, SYSTEM_PROMPT, user)
            candidates = _parse_candidates(bruto)
        except ProviderError as exc:
            if exc.status:
                return None, f'o provedor respondeu {exc.status}: {exc.message[:400]}'
            return None, exc.message[:400]
        except urllib.error.URLError as exc:
            return None, f'nao foi possivel falar com o provedor ({exc.reason})'
        except (ValueError, KeyError, IndexError) as exc:
            ultimo = f'resposta ilegivel ({exc})'
            continue
        approved = []
        rejected = []
        for pack in candidates:
            problemas = audit(pack, c)
            if problemas:
                rejected.extend(problemas)
            else:
                approved.append(pack)
        if approved:
            return max(approved, key=lambda item: _creative_score(item, c)), ''
        # Mantem a lista curta para nao gastar a segunda tentativa repetindo
        # dezenas de avisos equivalentes vindos de tres opcoes.
        unique = []
        for item in rejected:
            if item not in unique:
                unique.append(item)
        ultimo = '; '.join(unique[:8])
        user = (build_brief(c) + '\n\nA tentativa anterior foi recusada pela auditoria:\n- '
                + '\n- '.join(unique[:8]) + '\nReescreva as três opções corrigindo exatamente esses pontos.')
    return None, ultimo or 'o texto nao passou na auditoria'


# --------------------------------------------------------------------------- visao (analise de produto)
VISION_SYSTEM_PROMPT = """Você é um analista de produtos de moda para vídeos UGC de TikTok Shop.

Você recebe até duas fotos:
1. Foto do produto/roupa (como ele é, cor, tecido, corte).
2. Foto da página de descrição do produto no TikTok Shop/loja (specs, tecido, características escritas).

Sua tarefa: olhar SOMENTE o que está visível ou escrito nas fotos e devolver um JSON com estes campos,
todos em português do Brasil, para preencher automaticamente o briefing de um vídeo:

- "benefit": o principal benefício real do produto (curto, uma frase). Baseie-se no que é visível
  (caimento, tecido, corte) ou no que está escrito na foto da descrição. Nunca invente uma
  característica (elasticidade, compressão, proteção UV etc.) que não esteja visível ou escrita.
- "angle": o ângulo de venda mais forte para este produto especificamente (uma frase curta).
- "movements": de 4 a 7 movimentos corporais, separados por ponto e vírgula, que funcionam bem
  pra MOSTRAR esse produto específico em vídeo (ex.: para uma peça de manga longa, "esticar o
  braço mostrando o punho"; para uma legging, "agachar mostrando o caimento"). Pense no tipo de
  peça e no que a foto de descrição destaca.
- "details": detalhes técnicos visíveis ou escritos (tecido, cor, especificações, o que priorizar
  no enquadramento). Seja específico e curto.

Se não conseguir identificar um campo com confiança nas fotos, devolva ele como string vazia "" -
nunca invente. Responda SOMENTE com o JSON, sem texto antes ou depois."""

VISION_FIELDS = ('benefit', 'angle', 'movements', 'details')


def _parse_vision_result(raw: str) -> dict:
    texto = (raw or '').strip()
    texto = re.sub(r'^```(?:json)?|```$', '', texto, flags=re.M).strip()
    inicio, fim = texto.find('{'), texto.rfind('}')
    if inicio >= 0 and fim > inicio:
        texto = texto[inicio:fim + 1]
    dados = json.loads(texto)
    if not isinstance(dados, dict):
        raise ValueError('resposta não é um objeto')
    limits = {'benefit': 500, 'angle': 500, 'movements': 1500, 'details': 5000}
    out = {}
    for campo in VISION_FIELDS:
        valor = dados.get(campo)
        if isinstance(valor, str):
            out[campo] = valor.strip()[:limits[campo]]
    return out


def analyze_product(images: list[tuple[bytes, str]], settings: dict, context: str = '') -> tuple[dict | None, str]:
    """Analisa fotos do produto (e/ou da descrição) e devolve sugestoes pros
    campos do briefing. Usa a mesma configuracao (provedor/chave/modelo) das
    Configuracoes de Escrita com IA - se o modelo suportar visao (gpt-4o-mini
    e gemini-2.0-flash suportam, e sao os padroes do app), funciona sem
    nenhuma chave nova. Devolve (campos_sugeridos, motivo_da_falha)."""
    caller = CALLERS.get(settings.get('provider'))
    if not caller or not settings.get('api_key'):
        return None, 'Configure a IA em "Configurações de Escrita com IA" antes de analisar fotos.'
    if not images:
        return None, 'Nenhuma foto para analisar.'
    user = 'Analise as fotos anexadas e devolva o JSON pedido.'
    if context:
        user += f'\n\nContexto adicional (não invente além disso): {context}'
    try:
        bruto = caller(settings, VISION_SYSTEM_PROMPT, user, images)
        campos = _parse_vision_result(bruto)
    except ProviderError as exc:
        if exc.status:
            return None, f'o provedor respondeu {exc.status}: {exc.message[:400]}'
        return None, exc.message[:400]
    except urllib.error.URLError as exc:
        return None, f'não foi possível falar com o provedor ({exc.reason})'
    except (ValueError, KeyError, IndexError) as exc:
        return None, f'resposta ilegível ({exc})'
    if not any(campos.values()):
        return None, 'a IA não conseguiu identificar nada de útil nas fotos'
    return campos, ''
