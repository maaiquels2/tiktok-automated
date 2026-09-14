# Fábrica TikTok — Auditoria e plano de melhorias

**Data:** 13 de setembro de 2026  
**Projeto:** `C:\Users\Admin\Documents\Codex\2026-09-10\Fabrica TikTok`  
**Versão online examinada:** https://tiktok-automated.vercel.app/#/inicio  
**Escopo:** performance, UI/UX, geração de prompts de imagem e vídeo, falas/legendas e integridade do fluxo compartilhado.  
**Estado deste documento:** diagnóstico e recomendações; os itens abaixo não representam correções já implementadas.

## Como interpretar a auditoria

Este relatório reúne os **73 pontos apresentados na revisão**, mantendo a mesma numeração para facilitar acompanhamento. Cada item contém o problema, a evidência disponível, a correção recomendada, um critério de aceite e os arquivos relacionados.

A revisão combinou inspeção do código local, observação da interface publicada e verificações pontuais de funções de geração. A identidade exata entre o commit local e o deploy não foi comprovada: achados estáticos devem ser conferidos no commit usado pela Vercel antes de implementar. Não foram feitas alterações no código durante esta auditoria.

- **Observado online:** comportamento visto na interface publicada.
- **Código:** fluxo ou regra identificado nos arquivos inspecionados; não significa que todos os cenários foram reproduzidos em produção.
- **Reproduzido em função local:** resultado confirmado com uma chamada isolada ao gerador, sem chamar API paga.
- **Risco:** consequência possível sustentada pelo código/configuração, que ainda requer medição ou reprodução controlada.

Não houve benchmark de carga, relatório Lighthouse/Core Web Vitals, inspeção do painel da Vercel/Supabase nem teste em iPhone físico nesta revisão. Tamanhos de bundle citados são do build local, antes da compressão de transporte. Limites e capacidades externas precisam ser confirmados na configuração efetivamente utilizada.

## Prioridades

| Prioridade | Significado | Quantidade |
|---|---|---:|
| P1 — Alta | Pode causar perda/sobrescrita de trabalho, fluxo incorreto, custo relevante ou geração contraditória. | 40 |
| P2 — Média | Afeta agilidade, clareza, consistência ou qualidade; executar após as falhas de maior impacto. | 32 |
| P3 — Baixa | Acabamento visual sem bloqueio principal. | 1 |
| **Total** | Itens numerados e rastreáveis. | **73** |

Todos os itens começam como **pendentes de triagem/implementação**. A prioridade considera impacto possível; ela não afirma que uma falha de produção já ocorreu.

## Diretrizes que a melhoria deve preservar

1. **Preservar o jogo de câmeras que o usuário aprovou.** Resolver contradições entre continuidade e movimento sem transformar todo vídeo em câmera fixa. Zoom, aproximação e retorno precisam ser coerentes e intencionais.
2. **Manter a identidade e o cenário reconhecíveis.** A troca localizada de roupa é o padrão para o fluxo descrito pelo usuário. Uma nova fotografia/composição deve ser uma escolha explícita.
3. **Uma cor por geração.** Cada imagem/vídeo deve ter uma referência clara e um slot estável, com aprovação e publicação correspondentes.
4. **Vídeo pode ficar somente no aparelho.** A interface deve distinguir registro de aprovação, disponibilidade do arquivo e compartilhamento entre usuários.
5. **Português do Brasil e fala natural.** Instruções de produção não podem virar falas; materiais, atributos e experiências não devem ser inventados.
6. **Geração visual continua nos serviços escolhidos pelo usuário.** Este plano não pressupõe contratar API para gerar imagens ou vídeos. Eventuais chamadas de IA textual seguem a configuração já existente.
7. **Não sobrescrever o trabalho atual.** Antes de mudanças estruturais, preservar banco, referências, prompts ajustados e campanhas publicadas; testar migrações em ambiente separado.

## Ordem recomendada de implementação

| Etapa | Objetivo | Itens principais | Entrega verificável |
|---|---|---|---|
| 1 | Evitar perda de trabalho e gravação na campanha errada | 6–10, 18–19, 37–40, 63 | Rascunhos preservados, conflito de edição tratado e direção visual manual mantida. |
| 2 | Corrigir o uso diário online | 1–4, 11–17, 20 | Layout responsivo, destinos corretos, upload compreensível e revisão do vídeo local funcional. |
| 3 | Tornar nuvem e arquivos previsíveis | 21–36 | Geração retomável por cor, transações curtas, limpeza de Storage, cache efetivo e exportação segura. |
| 4 | Corrigir a base factual e as referências | 41–53, 67, 70–71 | Atributos com origem, referências numeradas, peça correta e nenhuma promessa originada de dúvida/negação. |
| 5 | Melhorar direção visual e variedade criativa | 54–62, 64–66, 68–69, 72–73 | Prompts sem contradições, ações executáveis, opções escolhíveis e autoria por variante. |
| 6 | Consolidar acabamento e medir resultados | 5 e revisão dos demais | Marca consistente e comparação de desempenho/qualidade com critérios documentados. |

As etapas se relacionam: o controle de concorrência do item 37 deve acompanhar a redução de transações do item 22; o contrato de atributos dos itens 48–51 sustenta a auditoria dos itens 70–73. Os itens 7–8 devem ser tratados juntos para não trocar um tipo de perda de rascunho por outro.

## 1. Interface, navegação e revisão

### 01. Layout quebrado em larguras intermediárias

**Prioridade:** P1 · **Área:** UI/UX · **Estado:** Pendente  
**Base do achado:** Observado online  
**Onde investigar:** `frontend/src/styles.css`

**Problema e impacto:** Em uma janela de aproximadamente 812 px, a produção ficou limitada a uma coluna de 210 px, com grande área vazia. A regra mais específica de `.produce-dense.produce-workspace` prevalece sobre a adaptação responsiva.

**O que fazer:** Unificar as regras do layout de produção, remover a disputa de `!important` e definir uma coluna real abaixo do breakpoint escolhido. Garantir `min-width: 0` nos filhos e rolagem apenas onde necessária.

**Critério de aceite:** Conferir 390, 430, 650, 812, 950 e 1440 px: formulário ocupa a largura disponível, etapas continuam acessíveis e não há coluna vazia ou rolagem horizontal da página.

### 02. TikTok Studio abre o destino errado no computador

**Prioridade:** P1 · **Área:** UI/UX · **Estado:** Pendente  
**Base do achado:** Código e comportamento dos links  
**Onde investigar:** `frontend/src/serviceLinks.jsx`

**Problema e impacto:** Na nuvem, o botão TikTok Studio aponta para a página inicial do TikTok, igual ao botão TikTok.

**O que fazer:** Separar dispositivo de ambiente de execução: computador na nuvem deve abrir o endereço web do Studio; celular deve manter o comportamento de aplicativo já aprovado. Manter os rótulos TikTok Studio e TikTok.

**Critério de aceite:** Conferir os dois links no computador local, computador acessando a Vercel e iPhone. Não abrir navegador no servidor nem trocar o destino do botão TikTok comum.

### 03. Mensagens locais aparecem na versão online

**Prioridade:** P2 · **Área:** UI/UX · **Estado:** Pendente  
**Base do achado:** Observado online  
**Onde investigar:** `frontend/src/App.jsx`, `frontend/src/components.jsx`

**Problema e impacto:** O cabeçalho informa Dados no computador e a ajuda promete perfil dedicado do Chrome, embora a versão hospedada use armazenamento remoto e links comuns.

