# 0003 — Nuvem na Vercel e Supabase, sem VPS

**Status:** aceito

**Contexto.** O app roda no PC local (SQLite) e na nuvem (Vercel com Postgres e Storage no Supabase).

**Decisão.** Não manter servidor próprio. O foco é desempenho do app e qualidade dos prompts virais, não infraestrutura.

**Consequências.** Funções da Vercel têm limite de tempo (300 s) e de pacote: `vercel.json` exclui testes, ferramentas e relatórios da função. O código precisa funcionar nos dois bancos.
