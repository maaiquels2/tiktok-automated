# Inventário da Fábrica TikTok (atualizado)

**Data:** 2026-09-11  
**App local:** pasta do projeto + `iniciar.vbs` → http://127.0.0.1:5050  
**GitHub:** https://github.com/maaiquels2/tiktok-automated  
**Conta TikTok (este PC):** configurável em Identidade (`data/studio_identity.json`) — padrão Micaela / `@dicasdamiicaela`

## Em uma frase

Fábrica local de Shorts/TikTok Shop (Flask + React + SQLite) com **Início / Produzir / Resultados**, identidade por PC, playbook a partir do Studio, fila de 5 posts/dia e Grok+Flow na **mesma janela** (abas).

## Stack

| Camada | Tecnologia |
|--------|------------|
| Backend | Python / Flask, SQLite |
| Frontend | Vite + React (stepper de etapas; sem React Flow) |
| Studio / métricas | Playwright + Chrome CDP (`browser_profiles/{modelo}-cdp`) |
| Geração mídia | Manual via Grok Imagine / Google Flow (perfil compartilhado `flow-maaiquels` ou `gen-maaiquels`) |
| Vídeo | FFmpeg mix + gate Critico |
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

Cada PC tem `data/studio_identity.json`. **Não copiar** `browser_profiles/` nem `data/` entre creators. Ver `COMO-INSTALAR-NO-OUTRO-PC.md`.

## O que continua humano (de propósito)

- Gerar imagem/vídeo no Grok/Flow  
- Publicar no TikTok Studio  

## Rotinas Grok Bot

- Auto-cut → Critico (dias úteis)  
- Digest semanal Studio (segunda 9h America/Sao_Paulo)

## Limitações

- Scrape do Studio pode quebrar se o TikTok mudar o DOM (há retries + mensagem clara)  
- Cloud Agents Cursor Pro são opcionais; a fábrica roda local  