**O que fazer:** Derivar as mensagens do modo real de execução. Usar uma descrição curta e correta do armazenamento e informar conta/perfil apenas quando o aplicativo consegue efetivamente controlá-los.

**Critério de aceite:** Na Vercel não aparecem promessas de arquivos no PC ou abertura em perfil dedicado; no modo local as informações continuam corretas.

### 04. Conta e identidade do estúdio se confundem

**Prioridade:** P2 · **Área:** UI/UX · **Estado:** Pendente  
**Base do achado:** Observado online  
**Onde investigar:** `frontend/src/App.jsx`

**Problema e impacto:** Dois controles com o nome Micaela e ícones semelhantes representam funções diferentes: usuário autenticado e identidade do estúdio.

**O que fazer:** Dar nomes e descrições acessíveis distintos: Minha conta e Identidade do estúdio. Organizar administração de acessos no menu da conta e modelo/referências no estúdio.

**Critério de aceite:** Uma pessoa identifica onde trocar usuário e onde configurar a modelo sem tentativa e erro; leitor de tela anuncia funções diferentes.

### 05. Logotipo principal usa um ponto de interrogação

**Prioridade:** P3 · **Área:** UI/UX · **Estado:** Pendente  
**Base do achado:** Observado online e código  
**Onde investigar:** `frontend/src/App.jsx`

**Problema e impacto:** O símbolo principal da Fábrica TikTok é o caractere `?` definido no JSX.

**O que fazer:** Substituir o marcador por um ativo de marca definitivo, com boa legibilidade em tema claro/escuro e tamanho pequeno. Centralizar o ativo para evitar versões divergentes.

**Critério de aceite:** Cabeçalho e ícone da aplicação apresentam a mesma identidade, sem marcador provisório e sem distorção.

### 06. Campanha inexistente abre outra campanha silenciosamente

**Prioridade:** P1 · **Área:** UI/UX · **Estado:** Pendente  
**Base do achado:** Observado online  
**Onde investigar:** `frontend/src/App.jsx`

**Problema e impacto:** Ao solicitar a campanha 26, a aplicação abriu a campanha 6. O fallback para a primeira campanha pode levar o usuário a editar o item errado.

**O que fazer:** Quando o ID da rota não existir ou não puder ser carregado, mostrar Campanha não encontrada ou erro de acesso com retorno à lista. Não substituir o ID solicitado silenciosamente.

**Critério de aceite:** Abrir um ID ausente, removido e um ID válido: os dois primeiros mostram estado explícito; o último mantém correspondência entre URL, título e dados.

### 07. Rascunhos por cor não sinalizam alterações pendentes

**Prioridade:** P1 · **Área:** UI/UX · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `frontend/src/components.jsx`, `frontend/src/App.jsx`

**Problema e impacto:** `VariantScriptField` mantém o texto localmente, mas não propaga a alteração ao controle global de rascunhos.

**O que fazer:** Integrar os campos por cor ao controle de alterações pendentes e permitir salvar ou descartar antes de sair. Incluir troca de campanha, etapa e geração de nova alternativa.

**Critério de aceite:** Editar uma fala de uma cor e navegar: o usuário recebe a opção de salvar/descartar e nunca perde o texto silenciosamente.

### 08. Salvar um campo pode apagar outros rascunhos

**Prioridade:** P1 · **Área:** UI/UX · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `frontend/src/App.jsx`, `frontend/src/components.jsx`

**Problema e impacto:** O painel remonta quando a versão da campanha muda. Rascunhos em outros campos ou cores desaparecem nessa remontagem.

**O que fazer:** Preservar rascunhos em estado estável por campanha, cor e campo; atualizar somente os campos efetivamente salvos. Adotar salvamento conjunto ou reconciliação explícita com a resposta do servidor.

**Critério de aceite:** Editar duas cores, salvar apenas uma e verificar que a outra continua intacta e marcada como pendente.

### 09. Navegar para Início ignora a confirmação de descarte

**Prioridade:** P1 · **Área:** UI/UX · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `frontend/src/App.jsx`

**Problema e impacto:** `goMode` pula a verificação de alterações pendentes quando o destino é a página inicial.

**O que fazer:** Aplicar a mesma proteção a todas as saídas que desmontam o editor, incluindo Início, logout e links externos que substituem a aba.

**Critério de aceite:** Com um briefing ou roteiro alterado, ir para Início exige uma decisão e preserva o rascunho se o usuário cancelar.

### 10. Trocar nicho sobrescreve personalizações

**Prioridade:** P1 · **Área:** UI/UX · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `frontend/src/components.jsx`

**Problema e impacto:** A seleção de nicho aplica o objeto completo de padrões sobre benefício, movimentos, estilo e outros campos existentes.

**O que fazer:** Preencher automaticamente apenas campos vazios ou ainda iguais ao padrão anterior. Oferecer ação separada para reaplicar todos os padrões, com resumo do que será substituído.

**Critério de aceite:** Personalizar benefício e movimentos, trocar o nicho e verificar que os textos pessoais são preservados ou substituídos apenas após escolha explícita.

### 11. Copiar pode anunciar sucesso sem copiar

**Prioridade:** P2 · **Área:** UI/UX · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `frontend/src/components.jsx`

**Problema e impacto:** No fallback de cópia, confirmar a caixa de texto já exibe Copiado; essa confirmação não comprova que o clipboard foi alterado.

**O que fazer:** Exibir sucesso somente quando a API de clipboard ou o comando de cópia retornar sucesso. No modo manual, mostrar instruções e um estado neutro, sem afirmar que copiou.

**Critério de aceite:** Simular recusa de permissão: o app oferece seleção manual, mas não mostra Copiado só porque a caixa foi fechada.

### 12. Prompts por cor não têm edição equivalente ao modo único

**Prioridade:** P2 · **Área:** UI/UX · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `frontend/src/components.jsx`, `frontend/src/App.jsx`, `app.py`

**Problema e impacto:** Imagem e vídeo por cor aparecem como parágrafos com botão de copiar, enquanto o fluxo de cor única oferece editor.

**O que fazer:** Adicionar edição e salvamento por cor aos prompts de imagem e vídeo, com a mesma proteção de rascunhos e regras de invalidação das aprovações.

**Critério de aceite:** Editar apenas o prompt de uma cor e confirmar que as demais permanecem intactas; a interface explica o impacto nas aprovações.

### 13. Todas as variações ficam expandidas

**Prioridade:** P2 · **Área:** UI/UX · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `frontend/src/components.jsx`

**Problema e impacto:** As listas de imagem, vídeo e roteiro abrem todas as cores, acumulando grandes textos e mídias no celular.

**O que fazer:** Adotar seleção de cor ou acordeões que respeitem o estado escolhido pelo usuário, com pendências e progresso visíveis no resumo. Abrir inicialmente a cor atual ou a primeira pendente.

**Critério de aceite:** Uma campanha com dez cores continua navegável sem percorrer todos os prompts; salvar não reabre automaticamente todos os blocos.

### 14. Uploads não mostram progresso nem cancelamento

**Prioridade:** P2 · **Área:** UI/UX · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `frontend/src/api.js`, `frontend/src/App.jsx`

**Problema e impacto:** O envio de arquivos apresenta espera genérica, sem porcentagem ou forma de interromper um envio lento.

**O que fazer:** Exibir a fase atual, bytes/percentual quando disponíveis e cancelamento com limpeza do upload pendente. Diferenciar envio ao Storage de validação e registro.

**Critério de aceite:** Em rede limitada, o usuário identifica a fase e consegue cancelar; o app não anuncia sucesso antes da confirmação final.

### 15. Primeiro vídeo da galeria já leva à aprovação

