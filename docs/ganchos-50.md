# Ganchos: tipos, regra e o que foi aproveitado dos 50

A lista de 50 ganchos (5 grupos de 10) é escrita para criadores de conteúdo. Aqui ela virou a regra de abertura dos vídeos de produto,
em `services/hook_types.py`. **27 dos 50 entraram (usados ou adaptados); 23 ficaram de fora** por inventar credencial, história ou
resultado que o app não pode afirmar (regras 1, 6 e 10 do prompt da IA e a auditoria do texto).

## A regra
1. Cada cor da campanha recebe um **tipo de gancho**. O que o briefing declarou abre (autoridade, dor); depois curiosidade, **suspense e FOMO**, direto e história.
2. **Dor** só existe com receio ou objeção no briefing. **Autoridade** só com prova social, altura/tamanho ou público com identidade
   declarados. Sem isso o tipo é pulado.
3. O gancho **fecha o próprio suspense** com o fato (`{det}`) ou a dor (`{pain}`). Pergunta só se carregar o fato ou a dor.
4. Bloqueado em qualquer gancho, local ou da IA: credencial inventada, história passada que ninguém verifica e
   pergunta vazia (auditoria em `hook_types.problems`, usada por `copywriter.audit`).
5. Com oferta real no briefing, o gancho de escassez continua na frente (a regra de tipo não se aplica).
6. A IA recebe a regra no prompt (regra 11) e, em campanha com várias cores, o tipo obrigatório de cada cor.

## Mapa dos 50
Legenda: **usado** = molde quase igual; **adaptado** = ideia mantida, texto reescrito para produto; **bloqueado** = não entra, com o motivo.

### 1. Curiosidade
| # | Original | Destino |
|---|---|---|
| 1 | Você sabia disso? | adaptado: "Você já percebeu {detalhe} nesse X? Eu só vi de perto." (a pergunta vazia é bloqueada) |
| 2 | Ninguém te conta isso… | usado: fecha com o detalhe |
| 3 | O que ninguém percebe é que… | usado |
| 4 | A maioria das pessoas faz errado. | adaptado (liberado): "A maioria nem repara {detalhe}…, e eu quase fiz igual." |
| 5 | Eu não deveria te dizer isso, mas… | adaptado (liberado): "Eu não deveria te contar isso, mas {detalhe}… me conquistou." |
| 6 | Isso aqui vai mudar seu conteúdo. | bloqueado: promessa de criador |
| 7 | Você nunca viu isso antes. | adaptado (liberado): "Você provavelmente nunca reparou {detalhe}…" |
| 8 | Isso parece simples, mas… | usado |
| 9 | Descobri algo que ninguém fala. | adaptado: "que quase ninguém comenta: {detalhe}" |
| 10 | Você já percebeu isso? | adaptado: com o detalhe dentro |

### 2. Autoridade e prova social
| # | Original | Destino |
|---|---|---|
| 11 | Depois de testar por 2 anos… | bloqueado: credencial inventada |
| 12 | Aprendi isso trabalhando com X marcas. | bloqueado: credencial inventada |
| 13 | O erro que todo iniciante comete. | bloqueado: nicho de criador |
| 14 | Isso me fez ganhar + seguidores. | bloqueado: resultado inventado |
| 15 | Se eu estivesse começando hoje… | bloqueado: nicho de criador |
| 16 | Aqui está o que realmente funciona. | bloqueado: promessa de desempenho |
| 17 | O que aprendi fazendo conteúdo todos os dias. | bloqueado: nicho de criador |
| 18 | Me pediram muito pra revelar isso. | bloqueado: prova social inventada |
| 19 | Só use se quiser crescer rápido. | bloqueado: promessa |
| 20 | Aprendi isso depois de perder muito tempo. | bloqueado: história passada |

Autoridade existe, mas só com prova real declarada: ganchos de vendas e nota (`persuasion.social_hooks`), de altura e tamanho
(`size_hooks`) e de identidade do público (`identity_hooks`).

