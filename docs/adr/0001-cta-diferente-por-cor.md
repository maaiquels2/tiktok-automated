# 0001 — CTA diferente em cada cor

**Status:** aceito (2026-11-02)

**Contexto.** Em campanhas com várias cores, os vídeos saíam com falas quase iguais, e a mesma chamada final repetia em todos.

**Decisão.** O CTA de cada cor é único: o texto inteiro e as três primeiras palavras não podem repetir entre cores (`distinct_ctas` em `services/prompts.py`). Cores repetidas são reescritas numa segunda passada.

**Consequências.** O banco de falas precisa de muitos CTAs variados. Editar uma fala à mão não é bloqueado, mas o prompt acompanha a fala editada.