**Prioridade:** P2 · **Área:** UI/UX · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `frontend/src/App.jsx`

**Problema e impacto:** O registro de vídeo local navega diretamente para a etapa 7, mesmo quando outras cores ainda estão sem arquivo.

**O que fazer:** Usar o estado retornado pelo servidor para decidir a navegação. Permanecer na etapa 6 enquanto houver cores pendentes e oferecer avanço quando o conjunto estiver completo.

**Critério de aceite:** Em três cores, selecionar a primeira mantém a produção aberta; selecionar a última libera a aprovação sem exigir idas e voltas.

### 16. Prévia local pode sumir na aprovação de cor única

**Prioridade:** P1 · **Área:** UI/UX · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `frontend/src/App.jsx`

**Problema e impacto:** O arquivo pode ser armazenado no estado do navegador com chave vazia, mas a etapa de aprovação procura pelo nome da cor registrado pelo servidor.

**O que fazer:** Normalizar a chave da variação uma única vez e usar o slot devolvido pela API para guardar e recuperar o File/ObjectURL.

**Critério de aceite:** Selecionar vídeo de uma única cor sem informar slot explicitamente e avançar: a prévia continua disponível na etapa 7.

### 17. Não fica claro quem possui o vídeo local

**Prioridade:** P2 · **Área:** UI/UX · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `app.py`, `frontend/src/components.jsx`

**Problema e impacto:** O registro compartilhado diz que o vídeo está na galeria, sem identificar o usuário/aparelho que o selecionou. O segundo acesso pode interpretar que também possui o arquivo.

**O que fazer:** Registrar proprietário do arquivo local e um apelido opcional do aparelho. Mostrar que o arquivo não foi enviado e oferecer reanexar/compartilhar quando necessário, sem prometer recuperação automática da galeria.

**Critério de aceite:** O segundo usuário vê a localização declarada e entende por que não consegue assistir; a aprovação permanece distinguível da disponibilidade do arquivo.

### 18. Autoria da aprovação é incorreta

**Prioridade:** P1 · **Área:** UI/UX · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `app.py`, `frontend/src/App.jsx`, `frontend/src/components.jsx`

**Problema e impacto:** A aprovação de vídeo local recebe o nome da modelo; imagens exibem Aprovado por você para qualquer usuário.

**O que fazer:** Gravar usuário autenticado, data e versão da mídia no servidor. Renderizar Aprovado por você apenas quando o aprovador corresponde à sessão atual; migrar registros antigos como autoria não identificada.

**Critério de aceite:** Duas contas aprovam mídias diferentes e a outra conta vê o autor correto; enviar um nome arbitrário no payload não altera a autoria.

### 19. Cores são normalizadas de formas diferentes

