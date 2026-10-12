# Lote de teste no Grok: "Na mesa, de perto"

Objetivo: descobrir **quais cenas o Grok aguenta** antes de investir em consertar o resto.
As cenas são hipótese (a partir do que já falhou nos seus testes). Nenhuma foi gerada ainda.

Nada aqui custa API: os prompts saíram do gerador do site (`monta_lote.py`) e passaram na auditoria
de honestidade. O custo é só o tempo e as gerações do Grok.

## Os 8 clipes

| Id | Cena | Produto | Para quê |
|---|---|---|---|
| C1 | creme no rosto, sentada | creme facial (pote) | mão no rosto: o ponto mais frágil |
| C2 | creme no rosto, sentada | protetor solar (bisnaga) | mesma cena, outra embalagem |
| C3 | brinco aproximado da lente | brinco de argola | objeto pequeno + orelha |
| C4 | colar aproximado da lente | colar ponto de luz | corrente e pingente mudando de forma |
| C5 | peça desdobrada na mesa | pijama de cetim | o tecido que mais escorrega |
| C6 | peça desdobrada na mesa | calça jeans | o tecido que mais segura a forma |
| K1 | **controle**: espelho | pijama de cetim | confirma que o Grok de hoje ainda acerta o espelho |
| K2 | **controle**: espelho | calça jeans | idem |

Cada pasta em `clipes/` tem: `1-imagem-base`, `2-prompt-completo`, `3-guia-grok`, `4-falas`
e, nos C1 a C6, o **plano B** (`5-planoB-...`, `6-planoB-...`): a mesma cena com o meio mais simples
(creme no dorso da mão, brinco na palma, colar pendurado, peça aberta só até a metade).

## Ordem recomendada (7 gerações na rodada 1)

**Rodada 1: uma cena de cada tipo.** C1, C3 e C5, cada um com o **prompt completo e o Guia do Grok**
(6 gerações), mais o controle **K1** só com o prompt completo (1 geração).

1. **Imagem-base.** No gerador de imagem, anexe a foto de referência da modelo e cole `1-imagem-base.txt`.
   **Anexe também a foto real do produto**, se tiver: sem ela o gerador inventa o pote, o brinco ou o colar,
   e você não consegue avaliar se o Grok manteve a forma. Aprove a imagem.
2. **Vídeo.** No Grok (720p, 15 s), anexe a imagem aprovada e cole `2-prompt-completo.txt`. Gere.
3. **De novo com `3-guia-grok.txt`**, com a mesma imagem. No seu teste de 6 produtos cada versão
   ganhou em alguns, por isso as duas.
4. Preencha `AVALIACAO.md` logo depois de ver cada vídeo.

**Rodada 2** (só se a decisão abaixo mandar): C2, C4, C6 e K2, ou o plano B das cenas que falharam.

## Antes de começar

- O texto "TEXTO NA TELA" em `4-falas.txt` **não vai no vídeo**: cole no CapCut ou no TikTok.
- Os dois controles usam a mesma regra de antes (espelho). Se o K1 falhar, o Grok mudou desde o seu teste:
  trate os resultados do dia como pouco confiáveis e repita outro dia.
- Gere cada clipe no máximo **duas vezes**. Se falhou nas duas, anote e siga: o objetivo é descobrir o padrão.
