# Teste de sequência para o CapCut: calça jeans no espelho

Objetivo: descobrir se **2 ou 3 vídeos de 15 s se encaixam num só** (cerca de 30 ou 45 s) e qual técnica
de emenda funciona no Grok. Base: o espelho que saiu perfeito no controle K2.

Nada aqui custa API: os prompts saem do gerador do app (`monta_sequencia.py`) e as falas passam na
auditoria de honestidade. O custo é só o tempo e as gerações do Grok.

## O que o primeiro teste mostrou

- **A identidade segurou:** modelo, roupa, espelho e luz iguais nos 14 vídeos, todos em 480p.
- **A emenda não foi testada.** Os clipes 2 e 3 começaram todos na **imagem-base** (a do K2), e não no
  último quadro do clipe anterior. O `confere_emenda.py` mede isso: imagem-base x início do clipe = 5,2
  (praticamente iguais) contra 15 a 35 para fim do clipe anterior x início. No corte, a pose e o
  enquadramento reiniciam. Funciona como corte seco, mas não é a emenda invisível que se quer avaliar.

## Os 4 arcos

| Arco | Clipes | Resumo |
|---|---|---|
| **A-motivos** | 3 (~45 s) | gancho + motivo 1 / motivos 2 e 3 / projeção + CTA |
| **B-questionada** | 3 (~45 s) | a pergunta / desmonta os motivos / resposta + CTA |
| **A-motivos-2clipes** | 2 (~30 s) | gancho + motivos 1 e 2 / motivo 3 + projeção + CTA |
| **B-questionada-2clipes** | 2 (~30 s) | a pergunta + 1º motivo desmontado / os outros 2 + resposta + CTA |

**2 ou 3 clipes?** Pela skill de sequência: 2 clipes quando há uma objeção principal ou o produto é simples
de explicar; 3 quando existem pelo menos duas provas distintas de verdade. Nunca escolha 3 pelo tamanho: um
terceiro clipe sem fato novo vira enchimento e derruba a retenção. A calça jeans tem 4 fatos e comporta os dois.
Os arcos de 2 clipes **não são os de 3 sem o clipe do meio**: o clipe do meio carrega as perguntas abertas e o
último carrega o CTA, por isso têm falas próprias.

Leis (já aplicadas nos prompts): só o último clipe pede a compra e aponta para o carrinho; os anteriores
terminam **no meio do gesto**, com uma pergunta aberta; os seguintes **não** recomeçam com hook nem
reapresentam a peça; o bloco de modelo e de cenário é copiado palavra por palavra.

## Próximo teste: a emenda de verdade (comece pelos arcos de 2 clipes, só há 1 emenda)

1. **Clipe 1:** anexe a imagem do K2 (`lote-grok-2026-10-12\clipes\K2-calca-jeans-espelho\calca_jeans.jpg`)
   e use `sequencias\A-motivos-2clipes\clipe-1\1-prompt-completo.txt`.
2. **Clipe 2, técnica "imagem":** rode
   `.venv\Scripts\python.exe lote-sequencia-2026-10-12\ultimo_quadro.py CAMINHO\video-do-clipe-1.mp4`,
   escolha o melhor dos 3 quadros (a, b ou c) e anexe **esse quadro, não a imagem do K2**, com
   `clipe-2\1-prompt-completo.txt`.
3. **Clipe 2, técnica "Extend Video":** no vídeo do clipe 1, use Extend Video com `clipe-2\3-extend-video.txt`.
4. **Confira:**
   `.venv\Scripts\python.exe lote-sequencia-2026-10-12\confere_emenda.py clipe1.mp4 clipe2.mp4 imagem_do_k2.jpg`
   Ele deve dizer **OK** (início do clipe 2 parecido com o fim do 1). Se disser ATENÇÃO, o clipe 2 partiu da
   imagem-base. Abra também a imagem `...-emenda.png` que ele gera e confira com os olhos.
5. **Monte no CapCut** (checklist abaixo) e preencha a `AVALIACAO.md`.
6. Depois, se a emenda funcionar, repita com os arcos de 3 clipes e com o B.

## Montagem no CapCut

- [ ] Todos os clipes na **mesma resolução e fps** antes de soltar na timeline
- [ ] Apare 2 a 4 quadros do início e do fim de cada clipe (é onde o Grok deforma)
- [ ] **Corte seco** entre os clipes, sem transição chamativa (se usou Extend Video, importe só o vídeo final)
- [ ] Normalize o volume da voz entre os clipes (Áudio > Normalizar volume)
- [ ] Mesmo ajuste de cor e luz em todos
- [ ] Legenda automática **uma vez**, sobre a timeline já unida, e revise palavra por palavra
- [ ] Texto na tela de cada clipe (em `4-falas.txt`; **não vai dentro do vídeo gerado**) e a capa de `ROTEIRO.md`
- [ ] Carrinho ou seta **só no trecho do CTA, no último clipe**
- [ ] Exporte em 1080×1920, 30 fps ou mais, H.264

## Sobre a qualidade (480p)

Gerar em 480p é bom para testar rápido. Para publicar, 480p exportado em 1080×1920 fica mais macio. Se o
resultado parecer borrado, regere só os takes escolhidos em 720p ou passe-os por um upscale; não precisa
refazer tudo. O importante é que **todos os clipes de uma mesma sequência tenham a mesma resolução**.

## Sobre as falas (para revisar antes de publicar)

- Os motivos citados são só os fatos que a foto da calça mostra: cintura alta, lavagem clara, modelagem reta e
  dois bolsos na frente. Se algum não for verdade na peça real, edite `FATOS` e as falas em
  `monta_sequencia.py` e rode de novo.
- "Sabe o que dizem por aí..." (arco B) é recurso retórico: não cita pessoa real nem comentário real.
- "Eu já me imagino com ela..." é imaginação em primeira pessoa, não promessa de resultado.
- Não há afirmação de conforto, caimento nem resultado.
