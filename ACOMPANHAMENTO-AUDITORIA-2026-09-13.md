# Acompanhamento da auditoria de 13/09 (Codex, 73 itens)

**Como foi feita a avaliação:** cada um dos 73 itens foi conferido contra o código real do projeto (não apenas contra a descrição do próprio relatório), usando cinco revisões independentes em paralelo, cada uma citando o arquivo e a linha exata onde o problema aparece. Resultado: **os 73 itens são factualmente corretos** — a auditoria do Codex é precisa sobre o que o código faz hoje. Nenhum item foi encontrado "errado" sobre o comportamento atual do sistema. As diferenças, registradas abaixo, são sobre **prioridade** e sobre **o tamanho da mudança necessária** para corrigir cada um.

**O que este documento mostra:** para cada item, se foi corrigido agora, corrigido parcialmente, ou adiado — e por quê. Os itens implementados já foram testados (90 testes automatizados do backend + build completo do frontend) e estão nos commits `f73e60a` e `a5fda90` (este último, o item 41, depois da sua confirmação sobre qual comportamento manter).

**Legenda de status:**
- ✅ **Corrigido** — implementado e testado nesta rodada.
- 🟡 **Corrigido parcialmente** — a causa mais grave foi resolvida; o pedido completo do item exige mais trabalho (fica registrado o que falta).
- ⏳ **Adiado** — confirmado como problema real, mas exige uma decisão sua (produto) ou uma mudança maior de arquitetura para ser feito com segurança.

---

## 1. Interface, navegação e revisão (itens 01–20)

