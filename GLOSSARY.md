# Glossário

Termos do domínio da Fábrica TikTok. Use estes nomes no código, nos testes e nas conversas.

**Campanha** — Um produto a ser vendido, com briefing (produto, público, benefício, tom, detalhes), modelo e uma ou mais cores. É a unidade que o usuário cria, aprova e acompanha.

**Cor** — Variante do produto dentro de uma campanha. Cada cor tem seu próprio prompt de imagem, de vídeo e sua própria fala (variante em `generate_variants`).

**Briefing** — Campos que descrevem a campanha. Mudar qualquer campo além do nome apaga prompts, variantes e mídia já gerados; o app pede confirmação antes.

**Fala** — Texto falado no vídeo, escrito em primeira pessoa no tom de UGC (nunca voz de catálogo). Tem três partes: gancho, desenvolvimento e CTA.

**Gancho (hook)** — Primeiros segundos da fala; prende a atenção.

**Desenvolvimento** — Miolo da fala, que mostra o produto e o motivo de compra.

**CTA** — Chamada final para comprar. Tem que ser diferente em cada cor (texto e as três primeiras palavras), ver `distinct_ctas` e o ADR 0001.

**Banco de falas** — Moldes de frases curadas (`speech_bank`, `speech_curated`, `speech_future`) que o gerador mistura antes de recorrer a uma IA externa.

**Eixo** — Ângulo de venda que diferencia uma fala da outra (dor, desejo, escassez). Usado na reescrita de falas repetidas.

**Arco** — Roteiro de uma sequência, por exemplo `motivos` ou `problema`, com um papel para cada clipe (`story_arcs`).

**Sequência** — Vídeo de venda de 30 a 45 s formado por 2 ou 3 clipes encadeados, montados depois no CapCut.

**Clipe** — Trecho de até ~15 s gerado de uma vez no Grok ou no Flow. Tem limite de palavras; acima de 60 o app avisa que a fala fica corrida.

**Imagem-base** — Primeiro quadro que ancora identidade, cenário e roupa de todos os clipes.

**Espelho** — Modo de vídeo em que a modelo se grava em selfie no espelho, com o celular na mão.

**Enquadramento** — Quanto do corpo aparece: corpo inteiro, joelhos ou cintura. O app escolhe pela peça (blusas ficam fechadas); o usuário pode forçar com as fichas `enq_*` em `video_style`.

**Agente do Grok** — Pacote de mensagens para o modo agente do Grok gerar as imagens de todas as cores de uma vez (`agent_images`).

**Gerador** — Ferramenta externa de vídeo: Grok Imagine ou Google Flow.

**Curadoria** — Pipeline offline (`ferramentas/curadoria_falas`) que gera, verifica e julga frases para alimentar o banco de falas.