**Prioridade:** P1 · **Área:** UI/UX · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/prompts.py`, `frontend/src/App.jsx`, `frontend/src/components.jsx`

**Problema e impacto:** O backend elimina duplicatas sem diferenciar maiúsculas e minúsculas; o frontend calcula slots diretamente do texto, podendo cobrar uma cor que não existe no servidor.

**O que fazer:** Devolver slots canônicos no contrato da API e usá-los em geração, upload, aprovação e publicação. Preservar o nome de apresentação sem usá-lo como identidade frágil.

**Critério de aceite:** Testar Azul/azul, espaços duplicados e vários separadores; cada cor corresponde a um único slot em todo o fluxo.

### 20. Recursos incompatíveis com a nuvem continuam visíveis

**Prioridade:** P2 · **Área:** UI/UX · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `app.py`, `frontend/src/App.jsx`, `frontend/src/components.jsx`

**Problema e impacto:** Mistura local de vídeos e operações dependentes de Chrome automatizado aparecem na interface, mas o backend bloqueia sua execução na nuvem.

**O que fazer:** Expor capacidades reais pela API e montar as ações a partir delas. Ocultar controles indisponíveis ou explicar a alternativa disponível sem deixar o usuário descobrir pelo erro.

**Critério de aceite:** No deploy, nenhuma ação habilitada termina apenas em Disponível somente no computador; o modo local mantém seus recursos.

## 2. Performance e armazenamento

### 21. Geração por cores pode exceder o tempo da função

**Prioridade:** P1 · **Área:** Performance · **Estado:** Pendente  
**Base do achado:** Risco demonstrado pelo fluxo e configuração  
**Onde investigar:** `app.py`, `services/copywriter.py`, `vercel.json`

**Problema e impacto:** A função está configurada com 60 segundos, enquanto o lote executa chamadas à IA e tentativas sequenciais para todas as cores; o resultado é confirmado somente no fim.

**O que fazer:** Separar geração em unidades por cor com gravação incremental e retomada. Usar processamento em segundo plano quando necessário, ou requisições curtas por cor com concorrência limitada e idempotência.

**Critério de aceite:** Simular IA lenta e falha na terceira cor: as cores concluídas permanecem salvas, a falha é identificada e só o item pendente precisa ser refeito.

### 22. Transações ficam abertas durante operações externas

**Prioridade:** P1 · **Área:** Performance · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `app.py`

**Problema e impacto:** Chamadas de IA e Storage ocorrem dentro de fluxos que já iniciaram transação, prolongando uso de conexão e aumentando conflitos.

**O que fazer:** Ler um snapshot curto, executar a operação externa fora da transação e abrir uma transação curta para persistir, verificando novamente a versão. Coordenar esta mudança com o item 37.

**Critério de aceite:** Uma chamada de IA lenta não mantém bloqueios de gravação desnecessários; se a campanha mudar durante a chamada, o resultado não sobrescreve a nova versão.

### 23. Confirmação de upload baixa toda a mídia novamente

**Prioridade:** P1 · **Área:** Performance · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `app.py`, `services/media.py`

**Problema e impacto:** Depois do envio direto ao Storage, a função baixa os bytes completos e cria uma cópia temporária para extrair metadados.

**O que fazer:** Inspecionar metadados sem trazer o arquivo inteiro quando possível, usando leitura parcial/streaming ou processamento separado. Metadados enviados pelo navegador podem antecipar feedback, mas não devem substituir toda validação do servidor.

**Critério de aceite:** Comparar transferência, memória e tempo com um vídeo grande; a confirmação não exige uma segunda cópia integral em memória dentro da requisição interativa.

### 24. Limite de vídeo não é reaplicado no upload direto

**Prioridade:** P1 · **Área:** Performance · **Estado:** Pendente  
**Base do achado:** Código; configuração externa não verificada  
**Onde investigar:** `app.py`, `frontend/src/api.js`

**Problema e impacto:** A confirmação do upload direto não reaplica explicitamente os 250 MB informados pela interface. O bucket pode impor seu próprio limite, que não foi verificado nesta auditoria.

**O que fazer:** Validar tamanho na solicitação, na política de upload e na confirmação por metadados confiáveis antes de baixar/processar. Rejeitar e remover objetos fora do limite.

**Critério de aceite:** Um upload direto acima do limite é recusado mesmo fora da interface e não é baixado integralmente pela função.

### 25. Fotos do produto são enviadas em sequência

**Prioridade:** P2 · **Área:** Performance · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `frontend/src/api.js`

**Problema e impacto:** Cada foto espera solicitação de URL e transferência antes de iniciar a próxima, aumentando o tempo total do lote.

**O que fazer:** Preparar o lote e enviar com concorrência limitada, progresso individual e possibilidade de repetir apenas as fotos que falharam. Evitar paralelismo ilimitado no celular.

**Critério de aceite:** Enviar oito fotos em conexão móvel: há progresso por arquivo, limite de simultaneidade e retomada sem reenviar as fotos concluídas.

### 26. Excluir campanha não remove objetos remotos

**Prioridade:** P1 · **Área:** Performance e armazenamento · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `app.py`

**Problema e impacto:** A exclusão remove registros do banco e a pasta local, mas não solicita a exclusão das mídias do Storage; o espaço continua ocupado.

**O que fazer:** Antes de apagar os registros, reunir os objetos exclusivos da campanha e executar limpeza rastreável, com repetição em caso de falha. Verificar referências compartilhadas antes de remover qualquer objeto.

**Critério de aceite:** Excluir uma campanha de teste remove seus objetos exclusivos; falha temporária do Storage fica pendente para nova tentativa, sem apagar mídia de outra campanha.

### 27. Uploads abandonados deixam objetos órfãos

**Prioridade:** P2 · **Área:** Performance e armazenamento · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `app.py`, `frontend/src/api.js`

**Problema e impacto:** Arquivos enviados e nunca confirmados, ou rejeitados depois do envio, podem permanecer no bucket sem vínculo com campanha ativa.

**O que fazer:** Criar registros de upload pendente com validade, marcar confirmação e remover periodicamente pendências expiradas. Limpar também objetos reprovados, respeitando retenção e referências.

**Critério de aceite:** Cancelar um envio, reprovar uma mídia e abandonar uma confirmação: após a política de expiração, só os arquivos efetivamente associados permanecem.

### 28. Cache da biblioteca é sobrescrito

**Prioridade:** P1 · **Área:** Performance · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `app.py`

**Problema e impacto:** A rota das fotos define cache próprio, mas o middleware global aplica no-store a toda resposta /api/, anulando a regra de cache da biblioteca.

**O que fazer:** Permitir a política específica de mídia privada versionada, preservando no-store em respostas sensíveis. Usar URLs de conteúdo versionadas e TTL menor que a validade do link assinado.

**Critério de aceite:** Inspecionar os headers finais: fotos reutilizáveis mantêm cache privado adequado, fotos trocadas recebem URL nova e nenhuma resposta de conta fica em cache público.

### 29. Galerias usam imagens originais como miniaturas

**Prioridade:** P2 · **Área:** Performance · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `frontend/src/components.jsx`, `serviços de mídia/armazenamento`

**Problema e impacto:** As principais galerias carregam imagens de resolução integral, sem variantes pequenas e sem carregamento adiado dos itens fora da tela.

**O que fazer:** Gerar miniaturas adequadas, reservar dimensões para evitar deslocamento e usar carregamento adiado abaixo da primeira tela. Manter o original acessível para download e inspeção.

**Critério de aceite:** A abertura de uma galeria não baixa todas as imagens originais; ampliar uma foto continua mostrando qualidade integral e a página não salta durante o carregamento.

### 30. Interface inteira no bundle inicial

**Prioridade:** P2 · **Área:** Performance · **Estado:** Pendente  
**Base do achado:** Build local inspecionado  
**Onde investigar:** `frontend/src/App.jsx`, `frontend/src/components.jsx`, `frontend/src/styles.css`, `frontend/vite.config.js`

**Problema e impacto:** O build local contém aproximadamente 477 KB de JavaScript e 77 KB de CSS antes da compressão de transporte, sem divisão por telas. Esses números não são uma medição de transferência ou Core Web Vitals em produção.

**O que fazer:** Separar telas e componentes pesados por carregamento sob demanda, revisar dependências/ativos e consolidar CSS duplicado. Medir antes/depois no acesso inicial e recorrente.

**Critério de aceite:** Comparar bundle e carregamento em rede móvel; Resultados e ferramentas opcionais não precisam entrar antes de o usuário abrir essas áreas.

### 31. Inicialização busca detalhes desnecessários

**Prioridade:** P2 · **Área:** Performance · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `frontend/src/App.jsx`

**Problema e impacto:** A abertura busca a primeira campanha mesmo na página inicial e pode buscar outro detalhe imediatamente para atender a uma rota específica.

**O que fazer:** Ler a rota primeiro e buscar somente os dados necessários à tela. Carregar detalhes de campanha sob demanda e eliminar a busca duplicada quando o ID já coincide.

**Critério de aceite:** Na página inicial não há busca de detalhe sem necessidade; num link direto há apenas uma busca do detalhe correto.

### 32. Operações pequenas recarregam listas completas

**Prioridade:** P2 · **Área:** Performance · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `frontend/src/App.jsx`, `app.py`

**Problema e impacto:** O helper de operação recarrega campanhas e referências após cada ação. A listagem retorna todas as campanhas, sem paginação.

**O que fazer:** Atualizar no estado apenas o item alterado; invalidar referências somente quando houver mudança relevante. Criar paginação, busca e filtros no servidor para o histórico.

**Critério de aceite:** Salvar uma frase não recarrega referências; centenas de campanhas não aumentam indefinidamente o payload inicial.

### 33. Conexões de banco são abertas por requisição

**Prioridade:** P2 · **Área:** Performance · **Estado:** Pendente  
**Base do achado:** Código; infraestrutura externa não inspecionada  
**Onde investigar:** `app.py`

**Problema e impacto:** O aplicativo abre conexão PostgreSQL por requisição, sem reutilização própria e sem timeout explícito de conexão. O DSN pode usar pooler externo, que não foi confirmado.

**O que fazer:** Verificar primeiro o pooler e limites da infraestrutura existente. Configurar timeout de conexão/consulta e adotar uma estratégia compatível com serverless, evitando criar pools excessivos por instância.

**Critério de aceite:** Medir conexões e latência sob acessos simultâneos; banco indisponível produz erro controlado em prazo definido e não esgota o limite de conexões.

### 34. Requisições não têm timeout ou cancelamento

**Prioridade:** P2 · **Área:** Performance e recuperação · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `frontend/src/api.js`, `frontend/src/App.jsx`

**Problema e impacto:** O fetch principal não define prazo ou AbortController; tarefas demoradas podem manter o estado global ocupado. A leitura de metadados de vídeo também pode esperar indefinidamente.

**O que fazer:** Definir prazos por operação, cancelamento e mensagens recuperáveis. Não repetir automaticamente mutações sem chave de idempotência, pois o servidor pode ter concluído a operação.

**Critério de aceite:** Simular conexão interrompida e leitura de vídeo que não termina: o app sai do estado de espera, mantém o rascunho e permite consultar/repetir com segurança.

### 35. Exportação ZIP concentra trabalho pesado na requisição

**Prioridade:** P1 · **Área:** Performance · **Estado:** Pendente  
**Base do achado:** Código; risco de limites não medido  
**Onde investigar:** `app.py`

**Problema e impacto:** A exportação baixa mídias sequencialmente e aplica compressão a arquivos já comprimidos, dentro da função que atende o usuário.

**O que fazer:** Montar exportações grandes fora da requisição interativa, guardar o pacote e devolver link temporário. Para pacotes pequenos, usar streaming e evitar recompressão inútil de MP4/JPEG.

**Critério de aceite:** Exportar uma campanha com vários vídeos grandes sem ultrapassar o tempo da função; mostrar progresso/estado e permitir baixar o pacote pronto sem refazê-lo.

## 3. Integridade dos dados e testes

### 36. ZIP repete nomes de arquivos de cores diferentes

**Prioridade:** P1 · **Área:** Confiabilidade · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `app.py`

**Problema e impacto:** Os nomes são montados pelo tipo de mídia e extensão, sem cor ou identificador; várias entradas recebem imagem-aprovada.png ou video-aprovado.mp4.

**O que fazer:** Incluir ordem, cor normalizada e identificador nos caminhos do ZIP; adicionar um manifesto que associe cada arquivo ao produto, cor e aprovação.

**Critério de aceite:** Exportar três cores com a mesma extensão e extrair: todos os arquivos permanecem distintos, com nomes legíveis e associação inequívoca.

### 37. Edição simultânea não está protegida corretamente no PostgreSQL

**Prioridade:** P1 · **Área:** Confiabilidade · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `app.py`

**Problema e impacto:** A adaptação de BEGIN IMMEDIATE deixa de aplicar o bloqueio usado no SQLite. Duas transações podem ler a mesma versão e gravar sem uma condição atômica de versão.

**O que fazer:** Usar atualização condicional por versão com verificação de linhas afetadas, ou bloqueio de linha em transações curtas. Exigir a versão nos endpoints de edição relevantes e oferecer recuperação de conflito na interface.

**Critério de aceite:** Dois clientes leem a mesma versão e salvam simultaneamente: um conclui; o outro recebe conflito sem perda do rascunho, podendo comparar alterações.

### 38. Biblioteca compartilhada é sobrescrita como JSON completo

**Prioridade:** P1 · **Área:** Confiabilidade · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/model_library.py`, `app.py`

