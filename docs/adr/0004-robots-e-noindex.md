# 0004 — Só a landing e as páginas legais ficam indexáveis

**Status:** aceito (2026-11-02)

**Contexto.** O app é uma ferramenta privada. Só a página inicial, `/termos` e `/privacidade` são públicas (exigência do TikTok).

**Decisão.** `/robots.txt` libera apenas essas três e bloqueia o resto; `/api/*` e `/creator` respondem `X-Robots-Tag: noindex, nofollow`. Não há sitemap.

**Consequências.** Nada do app aparece em buscas. Se um dia houver páginas públicas novas, incluir no `robots.txt`.
