# Revisão de interface — diretrizes da Vercel (12/10/2026)

Fonte das regras: `vercel-labs/web-interface-guidelines` (arquivo `command.md`, MIT). Revisão **só de leitura**, feita por
mim contra o código de `frontend/src` (App.jsx, components.jsx, Landing.jsx, serviceLinks.jsx, os 3 CSS e `index.html`).
O skill da Vercel **não foi instalado**; usei as regras diretamente. As regras de redação da Vercel (Title Case, voz ativa)
foram ignoradas: são preferências da marca deles e não valem para português.

**Limite da revisão:** foram checagens mecânicas (busca por padrões) mais leitura dos pontos que apareceram. Não abri
cada um dos ~150 botões e ~76 campos um a um, nem testei com leitor de tela.

## O que já está conforme
| Regra | Evidência |
|---|---|
| Nada de `transition: all` | 0 ocorrências |
| Foco visível e substituído quando removido | `design-fixes.css:332` tira o contorno do input, mas `:has(input:focus-visible)` desenha um no cartão |
| Movimento reduzido respeitado | `styles.css:4651` zera animações e transições |
| Zoom liberado | `<meta viewport>` sem `user-scalable=no` |
| Colar não é bloqueado | 0 `onPaste` |
| Tema escuro e área segura | `color-scheme` + `prefers-color-scheme: dark`; `safe-area-inset` em uso |
| Estado na URL | rotas por hash (`#/inicio`, `#/entrar`) em `App.jsx` |
| Aviso antes de perder alterações | `beforeunload` em `App.jsx:88` |
| Nomes acessíveis | 66 `aria-label`; os campos ficam dentro de `<label>`; nenhum botão só com ícone sem nome foi achado |
| Avisos anunciados | `role="status"`/`role="alert"`/`aria-live` em 13 pontos |
| Fechar com Esc | lightbox (`components.jsx:1665`) e renomeação (`:1819`) |
| Números alinhados | `tabular-nums` em 4 lugares |
| `autoFocus` | 4 usos, todos em campos que o usuário acabou de abrir (renomear, senha nova, nome de modelo): ok |

## O que eu corrigiria
Ordem pela utilidade para você, que usa no celular e no computador.

1. **`touch-action: manipulation` ausente (0 ocorrências).** No celular, toque duplo em botão pode dar zoom ou atraso.
   Correção de 1 linha no CSS global (`button, a, input, select, label { touch-action: manipulation; }`).
2. **Campos sem `autocomplete="off"` nos campos de briefing.** São ~76 campos e só 7 têm `autoComplete`. Produto, detalhes,
   movimentos e benefício podem receber sugestão do histórico do navegador ou até oferta de gerenciador de senhas.
   Em campos que não são de login a regra manda desligar.
3. **Imagens sem largura e altura (15 de 17 `<img>`).** Causa salto de layout quando a foto carrega. Pontos:
   `App.jsx:609, 745, 1009`; `components.jsx:64, 1143, 1144, 1262, 1840, 1886, 2616, 2621, 2626`. Só 3 têm `loading="lazy"`
   (as fotos fora da primeira tela da lista de campanhas poderiam ter).
4. **`:hover` sem `@media (hover: hover)`.** 29 regras `:hover` (19 em `styles.css`, 9 em `redesign.css`, 1 em
   `design-fixes.css`). No celular o hover "gruda" depois do toque.
5. **Falta `<meta name="theme-color">` no `index.html`.** A barra do navegador no celular não acompanha o fundo do app
   (e há tema escuro).
6. **`text-wrap: balance` nos títulos (0 usos).** Cosmético: evita linha final com uma palavra só.

## Observações, sem ação
- `components.jsx:1825` e `:1874–1875` são `<div onClick>`, mas só param a propagação ou fecham o lightbox (que tem
  `role="dialog"`, `aria-modal` e Esc). Não é navegação nem ação escondida.
- 20 usos de `confirm()` nativo para ações destrutivas: cumpre a regra de confirmar. Nenhum oferece "desfazer".
- Listas longas (regra: virtualizar acima de 50 itens): não verifiquei. Com poucas campanhas por conta, provavelmente não pesa.

## Fora do escopo desta revisão
O `components.jsx` tem 2.643 linhas e o `styles.css` 5.414. Isso não é regra de interface, mas pesa na manutenção e
no tamanho do pacote (o build avisa de arquivo acima de 500 kB).