**Problema e impacto:** Cada mudança lê e regrava o documento inteiro da biblioteca no Storage. Edições simultâneas podem apagar uma à outra.

**O que fazer:** Migrar os metadados para linhas transacionais por modelo/nicho no banco, ou adotar controle condicional por revisão. Manter as imagens no armazenamento de objetos.

**Critério de aceite:** Duas contas alteram nichos diferentes simultaneamente e ambas as alterações são preservadas; conflito no mesmo nicho é explícito.

### 39. Erro do Storage pode parecer biblioteca vazia

**Prioridade:** P1 · **Área:** Confiabilidade · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/model_library.py`

**Problema e impacto:** A leitura captura falhas remotas e retorna um dicionário vazio, ocultando indisponibilidade, permissão inválida ou resposta corrompida.

**O que fazer:** Distinguir ausência legítima, erro transitório e erro de configuração. Mostrar estado de falha com nova tentativa e impedir gravação destrutiva baseada numa leitura malsucedida.

**Critério de aceite:** Simular erro remoto: a tela não anuncia que as fotos foram removidas e nenhuma operação substitui a biblioteca existente por um documento vazio.

### 40. Caminho em nuvem sem cobertura automatizada equivalente

**Prioridade:** P1 · **Área:** Confiabilidade e testes · **Estado:** Pendente  
**Base do achado:** Código dos testes  
**Onde investigar:** `tests/test_app.py`, `app.py`, `vercel.json`

**Problema e impacto:** A suíte inspecionada não exercita o caminho CLOUD_MODE, a adaptação PostgreSQL e o ciclo completo de uploads assinados/persistência remota.

**O que fazer:** Adicionar testes de integração com PostgreSQL isolado e Storage de teste; cobrir concorrência, upload/confirm, limpeza, exportação e sessão. Usar mocks apenas onde não ocultem diferenças reais do banco.

**Critério de aceite:** A suíte falha quando uma consulta incompatível com PostgreSQL ou uma regressão do fluxo de upload é introduzida; dados e credenciais de produção não são usados.

## 4. Geração de imagens e análise do produto

### 41. Primeira cor pede fotografia inédita

**Prioridade:** P1 · **Área:** Prompt de imagem · **Estado:** Pendente  
**Base do achado:** Código; divergência do objetivo anteriormente declarado  
**Onde investigar:** `services/prompts.py`

**Problema e impacto:** O modo inicial manda criar uma nova fotografia, permitindo pose, enquadramento e peças complementares diferentes. O objetivo declarado era preservar a foto da modelo e alterar a roupa.

**O que fazer:** Definir explicitamente o modo de criação. Usar troca localizada da roupa como padrão para esse fluxo e deixar nova composição como opção consciente. Não assumir que primeira cor exige recriar a fotografia.

**Critério de aceite:** Com a referência de top rosa e legging estampada, o prompt padrão altera somente a peça selecionada e preserva pose, top, calçados e ambiente.

### 42. Cenário da referência conflita com cenário do nicho

**Prioridade:** P1 · **Área:** Prompt de imagem · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/prompts.py`, `frontend/src/nicheDefaults.js`, `services/model_library.py`

**Problema e impacto:** A preservação do ambiente convive com cenários e estilos sugeridos automaticamente pelo nicho, sem uma prioridade inequívoca.

**O que fazer:** Definir a referência visual escolhida como fonte principal de cenário; padrões de nicho não podem substituí-la. Usar nova locação somente por escolha explícita e retirar alternativas conflitantes do prompt final.

**Critério de aceite:** Uma foto de academia não recebe rua/praia como alternativa por texto herdado; o prompt contém um único cenário e uma única referência de continuidade.

### 43. Preservar foto e eliminar desfoque entram em conflito

**Prioridade:** P1 · **Área:** Prompt de imagem · **Estado:** Pendente  
**Base do achado:** Código; dependente da referência utilizada  
**Onde investigar:** `services/prompts.py`, `fluxo de referência e aprovação`

**Problema e impacto:** Se o fundo original já estiver desfocado, exigir fotografia idêntica e fundo nítido é incompatível.

**O que fazer:** Detectar essa decisão na preparação da referência: preservar o foco existente ou aprovar uma nova base nítida uma única vez. Usar a base aprovada nas demais cores sem reconstruir o fundo repetidamente.

**Critério de aceite:** O prompt não exige simultaneamente desfoque idêntico e ausência de desfoque. A mesma base visual aprovada orienta todas as variações.

### 44. Ordem dos anexos não acompanha a edição das próximas cores

**Prioridade:** P1 · **Área:** Prompt de imagem · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/prompts.py`, `frontend/src/components.jsx`, `app.py`

**Problema e impacto:** O prompt de edição localizada cita a imagem aprovada, mas a orientação geral continua pedindo modelo fixa primeiro e produto depois, sem identificar a base correta.

**O que fazer:** Criar um manifesto de anexos por geração: fotografia-base selecionada, identidade quando necessária e fotos do produto. Mostrar miniaturas numeradas com a função de cada referência e gerar o texto na mesma ordem.

**Critério de aceite:** Na segunda cor, interface e prompt apontam a mesma imagem-base e explicam que fotos de catálogo não fornecem rosto, pose nem cenário.

### 45. Enquadramento permitido pode cortar o produto

**Prioridade:** P2 · **Área:** Prompt de imagem · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/prompts.py`

**Problema e impacto:** A opção pessoa inteira ou até os joelhos pode ocultar a barra de calças e vestidos longos.

**O que fazer:** Escolher o enquadramento pela peça e pelo detalhe necessário, preservando a composição da referência quando o modo for edição localizada. Indicar margens para não cortar barras, mangas ou calçados relevantes.

**Critério de aceite:** Calça e vestido longo ficam completamente visíveis; detalhes de uma blusa não obrigam alteração desnecessária da fotografia-base.

### 46. Filtro remove instruções fotográficas legítimas

**Prioridade:** P1 · **Área:** Prompt de imagem · **Estado:** Pendente  
**Base do achado:** Reproduzido em função local  
**Onde investigar:** `services/prompts.py`

**Problema e impacto:** A remoção por palavras como câmera e enquadramento elimina orientações estáticas válidas; no teste, câmera na altura dos olhos e corpo inteiro desapareceram.