| # | Item | Prior. | Status | O que foi feito / motivo do adiamento |
|---|---|---|---|---|
| 01 | Layout quebrado em larguras intermediárias | P1 | ⏳ Adiado | Precisa reescrever a cascata de CSS (`!important`) do layout de produção — risco de quebrar outras larguras se feito às pressas. Recomendo tratar isolado, testando 6 larguras de tela. |
| 02 | TikTok Studio abre o destino errado no computador | P1 | ✅ Corrigido | No computador acessando a versão online, o botão agora abre `tiktok.com/tiktokstudio` (endereço real do Studio) em vez da home do TikTok. No celular continua igual (link que o app do TikTok já reconhece). |
| 03 | Mensagens locais aparecem na versão online | P2 | ✅ Corrigido | Os textos "Dados no computador" e "abre no perfil dedicado do Chrome" agora só aparecem no modo local; na versão online mostram a frase correta ("dados salvos na nuvem", "abre em nova aba"). |
| 04 | Conta e identidade do estúdio se confundem | P2 | ⏳ Adiado | Pede reorganizar dois botões do cabeçalho com nomes/ícones próprios — mudança de UI que prefiro fazer com sua validação visual antes. |
| 05 | Logotipo principal usa um ponto de interrogação | P3 | ⏳ Adiado | Precisa de um ativo de marca (logo definitivo) que ainda não existe — depende de você (ou de alguém do design) fornecer a imagem. |
| 06 | Campanha inexistente abre outra campanha silenciosamente | P1 | ✅ Corrigido | Confirmado: pedir uma campanha que não existe caía silenciosamente na primeira da lista. Agora mostra "Campanha não encontrada" e volta para a lista, tanto na abertura do app quanto ao trocar o link manualmente. |
| 07 | Rascunhos por cor não sinalizam alterações pendentes | P1 | ⏳ Adiado | Exige integrar cada campo por cor ao controle central de "alterações não salvas" — toca vários componentes ao mesmo tempo (item 08 é o mesmo problema por outro ângulo; melhor tratar os dois juntos, com testes manuais de navegação). |
| 08 | Salvar um campo pode apagar outros rascunhos | P1 | ⏳ Adiado | Mesma causa do item 07. Precisa de reconciliação de estado por campanha/cor/campo — risco real de regressão se feito sem tempo para testar bem. |
| 09 | Navegar para Início ignora a confirmação de descarte | P1 | ✅ Corrigido | Confirmado: ir para "Início" pulava a pergunta "Há alterações sem salvar?". Agora todo destino de navegação passa pela mesma confirmação. |
| 10 | Trocar nicho sobrescreve personalizações | P1 | ⏳ Adiado | Precisa mudar a lógica de preenchimento automático (só preencher campos vazios) com cuidado para não quebrar o fluxo de criação de campanha nova — melhor com um pente-fino dedicado. |
| 11 | Copiar pode anunciar sucesso sem copiar | P2 | ✅ Corrigido | Confirmado: fechar a caixa de texto manual já mostrava "Copiado", mesmo sem o usuário ter copiado nada. Agora o botão só mostra "Copiado" quando a cópia automática funciona; no modo manual mostra um aviso neutro. |
| 12 | Prompts por cor não têm edição equivalente ao modo único | P2 | ⏳ Adiado | Pede um editor completo (com rascunho e salvamento) para os prompts por cor, igual ao que já existe no modo de cor única — trabalho de UI maior, não pontual. |
| 13 | Todas as variações ficam expandidas | P2 | ✅ Corrigido | Confirmado: com várias cores, as visões de imagem/vídeo/roteiro abriam todas as cores ao mesmo tempo. Agora funciona como acordeão de verdade (uma cor aberta por vez, começando na primeira pendente). |
| 14 | Uploads não mostram progresso nem cancelamento | P2 | ⏳ Adiado | Pede barra de progresso e cancelamento de upload — precisa de uma UI nova, não é uma correção pontual. |
| 15 | Primeiro vídeo da galeria já leva à aprovação | P2 | ⏳ Adiado | Confirmado no código, mas a correção (navegação guiada pelo estado do servidor) tem efeito colateral em outras transições de etapa — prefiro tratar junto com os itens 07/08 de rascunho, que mexem na mesma área. |
| 16 | Prévia local pode sumir na aprovação de cor única | P1 | ⏳ Adiado | Precisa normalizar a "chave" da cor num único lugar (hoje o app usa nomes de cor de formas diferentes em telas diferentes — mesmo problema do item 19, que é maior e deveria ser resolvido primeiro). |
| 17 | Não fica claro quem possui o vídeo local | P2 | ⏳ Adiado | Exige registrar dono/aparelho do vídeo local no banco — mudança de schema, não pontual. |
| 18 | Autoria da aprovação é incorreta | P1 | ⏳ Adiado | Precisa gravar usuário autenticado + data na aprovação, hoje ausente do banco — mudança de schema; deve ser feita junto com o item 19 (que também mexe em como o servidor identifica cor/usuário). |
| 19 | Cores são normalizadas de formas diferentes | P1 | ⏳ Adiado | Este é o item mais estrutural do lote: hoje "Azul" e "azul" podem ser tratados de formas diferentes pelo backend e pelo frontend. A correção correta (a API devolver um "slot" oficial por cor) melhora vários outros itens (16, 18) mas precisa ser desenhada com calma — é a base de como o app identifica cada cor em todo o fluxo. |
| 20 | Recursos incompatíveis com a nuvem continuam visíveis | P2 | ⏳ Adiado | Pede expor pela API quais recursos realmente funcionam no modo atual, para esconder botões que sempre falhariam na nuvem — bom pedido, mas exige mapear todos os recursos primeiro. |

## 2. Performance e armazenamento (itens 21–35)

