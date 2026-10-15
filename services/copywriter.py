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

import contextvars
import difflib
import json
import math
import os
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from services import formats, persuasion, speech_bank

# Uso da IA por requisicao: cada chamada ao provedor anota os tokens aqui e o
# app grava por campanha (o que a OpenAI cobra).
_USAGE = contextvars.ContextVar('fabrica_ai_usage', default=None)


def usage_start() -> list:
    lista: list = []
    _USAGE.set(lista)
    return lista


def _record_usage(model, tokens_in, tokens_out):
    lista = _USAGE.get()
    if lista is not None:
        lista.append({'model': str(model or ''), 'input_tokens': int(tokens_in or 0),
                      'output_tokens': int(tokens_out or 0)})
from services.prompts import without_niche_defaults
from services.prompts import (
    _count_words, _objection_parts, _offer_text, _product_features,
    _dominant_motor, _chosen_motor, color_variants,
)

SETTINGS_FILE = 'llm.json'
PROVIDERS = ('openai', 'gemini')
# Avaliacao de 11/10/2026 (fotos reais de produto + prints de loja, chamadas
# reais): para LER as fotos, gpt-6-luna acertou tanto quanto Sol e Astra
# (produto, composicao, oferta e prova social com os numeros exatos, nada
# inventado) por ~1/15 do custo do Sol. Para ESCREVER as falas, gpt-6.1-sol
# teve 9/9 opcoes aprovadas, sempre em primeira pessoa (Luna 8/9, mais
# impessoal; Astra igual ao Sol por ~5x o preco; gpt-4o-mini prometeu
# "confortavel" sem fato e perdeu parte da oferta).
DEFAULT_MODELS = {'openai': 'gpt-6.1-sol', 'gemini': 'gemini-2.0-flash'}
VISION_MODELS = {'openai': 'gpt-6-luna'}
# Padroes antigos gravados na configuracao: tratados como "padrao" para a
# troca de modelo valer sem ninguem precisar reconfigurar.
LEGACY_DEFAULT_MODELS = {'openai': ('gpt-4o-mini',)}
TIMEOUT = 25
BATCH_TIMEOUT = 45
# Teto de tempo da etapa inteira de escrita. Duas tentativas de 25s somavam
# quase um minuto; aqui a segunda so comeca se couber dentro do orcamento.
BUDGET_SECONDS = 32
# Teto da leitura de fotos pela IA. A funcao na nuvem morre aos 60s, e uma
# resposta lenta do provedor derrubava o salvamento do look com "Task timed out"
# sem nenhuma mensagem util. Com o teto, o app responde antes e explica.
VISION_BUDGET_SECONDS = 40
# Lado maior das fotos mandadas pra IA. Print de tela do iPhone e foto da
# galeria passam de 3000px; a IA nao precisa disso pra ler texto e roupa, e
# arquivo menor sobe e e processado bem mais rapido.
VISION_MAX_SIDE = 1600

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
    r'\bacab(?:a|e|em|ou|ando|ar)\b',
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

# Tetos cabem em 15 s; os pisos sao baixos de proposito: piso alto obrigava
# o texto a encher linguica ("com calma", "e o tipo de detalhe que procuro").
# Faixas de ritmo: o piso evita fala rasa; o teto e so referencia. Contagem
# de palavras nao reprova roteiro -- fala natural vale mais que caber num
# numero (pedido do estudio depois de os roteiros soarem robóticos).
BUDGET = {'hook': (6, 20), 'development': (10, 45), 'cta': (4, 16)}

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

WEAK_CTA_PATTERNS = (
    r'^\s*se\b', r'^\s*quer\b', r'^\s*gosta\b',
    r'\bd[áa]\s+uma\s+(?:olhada|conferida)\b',
    r'\bconfere\s+l[áa]\b', r'\bolha\s+l[áa]\b',
)

