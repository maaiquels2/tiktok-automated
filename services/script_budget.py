"""Orcamento falado do roteiro de 15 s: gancho, desenvolvimento e chamada.

Antes cada parte do app tinha os proprios numeros (gerador local, prompt da IA,
auditoria, sequencia, tela) e eles discordavam. Todos leem daqui. A tela le
``frontend/src/scriptRules.json``, que um teste mantem igual a ``rules()``.
"""

CLIP_SECONDS = 15
# Ritmo de quem vende no TikTok. 46 a 57 palavras em 15 s da ~3 por segundo.
WORDS_PER_SECOND = 3
# Faixa-alvo de cada trecho: o que se pede a IA e o que a tela mostra.
TARGET = {'hook': (10, 18), 'development': (20, 40), 'cta': (7, 14)}
# Total que ocupa o clipe inteiro. Teste real: com 33 a 46 palavras sobraram
# 2 a 3 s de silencio no fim; com ~57 ja saiu um pouco acelerado.
FILL = (46, 57)
# Tolerancia antes de a tela avisar (WARN) e de a nota do prompt cair mais (HARD).
WARN = (44, 58)
HARD = (40, 64)
# Gancho acima disso demora a prender.
HOOK_MAX = 20
# Janelas do gerador local (frases prontas dos bancos): mais curtas que TARGET de
# proposito; quando o desenvolvimento fica abaixo de LOCAL_PAD_BELOW ganha uma
# frase de uso, para o total chegar a FILL.
LOCAL_PICK = {'hook': (10, 13), 'development': (10, 36), 'cta': (6, 10)}
LOCAL_PAD_BELOW = 26
# Piso da auditoria do texto da IA: abaixo disso a fala e rasa. Mais frouxo que
# TARGET de proposito: contagem de palavras nao reprova roteiro natural.
AUDIT_FLOOR = {'hook': 6, 'development': 10, 'cta': 4}

def count_words(text):
    # Ponto final solto nao conta como palavra.
    return len(str(text or '').strip().rstrip('.').split())


def rules():
    """O que a tela precisa para os chips do roteiro e a nota do prompt."""
    return dict(target={k: list(v) for k, v in TARGET.items()}, fill=list(FILL), warn=list(WARN),
                hard=list(HARD), hook_max=HOOK_MAX, words_per_second=WORDS_PER_SECOND,
                clip_seconds=CLIP_SECONDS)
