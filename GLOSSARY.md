# Glossário

Termos do domínio da Fábrica TikTok. Use estes nomes no código, nos testes e nas conversas.

**Campanha** — Um produto a ser vendido, com briefing (produto, público, benefício, tom, detalhes), modelo e uma ou mais cores. É a unidade que o usuário cria, aprova e acompanha.

**Cor** — Variante do produto dentro de uma campanha. Cada cor tem seu próprio prompt de imagem, de vídeo e sua própria fala (variante em `generate_variants`).

**Briefing** — Campos que descrevem a campanha. Mudar qualquer campo além do nome apaga prompts, variantes e mídia já gerados; o app pede confirmação antes.

**Fala** — Texto falado no vídeo, escrito em primeira pessoa no tom de UGC (nunca voz de catálogo). Tem três partes: gancho, desenvolvimento e CTA.

**Gancho (hook)** — Primeiros segundos da fala; prende a atenção.

**Gancho de identidade** — Gancho que chama o público pelo nome ("Amigas baixinhas que não acham calça…"). Só aparece quando o campo Público declara baixinha, alta, plus size, quadril largo ou curvilínea.

**Prova de tamanho** — Altura, numeração e observação de caimento que o operador escreve no briefing ("1,47 m, tamanho 34, sobrou um pouco na barra"). É a única fonte: o app nunca deduz nem inventa esses dados, e a falsa afirmação é barrada na auditoria.

**Desenvolvimento** — Miolo da fala, que mostra o produto e o motivo de compra.

**CTA** — Chamada final para comprar. Tem que ser diferente em cada cor (texto e as três primeiras palavras), ver `distinct_ctas` e o ADR 0001.

**Banco de falas** — Moldes de frases curadas (`speech_bank`, `speech_curated`, `speech_future`) que o gerador mistura antes de recorrer a uma IA externa.

**Eixo** — Ângulo de venda que diferencia uma fala da outra (dor, desejo, escassez). Usado na reescrita de falas repetidas.

**Arco** — Roteiro de uma sequência, por exemplo `motivos` ou `problema`, com um papel para cada clipe (`story_arcs`).

**Sequência** — Vídeo de venda de 30 a 45 s formado por 2 ou 3 clipes encadeados, montados depois no CapCut.

**Clipe** — Trecho de até ~15 s gerado de uma vez no Grok ou no Flow. Tem limite de palavras; acima de 60 o app avisa que a fala fica corrida.

**Clipe de 10 s** — Opção (`seconds=10`) da sequência para o Flow (Gemini Omni Flash, 720p): janelas 0–3, 3–8 e 8–10 s, falas de 33 a 40 palavras, nenhum prompt cita TikTok (o Flow desenhava o ícone) e o convite é "link aqui embaixo" (`clip_seconds`). Três clipes formam 30 s.

**Dor e FOMO** — Arco só do clipe de 10 s (`ARCS_10S`, `dor`): o clipe 1 abre numa dor da cliente (não ter o que vestir, não se sentir valorizada, vergonha) e numa lacuna ("o último motivo quase ninguém repara") que o clipe 3 fecha. A dor muda com a posição da cor. Sem estoque, prazo nem preço.

**Gancho de câmera** — Jogada de câmera nos primeiros 3 s do clipe 1 para prender o olhar (`HOOK_VISUALS`: espia pela borda, vem correndo, dedo na câmera; ainda não testados no Flow). O clipe abre num primeiro quadro próprio (`frame_prompt`) com a imagem aprovada de referência; as falas e os clipes 2 e 3 ficam iguais, para teste A/B. Só no espelho. "Tampa a câmera" e "aparece de surpresa" foram testados e descartados.

**Imagem-base** — Primeiro quadro que ancora identidade, cenário e roupa de todos os clipes.

**Espelho** — Modo de vídeo em que a modelo se grava em selfie no espelho, com o celular na mão.

**Enquadramento** — Quanto do corpo aparece: corpo inteiro, joelhos ou cintura. O app escolhe pela peça (blusas ficam fechadas); o usuário pode forçar com as fichas `enq_*` em `video_style`.

**Agente do Grok** — Pacote de mensagens para o modo agente do Grok gerar as imagens de todas as cores de uma vez (`agent_images`).

**Gerador** — Ferramenta externa de vídeo: Grok Imagine ou Google Flow.

**Curadoria** — Pipeline offline (`ferramentas/curadoria_falas`) que gera, verifica e julga frases para alimentar o banco de falas.

**Regra do Flow** — Todo prompt de Flow (15 s ou 10 s, clipe único ou sequência) sai sem a palavra TikTok, com a proibição de logotipo e marca d'água de aplicativo e com clima casual; a fala gerada fecha com "link aqui embaixo", nunca com "carrinho laranja" (no Flow o carrinho falado virava ícone na tela). Falas digitadas pelo operador nunca são reescritas, e o Grok não muda (`clip_seconds.flow_safe` e `link_cta`). Em sequência, o padrão é 3 clipes de 10 s no Flow e 2 clipes de 15 s no Grok (30 s nos dois).