| # | Item | Prior. | Status | O que foi feito / motivo do adiamento |
|---|---|---|---|---|
| 21 | Geração por cores pode exceder o tempo da função | P1 | ⏳ Adiado | Pede processamento em segundo plano com gravação incremental por cor — mudança de arquitetura (fila de trabalho), não algo para implementar sem planejar a infraestrutura. |
| 22 | Transações ficam abertas durante operações externas | P1 | ⏳ Adiado | O próprio documento pede coordenar com o item 37 (que já implementei — controle de versão). O restante (não segurar transação do banco durante chamadas de IA/Storage) é uma revisão maior do fluxo de gravação. |
| 23 | Confirmação de upload baixa toda a mídia novamente | P1 | ⏳ Adiado | Pede inspecionar metadados sem baixar o arquivo inteiro (leitura parcial/streaming) — otimização que exige reescrever a extração de metadados; o item 24 (limite de tamanho, que já implementei) reduz o pior caso enquanto isso não é feito. |
| 24 | Limite de vídeo não é reaplicado no upload direto | P1 | ✅ Corrigido | Confirmado: depois do envio direto ao Supabase Storage, nada verificava o limite de 250 MB antes de baixar/gravar o arquivo. Agora, se o arquivo passar de 250 MB, é rejeitado e apagado do Storage antes de virar mídia da campanha. |
| 25 | Fotos do produto são enviadas em sequência | P2 | ⏳ Adiado | Otimização de performance (enviar em paralelo) — baixo risco mas também baixo retorno imediato; fica na fila. |
| 26 | Excluir campanha não remove objetos remotos | P1 | ⏳ Adiado | Pede limpeza rastreável do Storage ao excluir campanha, com nova tentativa em caso de falha — prefiro implementar com um mecanismo de retomada em vez de um apagamento direto que pode falhar pela metade. |
| 27 | Uploads abandonados deixam objetos órfãos | P2 | ⏳ Adiado | Pede um sistema de "upload pendente com validade" e limpeza periódica — infraestrutura nova (job agendado), não pontual. |
| 28 | Cache da biblioteca é sobrescrito | P1 | ✅ Corrigido | Confirmado: o middleware global forçava "sem cache" em toda resposta `/api/`, mesmo quando uma rota específica (fotos da biblioteca) já tinha definido seu próprio cache. Agora a regra global só se aplica quando a rota não definiu a sua. |
| 29 | Galerias usam imagens originais como miniaturas | P2 | ⏳ Adiado | Pede gerar miniaturas de verdade — processamento de imagem novo, não uma correção de código existente. |
| 30 | Interface inteira no bundle inicial | P2 | ⏳ Adiado | Pede dividir o carregamento por tela (code splitting) — mudança de configuração de build que merece medição antes/depois dedicada. |
| 31 | Inicialização busca detalhes desnecessários | P2 | ⏳ Adiado | Pequena otimização de sequência de carregamento — fica na fila junto com o item 32 (mesma área do código). |
| 32 | Operações pequenas recarregam listas completas | P2 | ⏳ Adiado | Pede atualizar só o item alterado em vez de recarregar tudo, e paginação no histórico — mudança de padrão de estado no frontend inteiro, não pontual. |
| 33 | Conexões de banco são abertas por requisição | P2 | ✅ Corrigido | Adicionado tempo limite de conexão (10s) e de consulta (30s) nas conexões com o Postgres. Isso evita que o servidor trave indefinidamente se o banco ficar lento ou inacessível. (A parte de "verificar o pooler da infraestrutura" depende do painel do Supabase, que não tenho como inspecionar por aqui.) |
| 34 | Requisições não têm timeout ou cancelamento | P2 | ✅ Corrigido | Todas as chamadas do app ao servidor agora têm um tempo limite (2 minutos, 5 minutos para envio de arquivos) — se travar, o app mostra um erro em vez de ficar "carregando" para sempre. |
| 35 | Exportação ZIP concentra trabalho pesado na requisição | P1 | ⏳ Adiado | Pede mover a geração do ZIP para fora da requisição interativa (processamento em segundo plano) — mesma categoria do item 21, depende de decidir a infraestrutura de fila. |

## 3. Integridade dos dados e testes (itens 36–40)