**O que fazer:** Separar briefing de imagem, direção de vídeo e falas em campos estruturados. Na compatibilidade com textos antigos, classificar instruções por sentido em vez de excluir qualquer frase que contenha uma palavra.

**Critério de aceite:** Manter câmera na altura dos olhos e enquadramento de corpo inteiro no prompt de imagem; retirar duração, falas, cortes e ações temporais.

### 47. Produto unissex perde o substantivo específico

**Prioridade:** P2 · **Área:** Prompt de imagem · **Estado:** Pendente  
**Base do achado:** Reproduzido em função local  
**Onde investigar:** `services/prompts.py`

**Problema e impacto:** A função devolve peça para qualquer produto identificado como unissex; camisa unissex deixa de ser nomeada como camisa.

**O que fazer:** Separar gênero gramatical do substantivo, público e modelagem unissex. Preservar camisa, calça, casaco etc. na definição da região que será alterada.

**Critério de aceite:** Camisa unissex continua sendo camisa no prompt e na direção corporal, sem impor gênero ao público.

### 48. Fatos confirmados não têm origem confiável

**Prioridade:** P1 · **Área:** Imagem e vídeo · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/prompts.py`, `services/copywriter.py`, `app.py`, `formulário de briefing`

**Problema e impacto:** A extração por palavras mistura produto, roupa, detalhes, ângulo e benefício. Uma sugestão ou instrução pode virar atributo confirmado.

**O que fazer:** Criar ficha estruturada de atributos com fonte e estado: informado, identificado visualmente, sugerido e confirmado pelo usuário. Apenas atributos confirmados devem alimentar promessas; instruções de cena permanecem separadas.

**Critério de aceite:** Uma sugestão mostrar compressão não confirma compressão; cada fato usado em imagem, fala e vídeo tem origem identificável.

### 49. Negação de sem transparência vira confirmação

**Prioridade:** P1 · **Área:** Imagem e vídeo · **Estado:** Pendente  
**Base do achado:** Reproduzido em função local  
**Onde investigar:** `services/prompts.py`

**Problema e impacto:** O reconhecimento especial de sem transparência ignora a negação externa e pode confirmar o atributo quando o texto diz que ele não existe.

**O que fazer:** Resolver negação e incerteza no nível da afirmação, preferencialmente sobre atributos estruturados. Na migração de texto livre, marcar conflito para revisão em vez de assumir confirmação.

**Critério de aceite:** Testar não é sem transparência, não sei se é sem transparência e sem transparência confirmada: apenas a última alimenta a promessa.

### 50. Materiais e composição têm cobertura limitada

**Prioridade:** P2 · **Área:** Imagem e vídeo · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/prompts.py`, `briefing`, `análise de produto`

**Problema e impacto:** O vocabulário contempla poucos materiais e não preserva de forma estruturada percentuais, gramatura e detalhes fora da lista.

**O que fazer:** Permitir material principal, composição percentual, textura/acabamento e características livres confirmadas. Não inferir desempenho de um tecido apenas pelo seu nome; manter o texto original quando a classificação não reconhecer o material.

**Critério de aceite:** Produtos com viscose, linho, misturas e percentuais mantêm informações confirmadas sem convertê-las automaticamente em conforto, elasticidade ou durabilidade.

### 51. Atributos são priorizados por ordem fixa

**Prioridade:** P2 · **Área:** Imagem e vídeo · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/prompts.py`

**Problema e impacto:** O limite de atributos é preenchido pela ordem do dicionário interno, não pela importância para o produto ou argumento de venda.

**O que fazer:** Permitir selecionar o detalhe principal e ordenar atributos de apoio. Usar relevância para a peça e para o argumento, com limite explícito de detalhes por cena.

**Critério de aceite:** Ao escolher um fecho como diferencial, ele não é omitido só porque bolso, costura e barra aparecem antes no vocabulário.

### 52. Ordem das fotos contradiz a instrução da IA

**Prioridade:** P1 · **Área:** Análise de produto · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `app.py`, `services/copywriter.py`

**Problema e impacto:** A instrução descreve produto primeiro e descrição depois, mas o backend envia primeiro o print da descrição.

**O que fazer:** Enviar os anexos na ordem descrita e identificar cada um por função no conteúdo da requisição. Tratar explicitamente o caso com apenas descrição ou apenas produto.

**Critério de aceite:** Um teste inspeciona a ordem e os rótulos da requisição; a IA distingue o print técnico da fotografia da roupa em todos os casos.

### 53. Somente a primeira foto do produto é analisada

**Prioridade:** P2 · **Área:** Análise de produto · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `app.py`, `services/copywriter.py`, `frontend/src/components.jsx`

**Problema e impacto:** A consulta usa apenas a primeira imagem salva, ignorando detalhes presentes nas costas, laterais e aproximações.

**O que fazer:** Permitir selecionar fotos relevantes para análise, com limite de quantidade e tamanho. Enviar versões otimizadas e rótulos como frente, costas e detalhe quando informados.

**Critério de aceite:** Um bolso ou fecho que aparece somente na segunda foto é considerado na análise, sem precisar reordenar ou excluir referências.

## 5. Direção e geração de vídeo

### 54. Ordens de câmera são incompatíveis

**Prioridade:** P1 · **Área:** Prompt de vídeo · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/prompts.py`

**Problema e impacto:** O texto exige repetir posição, distância e perspectiva, mas também usar aproximação, acompanhamento e ângulo baixo.

**O que fazer:** Preservar o jogo de câmeras aprovado pelo usuário e definir movimentos permitidos dentro da mesma cena. Distinguir continuidade do cenário de movimento da câmera; retirar proibições que anulam zoom/retorno planejados.

**Critério de aceite:** O prompt permite aproximação e retorno coerentes, mantém a locação e não contém simultaneamente câmera imóvel e acompanhamento obrigatório. Comparar com o prompt de referência que o usuário aprovou.

### 55. Excesso de ações obrigatórias em 11 segundos

**Prioridade:** P1 · **Área:** Prompt de vídeo · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/prompts.py`, `services/copywriter.py`

**Problema e impacto:** O prompt exige todas as ações da lista, além de provas visuais, aproximação e fala; a análise por imagem também pode sugerir quatro a sete movimentos.

**O que fazer:** Selecionar poucas ações prioritárias e distribuir duração realista entre elas. Tratar sugestões como opções, não como uma lista obrigatória; manter somente demonstrações que sustentam o argumento escolhido.

**Critério de aceite:** Uma lista de sete sugestões produz um plano executável, sem exigir todas. Revisão manual confirma transições naturais e tempo suficiente para fala.

### 56. Regra das mãos interfere na demonstração

**Prioridade:** P1 · **Área:** Prompt de vídeo · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/prompts.py`

**Problema e impacto:** Uma mão deve tocar a roupa o tempo todo, mesmo quando outras instruções exigem movimentos incompatíveis, como alongar ou ajustar acessórios.

**O que fazer:** Descrever mãos por momento e por produto. Usar posição de repouso natural e gestos com propósito, evitando a obrigação permanente de contato com a roupa.

**Critério de aceite:** Cada ação pode ser executada anatomicamente; não existem comandos simultâneos incompatíveis para a mesma mão.

### 57. Encerramento é rígido e repetitivo

