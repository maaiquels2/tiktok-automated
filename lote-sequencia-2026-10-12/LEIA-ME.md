# Teste de sequência para o CapCut: calça jeans no espelho

Objetivo: descobrir se **3 vídeos de 15 s se encaixam num só** (cerca de 45 s) e qual arco e qual
técnica de emenda funcionam no Grok. Base: o espelho que saiu perfeito no controle K2.

Nada aqui custa API: os prompts saíram do gerador do app (`monta_sequencia.py`) e as falas passaram na
auditoria de honestidade. O custo é só o tempo e as gerações do Grok.

## Os 2 arcos (3 clipes cada)

| | Clipe 1 | Clipe 2 | Clipe 3 |
|---|---|---|---|
| **A · Motivos** | "3 motivos pra ter essa calça" + motivo 1 (cintura alta) | motivos 2 e 3 (lavagem clara, perna reta, bolsos) | projeção de uso + CTA |
| **B · Questionada** | "Calça jeans não te valoriza?" e os 3 motivos de quem duvida | desmonta cada motivo com um fato da peça | a resposta ("a pergunta é qual calça") + CTA |

Leis da sequência (já aplicadas nos prompts): só o clipe 3 pede a compra e aponta para o carrinho; os clipes
1 e 2 terminam **no meio do gesto**, com uma pergunta aberta; o clipe 2 e o 3 **não** recomeçam com hook
nem reapresentam a peça; o bloco de modelo e de cenário é copiado palavra por palavra.

## Antes de gerar (3 conferências)

1. **Os fatos da calça.** O script usa só o que a foto mostra: cintura alta, lavagem clara, modelagem reta e
   dois bolsos na frente. Se algum não for verdade na peça real, avise ou edite `FATOS` e as falas em
   `monta_sequencia.py` e rode de novo.
2. **A mesma resolução em todos os clipes.** No lote anterior só C1, C2 e um vídeo do C3 saíram em 720×1280;
   os outros vieram em 400×736. Numa sequência, resoluções diferentes aparecem como salto na emenda. Gere
   tudo na mesma qualidade do Grok e confira o tamanho de cada arquivo antes de montar.
3. **A imagem do clipe 1** é a que você já aprovou no K2:
   `lote-grok-2026-10-12\clipes\K2-calca-jeans-espelho\calca_jeans.jpg`.

## Ordem recomendada (cerca de 7 gerações no arco A e 3 no B)

**Arco A, o que decide a técnica:**
1. **Clipe 1:** anexe a imagem do K2 e use `sequencias\A-motivos\clipe-1\1-prompt-completo.txt`.
   (Se quiser as duas versões, gere também com `2-guia-grok.txt` e fique com a melhor.)
2. **Clipe 2, técnica "imagem":** rode `ultimo_quadro.py` no vídeo do clipe 1, escolha o melhor dos 3 quadros
   (a, b ou c), anexe e use `clipe-2\1-prompt-completo.txt`.
3. **Clipe 2, técnica "Extend Video":** no vídeo do clipe 1, use Extend Video com `clipe-2\3-extend-video.txt`.
4. **Compare as duas** com a `AVALIACAO.md`. A vencedora segue para o clipe 3.
5. **Clipe 3** pela técnica vencedora (`1-prompt-completo.txt` ou `3-extend-video.txt`).
6. **Monte no CapCut** (checklist abaixo) e avalie o vídeo final.

**Arco B:** repita os clipes 1, 2 e 3 só com a técnica vencedora.

## Montagem no CapCut (por arco)

- [ ] Todos os clipes na **mesma resolução e fps** antes de soltar na timeline
- [ ] Apare 2 a 4 quadros do início e do fim de cada clipe (é onde o Grok deforma)
- [ ] **Corte seco** entre os clipes, sem transição chamativa (se usou Extend Video, importe só o vídeo final)
- [ ] Normalize o volume da voz entre os clipes (Áudio > Normalizar volume)
- [ ] Mesmo ajuste de cor e luz nos três
- [ ] Legenda automática **uma vez**, sobre a timeline já unida, e revise palavra por palavra
- [ ] Texto na tela de cada clipe (está em `4-falas.txt`; **não vai dentro do vídeo gerado**) e a capa de `ROTEIRO.md`
- [ ] Carrinho ou seta **só no trecho do CTA, no clipe 3**
- [ ] Exporte em 1080×1920, 30 fps ou mais, H.264

## Sobre as falas (para você revisar antes de publicar)

- "Sabe o que dizem por aí..." (arco B) é recurso retórico: não cita pessoa real nem comentário real. Se um dia
  houver um comentário de verdade, vale trocar.
- "Eu já me imagino com ela..." é imaginação em primeira pessoa, não promessa de resultado.
- Os motivos citados são só os quatro fatos acima. Não há afirmação de conforto, caimento ou resultado.