| # | Item | Prior. | Status | O que foi feito / motivo do adiamento |
|---|---|---|---|---|
| 36 | ZIP repete nomes de arquivos de cores diferentes | P1 | ✅ Corrigido | Confirmado: exportar uma campanha com várias cores gerava `imagem-aprovada.png` duas vezes, uma sobrescrevendo a outra dentro do ZIP. Agora, quando há mais de uma cor, o nome do arquivo inclui a cor e um identificador; com uma cor só, o nome continua simples como sempre foi. |
| 37 | Edição simultânea não está protegida corretamente no PostgreSQL | P1 | ✅ Corrigido | Este é o item mais crítico do lote inteiro. O código usava `BEGIN IMMEDIATE` para travar a campanha contra edição simultânea — isso funciona no SQLite (modo local), mas **não faz nada no Postgres/nuvem** (o adaptador do app trata esse comando como vazio). Ou seja: **na versão online, duas pessoas podiam editar a mesma campanha ao mesmo tempo e uma sobrescrever o trabalho da outra sem aviso.** Corrigido implementando um controle de versão real: cada gravação só é aceita se a campanha ainda estiver na mesma versão lida no início da requisição; senão, o app avisa "a campanha mudou em outra janela, recarregue antes de salvar" — funciona igual no modo local e na nuvem. |
| 38 | Biblioteca compartilhada é sobrescrita como JSON completo | P1 | ⏳ Adiado | Pede migrar a biblioteca de modelos (fotos por nicho) de um arquivo JSON único para linhas no banco de dados — mudança de estrutura de armazenamento, não uma correção pontual. Enquanto isso, o item 39 (abaixo) já reduz o risco de perda de dados por erro silencioso. |
| 39 | Erro do Storage pode parecer biblioteca vazia | P1 | ✅ Corrigido | Confirmado: qualquer erro ao ler a biblioteca de fotos da modelo (rede, permissão, resposta corrompida) fazia o app achar que a biblioteca estava vazia — e uma gravação seguinte podia apagar fotos reais substituindo por um documento vazio. Agora só um "arquivo realmente não existe" (404) volta como vazio; qualquer outro erro é mostrado como falha, sem risco de sobrescrever dados. |
| 40 | Caminho em nuvem sem cobertura automatizada equivalente | P1 | ⏳ Adiado | Pede testes automatizados rodando contra um Postgres de teste de verdade (hoje os 90 testes rodam só em modo local/SQLite) — isso é um projeto de infraestrutura de testes, não uma correção de código. |

## 4. Geração de imagens e análise do produto (itens 41–53)

| # | Item | Prior. | Status | O que foi feito / motivo do adiamento |
|---|---|---|---|---|
| 41 | Primeira cor pede fotografia inédita | P1 | ✅ Corrigido | Confirmado: a primeira cor gerava uma **fotografia nova** (pose, ângulo e enquadramento podiam mudar), enquanto as demais cores já faziam **edição localizada** (só trocam a roupa). Você confirmou que a primeira cor também deve preservar a foto da modelo. Corrigido: agora a primeira cor edita a própria foto de referência (mesma lógica de "trocar só a roupa"); as cores seguintes continuam editando a imagem aprovada da campanha, como já faziam. Commit `a5fda90`. |
| 42 | Cenário da referência conflita com cenário do nicho | P1 | ✅ Corrigido | Rodada de imagem do Codex: a fotografia-base passou a ser a única fonte de cenário, iluminação, perspectiva e foco. Estilo, tom, público e ângulo do nicho não são mais reinseridos como direção de imagem. As notas estáticas também são filtradas para não substituir a composição da base. O vídeo mantém sua direção anterior. |
| 43 | Preservar foto e eliminar desfoque entram em conflito | P1 | ✅ Corrigido | Confirmado: o prompt pedia simultaneamente "fundo idêntico" e "fundo nítido, sem desfoque" — instrução contraditória quando a foto de referência já tem fundo desfocado. Agora o texto pede para manter o mesmo nível de nitidez/desfoque que a referência já tem, em vez de exigir nitidez artificial. |
| 44 | Ordem dos anexos não acompanha a edição das próximas cores | P1 | 🟡 Corrigido parcialmente | Rodada de imagem do Codex: removidas as duas ordens concorrentes. Agora há uma única instrução: primeira cor usa a referência da modelo; próximas cores usam a imagem aprovada da campanha; em seguida vêm as fotos do produto. O primeiro anexo é a única base de composição. O manifesto visual com miniaturas numeradas ainda está pendente. |
| 45 | Enquadramento permitido pode cortar o produto | P2 | ✅ Corrigido | Rodada de imagem do Codex: retirada a autorização de ajustar o enquadramento, que contradizia a edição localizada. O prompt preserva os limites e a proporção da base, sem recorte, ampliação do campo ou reconstrução de partes ausentes. A etapa Criar imagem orienta conferir toda a peça e escolher outra referência em Modelo fixa se ela estiver cortada. Essa conferência é humana, não uma detecção automática por visão. |
| 46 | Filtro remove instruções fotográficas legítimas | P1 | 🟡 Corrigido parcialmente | Rodada de imagem do Codex: filtragem por palavras/expressões e preservação de quebras de linha, separando notas do produto de ações, falas e tempos. Instruções fotográficas estáticas são reconhecidas, mas não sobrescrevem câmera/cenário/pose no modo de edição localizada. Exemplos como manga alongada e corte reto são preservados. Campos estruturados de imagem/vídeo/fala continuam pendentes; o filtro de texto livre permanece uma heurística. |
| 47 | Produto unissex perde o substantivo específico | P2 | ✅ Corrigido | Confirmado e reproduzido: uma "camisa unissex" virava só "peça" no prompt. Agora o substantivo específico (camisa, calça, etc.) é procurado primeiro; "peça" só é usado quando nenhum substantivo específico é encontrado. |
| 48 | Fatos confirmados não têm origem confiável | P1 | ⏳ Adiado | Pede uma ficha estruturada de atributos com origem (informado / visual / sugerido / confirmado) — redesenho do modelo de dados do briefing, é o item de maior escopo do lote de imagem/vídeo. |
| 49 | Negação de sem transparência vira confirmação | P1 | ✅ Corrigido | Confirmado e reproduzido: o texto "não sei se é sem transparência" podia ser lido como confirmação do atributo "sem transparência". Agora o código verifica se há uma dúvida/negação antes da frase e, se houver, não confirma o atributo. |
| 50 | Materiais e composição têm cobertura limitada | P2 | ⏳ Adiado | Pede suportar percentuais de composição e texturas fora da lista atual — ampliação de vocabulário que prefiro fazer junto com o item 48 (mesma área de dados de atributos). |
| 51 | Atributos são priorizados por ordem fixa | P2 | ⏳ Adiado | Pede permitir escolher manualmente o atributo principal — depende da mesma ficha estruturada do item 48. |
| 52 | Ordem das fotos contradiz a instrução da IA | P1 | ✅ Corrigido | Confirmado: o próprio texto de instrução da IA diz "você recebe: 1. foto do produto, 2. foto da descrição", mas o código enviava a foto da descrição primeiro. Corrigido: agora a ordem de envio bate com a ordem descrita, e cada foto é identificada por função na mensagem (evita a IA confundir uma com a outra). |
| 53 | Somente a primeira foto do produto é analisada | P2 | 🟡 Corrigido parcialmente | Confirmado: a análise usava só a primeira foto salva do produto, ignorando fotos de costas/detalhe. Agora até 3 fotos do produto (já salvas) entram na análise. O pedido completo — deixar você escolher quais fotos analisar, com rótulos "frente/costas/detalhe" — é uma mudança de interface que não fiz. |