**Prioridade:** P2 · **Área:** Prompt de vídeo · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/prompts.py`

**Problema e impacto:** Todos os produtos recebem mãos no cós, barra ou cintura e corpo parado, com movimento apenas de rosto/olhar.

**O que fazer:** Criar encerramentos naturais adequados à peça e à fala, mantendo a preferência de evitar acenos involuntários. Deixar a posição final escolhível e evitar imobilidade absoluta como padrão.

**Critério de aceite:** Camisa, calça e vestido recebem finais apropriados; não há aceno obrigatório nem a mesma pose engessada em todos os vídeos.

### 58. Abertura visual sempre repete o segredo

**Prioridade:** P2 · **Área:** Prompt de vídeo · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/prompts.py`

**Problema e impacto:** O início manda a modelo dar um passo em direção à câmera como quem vai contar um segredo, independentemente do argumento.

**O que fazer:** Vincular a abertura ao hook e ao produto: apresentação direta, detalhe, comparação visual ou aproximação quando fizer sentido. Variar sem mudar a identidade ou o cenário.

**Critério de aceite:** Gerar propostas para diferentes argumentos e confirmar que não repetem obrigatoriamente a aproximação de segredo.

### 59. Movimentos do nicho não respeitam a peça real

**Prioridade:** P1 · **Área:** Prompt de vídeo · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/prompts.py`, `frontend/src/nicheDefaults.js`, `services/model_library.py`

**Problema e impacto:** O padrão de academia injeta agachamento e foco em legging mesmo para top ou outra peça; outros nichos também carregam ações genéricas.

**O que fazer:** Resolver primeiro tipo de produto e detalhes confirmados, depois escolher a demonstração. Usar nicho apenas como contexto; movimentos explícitos do usuário devem prevalecer quando compatíveis.

**Critério de aceite:** Top, camisa e legging do mesmo nicho produzem demonstrações específicas e não recebem detalhes ou regiões anatômicas de outra peça.

### 60. Somente câmera descreve movimento da modelo

**Prioridade:** P2 · **Área:** Prompt de vídeo · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/prompts.py`

**Problema e impacto:** Os trechos rotulados somente câmera incluem caminhar, girar, sentar e agachar; o texto tenta dizer sem nova fala, mas usa outro significado.

**O que fazer:** Separar por tempo três trilhas claras: ação da pessoa, câmera e fala. Usar sem fala adicional quando a fala do desenvolvimento deve continuar.

**Critério de aceite:** Cada trecho informa inequivocamente o que a modelo faz, o que a câmera faz e qual fala continua, sem títulos contraditórios.

### 61. Pós-produção aparece dentro do prompt de geração

**Prioridade:** P2 · **Área:** Prompt de vídeo · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/prompts.py`, `frontend/src/components.jsx`

**Problema e impacto:** Unir clipes e exportar um MP4 são instruções ao operador, mas entram no mesmo texto enviado ao gerador.

**O que fazer:** Mover essas orientações para a interface ou checklist de pós-produção. Quando houver geração por clipes, produzir prompts separados e instruções de montagem fora deles.

**Critério de aceite:** O texto copiado para o gerador contém apenas a cena a gerar; exportação e montagem aparecem em orientações distintas.

### 62. Adaptação entre Grok e Flow é superficial

**Prioridade:** P2 · **Área:** Prompt de vídeo · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/prompts.py`, `frontend/src/components.jsx`

**Problema e impacto:** A estrutura de direção é essencialmente a mesma e a diferença principal é resolução, sem plano próprio de operação e continuidade por serviço.

**O que fazer:** Criar perfis configuráveis de geração com duração/forma de uso escolhidas pelo usuário e capacidades verificadas no serviço atual. Adaptar referência, clipes e continuidade sem prometer que texto controla resolução ou duração sozinho.

**Critério de aceite:** Para cada serviço, o prompt e a orientação operacional correspondem ao modo realmente usado; limitações são tratadas antes da geração, sem reconstrução improvisada depois.

### 63. Atualizar fala substitui direção manual

**Prioridade:** P1 · **Área:** Prompt de vídeo · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/prompts.py`, `app.py`, `frontend/src/App.jsx`

**Problema e impacto:** A regeneração de hook/desenvolvimento/CTA reconstrói todo o prompt de vídeo, podendo apagar câmera e movimentos que já funcionavam.

**O que fazer:** Guardar direção visual e falas em estruturas separadas. Atualizar somente a trilha falada, preservando ajustes visuais; oferecer restauração de versões e ação explícita para regenerar a direção.

**Critério de aceite:** Personalizar zoom, movimentos e encerramento, atualizar apenas o hook e verificar que todas as instruções visuais permanecem idênticas.

### 64. Contagem de palavras não garante duração

**Prioridade:** P2 · **Área:** Prompt de vídeo · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/prompts.py`, `services/copywriter.py`, `frontend/src/App.jsx`

**Problema e impacto:** A faixa de palavras é tratada como encaixe em 15 segundos, sem considerar pausas, números, palavras longas ou interpretação.

**O que fazer:** Apresentar duração como estimativa, considerar velocidade configurável e carga por trecho e manter leitura/revisão humana. Se houver áudio disponível, medir sua duração; não exigir fala acelerada para caber.

**Critério de aceite:** Texto com números extensos ou pausas recebe estimativa coerente e alerta; a interface não afirma que apenas contar palavras garante 15 segundos.

## 6. Falas, legendas e controle de qualidade

### 65. Regras de urgência se contradizem

**Prioridade:** P1 · **Área:** Falas · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/copywriter.py`, `frontend/src/components.jsx`

**Problema e impacto:** Uma regra proíbe corre sem oferta, outra permite sempre e o briefing volta a proibir qualquer palavra de urgência.

**O que fazer:** Definir uma política única distinguindo convite entusiasmado de afirmação verificável sobre estoque, prazo e preço. Aplicá-la igualmente no prompt, auditoria e interface.

**Critério de aceite:** O mesmo CTA recebe a mesma decisão em todos os caminhos; desconto e prazo só entram quando constam da oferta confirmada.

### 66. Estrutura favorece sempre receio e surpresa

**Prioridade:** P2 · **Área:** Falas · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/copywriter.py`, `services/prompts.py`

**Problema e impacto:** Primeira pessoa, confissão, medo e descoberta são exigidos ou premiados, estreitando a diversidade criativa.

**O que fazer:** Permitir estratégias distintas: versatilidade, economia comprovada, ocasião, detalhe de qualidade, autoestima, descoberta e quebra de objeção. Avaliar coerência e especificidade em vez de favorecer um grupo fixo de palavras.

**Critério de aceite:** Gerar um lote de opções e verificar diversidade real de estruturas, sem obrigar toda abertura a confesso, achei ou tinha medo.

### 67. Depoimentos pessoais são incentivados sem comprovação

**Prioridade:** P1 · **Área:** Falas · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/copywriter.py`, `briefing`

**Problema e impacto:** A instrução manda falar como quem comprou, vestiu e testou, mas o briefing não registra que essas experiências ocorreram.

**O que fazer:** Separar demonstração da personagem de relato real. Exigir experiência fornecida para alegações como comprei, usei por meses ou testei; permitir linguagem natural baseada no que é visível sem inventar histórico.

**Critério de aceite:** Sem experiência cadastrada, os roteiros não inventam compra, teste ou uso prolongado; com relato confirmado, preservam os limites do que foi informado.

### 68. Alternativas geradas são descartadas sem escolha

**Prioridade:** P2 · **Área:** Falas · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/copywriter.py`, `app.py`, `frontend/src/components.jsx`

**Problema e impacto:** A API pede três opções, mas só retorna a vencedora de uma pontuação por palavras-chave; o usuário perde as demais alternativas já geradas.

**O que fazer:** Salvar e apresentar as opções aprovadas com o argumento central, permitir escolha e guardar as anteriores. Usar a pontuação como sugestão, não como descarte definitivo.

