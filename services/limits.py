"""Numeros que o gerador, a IA, as sequencias e a tela precisam concordar.

Antes cada um tinha o seu: o gerador cortava acima de 57 palavras, a IA recebia "45 a 55", a tela avisava abaixo
de 44 e as sequencias usavam 46 a 57. A tela le os mesmos numeros em frontend/src/speechBudget.js, e um teste
confere que os dois arquivos batem.
"""

# Fala de um clipe de 15 s. Teste real: com 33 a 46 palavras sobravam 2 a 3 s de silencio no fim; com ~57 ficou
# um pouco acelerado. O alvo e 45 a 56; acima de 57 o gerador encurta pelo fim do desenvolvimento.
SPEECH_MIN = 45
SPEECH_MAX = 56
SPEECH_CEILING = 57

# O Grok corta o prompt em 4000 caracteres sem avisar. A margem cobre nome do produto, cor e movimentos, que
# vem do briefing e variam de tamanho.
GROK_PROMPT_LIMIT = 4000
GROK_PROMPT_MARGIN = 60
GROK_PROMPT_BUDGET = GROK_PROMPT_LIMIT - GROK_PROMPT_MARGIN