## 5. Direção e geração de vídeo (itens 54–64)

| # | Item | Prior. | Status | O que foi feito / motivo do adiamento |
|---|---|---|---|---|
| 54 | Ordens de câmera são incompatíveis | P1 | ✅ Corrigido | Confirmado: o prompt pedia "câmera fixa" e, ao mesmo tempo, instruções de aproximação/acompanhamento — contraditório. Reescrevi para deixar claro que a câmera pode se aproximar ou acompanhar a modelo durante a demonstração, voltando à posição inicial no encerramento (mantendo a cena, não a câmera, fixa). |
| 55 | Excesso de ações obrigatórias em 11 segundos | P1 | ✅ Corrigido | Confirmado: o texto pedia "executar TODAS as ações da lista entre 0s e 11s", o que é fisicamente impossível quando a lista tem várias ações. Agora pede escolher 2 a 3 ações, na ordem em que aparecem. |
| 56 | Regra das mãos interfere na demonstração | P2 | ✅ Corrigido | Confirmado: "as duas mãos nunca ficam livres ao mesmo tempo" impede gestos que precisam das duas mãos (abrir um zíper, ajustar um acessório). Adicionei uma exceção explícita para esses casos, limitada a 1 segundo. |
| 57 | Encerramento é rígido e repetitivo | P2 | ⏳ Adiado | Pede encerramentos variados por tipo de peça — mudança de conteúdo maior (múltiplas variações por família de produto), fica para uma rodada dedicada a variedade criativa. |
| 58 | Abertura visual sempre repete o segredo | P2 | 🟡 Corrigido parcialmente | Confirmado: todo vídeo começava com a mesma instrução ("como quem vai contar um segredo"), independente do produto ou argumento. Troquei por uma abertura mais direta e ligada à energia do hook. O pedido completo — variar a abertura automaticamente por tipo de argumento (apresentação, comparação, detalhe) — não foi implementado; hoje há uma abertura só, mais neutra que a anterior. |
| 59 | Movimentos do nicho não respeitam a peça real | P1 | ⏳ Adiado | Pede resolver primeiro o tipo de produto e só depois escolher a demonstração (hoje o nicho "academia" pode sugerir agachamento até para um top) — mudança na ordem de decisão do gerador de prompts, quero testar com mais exemplos reais antes de mudar. |
| 60 | Somente câmera descreve movimento da modelo | P2 | ✅ Corrigido | Confirmado: trechos chamados "(somente câmera, sem nova fala)" na verdade descreviam ações da modelo (caminhar, girar, sentar), não da câmera — texto contraditório. Renomeado para "(ação silenciosa da modelo, sem nova fala)" nos 3 trechos. |
| 61 | Pós-produção aparece dentro do prompt de geração | P2 | ✅ Corrigido | Confirmado: a frase "una os clipes e exporte 1 MP4 de 15s" (instrução para você, não para o gerador de vídeo) estava dentro do texto que vai colado no Grok/Flow. Removida do prompt e adicionada como item de checklist na seção "revisão humana" do pacote de texto. |
| 62 | Adaptação entre Grok e Flow é superficial | P2 | ⏳ Adiado | Pede perfis de geração configuráveis por serviço (duração, forma de uso) — funcionalidade nova, não correção de um texto existente. |
| 63 | Atualizar fala substitui direção manual | P1 | ✅ Corrigido | Confirmado: pedir um "refresh" de fala reconstruía o prompt de vídeo inteiro do zero, apagando qualquer ajuste manual de câmera/coreografia/encerramento que você tivesse feito. Agora o app tenta trocar só as três falas dentro do texto existente, preservando o resto; só reconstrói tudo quando essa troca segura não é possível (ex.: texto muito alterado). |
| 64 | Contagem de palavras não garante duração | P2 | ⏳ Adiado | Pede tratar a duração como estimativa (considerando pausas, números, velocidade de leitura) em vez de uma contagem fixa de palavras — mudança de cálculo que quero validar com áudio real antes de trocar. |