**Critério de aceite:** Uma chamada retorna alternativas revisáveis; escolher outra não precisa gastar nova chamada e mantém a opção anterior no histórico.

### 69. Proteção contra repetição é literal e curta

**Prioridade:** P2 · **Área:** Falas · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/copywriter.py`, `app.py`

**Problema e impacto:** A auditoria compara principalmente igualdade exata com o roteiro atual; não mede repetição de estrutura, de argumento ou entre campanhas/cores.

**O que fazer:** Manter histórico recente por produto e personagem, comparar similaridade textual e registrar estratégia usada. Tratar repetição como sinal de revisão, sem forçar diferenças artificiais em nomes ou fatos.

**Critério de aceite:** Roteiros quase iguais com palavras trocadas são sinalizados; uma sequência de cores evita repetir a mesma história sem necessidade.

### 70. Objeção pode liberar uma promessa

**Prioridade:** P1 · **Área:** Falas e legendas · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/copywriter.py`

**Problema e impacto:** A auditoria procura termos no briefing incluindo objeção. A presença da palavra em uma dúvida ou negação pode ser tratada como autorização para afirmá-la.

**O que fazer:** Validar promessas exclusivamente contra atributos confirmados e sua polaridade. Usar objeção para escolher o argumento, nunca como evidência de que o produto resolve o problema.

**Critério de aceite:** A objeção tenho medo de transparência não permite dizer que o produto não fica transparente; a afirmação só passa com comprovação cadastrada.

### 71. Auditoria é menos rigorosa que a das falas

**Prioridade:** P1 · **Área:** Legendas · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `services/copywriter.py`, `services/prompts.py`

**Problema e impacto:** A legenda é verificada quanto à presença e quantidade de hashtags, mas não recebe as mesmas checagens de atributos e urgência.

**O que fazer:** Aplicar às legendas as mesmas regras de fatos, oferta, experiência e negação, além de pertinência e deduplicação de hashtags. Respeitar diferenças entre linguagem falada e escrita.

**Critério de aceite:** Uma legenda com desconto inventado ou benefício não confirmado é recusada, mesmo quando hook, desenvolvimento e CTA estão corretos.

### 72. Origem do texto é registrada apenas por campanha

**Prioridade:** P2 · **Área:** Falas · **Estado:** Pendente  
**Base do achado:** Código  
**Onde investigar:** `app.py`, `frontend/src/App.jsx`, `frontend/src/components.jsx`

**Problema e impacto:** O selo de autoria é salvo no checklist da campanha e pode refletir somente a última geração, mesmo com cores escritas por fontes diferentes.

**O que fazer:** Registrar origem por variante e revisão: geração local/API/edição manual, provedor, modelo e data. Exibir o selo correspondente ao texto mostrado, sem registrar segredos.

**Critério de aceite:** Uma cor gerada localmente e outra por IA apresentam selos corretos; editar manualmente não continua sendo apresentado como saída intacta do provedor.

### 73. Falta revisão conjunta das contradições

**Prioridade:** P1 · **Área:** Qualidade dos prompts · **Estado:** Pendente  
**Base do achado:** Código e cobertura inspecionada  
**Onde investigar:** `services/prompts.py`, `services/copywriter.py`, `tests/test_app.py`

**Problema e impacto:** Há verificações de trechos e presença de frases, mas não um contrato que avalie cenário, câmera, pose, mãos, duração, peça e referências em conjunto.

**O que fazer:** Montar os prompts a partir de uma especificação estruturada e executar validações cruzadas antes da cópia. Criar casos de regressão representativos e comparar resultados visuais com o prompt aprovado pelo usuário.

**Critério de aceite:** A revisão detecta câmera fixa com acompanhamento, mãos ocupadas com ação incompatível, produto cortado, referência ausente e mudança de cenário. Os testes não se limitam a procurar frases literais.

## Plano de validação da implementação

### Fluxos funcionais

- Criar, editar, copiar e excluir campanhas sem trocar o alvo da operação ou perder rascunhos.
- Produzir uma cor, várias cores e cores com variações de escrita/espaço.
- Usar vídeo enviado ao Storage e vídeo mantido apenas na galeria; revisar com os dois usuários.
- Salvar campos diferentes simultaneamente e tratar conflito no mesmo campo/campanha.
- Atualizar somente o hook, somente a legenda e o roteiro inteiro, verificando preservação da direção visual quando aplicável.
- Exportar várias cores com a mesma extensão e conferir integridade e nomes únicos no pacote.
- Simular falhas de rede, sessão expirada, API lenta e Storage indisponível sem anunciar sucesso incorreto.

### Interface e dispositivos

- Conferir as larguras indicadas no item 1, incluindo orientação horizontal e teclado virtual.
- Validar Safari em iPhone físico: seleção do vídeo, prévia, retorno dos aplicativos e persistência dos rascunhos.
- Conferir rótulos acessíveis, navegação por teclado, foco dos diálogos, mensagens de erro e estado dos controles.
- Comparar comportamento local e online de Grok, Flow, TikTok e TikTok Studio.

### Performance e nuvem

- Medir abertura inicial/recorrente, número de requisições, bytes de imagem, tempo de upload/validação e consumo de memória.
- Medir geração por cor e por lote com provedor lento; verificar retomada sem cobranças duplicadas evitáveis.
- Inspecionar headers finais de cache e validade dos links, sem cache público de conteúdo privado.
- Verificar limite e uso de conexões do banco, integridade sob concorrência e política de limpeza de objetos órfãos.
- Executar testes de integração fora do banco e bucket de produção.

### Qualidade dos prompts

- Manter um conjunto pequeno e representativo de produtos: legging, top, camisa unissex, vestido longo, peça com fecho/bolso, materiais mistos e produto sem composição confirmada.
- Usar referências com fundo nítido e já desfocado, distinguindo preservação da base de criação de nova composição.
- Incluir negações, dúvidas, oferta ausente e detalhes encontrados somente na segunda foto.
- Avaliar consistência da identidade, fundo, roupa complementar, enquadramento, mãos e cor; separar defeitos do prompt das limitações do gerador.
- Comparar o plano visual com o prompt que o usuário já aprovou, sem substituir automaticamente sua direção por um novo padrão.
- Conferir naturalidade das falas em leitura real e ausência de comandos de filmagem, experiências inventadas ou promessas sem suporte.
- Registrar qual prompt/versão produziu cada resultado aprovado para evitar repetir regressões.

## Registro de acompanhamento

Para cada item implementado, registrar:

| Campo | Conteúdo esperado |
|---|---|
| Item | Número original de 1 a 73. |
| Responsável | Pessoa que executou a alteração. |
| Status | Pendente, em andamento, em validação, concluído ou descartado com justificativa. |
| Implementação | Commit/PR e descrição objetiva da mudança. |
| Evidência | Teste, captura, medição ou resultado que atende ao critério de aceite. |
| Observações | Dependências, decisão do usuário e limitações que permaneceram. |

Um item só deve ser marcado como concluído quando sua correção e seu critério de aceite forem verificados. Melhorias de performance devem ter comparação antes/depois; melhorias criativas devem preservar também os casos que já funcionavam.

## Relação com documentos anteriores

Este documento é um retrato da revisão de **13/09/2026** e complementa os relatórios anteriores. Não altera retroativamente itens marcados como feitos em `MELHORIAS-SUGERIDAS.md`: alguns comportamentos mudaram depois, outros dependem da nova execução em nuvem. Em caso de divergência, conferir o código e o deploy atuais e registrar a decisão no item correspondente.