### 3. Dor e problema
| # | Original | Destino |
|---|---|---|
| 21 | Se tu tá passando por isso, presta atenção… | adaptado: "Se o seu medo é {dor}, presta atenção nesse X." |
| 22 | Isso pode estar te travando. | adaptado: "O medo de {dor} me travava, até eu olhar de perto." |
| 23 | Você tá cometendo esse erro e nem percebe. | adaptado: "Você pode estar evitando esse X por medo de {dor}." |
| 24 | Por isso teu conteúdo não cresce. | bloqueado: nicho de criador |
| 25 | Pare de fazer isso agora. | adaptado: "Não deixa o medo de {dor} te segurar" |
| 26 | Isso aqui tá matando o teu alcance. | bloqueado: nicho de criador |
| 27 | Ninguém cresce porque ignora isso. | bloqueado: nicho de criador |
| 28 | Se você se identifica com isso, assiste até o final. | adaptado |
| 29 | Não cometa o mesmo erro que eu. | bloqueado: história passada |
| 30 | Você se sabota sem perceber. | bloqueado: acusa o espectador (a ideia de passar batido entrou no 4 e no 7) |

### 4. Diretos e chamativos
| # | Original | Destino |
|---|---|---|
| 31 | Vou te mostrar exatamente o que fazer. | bloqueado: "vou te mostrar" é proibido no prompt e promete resultado |
| 32 | Faz isso e tu já melhora. | bloqueado: promessa |
| 33 | Presta atenção nessa parte. | usado: com o detalhe |
| 34 | Olha isso aqui. | usado: "Olha isso aqui: {detalhe}…" |
| 35 | Eu vou ser direto: | usado: "Eu vou ser direta: {detalhe} foi o que me fez separar…" |
| 36 | Talvez isso seja o vídeo mais importante pra você. | adaptado (liberado): "Talvez este seja o vídeo que eu queria ter visto antes de escolher…" |
| 37 | Se tu criar conteúdo, tu precisa saber disso. | bloqueado: nicho de criador |
| 38 | Aqui está o segredo. | adaptado (liberado): "Aqui está o segredo do X que eu descobri: {detalhe}." |
| 39 | Eu descobri a solução. | bloqueado: promessa de resultado |
| 40 | Para tudo e olha isso. | usado: "Para tudo e olha {detalhe}, eu quase passei batido." |

### 5. Storytelling
| # | Original | Destino |
|---|---|---|
| 41 | Eu nunca contei isso, mas… | usado: expectativa contra o que se vê agora |
| 42 | Tudo começou quando… | adaptado: "Tudo mudou quando eu vi {detalhe} de perto." |
| 43 | Eu pensei que isso não funcionava… | adaptado: "Eu pensei que esse X não ia me convencer, até ver {detalhe}." |
| 44 | O dia que tudo deu errado… | bloqueado: história passada |
| 45 | Eu aprendi da pior forma possível. | bloqueado: história passada |
| 46 | Você não vai acreditar no que aconteceu. | adaptado (liberado): "…no que {detalhe} me mostrou." |
| 47 | Se eu te contar, você não acredita. | adaptado (liberado): "Se eu te contar o que tem nesse X, você não acredita: {detalhe}." |
| 48 | Isso me deixou sem reação. | adaptado: "…me surpreendeu mais do que eu esperava." |
| 49 | Eu precisava compartilhar isso. | adaptado (liberado): "…{detalhe} me pegou de surpresa." |
| 50 | Isso mudou completamente como eu crio conteúdo. | bloqueado: nicho de criador |

## Se quiser liberar os bloqueados
Os de autoridade (11, 12, 14, 18) só seriam verdade se o operador tivesse de fato aquela experiência. Dá para criar um campo
"Credencial declarada" no briefing e liberar essas frases só quando ele estiver preenchido, como já é feito com prova social.

## Suspense e FOMO (liberado pelo estúdio em 2026-11-05)
Os ganchos de suspense e de "todo mundo passa batido" (4, 5, 7, 36, 38, 46, 47, 49) entraram como um sexto tipo. Eles abrem uma lacuna e
fecham dentro do próprio gancho. **Urgência de estoque, prazo ou preço continua só com oferta real no briefing**: isso é afirmação de
fato (a auditoria barra "últimas peças", "acaba hoje" sem oferta) e não faz parte deste tipo.
