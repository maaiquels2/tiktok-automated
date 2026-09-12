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

URGENCY_TERMS = (
    'últimas', 'ultimas', 'acaba', 'acabando', 'esgot', 'só hoje', 'so hoje',
    'corre', 'promoção relâmpago', 'promocao relampago', 'por tempo limitado',
    'última chance', 'ultima chance', 'desconto', 'off', 'frete grátis',
    'frete gratis', 'oferta',
)

BUDGET = {'hook': (9, 14), 'development': (18, 26), 'cta': (6, 10)}
TOTAL_MAX = 45

SYSTEM_PROMPT = """Você escreve falas de vídeos UGC de 15 segundos para TikTok Shop, em português do Brasil.

Escreve como uma pessoa real falando com o celular na mão — não como anúncio, não como catálogo, não como locutor.

ESTRUTURA (obrigatória)
- hook (0–4s, 10 a 12 palavras): cria tensão e NÃO pode resolvê-la. Se você faz uma pergunta, não responda na mesma frase.
- development (4–12s, 20 a 24 palavras): três batidas curtas — prova (um fato visível), quebra da objeção (demonstração, não promessa), e onde a pessoa vai usar.
- cta (12–15s, 7 a 9 palavras): uma ação só, citando o produto marcado.
- caption: uma frase de gancho + o que é o produto, e no máximo 5 hashtags no fim.

REGRAS INEGOCIÁVEIS
1. Só pode afirmar o que estiver em FATOS CONFIRMADOS. Nada de compressão, elasticidade, durabilidade, secagem, proteção ou qualquer desempenho que não esteja lá.
2. Urgência (últimas peças, corre, acaba hoje, desconto) só se houver OFERTA REAL no briefing. Sem oferta, nenhuma palavra de urgência.
3. Nunca repita a mesma expressão em duas batidas. Se o hook usou uma palavra-chave, o desenvolvimento usa outra.
4. Nunca leia o rótulo do atributo em voz alta. "sem transparência" é uma ficha técnica; a pessoa fala "dá pra agachar sem medo", "não aparece nada", "pode usar legging clarinha".
5. Nada de saudação ("oi gente", "vem comigo") nem de "nesse vídeo eu vou te mostrar".
6. Fale na primeira pessoa, com a naturalidade de quem comprou e está mostrando.

Responda SOMENTE com um objeto JSON válido, sem markdown, sem comentário:
{"hook": "...", "development": "...", "cta": "...", "caption": "..."}"""


# --------------------------------------------------------------------------- config
def load_settings(data_dir) -> dict:
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


def save_settings(data_dir, values: dict) -> dict:
    current = load_settings(data_dir)
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
    path = Path(data_dir)/SETTINGS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding='utf-8')
    return current


def public_settings(data_dir) -> dict:
    s = load_settings(data_dir)
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
    briefing = ' '.join(str(c.get(k) or '') for k in
                        ('product', 'outfit', 'details', 'benefit', 'angle', 'objection')).casefold()
    for termo in CLAIM_TERMS:
        if termo in falado and termo not in briefing:
            problemas.append(f'"{termo}" não está no briefing e não pode ser afirmado')

    if not _offer_text(c):
        for termo in URGENCY_TERMS:
            if re.search(r'\b' + re.escape(termo), falado):
                problemas.append(f'"{termo}" é urgência e não existe oferta real no briefing')
                break

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


def _call_openai(settings: dict, system: str, user: str) -> str:
    body = {
        'model': settings['model'] or DEFAULT_MODELS['openai'],
        'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
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


def _call_gemini(settings: dict, system: str, user: str) -> str:
    model = settings['model'] or DEFAULT_MODELS['gemini']
    url = (f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
           f"?key={settings['api_key']}")
    body = {
        'systemInstruction': {'parts': [{'text': system}]},
        'contents': [{'role': 'user', 'parts': [{'text': user}]}],
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


def _parse(raw: str) -> dict:
    texto = (raw or '').strip()
    texto = re.sub(r'^```(?:json)?|```$', '', texto, flags=re.M).strip()
    inicio, fim = texto.find('{'), texto.rfind('}')
    if inicio >= 0 and fim > inicio:
        texto = texto[inicio:fim + 1]
    dados = json.loads(texto)
    if not isinstance(dados, dict):
        raise ValueError('resposta não é um objeto')
    return {k: str(dados.get(k) or '').strip() for k in ('hook', 'development', 'cta', 'caption')}


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
            pack = _parse(bruto)
        except ProviderError as exc:
            if exc.status:
                return None, f'o provedor respondeu {exc.status}: {exc.message[:400]}'
            return None, exc.message[:400]
        except urllib.error.URLError as exc:
            return None, f'nao foi possivel falar com o provedor ({exc.reason})'
        except (ValueError, KeyError, IndexError) as exc:
            ultimo = f'resposta ilegivel ({exc})'
            continue
        problemas = audit(pack, c)
        if not problemas:
            return pack, ''
        ultimo = '; '.join(problemas)
        user = (build_brief(c) + '\n\nA tentativa anterior foi recusada pela auditoria:\n- '
                + '\n- '.join(problemas) + '\nReescreva corrigindo exatamente esses pontos.')
    return None, ultimo or 'o texto nao passou na auditoria'
