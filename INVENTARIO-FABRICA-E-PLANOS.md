# Inventário da Fábrica TikTok (atualizado)

**Data:** 2026-09-13  
**App local:** pasta do projeto + `iniciar.vbs` → http://127.0.0.1:5050  
**App em nuvem:** URL do deploy na Vercel, com login (usuário/senha)  
**GitHub:** https://github.com/maaiquels2/tiktok-automated  
**Conta TikTok (este PC):** configurável em Identidade (`data/studio_identity.json`) — padrão Micaela / `@dicasdamiicaela`

## Em uma frase

Fábrica de Shorts/TikTok Shop (Flask + React), que roda **local (SQLite) ou em nuvem (Postgres/Supabase, na Vercel)** com o mesmo código, com **Início / Produzir / Resultados**, playbook a partir do Studio, fila de 5 posts/dia e Grok+Flow na **mesma janela** (abas).

## Stack

| Camada | Tecnologia |
|--------|------------|
| Backend | Python / Flask — SQLite (local) ou Postgres/Supabase (nuvem, `FABRICA_CLOUD=1`) |
| Frontend | Vite + React (stepper de etapas) |
| Hospedagem nuvem | Vercel (`vercel.json`, `wsgi.py`) + Supabase Storage para mídia |
| Studio / métricas | Playwright + Chrome CDP (`browser_profiles/{modelo}-cdp`) — **só na versão local** |
| Geração mídia | Manual via Grok Imagine / Google Flow (perfil compartilhado `flow-maaiquels` ou `gen-maaiquels`) — abertura assistida só na versão local; na nuvem os links abrem direto |
| Vídeo | FFmpeg mix + gate Critico — **só na versão local** |
| Login (nuvem) | Contas `owner`/`editor` por sessão Flask, criadas pelo ícone Acessos do estúdio |
| Agentes | Critico de Vendas, Editor de Mix |

## UI

### Início
- Checklist de setup (identidade, nichos, Grok/Flow, CDP)
- **Fila de hoje (5 posts)** a partir do playbook
- Biblioteca de fotos por nicho (progresso X/6)
- Identidade no ícone do header (modal)

### Produzir
- Stepper horizontal de etapas
- Criação / prompts / anexos embaixo
- Botões Abrir Grok / Flow com logos (mesma janela, abas)

### Resultados
- O que fazer / Studio / Lote / Playbook / Histórico / Campanha
- Coletar métricas, auditar lote, gerar playbook, criar campanha do brief

## APIs úteis

`/api/setup-status`, `/api/productivity` (inclui `daily_queue`), `/api/studio/identity`, `/api/studio/playbook`, `/api/studio/playbook/campaign`, `/api/studio/audit`, performance/fetch, published-link.

## Multi-creator

**Versão local:** cada PC tem `data/studio_identity.json`. **Não copiar** `browser_profiles/` nem `data/` entre creators. Ver `COMO-INSTALAR-NO-OUTRO-PC.md`.

**Versão em nuvem:** não existe separação por PC — é a mesma conta (`users`) para todo mundo. A responsável cria a conta principal e, pelo ícone Acessos do estúdio, cria/reseta a senha da segunda pessoa.

## O que continua humano (de propósito)

- Gerar imagem/vídeo no Grok/Flow  
- Publicar no TikTok Studio  

## Rotinas Grok Bot

- Auto-cut → Critico (dias úteis)  
- Digest semanal Studio (segunda 9h America/Sao_Paulo)

## Limitações

- Scrape do Studio pode quebrar se o TikTok mudar o DOM (há retries + mensagem clara) — e só existe na versão local  
- Na nuvem não há Chrome/Playwright no servidor: mixer de vídeo, auto-cut e coleta automática de métricas ficam indisponíveis lá (entrada manual)  
- Cloud Agents Cursor Pro são opcionais; a fábrica roda local ou em nuvem própria (Vercel + Supabase), sem depender deles  
- Deploy em produção está no domínio padrão da Vercel; domínio próprio ainda é próximo passo  
