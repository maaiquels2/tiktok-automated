"""Clipes de 10 s para o Flow (Gemini Omni Flash, 720p): o formato validado nos lotes de 2026-11-06.

O gerador de prompts do app escreve tudo para 15 s (janelas 0-4, 4-12 e 12-15 s, "15 segundos", 1080p no Flow). Quem monta
a sequencia em 10 s passa o texto pronto por ``retime`` e ``flow_safe``: so o texto muda, nada no gerador. Opt-in: sem
``seconds=10`` nada aqui roda e a saida de 15 s e a de sempre.

O que a producao no Flow ensinou (lotes do top, do maio e do colete):
  - o Flow desenhou o ícone e a marca d'água do TikTok quando o prompt citava "TikTok" e "carrinho laranja": nenhuma
    menção a TikTok, proibição explícita de logotipo de aplicativo e o convite vira "link aqui embaixo";
  - o clima do prompt diz que é uma cena casual do dia a dia (um clipe foi recusado como conteúdo sexual);
  - o clipe de 10 s sai em 720p.
"""
import re

SECONDS = (15, 10)
# (inicio, fim) de cada trecho: abertura, meio e fechamento
WINDOWS = {10: ((0, 3), (3, 8), (8, 10))}
# Faixa de palavras de um clipe de 10 s: abaixo disso sobra silencio no fim; acima a fala fica corrida (cerca de 3,6 a 4
# palavras por segundo, a densidade do app em 15 s).
WORDS = {10: (33, 40)}

CASUAL = ('Clima: fit check casual no espelho, gravado com o celular, tom leve e simpático, roupa de passeio do dia a '
          'dia.')
NO_LOGO = "logotipo, ícone ou marca d'água de qualquer aplicativo ou rede social"

_CTA_LINK = (
    (re.compile(r'\b(?:pro|no|ao) carrinho laranja\b', re.I), 'no link aqui embaixo'),
    (re.compile(r'\bcarrinho laranja\b', re.I), 'link aqui embaixo'),
    (re.compile(r'\bcarrinho\b', re.I), 'link'),
)


def valid(seconds):
    return seconds in SECONDS


def word_window(seconds):
    """(piso, teto) de palavras por clipe, ou None para 15 s (a faixa de sempre, em script_budget)."""
    return WORDS.get(seconds)


def link_cta(text):
    """A fala sem "carrinho laranja": no Flow o carrinho falado virava ícone na tela. "Corre pro carrinho laranja e garante
    o teu" vira "Corre no link aqui embaixo e garante o teu"."""
    for pattern, new in _CTA_LINK:
        text = pattern.sub(new, text)
    return text


def retime(text, seconds):
    """Leva um prompt escrito para 15 s às janelas de ``seconds`` (10). 15 devolve o texto como veio."""
    if seconds == 15 or not text:
        return text
    (h0, h1), (m0, m1), (f0, f1) = WINDOWS[seconds]
    t = text
    t = t.replace('exatamente 15 segundos', f'exatamente {seconds} segundos')
    t = re.sub(r'\b15 segundos', f'{seconds} segundos', t)
    t = t.replace('SHOT LIST 15s', f'SHOT LIST {seconds}s')
    t = re.sub(r'(?<!\d)15 s\b', f'{seconds} s', t)
    t = re.sub(r'de 15s em leitura', f'de {seconds}s em leitura', t)
    t = re.sub(r'0–\d+s (HOOK|CONTINUAÇÃO)', rf'{h0}–{h1}s \1', t)
    t = re.sub(r'\d+–\d+s DESENVOLVIMENTO', f'{m0}–{m1}s DESENVOLVIMENTO', t)
    t = re.sub(r'\d+–15s (CTA|FIM DO TRECHO)', rf'{f0}–{f1}s \1', t)
    t = re.sub(r'ENCERRAMENTO \(\d+–\d+s\)', f'ENCERRAMENTO ({f0}–{f1}s)', t)
    # Janelas de gesto ("entre 5s e 10s"): proporcionais, sem passar do fim do trecho do meio.
    t = re.sub(r'entre (\d+)s e (\d+)s',
               lambda m: f'entre {round(int(m.group(1)) * seconds / 15)}s e {min(round(int(m.group(2)) * seconds / 15), m1)}s',
               t)
    # O Flow gera o clipe de 10 s em 720p.
    t = t.replace('1080 × 1920 (1080p)', '720 × 1280 (720p)')
    return t


def flow_safe(text, strip_context=False):
    """Texto sem o que fez o Flow desenhar o ícone do TikTok e sem o tom que levou a recusa: ver o topo do módulo."""
    if not text:
        return text
    t = text
    t = t.replace('UGC TikTok Shop vertical', 'UGC vertical')
    t = re.sub(r'Clima: fit check no espelho gravado com o celular e postado no TikTok\.', CASUAL, t)
    t = re.sub(r' e postado no TikTok\b', '', t)
    t = re.sub(r'\bpostado no TikTok\b', 'postado nas redes', t)
    t = re.sub(r'\bTikTok Shop\b', 'a loja', t)
    t = re.sub(r'\bTikTok\b', 'as redes', t)
    # "Sentar, levantar e caminhar para revelar o caimento" contradiz o espelho fixo do clipe de 10 s (e os ganchos).
    if strip_context:
        t = re.sub(r' CONTEXTO VISUAL OPCIONAL \(não é fato do produto; não inventar\): [^.]*\.', '', t)
    t = t.replace('EVITAR: textos, ícones, carrinho,', f'EVITAR: {NO_LOGO}, textos, ícones, carrinho,')
    t = t.replace('sem texto, ícone, carrinho,', f'sem {NO_LOGO}, sem texto, ícone, carrinho,')
    return t


def timing_problems(text, seconds):
    """O que sobrou de 15 s num texto de ``seconds`` (lista vazia = ok). Devolve avisos, nunca levanta: um aviso na tela
    vale mais que um erro 500 na producao."""
    if seconds == 15 or not text:
        return []
    out = []
    if re.search(r'(?<!\d)15 ?(s\b|seg)', text):
        out.append('sobrou "15 s" no texto')
    if re.search(r'\b1080p\b', text):
        out.append('sobrou 1080p no texto')
    if re.search(r'TikTok', text):
        out.append('o prompt ainda cita TikTok: o Flow pode desenhar o ícone')
    for a, b in re.findall(r'(\d+)–(\d+)\s?s\b', text):
        if int(b) > seconds or int(a) >= int(b):
            out.append(f'janela {a}–{b}s fora dos {seconds} s')
            break
    for a, b in re.findall(r'entre (\d+)s e (\d+)s', text):
        if int(b) > WINDOWS[seconds][1][1]:
            out.append(f'gesto entre {a}s e {b}s invade o fechamento')
            break
    return out
