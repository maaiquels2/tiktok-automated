# CTAs dos vídeos longos: os 10 tipos e o suspense/FOMO na abertura

A lista de 10 CTAs ("Roube essas 10 CTAs para vender mais") é escrita para criadores. Aqui ela virou o **fechamento do último
clipe** das sequências de 2 ou 3 clipes (`services/story_arcs.py`), em `services/cta_types.py`, sob as regras do projeto: só
afirma o que o briefing sustenta, e só o último clipe pede a compra (sempre com "carrinho laranja").

## A regra
1. **A cor 1 do vídeo longo é o rascunho validado de sempre.** Da segunda cor em diante, cada cor recebe um **tipo de CTA** (na
   ordem abaixo, só entre os que o briefing sustenta) e as cores de posição ímpar (2ª, 4ª…) abrem com **suspense e FOMO**.
2. Cada cor fecha diferente: nem o mesmo texto nem as mesmas 3 primeiras palavras das cores anteriores.
3. Tipo sem fala livre passa para o próximo; sem nenhum, vale o fechamento de sempre.
4. Vale só para o rascunho. Fala editada pelo operador ou escrita pela IA não leva tipo (a IA recebe a regra e o tipo da cor no
   pedido: `write_lines_with_ai`).
5. A resposta da API traz `closing_type` e `opening_type` do rascunho de cada cor (a partir da segunda).

## Mapa dos 10 CTAs
| # | CTA original | Destino | Condição |
|---|---|---|---|
| 1 | Reforçar o custo-benefício | **adaptado**: "Pra mim, por esses três motivos, vale conferir no carrinho laranja." Opinião em 1ª pessoa, sem preço (não existe campo de preço) | sempre |
| 2 | Criar urgência com oferta | **usado**: "Tá com 20% de desconto: abre o carrinho laranja." Só com os números da oferta declarada | oferta real no briefing |
| 3 | Quebrar uma objeção | **usado**: "Com receio de {dor}? Tira essa dúvida no carrinho laranja." (a dor só entra se tiver até 4 palavras) | objeção no briefing |
| 4 | Reforçar a prova real | **usado**: "Ela já vendeu mais de 2 mil", nota, altura ou tamanho declarados | prova social ou de tamanho |
| 5 | Destacar um diferencial | **usado**: "Só por {fato}, já vale conferir…", com um dos 3 fatos confirmados | sempre (o arco tem 3 fatos) |
| 6 | Falar com um público específico | **usado**: "Amigas baixinhas, confere no carrinho laranja." | identidade declarada em "Público" |
| 7 | Comparar com uma alternativa | **adaptado**: "Compara com o que você já tem…". Convida a comparar, não afirma nada de outro produto | sempre |
| 8 | Usar sua experiência pessoal | **adaptado**: "Eu mesma ficaria com ela". Gosto, nunca "usei por 3 meses" (história que ninguém verifica) | sempre |
| 9 | Relembrar o problema | **usado**: a dor do briefing, a dúvida do arco "Dúvida e resposta" ou o "nada parece certo" do arco "Problema e solução" | dor ou arco de dúvida/problema |
| 10 | Deixar a decisão com o comprador | **usado**: "A decisão é sua: o carrinho laranja tá aí." | sempre |

Ordem de rotação: oferta, objeção, prova, público, problema, diferencial, experiência, custo-benefício, comparar, decisão.

## Suspense e FOMO na abertura (cores 2, 4, 6…)
Abre uma lacuna que o próprio vídeo fecha: "Fica até o fim: o terceiro motivo pra essa calça é o que quase todo mundo passa
batido." Uma frase para cada arco, duas versões que se alternam. **Não é escassez**: estoque, prazo e preço continuam só com
oferta real (a auditoria barra "últimas peças", "acaba hoje" sem oferta), e a abertura nunca pede a compra.

## Testes
`tests/test_cta_types.py`: todos os arcos, 2 e 3 clipes, espelho e de frente, 11 cores e 6 briefings (nada, objeção, prova,
público, oferta, tudo): auditoria, faixa de palavras, "carrinho" só no último clipe, fechamento diferente por cor e cada fala só
com o que o briefing sustenta.