## 6. Falas, legendas e controle de qualidade (itens 65–73)

| # | Item | Prior. | Status | O que foi feito / motivo do adiamento |
|---|---|---|---|---|
| 65 | Regras de urgência se contradizem | P1 | ✅ Corrigido | Confirmado: uma regra proibia "corre" sem oferta, outra dizia que "corre" é sempre permitido — contraditório. Unifiquei: "corre"/"garante a tua" continuam livres (são entusiasmo, não fato), mas a proibição de urgência agora cobre claramente estoque, prazo **e** preço. |
| 66 | Estrutura favorece sempre receio e surpresa | P2 | ⏳ Adiado | É uma escolha de direção criativa (o app hoje favorece aberturas de confissão/medo/descoberta), não exatamente um bug — mudar isso é uma decisão de produto sobre variedade de tom, prefiro conversar com você antes de reduzir esse padrão que hoje funciona. |
| 67 | Depoimentos pessoais são incentivados sem comprovação | P1 | ✅ Corrigido | Confirmado: a instrução mandava "falar como quem comprou, vestiu e testou" o produto, mesmo sem essa experiência estar registrada no briefing. Reescrita a regra para não afirmar compra/teste/uso prolongado sem confirmação. |
| 68 | Alternativas geradas são descartadas sem escolha | P2 | ⏳ Adiado | Pede guardar e deixar você escolher entre as 3 opções que a IA gera (hoje só a "vencedora" por pontuação chega até você) — precisa de tela nova para revisar/escolher alternativas. |
| 69 | Proteção contra repetição é literal e curta | P2 | 🟡 Corrigido parcialmente | Confirmado: a auditoria só barrava repetição **idêntica**; um roteiro quase igual com 2-3 palavras trocadas passava. Troquei a comparação por similaridade de texto (mais de 85% igual já é sinalizado). O pedido completo — histórico entre campanhas/cores diferentes — não foi implementado (hoje compara só com a versão anterior do mesmo campo). |
| 70 | Objeção pode liberar uma promessa | P1 | ⏳ Adiado | Confirmado no código (busca a palavra "objeção" no briefing sem checar se é uma dúvida ou uma negação), mas a correção correta depende da mesma ficha estruturada de atributos do item 48 — implementar isso isoladamente é remendo, não solução. |
| 71 | Auditoria é menos rigorosa que a das falas | P1 | 🟡 Corrigido parcialmente | Confirmado: a legenda só era checada quanto a hashtags, sem passar pelas mesmas regras de fatos/oferta/experiência que hook, desenvolvimento e CTA passam. Agora a legenda entra no mesmo texto verificado por essas regras. As checagens específicas de legenda (pertinência e duplicação de hashtags) continuam como estavam. |
| 72 | Origem do texto é registrada apenas por campanha | P2 | ⏳ Adiado | Conferido em detalhe: a correção correta (guardar quem escreveu cada cor separadamente, não só a última geração da campanha) toca `app.py`, as duas telas do frontend **e** quebra suposições de testes existentes que checam o formato atual — é maior do que os outros itens "rápidos" desta rodada. Fica registrado como próximo passo, não descartado. |
| 73 | Falta revisão conjunta das contradições | P1 | ⏳ Adiado | Pede um "contrato" estruturado que valide cenário, câmera, mãos, duração etc. em conjunto, com testes que não dependam de frases literais — é essencialmente construir uma nova camada de validação, projeto à parte. Os itens 54-63 (já corrigidos) removem várias das contradições que esse contrato pegaria hoje. |