# Marcas de fala em primeira pessoa. A lista antiga deixava de fora formas
# obviamente pessoais ("reparei", "gostei", "pra mim") e por isso reprovava
# texto correto -- era parte do motivo de o gerador local nunca passar aqui.
FIRST_PERSON_PATTERNS = (
    r'\beu\b', r'\bme\b', r'\bmim\b', r'\bminh[ao]s?\b', r'\bmeus?\b', r'\bcomigo\b', r'\btô\b',
    r'\bachei\b', r'\bvesti\b', r'\busei\b', r'\buso\b',
    r'\btestei\b', r'\bexperimentei\b', r'\bpercebi\b',
    r'\breparei\b', r'\bolhei\b', r'\bpeguei\b', r'\bgostei\b',
    r'\bencontrei\b', r'\bsurpreendi\b',
    # Preterito de primeira pessoa em geral: agachei, amei, fiquei, separei.
    r'\b\w{2,}ei\b', r'\bfiz\b', r'\bquis\b', r'\bsenti\b',
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
- hook (abertura, de 10 a 18 palavras): uma confissão, receio, contraste ou descoberta específica. Abre tensão sem usar perguntas genéricas como "quer ver?", "como fica?", "você usaria?" ou "será que parece bonita?".
- development (meio, de 20 a 40 palavras): linguagem falada em primeira pessoa, com as pausas e emendas de quem conversa ("e olha", "sério", "aí"). Traz uma prova concreta, resolve a objeção e conecta a peça a uma ocasião real. Descreva a experiência, nunca a câmera.
- cta (fechamento, de 7 a 14 palavras): fechamento assertivo com UMA ação concreta e imediata. Use "carrinho laranja" e verbos como "corre", "abre", "toca", "escolhe", "garante" ou "aproveita". Exemplos sem oferta real: "Corre pro carrinho laranja e confere os detalhes agora." / "Abre o carrinho laranja e escolhe a sua versão." Exemplos com OFERTA REAL confirmada: "Aproveita a oferta e corre pro carrinho laranja agora." Nunca comece com "se gostou", "se fez sentido", "quer levar", "gosta de" ou outro pedido de permissão. Nunca diga "produto marcado".
- TOTAL das três falas: de 45 a 56 palavras. O vídeo tem 15 segundos e quem vende fala o tempo todo: fala curta
  deixa silêncio no fim (aconteceu no teste real). Encha com conversa de verdade, nunca com palavra vazia.
- caption: uma frase de gancho + o que é o produto, e no máximo 5 hashtags no fim.

EXEMPLO DE TRANSFORMAÇÃO (aprenda o princípio, não copie as palavras)
Fraco: "De perto, será que essa legging parece bonita?" / "Aproximo a câmera do acabamento." / "Se gostou, confere no carrinho."
Forte: "Eu achei que ela ia parecer barata, até olhar de perto." / "O acabamento me surpreendeu e, quando vesti, o caimento ficou muito mais bonito do que eu esperava." / "Corre pro carrinho laranja e confere os detalhes agora."

REGRAS INEGOCIÁVEIS
1. Só pode afirmar o que estiver em FATOS CONFIRMADOS. Nada de compressão, elasticidade, durabilidade, secagem, proteção ou qualquer desempenho que não esteja lá.
2. Urgência (últimas peças, acaba hoje, desconto) só se houver OFERTA REAL no briefing. Sem oferta, nenhuma palavra de urgência sobre estoque, prazo ou preço.
3. Nunca repita a mesma expressão em duas batidas. Se o hook usou uma palavra-chave, o desenvolvimento usa outra.
4. Nunca leia o rótulo do atributo em voz alta. "sem transparência" é uma ficha técnica; a pessoa fala "dá pra agachar sem medo", "não aparece nada", "pode usar legging clarinha".
5. Nada de saudação ("oi gente", "vem comigo") nem de "nesse vídeo eu vou te mostrar".
6. Fale na primeira pessoa, com a naturalidade de quem está mostrando e recomendando o produto. Pode falar do momento que o vídeo mostra ("tô usando agora", "olha como ela fica no corpo", "fiquei com vontade de usar todo dia"). Não invente história que ninguém pode verificar ("uso há meses", "lavei vinte vezes", "comprei mês passado").
7. "Corre", "aproveita", "agora" e "garante a tua" criam impulso e podem ser usados sempre. O que a regra 2 proíbe é afirmar FATO falso sobre estoque, prazo ou preço: "últimas peças", "antes que esgote", "acaba hoje", "esse preço vai sumir", "50% off", "promoção relâmpago". Só use essas alegações quando a OFERTA REAL confirmar exatamente isso.
8. As três opções devem usar ângulos narrativos e palavras diferentes. Não entregue paráfrases da mesma ideia.
9. ORALIDADE: escreva como se fala no Brasil, não como se escreve. Use "pra", "tá", "tô", "cê" quando soar natural; no máximo uma interjeição curta ("gente", "olha", "sério"); frases curtas ligadas por "e", "aí", "e o melhor". Hook, desenvolvimento e CTA são UM pensamento contínuo: o desenvolvimento continua o hook, não recomeça. Nunca empilhe ordens ("Repara... Olha... Veja..."), nunca liste atributos e nunca repita no desenvolvimento o atributo que o hook já disse.
10. GATILHOS DE VENDA, SEMPRE COM FATO: curiosidade (o hook abre um "por quê" que o meio responde), especificidade (um detalhe concreto vale mais que três adjetivos), identificação com a dor, imaginação de uso ("imagina…"), prova social e escassez. Prova social (vendidos, nota, avaliações) só com PROVA SOCIAL DECLARADA; escassez (prazo, estoque, desconto, frete, cupom) só com os FATOS DE URGÊNCIA PERMITIDOS, com o número exato. Uma única ação no CTA.

Responda SOMENTE com um objeto JSON válido, sem markdown, sem comentário:
{"options": [{"hook": "...", "development": "...", "cta": "...", "caption": "..."}, {"hook": "...", "development": "...", "cta": "...", "caption": "..."}, {"hook": "...", "development": "...", "cta": "...", "caption": "..."}]}"""


# Reaproveita todas as regras editoriais acima, trocando apenas o contrato de
# resposta. Assim uma campanha com cinco cores custa uma solicitacao ao
# provedor, mas cada cor continua recebendo um roteiro independente.
_SYSTEM_RULES = SYSTEM_PROMPT.rsplit('\n\nResponda SOMENTE', 1)[0]
_BATCH_SYSTEM_RULES = re.sub(r'\n- caption:.*', '', _SYSTEM_RULES)
_BATCH_SYSTEM_RULES = _BATCH_SYSTEM_RULES.replace(
    'linguagem falada em primeira pessoa.', 'linguagem falada natural.')
_BATCH_SYSTEM_RULES = re.sub(
    r'\n6\. Fale na primeira pessoa,.*?(?=\n7\.)', '',
    _BATCH_SYSTEM_RULES, flags=re.S)
BATCH_SYSTEM_PROMPT = _BATCH_SYSTEM_RULES + """

MODO LOTE — CORES DA MESMA CAMPANHA
- Você receberá vários briefings, cada um com uma CHAVE única.
- Escreva três opções completas e independentes para CADA chave.
- Não misture cores, fatos, objeções ou benefícios entre os briefings.
- Varie a ideia central entre as cores sempre que os fatos permitirem. Não
  entregue o mesmo roteiro trocando apenas o nome da cor.
- Cada briefing contém um EIXO NARRATIVO OBRIGATÓRIO diferente. Esse eixo
  determina a história e a abertura daquela cor; não é um rótulo para ser
  pronunciado. Não use a estrutura, a tensão nem a conclusão de outro eixo.
- A cor pode aparecer na fala quando for relevante, mas não precisa ser a
  ideia central de todas as versões.
- Primeira pessoa é uma opção, não uma obrigação. Alterne naturalmente entre
  experiência pessoal, observação direta, contraste e situação de uso.
- As faixas mínimas de palavras são alvos de ritmo. Uma frase natural um pouco
  mais curta é válida; nunca preencha espaço com palavras artificiais.
- Devolva todas as chaves recebidas exatamente uma vez.
- Gere somente hook, development e cta. A legenda pertence à etapa de
  publicação e não faz parte desta solicitação.

Responda SOMENTE com um objeto JSON válido, sem markdown, sem comentário:
{"scripts": [{"key": "CHAVE_RECEBIDA", "options": [{"hook": "...", "development": "...", "cta": "..."}, {"hook": "...", "development": "...", "cta": "..."}, {"hook": "...", "development": "...", "cta": "..."}]}]}"""


_BATCH_AXES = (
    ('quebra de objeção', 'parta do principal receio e mostre a descoberta que o desfaz'),
    ('qualidade percebida', 'comece por um detalhe visível de corte, acabamento ou modelagem'),
    ('versatilidade', 'conecte a peça a ocasiões diferentes sem inventar característica técnica'),
    ('autoestima', 'conte como o visual muda a confiança ou a vontade de se arrumar'),
    ('praticidade', 'mostre como a peça simplifica a escolha ou a combinação do visual'),
    ('prova em movimento', 'abra com uma dúvida de uso e resolva com o benefício demonstrável'),
    ('cor e estilo', 'faça desta cor a razão visual da escolha, sem apenas repetir seu nome'),
    ('descoberta inesperada', 'contraste a primeira impressão com um detalhe observado depois'),
    ('detalhe de design', 'construa a história ao redor do fato confirmado mais específico'),
)


def _batch_axis(index: int, campaign: dict) -> tuple[str, str]:
    """Assign a stable, safe creative lane to each color in the same request."""
    axes=list(_BATCH_AXES)
    if _offer_text(campaign):
        axes.insert(5,('economia real', 'use somente a oferta confirmada para explicar o valor da escolha'))
    return axes[index % len(axes)]


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
    api_key = str(raw.get('api_key') or '')
    enabled = bool(raw.get('enabled'))
    source = 'saved' if api_key else ''
    # Chave da OpenAI guardada como variavel de ambiente secreta (Vercel ou
    # variavel do Windows; o app nao le .env). Nunca no codigo: o repositorio vai para o GitHub e a
    # OpenAI revoga sozinha toda chave que aparece la. A chave salva pela
    # tela continua tendo prioridade; desligar a IA na tela tambem vale.
    env_key = os.environ.get('OPENAI_API_KEY', '').strip()
    if not api_key and env_key and provider in ('', 'openai'):
        provider, api_key, source = 'openai', env_key, 'env'
        # Ligada por padrao: o "enabled: false" de um arquivo salvo antes de
        # a chave existir nao conta. So desliga quem desmarcou na tela.
        enabled = not raw.get('disabled_by_user')
    model = str(raw.get('model') or '')
    if not model or model in LEGACY_DEFAULT_MODELS.get(provider, ()):
        model = DEFAULT_MODELS.get(provider, '')
    return {
        'provider': provider,
        'api_key': api_key,
        'model': model,
        'enabled': enabled and bool(provider) and bool(api_key),
        'key_source': source,
        'disabled_by_user': bool(raw.get('disabled_by_user')),
    }


# Formato de cada chave. Conferir antes de gravar evita o caso mais comum:
# colar so um pedaco da chave, ou a chave do outro provedor.
KEY_FORMATS = {
    'openai': (r'^sk-[A-Za-z0-9_\-]{20,}$', 'A chave da OpenAI começa com "sk-" e é bem mais longa.'),
    'gemini': (r'^AIza[0-9A-Za-z_\-]{30,}$', 'A chave do Gemini começa com "AIza".'),
}
VERIFY_TIMEOUT = 12


def verify_key(provider: str, key: str, model: str = '') -> tuple[bool, str]:
    """Confere a chave (e o modelo) direto no provedor, sem gastar créditos.

    Listar os modelos da conta e gratuito e responde 401/403 para chave
    invalida. Antes a chave era gravada e ligada sem nenhuma conferencia: o
    erro so aparecia na hora de escrever um roteiro, longe da configuracao.
    """
    if provider not in KEY_FORMATS:
        return False, 'Escolha OpenAI ou Gemini.'
    pattern, hint = KEY_FORMATS[provider]
    if not re.match(pattern, key or ''):
        return False, f'Chave em formato inválido. {hint}'
    if provider == 'openai':
        request = urllib.request.Request('https://api.openai.com/v1/models',
                                         headers={'Authorization': f'Bearer {key}'})
    else:
        request = urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000',
                                         headers={'x-goog-api-key': key})
    try:
        with urllib.request.urlopen(request, timeout=VERIFY_TIMEOUT) as response:
            data = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403) or (provider == 'gemini' and exc.code == 400):
            return False, ('A chave foi recusada pelo provedor. Confira se copiou a chave inteira '
                           'e se ela continua ativa na sua conta.')
        if exc.code == 429:
            return False, 'O provedor recusou por limite de uso ou falta de créditos na conta (429).'
        return False, f'O provedor respondeu {exc.code} ao conferir a chave. Tente de novo em instantes.'
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False, 'Não foi possível falar com o provedor para conferir a chave. Verifique a internet e tente de novo.'
    model = (model or '').strip()
    if model:
        if provider == 'openai':
            names = {str(item.get('id') or '') for item in data.get('data') or [] if isinstance(item, dict)}
        else:
            names = {str(item.get('name') or '').removeprefix('models/') for item in data.get('models') or []
                     if isinstance(item, dict)}
        if names and model not in names:
            return False, f'O modelo "{model}" não está disponível para esta chave. Confira o nome do modelo.'
    return True, ''


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
        current['disabled_by_user'] = not current['enabled']
    current['enabled'] = bool(current['enabled'] and current['provider'] and current['api_key'])
    # A chave que veio do ambiente nunca e copiada para o arquivo salvo.
    from_env = current.pop('key_source', '') == 'env' and not (isinstance(key, str) and key.strip())
    if from_env:
        current['api_key'] = ''
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
        'key_source': s.get('key_source', ''),
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
        f"MOTOR DOMINANTE: {_dominant_motor(c)}"
        + (" (escolhido pelo operador -- use as formulas desse motor, nao troque)" if _chosen_motor(c) else ""),
    ]
    if _dominant_motor(c) == 'escassez' and not offer:
        linhas.append("ESCASSEZ DE CONTEXTO (sem oferta real): use só descoberta honesta "
                      "(\"achei e não esperava\", \"não sabia que tinha\"), nunca prazo, estoque ou desconto inventado.")
    if pain:
        linhas.append(f"OBJEÇÃO Nº 1 DO CLIENTE: {pain}")
    if check:
        linhas.append(f"COMO A CÂMERA DERRUBA ESSA OBJEÇÃO: {check}")
    if offer:
        linhas.append(f"OFERTA REAL (pode usar urgência): {c.get('offer')}")
    else:
        linhas.append("OFERTA REAL: não existe — PROIBIDO usar qualquer palavra de urgência.")
    linhas.extend(persuasion.brief_lines(_dominant_motor(c), c.get('offer') if offer else '',
                                         c.get('social_proof'), bool(pain)))
    linhas.extend(formats.brief_lines(c, pain))
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
    linhas.extend(_category_lines(c))
    linhas.extend(_learning_lines(c.get('learning')))
    return '\n'.join(linhas)


def _category_lines(c: dict) -> list[str]:
    """Voz da categoria (banco de falas) e falas que o estudio aprovou.

    Exemplo e direcao de ritmo e de jeito de falar. Fato continua vindo so
    dos FATOS CONFIRMADOS: uma fala aprovada de outro biquini nao autoriza
    dizer "tem bojo" deste.
    """
    cat = speech_bank.category(speech_bank.detect(c))
    linhas = []
    if cat:
        linhas.append(f"CATEGORIA DA PEÇA: {cat['label']}. Como quem usa fala dela: {cat['tone']} "
                      f"Cuidado: {cat['avoid']}")
        linhas.append('OCASIÕES QUE COMBINAM COM ESSA PEÇA (no máximo uma, e só se servir ao nicho): '
                      + ', '.join(cat['occasions']))
    salvas = [i for i in (c.get('speech_bank') or []) if isinstance(i, dict) and i.get('hook')][:4]
    if salvas:
        linhas.append('FALAS APROVADAS PELO ESTÚDIO (siga o ritmo e o jeito de falar; '
                      'nunca copie a frase nem traga fato de outra peça):')
        linhas.extend(f"- \"{i.get('hook')}\" / \"{i.get('development')}\" / \"{i.get('cta')}\""
                      for i in salvas)
    elif cat:
        exemplos = [e for e in speech_bank.showcase(cat['id']) if not e.get('needs')][:2]
        if exemplos:
            linhas.append('EXEMPLOS DE VOZ DESSA CATEGORIA (ritmo e naturalidade; não copie):')
            linhas.extend(f"- \"{e['hook']}\" / \"{e['development']}\" / \"{e['cta']}\"" for e in exemplos)
    return linhas


def _learning_lines(learning: dict | None) -> list[str]:
    """Traduz o desempenho real dos videos publicados em direcao de escrita.

    Ate aqui o video numero 100 era escrito com a mesma informacao do video
    numero 1: nada do que ja tinha ido ao ar chegava a quem escreve. Estas
    linhas fecham esse ciclo.

    Cuidado deliberado: o que entra e DIRECAO (que tipo de abertura prendeu,
    que busca trouxe gente), nunca fato de produto. Um gancho que funcionou em
    outra peca nao autoriza afirmar nada sobre esta -- por isso o bloco termina
    lembrando que os FATOS CONFIRMADOS continuam sendo a unica fonte.
    """
    if not isinstance(learning, dict):
        return []
    linhas = []
    vencedores = [t for t in (learning.get('top_hooks') or []) if str(t or '').strip()][:3]
    fracos = [t for t in (learning.get('weak_hooks') or []) if str(t or '').strip()][:2]
    buscas = [t for t in (learning.get('hot_queries') or []) if str(t or '').strip()][:5]
    if vencedores:
        linhas.append('ABERTURAS QUE PRENDERAM NESTA CONTA (use o tipo de abordagem, '
                      'jamais copie a frase nem transfira atributo de uma peça para outra):')
        linhas.extend(f'- {t}' for t in vencedores)
    if fracos:
        linhas.append('ABERTURAS QUE NÃO PRENDERAM (evite esta abordagem):')
        linhas.extend(f'- {t}' for t in fracos)
    if buscas:
        linhas.append('BUSCAS QUE TROUXERAM PÚBLICO DE VERDADE (vale usar o vocabulário '
                      'delas quando descrever a peça): ' + ', '.join(buscas))
    if linhas:
        linhas.append('Esse histórico é direção de escrita. Os FATOS CONFIRMADOS acima '
                      'continuam sendo a única coisa que você pode afirmar sobre esta peça.')
    return linhas


# --------------------------------------------------------------------------- auditoria
def audit(pack: dict, c: dict, require_caption: bool = True,
          strict_style: bool = True) -> list[str]:
    """Devolve violações que realmente impedem o uso do roteiro.

    ``strict_style`` conserva a curadoria mais exigente da geração individual.
    No lote ele fica desligado: contagem mínima, primeira pessoa e formato do
    gancho são preferências editoriais, não motivos para perder todas as cores
    de uma chamada válida. Tetos de duração, fatos inventados, falsa urgência,
    direção de cena falada e repetição do roteiro anterior continuam bloqueando.
    """
    problemas = []
    for campo, (low, high) in BUDGET.items():
        texto = (pack.get(campo) or '').strip()
        if not texto:
            problemas.append(f'{campo} veio vazio')
            continue
        n = _count_words(texto)
        if strict_style and n < low:
            problemas.append(f'{campo} tem {n} palavras, precisa de pelo menos {low}')

    checked_fields = ('hook', 'development', 'cta', 'caption') if require_caption else ('hook', 'development', 'cta')
    falado = ' '.join((pack.get(k) or '') for k in checked_fields).casefold()
    hook = (pack.get('hook') or '').strip().casefold()
    development = (pack.get('development') or '').strip().casefold()
    cta = (pack.get('cta') or '').strip().casefold()
    # Texto padrao do nicho ("mostrar tecido stretch, cos e suporte") nao
    # libera promessa: so o que o operador escreveu.
    briefing = ' '.join(without_niche_defaults(c.get(k)) for k in
                        ('product', 'outfit', 'details', 'benefit', 'angle', 'objection'))
    for termo in CLAIM_TERMS:
        if termo in falado and termo not in briefing:
            problemas.append(f'"{termo}" não está no briefing e não pode ser afirmado')

    if not _offer_text(c):
        for padrao in URGENCY_PATTERNS:
            achado = re.search(padrao, falado)
            if achado:
                problemas.append(f'"{achado.group(0)}" é urgência e não existe oferta real no briefing')
                break
    # Com oferta, cada tipo de urgencia precisa do seu fato (prazo, estoque,
    # desconto com o numero exato...); prova social so se declarada.
    problemas.extend(persuasion.urgency_problems(
        falado, c.get('offer') if _offer_text(c) else '', c.get('social_proof')))

    for padrao in STAGE_DIRECTION_PATTERNS:
        achado = re.search(padrao, falado)
        if achado:
            problemas.append(f'"{achado.group(0)}" é direção de cena e não pode ser pronunciada')
            break

    if strict_style:
        for padrao in GENERIC_HOOK_PATTERNS:
            if re.search(padrao, hook):
                problemas.append('o hook é uma pergunta ou abertura genérica; use uma experiência, receio ou descoberta específica')
                break

        if not any(re.search(padrao, f'{hook} {development}') for padrao in FIRST_PERSON_PATTERNS):
            problemas.append('hook e desenvolvimento não soam como experiência pessoal em primeira pessoa')

        if any(re.search(padrao, cta) for padrao in WEAK_CTA_PATTERNS):
            problemas.append('o CTA pede permissão ou termina fraco; use uma ação direta no carrinho laranja')

    if re.search(r'\b(?:mulheres|homens|pessoas)\s+(?:de\s+)?\d{2}\s*(?:a|-|–)\s*\d{2}\b', falado):
        problemas.append('a fala recita a faixa etária do público')

    colors = color_variants(c.get('color'))
    color = (c.get('color') or '').strip().casefold()
    if strict_style and color and len(colors) <= 1 and color in cta:
        problemas.append('o CTA repete a cor sem acrescentar uma razão para agir')

    previous = c.get('previous_script') or {}
    if isinstance(previous, dict):
        for field in ('hook','development','cta'):
            old = re.sub(r'\W+', ' ', str(previous.get(field) or '').casefold()).strip()
            new = re.sub(r'\W+', ' ', str(pack.get(field) or '').casefold()).strip()
            if old and new and difflib.SequenceMatcher(None, old, new).ratio() > 0.85:
                problemas.append(f'{field} repete quase literalmente o roteiro atual (poucas palavras trocadas)')

    caption = (pack.get('caption') or '')
    if require_caption:
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


def _post_json(url: str, payload: dict, headers: dict, timeout: int = TIMEOUT) -> dict:
    data = json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json', **headers})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))
    except TimeoutError as exc:
        raise ProviderError(
            f'o provedor de IA não respondeu em {timeout} segundos. '
            'Tente novamente; nenhuma fala foi alterada.'
        ) from exc
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
_OPTIONAL_OPENAI = ('temperature', 'response_format', 'top_p', 'reasoning_effort')
# Modelos que raciocinam (gpt-5.x / gpt-6.x / o-series): esforco baixo basta
# para extrair dados e escrever 3 falas curtas, e corta tempo e custo. Quem
# nao aceita o parametro tem ele retirado na repeticao (sem custo: o 400 nao
# consome tokens).
REASONING_EFFORT = 'low'


def _reasoning_model(model: str) -> bool:
    return bool(re.match(r'^(gpt-5|gpt-6|o\d)', str(model or '')))


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
    if _reasoning_model(body['model']):
        # Modelo que raciocina recusa temperature: nem manda, e economiza a
        # repeticao.
        body.pop('temperature')
        body['reasoning_effort'] = settings.get('reasoning_effort') or REASONING_EFFORT
    for _ in range(len(_OPTIONAL_OPENAI) + 1):
        try:
            post_args=(
                'https://api.openai.com/v1/chat/completions', body,
                {'Authorization': f"Bearer {settings['api_key']}"},
            )
            if settings.get('_request_timeout'):
                out = _post_json(
                    *post_args, timeout=int(settings['_request_timeout']))
            else:
                # Mantém a assinatura de três argumentos usada também pelas
                # integrações e testes antigos; _post_json aplica TIMEOUT.
                out = _post_json(*post_args)
            uso = out.get('usage') or {}
            _record_usage(body.get('model'), uso.get('prompt_tokens'), uso.get('completion_tokens'))
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
            if settings.get('_request_timeout'):
                out = _post_json(
                    url, body, {}, timeout=int(settings['_request_timeout']))
            else:
                out = _post_json(url, body, {})
            uso = out.get('usageMetadata') or {}
            _record_usage(settings.get('model'), uso.get('promptTokenCount'), uso.get('candidatesTokenCount'))
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


def _tidy(text: str) -> str:
    """Acerta o que a IA erra na pontuacao: inicial minuscula e virgula
    depois de conectivo no inicio ("Mas, essa aqui")."""
    text = ' '.join(str(text or '').split())
    text = re.sub(r'(^|[.!?]\s+)(Mas|E|Aí|Então|Só que),\s+', r'\1\2 ', text)
    return text[:1].upper() + text[1:]


def _clean_pack(dados: dict) -> dict:
    pack = {k: str(dados.get(k) or '').strip() for k in ('hook', 'development', 'cta', 'caption')}
    for k in ('hook', 'development', 'cta'):
        pack[k] = _tidy(pack[k])
    return pack


def _weak_cta(text: str) -> bool:
    value=(text or '').strip().casefold()
    return not value or any(re.search(pattern,value) for pattern in WEAK_CTA_PATTERNS)


def _strong_cta(c: dict, index: int = 0) -> str:
    """Close with action and ethical urgency, never invented scarcity."""
    offer=_offer_text(c).casefold()
    if offer:
        offer_short=' '.join(offer.split()[:5]).rstrip('.,;:')
        if re.search(r'últim|ultim|estoque|esgot|peças|pecas|unidades',offer):
            pool=[f'Corre pro carrinho laranja: {offer_short}.']
        else:
            pool=[f'Aproveita {offer_short} no carrinho laranja.']
    else:
        pool=[
            'Corre pro carrinho laranja e confere os detalhes agora.',
            'Abre o carrinho laranja e escolhe a sua versão.',
            'Aproveita e garante a sua versão no carrinho laranja.',
            'Não deixa pra depois: confere no carrinho laranja agora.',
            'Toca no carrinho laranja e vê todos os detalhes.',
        ]
        if len(color_variants(c.get('color'))) > 1:
            pool.insert(0,'Escolhe a tua cor agora no carrinho laranja.')
    return pool[int(index or 0)%len(pool)]


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


def _parse_batch_candidates(raw: str) -> dict[str, list[dict]]:
    """Parse the keyed batch format without allowing duplicate colors/keys."""
    texto = (raw or '').strip()
    texto = re.sub(r'^```(?:json)?|```$', '', texto, flags=re.M).strip()
    inicio, fim = texto.find('{'), texto.rfind('}')
    if inicio >= 0 and fim > inicio:
        texto = texto[inicio:fim + 1]
    dados = json.loads(texto)
    scripts = dados.get('scripts') if isinstance(dados, dict) else None
    if not isinstance(scripts, list):
        raise ValueError('resposta em lote não contém scripts')
    parsed: dict[str, list[dict]] = {}
    for item in scripts:
        if not isinstance(item, dict):
            continue
        key = str(item.get('key') or '').strip()
        options = item.get('options')
        if not key or key in parsed or not isinstance(options, list):
            raise ValueError('chave ausente ou repetida na resposta em lote')
        packs = [_clean_pack(option) for option in options if isinstance(option, dict)]
        if not packs:
            raise ValueError(f'nenhuma opção recebida para a chave {key}')
        parsed[key] = packs[:5]
    return parsed


ORAL_MARKERS = (r'\bpra\b', r'\btá\b', r'\btô\b', r'\bgente\b', r'\bsério\b',
                r'\bnuma boa\b', r'\bdemais\b', r'\bjeitinho\b', r'\baí\b')


def _creative_score(pack: dict, c: dict) -> int:
    """Desempata candidatos validos pela naturalidade e especificidade."""
    hook = (pack.get('hook') or '').casefold()
    development = (pack.get('development') or '').casefold()
    cta = (pack.get('cta') or '').casefold()
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
    # Marcas de fala de verdade ("pra", "tô", "gente", "sério") contam a favor.
    falado = f'{hook} {development}'
    score += min(3, sum(1 for m in ORAL_MARKERS if re.search(m, falado)))
    # Meio que vira fila de ordens ("Repara... Olha... Confere...") soa locutor.
    ordens = len(re.findall(r'(?:^|[.!?]\s+)(?:e\s+)?(?:repara|olha|confere|veja|note|observe)\b', development))
    score -= 2 * max(0, ordens - 1)
    if 'carrinho laranja' in cta:
        score += 3
    if re.match(r'^(corre|abre|toca|escolhe|garante|aproveita|não deixa)',cta):
        score += 2
    if _weak_cta(cta):
        score -= 5
    return score


def _spoken_similarity(left: dict, right: dict) -> tuple[float, float, float]:
    """Similarity of hook, development and their combined narrative.

    CTA is intentionally excluded: the honest TikTok actions are limited and
    two good scripts may legitimately close with the same short instruction.
    """
    def clean(value):
        return re.sub(r'\W+', ' ', str(value or '').casefold()).strip()
    left_hook, right_hook = clean(left.get('hook')), clean(right.get('hook'))
    left_dev, right_dev = clean(left.get('development')), clean(right.get('development'))
    hook = difflib.SequenceMatcher(None,left_hook,right_hook).ratio()
    development = difflib.SequenceMatcher(None,left_dev,right_dev).ratio()
    combined = difflib.SequenceMatcher(
        None,f'{left_hook} {left_dev}',f'{right_hook} {right_dev}').ratio()
    return hook,development,combined


def batch_diversity_issues(items: list[tuple[str, dict]]) -> list[str]:
    """Reject scripts that merely swap the color while keeping the same copy."""
    issues=[]
    for index,(left_label,left) in enumerate(items):
        for right_label,right in items[index+1:]:
            hook,development,combined=_spoken_similarity(left,right)
            if (combined>=0.82 or (hook>=0.88 and development>=0.72)
                    or (development>=0.90 and hook>=0.65)):
                issues.append(
                    f'{left_label} e {right_label} repetem a mesma estrutura '
                    f'(similaridade {round(combined*100)}%)')
    return issues


def _parse(raw: str) -> dict:
    """Formato antigo usado por testes e integracoes locais."""
    return _parse_candidates(raw)[0]


def write_script(c: dict, settings: dict, attempts: int = 2,
                 orcamento_s: float = BUDGET_SECONDS) -> tuple[dict | None, str]:
    """Escreve as falas com o modelo. Devolve (pacote, motivo_da_falha).

    ``orcamento_s`` limita o tempo TOTAL da etapa. Sem ele, duas tentativas de
    25 segundos somavam quase um minuto de tela parada para quem so queria
    gerar o roteiro -- e, na nuvem, chegavam perto do teto de duracao da
    funcao. Esgotado o orcamento, o app usa o texto deterministico, que agora
    passa na mesma auditoria.
    """
    caller = CALLERS.get(settings.get('provider'))
    if not caller or not settings.get('api_key'):
        return None, 'sem provedor configurado'
    user = build_brief(c)
    ultimo = ''
    comeco = time.monotonic()
    for tentativa in range(max(1, attempts)):
        if tentativa and (time.monotonic() - comeco) + TIMEOUT > orcamento_s:
            # Nao comeca uma tentativa que nao tem tempo de terminar.
            return None, (ultimo or 'sem tempo para uma nova tentativa')
        restante = max(1.0, orcamento_s - (time.monotonic() - comeco)) if tentativa else orcamento_s
        try:
            # Teto de tempo TOTAL da chamada. O timeout do urllib vale por
            # operacao de rede e o provedor ainda repete ao recusar um
            # parametro: sem isto uma chamada lenta passava do limite de 60s
            # da funcao na nuvem e a tela so mostrava "demorou demais".
            bruto = _call_with_deadline(
                lambda s, sy, u, _imgs: caller(s, sy, u),
                settings, SYSTEM_PROMPT, user, None, orcamento_s=restante)
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
        for candidate_index,pack in enumerate(candidates):
            if _weak_cta(pack.get('cta')):
                pack={**pack,'cta':_strong_cta(c,candidate_index)}
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


def write_scripts(campaigns: list[dict], settings: dict,
                  attempts: int = 1,
                  orcamento_s: float = BUDGET_SECONDS,
                  index_offset: int = 0) -> tuple[dict[str, dict] | None, str]:
    """Write and audit several color scripts in one provider request.

    The result is keyed by ``batch_key`` so a provider cannot silently reorder
    colors. The operation succeeds only when every requested color has an
    audited script; callers can therefore persist the batch atomically.

    ``index_offset`` e a posicao do primeiro item deste lote no pedido inteiro: quando
    write_scripts_in_groups divide as cores em grupos, cada cor continua com o seu eixo
    narrativo e o seu CTA, sem repetir os do outro grupo.
    """
    caller = CALLERS.get(settings.get('provider'))
    if not caller or not settings.get('api_key'):
        return None, 'sem provedor configurado'
    if not campaigns:
        return None, 'nenhuma cor recebida'

    briefs = []
    expected: dict[str, dict] = {}
    for index, campaign in enumerate(campaigns):
        key = str(campaign.get('batch_key') or index)
        if key in expected:
            return None, f'chave repetida no lote: {key}'
        axis_name,axis_direction=_batch_axis(index+index_offset,campaign)
        campaign={**campaign,'batch_axis':axis_name}
        expected[key] = campaign
        briefs.append(
            f'### CHAVE: {key}\n'
            f'EIXO NARRATIVO OBRIGATÓRIO: {axis_name} — {axis_direction}.\n'
            f'PROIBIDO reutilizar este eixo, a estrutura do hook ou a sequência do desenvolvimento em outra chave.\n'
            f'{build_brief(campaign)}')
    base_user = ('Gere os roteiros de TODAS as chaves abaixo. Cada bloco é um '
                 'vídeo separado; nunca combine cores no mesmo roteiro.\n\n'
                 + '\n\n'.join(briefs))
    user = base_user
    ultimo = ''
    comeco = time.monotonic()

    for tentativa in range(max(1, attempts)):
        if tentativa and (time.monotonic() - comeco) + TIMEOUT > orcamento_s:
            return None, ultimo or 'sem tempo para uma nova tentativa'
        try:
            # Um lote com cinco cores produz muito mais JSON que uma única
            # fala. Ele ganha uma janela própria, sem deixar os demais botões
            # da interface presos por 45 segundos quando o provedor oscila.
            batch_settings={**settings, '_request_timeout': BATCH_TIMEOUT}
            bruto = caller(batch_settings, BATCH_SYSTEM_PROMPT, user)
            parsed = _parse_batch_candidates(bruto)
        except ProviderError as exc:
            if exc.status:
                return None, f'o provedor respondeu {exc.status}: {exc.message[:400]}'
            return None, exc.message[:400]
        except urllib.error.URLError as exc:
            return None, f'nao foi possivel falar com o provedor ({exc.reason})'
        except (ValueError, KeyError, IndexError) as exc:
            ultimo = f'resposta em lote ilegível ({exc})'
            continue

        missing = [key for key in expected if key not in parsed]
        extras = [key for key in parsed if key not in expected]
        if missing or extras:
            ultimo = ('chaves ausentes: ' + ', '.join(missing) if missing else '')
            if extras:
                ultimo += ('; ' if ultimo else '') + 'chaves desconhecidas: ' + ', '.join(extras)
            continue

        approved_by_key: dict[str, list[dict]] = {}
        rejected: list[str] = []
        for key_index,(key, campaign) in enumerate(expected.items()):
            approved = []
            for candidate_index,pack in enumerate(parsed[key]):
                if _weak_cta(pack.get('cta')):
                    pack={**pack,'cta':_strong_cta(campaign,index_offset+key_index+candidate_index)}
                # Em lote, estilo e comprimento minimo orientam o modelo, mas
                # nao anulam todas as cores. A auditoria ainda bloqueia riscos
                # concretos (fato inventado, urgencia falsa, camera falada).
                problemas = audit(
                    pack, campaign, require_caption=False, strict_style=False)
                if problemas:
                    rejected.extend(f'{campaign.get("color") or key}: {item}' for item in problemas)
                else:
                    approved.append(pack)
            if approved:
                approved_by_key[key]=sorted(
                    approved,key=lambda item:_creative_score(item,campaign),reverse=True)
            else:
                rejected.append(f'{campaign.get("color") or key}: nenhuma opção passou na auditoria')
        if len(approved_by_key) == len(expected):
            # Escolhe cada roteiro considerando os ja escolhidos. Antes, o
            # ranking isolado selecionava o mesmo candidato "forte" para todas
            # as cores, mesmo quando o modelo tinha devolvido alternativas.
            selected: dict[str, dict] = {}
            for key,campaign in expected.items():
                choices=[]
                for candidate in approved_by_key[key]:
                    comparisons=[_spoken_similarity(candidate,other) for other in selected.values()]
                    if any(combined>=0.82 or (hook>=0.88 and development>=0.72)
                           or (development>=0.90 and hook>=0.65)
                           for hook,development,combined in comparisons):
                        continue
                    max_similarity=max((combined for _h,_d,combined in comparisons),default=0.0)
                    choices.append((_creative_score(candidate,campaign)-round(max_similarity*10),candidate))
                if not choices:
                    rejected.append(
                        f'{campaign.get("color") or key}: as opções repetem o roteiro de outra cor')
                    break
                selected[key]=max(choices,key=lambda item:item[0])[1]
            if len(selected)==len(expected):
                diversity=batch_diversity_issues([
                    (expected[key].get('color') or key,pack) for key,pack in selected.items()])
                if not diversity:
                    return selected, ''
                rejected.extend(diversity)

        unique = []
        for item in rejected:
            if item not in unique:
                unique.append(item)
        ultimo = '; '.join(unique[:12])
        user = (base_user + '\n\nA tentativa anterior foi recusada pela auditoria:\n- '
                + '\n- '.join(unique[:12]) + '\nReescreva todas as chaves corrigindo esses pontos.')
    return None, ultimo or 'os textos do lote não passaram na auditoria'


# Cores por chamada ao provedor. Com 8 cores numa chamada so, a IA precisava escrever os roteiros de
# todas de uma vez e estourava a janela de 45 s do lote (422 depois de 52 s no Vercel, cuja funcao morre
# em 60 s). Em grupos de ate 4, cada chamada tem metade do trabalho e os grupos correm ao mesmo tempo.
BATCH_CHUNK = 4


def split_even(items: list, size: int = BATCH_CHUNK) -> list[list]:
    """Divide em grupos equilibrados de no maximo `size` (8 -> 4+4, 5 -> 3+2, 9 -> 3+3+3)."""
    if not items:
        return []
    groups = math.ceil(len(items) / max(1, size))
    base, extra = divmod(len(items), groups)
    out, start = [], 0
    for index in range(groups):
        count = base + (1 if index < extra else 0)
        out.append(items[start:start + count])
        start += count
    return out


def write_scripts_in_groups(campaigns: list[dict], settings: dict,
                            attempts: int = 1,
                            orcamento_s: float = BUDGET_SECONDS,
                            group_size: int = BATCH_CHUNK) -> tuple[dict[str, dict] | None, str]:
    """Escreve os roteiros de TODAS as cores em grupos de ate `group_size`, com os grupos ao mesmo tempo.

    Ate `group_size` cores e exatamente o write_scripts de antes (uma chamada). Acima disso, cada grupo
    e um write_scripts (com a sua auditoria e a sua diversidade interna) e o resultado so existe se TODOS
    os grupos passarem: um grupo recusado recusa o lote inteiro, como sempre, e a mensagem diz qual.
    """
    if len(campaigns) <= group_size:
        return write_scripts(campaigns, settings, attempts, orcamento_s)
    groups = split_even(campaigns, group_size)
    offsets, total = [], 0
    for group in groups:
        offsets.append(total)
        total += len(group)
    with ThreadPoolExecutor(max_workers=len(groups)) as pool:
        futures = [pool.submit(write_scripts, group, settings, attempts, orcamento_s, offset)
                   for group, offset in zip(groups, offsets)]
        results = [future.result() for future in futures]
    failures = []
    for number, ((written, reason), group) in enumerate(zip(results, groups), 1):
        if not written:
            cores = ', '.join(str(item.get('color') or item.get('batch_key')) for item in group)
            failures.append(f'{reason or "resposta inválida"} (grupo {number} de {len(groups)}: {cores})')
    if failures:
        return None, '; '.join(failures)
    merged: dict[str, dict] = {}
    for written, _reason in results:
        merged.update(written)
    # Cada grupo e diverso por dentro; aqui confere o conjunto (cores de grupos diferentes).
    colors = {str(item.get('batch_key') or index): item.get('color') for index, item in enumerate(campaigns)}
    issues = batch_diversity_issues([(colors.get(key) or key, pack) for key, pack in merged.items()])
    if issues:
        return None, 'os grupos repetiram roteiros entre cores: ' + '; '.join(issues[:6])
    return merged, ''


# --------------------------------------------------------------------------- visao (analise de produto)
VISION_SYSTEM_PROMPT = """Você é um analista de produtos de moda para vídeos UGC de TikTok Shop.

Você recebe até quatro fotos, nesta ordem:
1. Uma ou mais fotos do produto/roupa (como ele é, cor, tecido, corte; podem ser ângulos diferentes da mesma peça).
2. Por último, a foto da página de descrição do produto no TikTok Shop/loja (specs, tecido, características escritas).

Cada foto vem identificada por função na mensagem do usuário - use essa identificação para saber qual é qual.

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


def _shrink_for_vision(image_bytes: bytes, mime: str) -> tuple[bytes, str]:
    """Reduz a foto para no maximo VISION_MAX_SIDE px (JPEG). Se nao der pra
    abrir a imagem, manda a original -- a IA decide se consegue ler."""
    try:
        import io
        from PIL import Image, ImageOps
        with Image.open(io.BytesIO(image_bytes)) as img:
            img = ImageOps.exif_transpose(img)
            if max(img.size) <= VISION_MAX_SIDE and len(image_bytes) <= 1_500_000:
                return image_bytes, mime
            img.thumbnail((VISION_MAX_SIDE, VISION_MAX_SIDE))
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            out = io.BytesIO()
            img.save(out, format='JPEG', quality=85)
            return out.getvalue(), 'image/jpeg'
    except Exception:
        return image_bytes, mime


def _call_with_deadline(caller, settings: dict, system: str, user: str, images, orcamento_s: float) -> str:
    """Chama o provedor com teto de tempo TOTAL. O timeout do urllib vale por
    operacao de rede (e o provedor ainda pode repetir a chamada ao recusar um
    parametro), entao sozinho nao garante que a requisicao termine antes do
    limite da funcao na nuvem."""
    import threading
    resultado: dict = {}

    def alvo():
        try:
            resultado['ok'] = caller(settings, system, user, images)
        except BaseException as exc:  # repassado para quem chamou
            resultado['erro'] = exc

    # O contexto vai junto para a thread: sem isso o uso da IA se perdia.
    tarefa = threading.Thread(target=contextvars.copy_context().run, args=(alvo,), daemon=True)
    tarefa.start()
    tarefa.join(orcamento_s)
    if tarefa.is_alive():
        raise ProviderError(
            f'a IA não respondeu em {int(orcamento_s)} segundos. '
            'O briefing foi salvo; tente de novo ou preencha os campos à mão.')
    if 'erro' in resultado:
        raise resultado['erro']
    return resultado['ok']


def analyze_product(images: list[tuple[bytes, str, str]], settings: dict, context: str = '') -> tuple[dict | None, str]:
    """Analisa fotos do produto (e/ou da descrição) e devolve sugestoes pros
    campos do briefing. Cada item de `images` e (bytes, mime, rotulo) - o
    rotulo diz pra IA qual foto e qual (produto ou descricao), na mesma
    ordem descrita no prompt de visao. Usa a mesma configuracao
    (provedor/chave/modelo) das Configuracoes de Escrita com IA - se o
    modelo suportar visao (gpt-6-luna e gemini-2.0-flash suportam, e sao
    os padroes do app), funciona sem nenhuma chave nova. Devolve
    (campos_sugeridos, motivo_da_falha)."""
    caller = CALLERS.get(settings.get('provider'))
    if not caller or not settings.get('api_key'):
        return None, 'Configure a IA em "Configurações de Escrita com IA" antes de analisar fotos.'
    if not images:
        return None, 'Nenhuma foto para analisar.'
    identificacao = '; '.join(f'Foto {i}: {rotulo}' for i, (_, _, rotulo) in enumerate(images, start=1) if rotulo)
    user = 'Analise as fotos anexadas e devolva o JSON pedido.'
    if identificacao:
        user += f'\n\nIdentificação de cada foto, na ordem enviada: {identificacao}.'
    if context:
        user += f'\n\nContexto adicional (não invente além disso): {context}'
    fotos = [_shrink_for_vision(dados, mime) for dados, mime, _ in images]
    settings = vision_settings(settings)
    try:
        bruto = _call_with_deadline(
            caller, {**settings, '_request_timeout': min(TIMEOUT, VISION_BUDGET_SECONDS)},
            VISION_SYSTEM_PROMPT, user, fotos, orcamento_s=VISION_BUDGET_SECONDS)
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


# --------------------------------------------------------------------------- criar com IA
QUICK_VISION_PROMPT = """Você monta o briefing de um vídeo UGC de TikTok Shop a partir de fotos.

Você recebe, nesta ordem: uma a três fotos do produto/roupa; se houver, a foto das cores (print do
seletor de cores da loja ou as variações lado a lado); e, por último (se houver), o print da página do
produto no TikTok Shop ou na loja (título, especificações, preço, avaliações).
Cada foto vem identificada na mensagem do usuário.

Se a foto mostra um look com várias peças, o produto é a peça indicada pela pessoa ou citada no print.
Sem essa indicação, escolha a peça mais destacada e descreva SÓ ela: nunca misture peças diferentes
(teste real: a IA descreveu a blusa quando o produto era a calça).

Olhe SOMENTE o que está visível ou escrito nas fotos e devolva um JSON com estes campos, em
português do Brasil:

- "product": nome curto e claro da peça, como a cliente falaria (ex.: "Biquíni de amarração com bojo",
  "Calça jeans wide leg"). Sem marca, sem código, no máximo 8 palavras.
- "colors": uma lista com cada cor à venda. Descreva cada cor como a cliente diria: a cor de fundo
  mais o detalhe visível que a diferencia (estampa, flores, listras, debrum, cordão), no máximo 6
  palavras e SEM vírgula dentro da cor (ex.: ["Laranja com floral branco", "Verde com floral branco"]).
  Fonte, em ordem de prioridade: a foto das cores; as cores listadas no print; a cor da foto do
  produto. Olhe a cor real dos pixels, não o nome comercial (se o print diz "Terracota" e a peça é
  laranja, escreva "Laranja"). Nunca invente uma cor que não aparece.
- "niche": exatamente um destes: "praia", "academia", "casual", "dia-a-dia", "intima", "fantasia".
- "details": fatos do produto que estão escritos ou claramente visíveis (tecido/composição, forro,
  bojo, bolso, cintura alta, amarração, renda, zíper...), separados por vírgula. Nada de opinião.
- "benefit": o principal benefício real, uma frase curta, só com o que está visível ou escrito.
- "angle": o ângulo de venda mais forte para esta peça, uma frase curta.
- "movements": de 3 a 5 movimentos corporais simples para mostrar esta peça em vídeo, separados por
  ponto e vírgula (ex.: "ajustar a alça; dar dois passos; virar de leve para o lado").
- "objection": a dúvida que mais segura a compra DESTE tipo de peça, do jeito que a cliente pensa
  (ex.: "fica transparente no agachamento", "não segura em cima", "parece plástico de perto").
- "offer": SOMENTE se o print mostrar desconto, preço de/por, prazo, estoque, frete grátis ou cupom
  escritos na página. Copie os números exatamente (ex.: "20% off, de R$ 89 por R$ 69, frete grátis").
  Se não estiver escrito, "".
- "social_proof": SOMENTE se o print mostrar vendidos, nota ou número de avaliações. Copie os números
  exatamente (ex.: "2 mil vendidos, nota 4,8"). Se não estiver escrito, "".

Nunca invente característica (elasticidade, compressão, proteção UV, "não marca"...), desconto,
prazo, estoque ou avaliação. Campo sem informação confiável volta como "".
Responda SOMENTE com o JSON, sem texto antes ou depois."""

QUICK_FIELDS = ('product', 'colors', 'niche', 'details', 'benefit', 'angle', 'movements',
                'objection', 'offer', 'social_proof')
QUICK_LIMITS = {'product': 120, 'colors': 300, 'niche': 20, 'details': 1500, 'benefit': 300,
                'angle': 300, 'movements': 800, 'objection': 200, 'offer': 300, 'social_proof': 200}


def _parse_quick(raw: str, niches) -> dict:
    texto = re.sub(r'^```(?:json)?|```$', '', (raw or '').strip(), flags=re.M).strip()
    inicio, fim = texto.find('{'), texto.rfind('}')
    if inicio >= 0 and fim > inicio:
        texto = texto[inicio:fim + 1]
    dados = json.loads(texto)
    if not isinstance(dados, dict):
        raise ValueError('resposta não é um objeto')
    out = {}
    for campo in QUICK_FIELDS:
        valor = dados.get(campo)
        if isinstance(valor, list):
            valor = ', '.join(str(v) for v in valor)
        if isinstance(valor, str) and valor.strip():
            out[campo] = ' '.join(valor.split())[:QUICK_LIMITS[campo]]
    if out.get('niche') not in niches:
        out.pop('niche', None)
    # Oferta e prova social so passam com numero ou fato reconhecivel: texto
    # vago ("preço ótimo") nao vira urgencia.
    if out.get('offer') and not persuasion.offer_facts(out['offer']).keys() - {'raw'}:
        out.pop('offer')
    if out.get('social_proof') and not persuasion.social_facts(out['social_proof']):
        out.pop('social_proof')
    return out


def vision_settings(settings: dict) -> dict:
    """Leitura de fotos usa o modelo de visao do provedor (mais barato e tao
    preciso quanto o de escrita para extrair dados), salvo se a configuracao
    pedir outro."""
    model = settings.get('vision_model') or VISION_MODELS.get(settings.get('provider'))
    return {**settings, 'model': model} if model else settings


def quick_brief(images: list[tuple[bytes, str, str]], settings: dict, niches,
                niche: str = '', hint: str = '') -> tuple[dict | None, str]:
    """Briefing inteiro a partir das fotos do produto e do print da pagina
    ("Criar com IA"). Devolve (campos, motivo_da_falha). Nada e gravado aqui:
    a tela mostra o resultado para a pessoa conferir antes de criar."""
    caller = CALLERS.get(settings.get('provider'))
    if not caller or not settings.get('api_key'):
        return None, 'A escrita por IA não está configurada.'
    if not images:
        return None, 'Envie pelo menos uma foto do produto.'
    identificacao = '; '.join(f'Foto {i}: {rotulo}' for i, (_, _, rotulo) in enumerate(images, start=1))
    user = f'Monte o briefing com as fotos anexadas.\n\nIdentificação de cada foto, na ordem: {identificacao}.'
    if niche in niches:
        user += f'\n\nNicho escolhido pela pessoa (use este): {niche}.'
    hint = ' '.join((hint or '').split())[:80]
    if hint:
        user += (f'\n\nA PEÇA À VENDA é: {hint}. Descreva SOMENTE essa peça (nome, cores, detalhes, movimentos e '
                 'objeção); ignore as outras roupas e acessórios da foto.')
    fotos = [_shrink_for_vision(dados, mime) for dados, mime, _ in images]
    settings = vision_settings(settings)
    try:
        bruto = _call_with_deadline(
            caller, {**settings, '_request_timeout': min(TIMEOUT, VISION_BUDGET_SECONDS)},
            QUICK_VISION_PROMPT, user, fotos, orcamento_s=VISION_BUDGET_SECONDS)
        campos = _parse_quick(bruto, niches)
    except ProviderError as exc:
        if exc.status:
            return None, f'o provedor respondeu {exc.status}: {exc.message[:300]}'
        return None, exc.message[:300]
    except urllib.error.URLError as exc:
        return None, f'não foi possível falar com o provedor ({exc.reason})'
    except (ValueError, KeyError, IndexError) as exc:
        return None, f'resposta ilegível ({exc})'
    if not campos.get('product'):
        return None, 'a IA não conseguiu identificar o produto nas fotos'
    if niche in niches:
        campos['niche'] = niche
    return campos, ''
