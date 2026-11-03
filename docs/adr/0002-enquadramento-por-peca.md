# 0002 — Enquadramento do espelho escolhido pela peça

**Status:** aceito (2026-11-02)

**Contexto.** Selfie de corpo inteiro esconde o detalhe de blusas e tops. Calças e shorts precisam do corpo inteiro.

**Decisão.** `services/framing.py` escolhe o quadro pela peça: blusas e tops usam plano fechado da cabeça até logo abaixo da barra, medido pela peça e não pela cintura. As demais peças mantêm o prompt de corpo inteiro já validado. O usuário sobrescreve com as fichas `enq_inteiro`, `enq_joelhos` e `enq_cintura`; escolher mais de uma é erro 400.

**Consequências.** Todos os textos de vídeo (completo, guia, sequência, arcos, agente) seguem o mesmo quadro da imagem-base. Ainda não testado com a blusa real no Grok.