---

## Resumo

- **27 itens corrigidos** (✅) — os 26 da rodada anterior, mais o item 42 nesta rodada de imagem. O item 45 recebeu uma correção complementar para preservar o enquadramento.
- **7 itens corrigidos parcialmente** (🟡) — a parte mais grave foi resolvida; o que falta está anotado item a item acima.
- **39 itens adiados** (⏳) — o item 42 saiu desta lista. Os demais mantêm os motivos registrados acima.

## Rodada complementar — prompts de imagem (Codex, 13/09/2026)

Escopo autorizado: itens **42, 44, 45 e 46**, preservando a decisão do item 41 de trocar somente a roupa na fotografia existente.

- `services/prompts.py`: a imagem passou a usar uma única ordem de anexos e a fotografia-base como fonte de identidade, cenário, iluminação, pose, proporção e enquadramento. Foram retiradas instruções genéricas de estilo do nicho e a obrigação de converter a foto em 9:16; a proporção original prevalece na edição localizada.
- `frontend/src/App.jsx`: aviso na etapa Criar imagem para conferir se a base já mostra toda a peça; quando cortada, escolher outra referência antes de gerar os prompts.
- `tests/test_image_prompts.py`: regressões para os seis nichos, primeira/próximas cores, zero/uma/várias fotos do produto, preservação de composição, enquadramento, notas estáticas, ações de vídeo e quebras de linha.
- `tests/test_app.py`: atualizada a expectativa antiga que permitia ao cenário escrito no briefing substituir o ambiente da fotografia-base.

Os itens 44 e 46 continuam parciais porque esta rodada não criou o manifesto visual nem os novos campos estruturados. Os itens 48, 50, 51 e a validação completa do item 73 não foram implementados aqui.

### Validação desta rodada

- Suíte completa: **106 testes aprovados** (`python -m unittest discover -s tests -q`). Há avisos preexistentes sobre recursos e tarefas de monitoramento de navegador pendentes; a suíte terminou com `OK`.
- Build de produção do frontend: **aprovado** (`npm run build`).
- Comparação com a versão anterior em **12 cenários** (seis nichos, Grok e Flow): prompts de vídeo, falas e legendas permaneceram idênticos.
- Verificação do diff sem erros de espaços em branco. Não foi gerada uma imagem real no Grok/Flow: os testes validam a construção do prompt, não garantem a fidelidade visual de um gerador externo.

### Disponibilidade

As alterações estão no código local e no build do frontend. Elas precisam entrar no próximo deploy para aparecer na Vercel. Não houve publicação automática, alteração de campanhas salvas ou chamada paga aos geradores nesta rodada. Prompts já armazenados continuam como estavam; o comportamento novo é aplicado na próxima geração. Para campanhas avançadas/publicadas, use uma cópia editável e siga o fluxo normal de revisão antes de gerar novamente.
