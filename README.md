# Fábrica TikTok

App da fábrica TikTok para o perfil da **Micaela**: produção de shorts/UGC para TikTok Shop com interface em **React + Vite** (navegação Início / Produzir / Resultados), API **Flask**. Organiza campanhas com modelo fixa, produto, **várias cores**, prompts, roteiros de 15s, imagens, vídeos, legendas inteligentes e publicação **manual** no TikTok Studio (uma cor por vez).

Repositório: [maaiquels2/tiktok-automated](https://github.com/maaiquels2/tiktok-automated)

## Duas formas de rodar o mesmo app

O código é um só (`app.py` + `frontend/`), mas ele roda de duas formas diferentes, e **as duas continuam existindo ao mesmo tempo**:

| | **Local (Windows)** | **Nuvem** |
|---|---|---|
| Onde fica | No seu PC, ligado | `https://tiktok-automated.vercel.app` (Vercel) |
| Banco de dados | SQLite (`data/fabrica_tiktok.db`) | Postgres (Supabase) |
| Mídia (fotos/vídeos) | Pasta `media/` no disco | Supabase Storage |
| Acesso | `http://127.0.0.1:5050`, ou pelo IP do PC na mesma Wi‑Fi | Qualquer navegador, celular ou computador, de qualquer lugar |
| Login | Nenhum por padrão (é só você no seu PC) | Login com usuário e senha — **até 2 contas**, mesmo estúdio |
| Abrir Grok/Flow/TikTok Studio | Perfil dedicado do Chrome, controlado pelo app (Playwright) | Link direto — abre o app instalado no celular ou uma aba nova no navegador |
| Misturar vídeos (FFmpeg) | ✅ Disponível | ❌ Não disponível (precisa de FFmpeg local) |
| Auto-cut / Critico de Vendas | ✅ Disponível | ❌ Não disponível (avisa um robô que roda no PC) |
| Coleta automática de métricas do Studio (Playwright/CDP) | ✅ Disponível | ❌ Não disponível — preencha o painel de Performance manualmente |

Em resumo: **a nuvem é a forma do dia a dia**, pra você e a Micaela acessarem do celular sem precisar ligar o PC nem instalar nada. **O local continua existindo** pra quando o computador está ligado mesmo assim e você quer usar o mixer de vídeo, o auto-cut ou a coleta automática de métricas — coisas que dependem de programas instalados no Windows (FFmpeg, Chrome com Playwright) e não fazem sentido rodando num servidor.

Escrita de prompts/roteiro/legenda, biblioteca de modelo, análise de foto por IA, publicação em fila por cor e tudo o mais descrito abaixo funciona **igual nos dois modos**.

## O que o projeto entrega

### Produção multi-cor
- Informe várias cores no briefing (`Branco, Preto, Azul Marinho…`).
- **Gerar prompts e roteiro** cria automaticamente **um pacote por cor** (imagem, vídeo, falas e legenda).
- A IA **nunca** recebe todas as cores no mesmo prompt de imagem.

### Imagens
- Etapa **Criar imagem** com cartão por cor: prompt + anexar resultado.
- Várias imagens ativas na mesma campanha (slot por cor).
- **Aprovar todas as imagens** só libera quando cada cor tem arquivo.

### Modelo fixa e consistência de identidade
- **Biblioteca da modelo** por nicho (praia, academia, casual, dia a dia, íntima, fantasia): suba as fotos padrão uma vez e reutilize em qualquer campanha.
- Suporta **mais de uma modelo** na biblioteca (não só a Micaela) — escolha qual conjunto de fotos usar por campanha.
- Renomeie o rótulo de cada foto para achar rápido depois, ou exclua a foto de um nicho.
- **Ficha de consistência de personagem**: gera um prompt mestre (com lista de negativos contra troca de rosto, CGI e mãos malformadas) e abre o Grok já pronto para criar a ficha de referência da modelo.

### Análise de foto por IA (opcional)
- Ao criar ou editar o briefing, anexe a **foto de descrição do produto** (aquela print com as características, tamanho, tecido etc.).
- Se a Escrita por IA estiver configurada (ver abaixo), o app manda a foto pra um modelo com visão (`gpt-4o-mini` ou `gemini-2.0-flash` — os mesmos padrões da escrita de texto, sem precisar de chave nova) e preenche sozinho benefício, ângulo, movimentos e detalhes.
- **A foto manda mais que o modelo padrão do nicho**: o que a IA encontrar na foto substitui o texto genérico do nicho; o texto do nicho só continua valendo pros campos que a foto não esclareceu.
- Sem IA configurada, ou se a análise não encontrar nada de útil, os campos ficam com o padrão do nicho escolhido, como sempre foi.

### Argumento de venda (objeção e oferta)
- Dois campos opcionais no briefing mudam bastante o roteiro:
  - **O que mais segura a compra?** — com ele preenchido, o hook passa a falar da dor do cliente e o meio do roteiro vira a prova que derruba a dúvida.
  - **Oferta real** — só preencha se for verdade. É o único caso em que o roteiro usa urgência; prazo ou estoque inventado é propaganda enganosa.
- Sem esses campos, o gerador usa o motor de **desejo**, que não afirma nada além do que está no briefing.

### Roteiros 15s inteligentes
- Produto único também tem **Atualizar hook + legenda** e **Atualizar fala inteira**. Salve edições manuais antes de regenerar. A imagem aprovada é preservada; novas falas exigem revisão do roteiro e um novo vídeo.
- O hook usa uma abertura completa com janela sugerida de 4s. Confira o tempo total com leitura em voz alta.
- Hook (0–4s), desenvolvimento (4–12s) e CTA (12–15s) **variam por cor**.
- **Orçamento de fala por trecho**, com contador colorido no editor: hook 10–12 palavras, desenvolvimento 20–24, CTA 7–9, total de 38 a 45 (português falado rende ~2,8 palavras por segundo).
- O desenvolvimento segue três batidas: prova → objeção quebrada → posse. Se o roteiro estoura o tempo, a posse cai primeiro — a prova nunca é descartada.
- Botões **Atualizar hook + legenda** e **Atualizar fala inteira** para gerar outra variação sem recomeçar a campanha.
- Edição manual por campo, com prompt de vídeo recalculado a partir das falas.

### Vídeos
- **Um MP4 por cor**, espelhando o fluxo das imagens.
- Botão único **Abrir Grok/Flow para vídeo** no topo (sem repetir em cada cor).
- Aprovação em lote: 15s e resolução alvo (1080×1920 Flow ou 720×1280 Grok).

### Misturar vídeos (só na versão local)
- Na etapa **Criar vídeo**, bloco **Misturar vídeos**.
- Escolha 2+ MP4s da campanha, ordene, defina segundos por clip (ou deixe vazio para dividir ~15s).
- Salva no slot de uma **cor** ou em **Mix** (requer FFmpeg no PATH / instalado).
- O MP4 gerado precisa ser revisado de novo na aprovação (~15s, 9:16).
- Na nuvem esse bloco não aparece — depende de FFmpeg instalado no computador que roda o servidor.

### Legendas e hashtags para o TikTok
- Legendas alinhadas a produto, benefício, público e cor.
- Até **5 hashtags** por legenda, escolhidas pelo nicho (ex.: fitness, legging, TikTok Shop).
- Botão **Nova legenda** na publicação para refresh rápido.

### Publicação no Studio (fila por cor)
- Abas user-friendly por cor/produto.
- Escolha qual cor subir agora → copie legenda e caminho do MP4 → abra o Studio → registre.
- Passe para a próxima cor; a campanha só fecha como **publicada** quando todas as cores forem registradas.
- Legendas com no máximo **5 hashtags** (nicho + produto + cor).
- **Ver publicação** abre os links do TikTok (`published_url` / slots da checklist) quando a cor ou a campanha já foi registrada.
- O app **não** publica sozinho no TikTok (sem automação de post/tag), em nenhum dos dois modos.

### Performance, Insights e preview 9:16
- No **Studio** (status pronto/publicado): painel **Performance & Insights** por cor — informe views, watch%, likes, saves, pedidos etc. e salve em `checklist.performance`.
- Na versão local, o app pode coletar boa parte desses números sozinho, direto do TikTok Studio (Playwright/Chrome CDP). Na nuvem, esse preenchimento é manual.
- **Gerar insights** roda um crítico local (`services/insights.py`) e grava `checklist.insights` (Hook / Desenvolvimento / CTA + ações). Sem dados inventados do TikTok.
- **Preview 9:16** na aprovação de vídeo: telefone, scrubber e beats Hook (0–4s) · Desenvolvimento (4–12s) · CTA (12–15s) com overlay do roteiro.

### Renomear campanha
- Controle **Renomear** (lápis) perto do título da campanha.
- PATCH só de `name` — não invalida etapas nem dispara guards de busy/discard de forma agressiva.

### Navegação e campanhas
- Três áreas: **Início** (biblioteca de fotos, atalhos de serviço, lista de campanhas), **Produzir** (stepper das etapas) e **Resultados** (Studio, lote, playbook, histórico, campanha).
- Endereços internos: `#/inicio`, `#/produzir/<id>/<etapa>`, `#/resultados/<aba>` — dá para salvar o link de uma etapa específica.
- Pipeline: modelo → look → imagem → aprovação → roteiro → vídeo → aprovação → Studio → performance.
- Campanhas com **renomear**, editar, copiar e excluir; versão editável a partir de campanha publicada.
- Reuso da referência da mesma modelo entre campanhas.
- Até 8 fotos de produto por campanha; movimentos do produto no prompt de vídeo.
- Exportação TXT/ZIP do pacote (só mídias aprovadas no ZIP) — na versão local.
- Interface ajustada pra celular: menos texto, atalhos de serviço em grade 2×2, fotos da modelo lado a lado, formulários em coluna única.

### Privacidade
- Rascunhos de texto são **determinísticos e locais** (sem API paga de LLM para gerar prompts, a menos que você ligue a Escrita por IA).
- Geração de imagem/vídeo é **manual** no Flow ou Grok Imagine (sua assinatura).
- Na versão local, tudo fica no PC: banco, mídia, perfis de navegador. `.gitignore` exclui `data/`, `media/`, `browser_profiles/`, `.venv/`, etc.
- Na nuvem, banco e mídia ficam no Supabase da conta do projeto; o acesso exige login.

## Stack

| Camada | Tecnologia |
|---|---|
| UI | React + Vite (stepper de etapas, navegação por hash, tema claro/escuro, layout mobile) |
| API | Flask (Python) — mesmo `app.py` nos dois modos |
| Banco | SQLite local (`data/fabrica_tiktok.db`) **ou** Postgres via Supabase na nuvem |
| Mídia | Pasta `media/campanha-XXXX/` local **ou** Supabase Storage na nuvem |
| Navegador (só local) | Chrome/Edge + Playwright (Flow/Studio); Grok em processo normal |
| Deploy da nuvem | Vercel (`vercel.json` + `wsgi.py`), build do frontend embutido no build do Vercel |

## Nuvem — usar pelo navegador ou celular

Acesse **`https://tiktok-automated.vercel.app`** em qualquer navegador (celular ou computador). No primeiro acesso, crie a conta principal (usuário + senha); pelo ícone de **Acessos do estúdio** no cabeçalho, o responsável cria a segunda conta e pode redefinir a senha dela depois. As duas contas enxergam **o mesmo estúdio e as mesmas campanhas**.

No celular, os botões de Grok/Flow/TikTok Studio/TikTok abrem como links diretos — o próprio sistema entrega para o aplicativo instalado quando existe associação, ou abre no navegador do celular. Fotos e vídeos anexados sobem direto para o Supabase Storage.

### Variáveis de ambiente da nuvem (configuradas no projeto Vercel)

| Variável | Para quê |
|---|---|
| `FABRICA_CLOUD=1` | Liga o modo nuvem (Postgres + Storage + login obrigatório) |
| `FABRICA_DATABASE_URL` | String de conexão do Postgres (Supabase) |
| `FABRICA_SECRET_KEY` | Chave de sessão do Flask (login) |
| `FABRICA_SUPABASE_URL` | URL do projeto Supabase |
| `FABRICA_SUPABASE_SERVICE_KEY` | Chave de serviço do Supabase (Storage) |
| `FABRICA_SUPABASE_ANON_KEY` | Chave anônima, exigida pelo cabeçalho `Authorization` do Storage |
| `FABRICA_STORAGE_BUCKET` | Nome do bucket de mídia no Supabase Storage |

### Fazer um novo deploy

Depois de uma sessão de mudanças, o fluxo é: revisar o que foi commitado localmente (`git log`, `git status`), `git push origin main`, e então redeployar no painel do Vercel (ou deixar o deploy automático do Vercel disparar pelo push, se estiver configurado assim). O build do Vercel roda `cd frontend && npm ci && npm run build` (ver `vercel.json`) antes de subir o `wsgi.py`.

## Abrir no Windows (versão local)

Dois cliques em **`iniciar.vbs`**: sobe o servidor e abre `http://127.0.0.1:5050`. Se a porta estiver ocupada, tenta `5051`–`5059`.

Pelo terminal:

```powershell
cd C:\Users\Admin\Documents\Codex\2026-09-10\Fabrica TikTok
.\.venv\Scripts\python.exe app.py
```

Fechar a aba do navegador **não** encerra o servidor. No terminal, use Ctrl+C. Com o iniciador, finalize o Python no Gerenciador de Tarefas se precisar.

### Se o servidor travar

Duplo clique em **`reiniciar-fabrica.bat`**: encerra o processo do app naquela pasta e sobe de novo.

### Usar pelo celular (mesma Wi‑Fi, sem ser a versão nuvem)

O iniciador imprime o endereço de LAN (algo como `http://192.168.0.10:5050`). Abra esse endereço no celular conectado à mesma rede. A interface se adapta à tela, e os botões de Grok / Flow / TikTok viram links nativos, abrindo o app instalado em vez do perfil de Chrome do PC.

Isso **não** é a versão nuvem: o servidor continua sendo o seu PC, que precisa estar ligado. Para restringir o acesso a `127.0.0.1`, defina `FABRICA_LAN=0`.

### Quem escreve as falas — três coisas diferentes

É fácil confundir, então vale separar:

| Onde | O que é | Quando age |
|---|---|---|
| **Gerador local** (`services/prompts.py`) | Regras em Python. Monta hook, desenvolvimento, CTA e legenda a partir dos campos do briefing. Não usa internet nem API. | Sempre que a escrita por IA está desligada, falha ou é reprovada. |
| **Escrita por IA** (`services/copywriter.py`) | O app chama a API da OpenAI ou do Gemini com a sua chave, recebe o texto e audita antes de aceitar. Também usada pra analisar a foto de descrição do produto (mesma chave, se o modelo tiver visão). | Só quando você liga em Identidade → Escrita das falas. É o app que faz a chamada, sozinho, a cada geração. |
| **Skill `roteiro-ugc-15s`** | Um documento de método. Vive no Claude, **não** dentro do app. | Quando você pede roteiro ao Claude numa conversa. O app não lê esse arquivo. |

As regras da skill foram traduzidas para a instrução que o app manda ao modelo, mas são **duas cópias**: mudar a skill não muda o app, e vice-versa. Se você evoluir a skill e quiser que o app acompanhe, peça a sincronização.

**Como saber qual dos dois escreveu:** a etapa *Roteiro de 15s* mostra um selo no topo — "Escrito por IA · OpenAI" ou "Texto local (sem IA)". Quando a IA é recusada pela auditoria ou pelo provedor, o selo mostra o motivo.

### Escrita das falas por IA (opcional, funciona nos dois modos)

O gerador local é correto e nunca inventa atributo, mas monta a frase a partir do rótulo do briefing — por isso sai coisa como *"Repara no tecido sem transparência"*. Quem escreve bem é um modelo de linguagem; quem garante a honestidade é o código.

Por isso os dois trabalham juntos:

1. O app monta o briefing estruturado (fatos confirmados, objeção, oferta, motor, orçamento de palavras).
2. O modelo escreve hook, desenvolvimento, CTA e legenda.
3. O app **audita** o resultado: palavras por trecho, nenhum atributo de desempenho fora do briefing, urgência só com oferta real, no máximo 5 hashtags.
4. Reprovado? Volta para o modelo com os erros apontados, uma vez. Reprovado de novo? Usa o texto local.

Configure no ícone de **Identidade** no cabeçalho: escolha OpenAI ou Gemini, cole a chave e ligue. O botão **Testar conexão** gera um exemplo na hora.

Na versão local, a chave fica em **`data/llm.json`**, só neste computador — fora do Git. Na nuvem, a mesma configuração fica salva no Postgres do projeto (visível pras duas contas do estúdio). Em ambos os casos a API do app nunca devolve a chave inteira — só os últimos quatro caracteres.

### Backup automático (versão local)

A cada inicialização o app copia o banco para `data/backups/fabrica-AAAA-MM-DD.db` e mantém os últimos 10 dias. `data/` fica fora do Git de propósito, então essa cópia é a única proteção contra perder campanhas, playbook e histórico. Na nuvem, o backup é responsabilidade do próprio Supabase (backups do Postgres gerenciado).

### PIN para acesso pela rede (versão local)

Quando você abre a Fábrica local pelo celular (mesma Wi‑Fi), o app pede um **PIN de 4 dígitos**. Ele aparece no cabeçalho (só neste computador), é impresso pelo iniciador e fica guardado em `data/lan_pin.txt`. Sem isso, qualquer pessoa na mesma Wi‑Fi que chegasse à porta 5050 poderia editar ou excluir campanhas. Acesso pelo próprio computador (`127.0.0.1`) nunca pede PIN. Na nuvem, quem protege o acesso é o login (usuário + senha), não o PIN.

### Instalação em outro computador (rodar a versão local em outro PC)

Requer **Python 3.11+**, **Node.js** compatível com Vite 7 (20.19+ ou 22.12+) e **Chrome ou Edge**. Na pasta do projeto:

```powershell
.\instalar.ps1
```

Instala dependências e compila a interface. Rascunhos de texto funcionam offline; Flow/Grok/Studio precisam de internet e login. Veja também [`COMO-INSTALAR-NO-OUTRO-PC.md`](COMO-INSTALAR-NO-OUTRO-PC.md) — hoje, pra um segundo acesso simples sem instalar nada num segundo PC, considere a **versão nuvem** com uma segunda conta em vez de clonar o app localmente.

## Pipeline

**referência → personagem → roteiro → imagem (por cor) → vídeo (por cor) → Studio/publicação**

## Fluxo de uso (resumo)

1. **Nova campanha** — briefing + Flow (1080p) ou Grok (720p).
2. **Modelo fixa** — anexe a referência (ou reutilize de outra campanha).
3. **Definir look** — produto, cores (vírgulas), movimentos, fotos do produto (e, se quiser, a foto de descrição pra IA sugerir os campos) → **Gerar prompts e roteiro**.
4. **Criar imagem** — uma geração/anexo por cor.
5. **Aprovar imagens** — todas as cores.
6. **Roteiro** — revise falas; use refresh se não gostar.
7. **Criar vídeo** — um MP4 de 15s por cor (Grok/Flow no topo).
8. **Aprovar vídeos** — lote com checagem de duração/resolução.
9. **Preparar publicação** — fila por cor: legenda (≤5 hashtags) + MP4 + Studio + registrar.
10. **Editar / copiar / excluir** campanhas na fila lateral.

Identidade da modelo é guiada por prompt + revisão humana (sem reconhecimento facial automático).

## Variáveis e privacidade

Copie `.env.example` para `.env` se existir no projeto, para rodar local. Chaves típicas (nunca commitar `.env`):

- Credenciais/tokens só em `.env` local
- Opcionais: `FABRICA_MICAELA_PROFILE`, `FABRICA_CHROME_USER_DATA`
- Nuvem: ver a tabela de variáveis do Vercel, acima

`.gitignore` deve cobrir: `data/`, `media/`, `.venv/`, `browser_profiles/`, `.env`, secrets e caches.

## Persistência e arquivos

**Local:**
- Estado: `data/fabrica_tiktok.db` (com backups em `data/backups/`).
- Mídia por campanha:

```text
media/campanha-0001/
  reference-*.jpg
  image-*.png          # uma (ou mais) por cor (slot)
  video-*.mp4          # uma por cor (slot)
  downloads/
```

**Nuvem:** o mesmo formato de dados vive nas tabelas do Postgres (Supabase) e a mídia fica em objetos no Supabase Storage, servidos por link assinado ou por cache de longa duração quando a URL já indica a versão do arquivo.

Em ambos os modos:
- Alterar briefing/referência invalida etapas seguintes conforme regras do app.
- Uploads: imagens até 40 MB / 40 MP; MP4 até 250 MB.
- Controle de versão evita sobrescrita silenciosa entre janelas.

## Perfis de navegador (versão local)

| Perfil | Uso |
|---|---|
| `browser_profiles/flow-maaiquels` | Google Flow e Grok (`maaiquels@gmail.com`) |
| `browser_profiles/tiktok-micaela` | TikTok Studio (conta da Micaela) |

- Confirmação antes de abrir serviços externos.
- Grok abre em Chrome/Edge comum (sem Playwright). Feche o Flow desse perfil antes do Grok e vice-versa.
- O app **não** clica em gerar, **não** escolhe produto no Shop e **não** publica.
- Variáveis opcionais: `FABRICA_MICAELA_PROFILE`, `FABRICA_CHROME_USER_DATA`.
- Na nuvem não existe perfil de navegador: os botões abrem link direto (ver `frontend/src/serviceLinks.jsx`).

## Desenvolvimento

```powershell
# API (local, SQLite)
.\.venv\Scripts\python.exe app.py

# API simulando modo nuvem (Postgres precisa estar acessível)
$env:FABRICA_CLOUD=1; .\.venv\Scripts\python.exe app.py

# UI com hot reload
cd frontend
npm run dev

# Build servido pelo Flask (local) ou pelo Vercel (nuvem)
npm run build

# Testes
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Rotas úteis: `/` e `/creator` (nova campanha). A documentação completa do projeto — propósito, escopo, arquivo por arquivo, banco de dados, arquitetura da nuvem, as rotas da API e o histórico de mudanças — está em [`DOCUMENTACAO-PROJETO.md`](DOCUMENTACAO-PROJETO.md).

## O que este projeto deliberadamente NÃO faz

- Não chama API paga de imagem/vídeo sozinho (usa Flow/Grok da sua assinatura, manualmente).
- Não automatiza publicação, tag de produto ou login no TikTok, em nenhum dos dois modos.
- Não faz montagem criativa completa de vídeo por IA — o mixer local apenas corta, normaliza e reúne clipes escolhidos pelo operador, e nem está disponível na nuvem.
- Na nuvem, não abre nem controla um Chrome de verdade (sem Playwright/CDP no servidor) — por isso o mixer de vídeo, o auto-cut e a coleta automática de métricas do Studio ficam restritos à versão local.

## Empacotamento futuro

EXE (PyInstaller), Tauri/Electron e montagem automática de vídeo ficam para depois. O iniciador Windows já isola dados locais.

## Referências

- [Vite](https://vite.dev/guide/)
- [Playwright persistent context](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context)
- [Documentação do Supabase](https://supabase.com/docs)
- [Documentação do Vercel](https://vercel.com/docs)
