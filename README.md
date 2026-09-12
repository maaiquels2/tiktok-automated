# Fábrica TikTok — versão local

App **local** (Windows) da fábrica TikTok para o perfil da **Micaela**: produção de shorts/UGC para TikTok Shop com interface em **React + Vite** (navegação Início / Produzir / Resultados), API **Flask**, **SQLite** e mídia no disco. Organiza campanhas com modelo fixa, produto, **várias cores**, prompts, roteiros de 15s, imagens, vídeos, legendas inteligentes e publicação **manual** no TikTok Studio (uma cor por vez).

Repositório: [maaiquels2/tiktok-automated](https://github.com/maaiquels2/tiktok-automated)

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
- Renomeie o rótulo de cada foto para achar rápido depois.
- **Ficha de consistência de personagem**: gera um prompt mestre (com lista de negativos contra troca de rosto, CGI e mãos malformadas) e abre o Grok já pronto para criar a ficha de referência da modelo.

### Roteiros 15s inteligentes
- Produto único também tem **Atualizar hook + legenda** e **Atualizar fala inteira**. Salve edições manuais antes de regenerar. A imagem aprovada é preservada; novas falas exigem revisão do roteiro e um novo vídeo.
- O hook usa uma abertura completa com janela sugerida de 4s. Confira o tempo total com leitura em voz alta.
- Hook (0–4s), desenvolvimento (4–12s) e CTA (12–15s) **variam por cor**.
- Botões **Atualizar hook + legenda** e **Atualizar fala inteira** para gerar outra variação sem recomeçar a campanha.
- Edição manual por campo, com prompt de vídeo recalculado a partir das falas.

### Vídeos
- **Um MP4 por cor**, espelhando o fluxo das imagens.
- Botão único **Abrir Grok/Flow para vídeo** no topo (sem repetir em cada cor).
- Aprovação em lote: 15s e resolução alvo (1080×1920 Flow ou 720×1280 Grok).


### Misturar videos
- Na etapa **Criar video**, bloco **Misturar videos**.
- Escolha 2+ MP4s da campanha, ordene, defina segundos por clip (ou deixe vazio para dividir ~15s).
- Salva no slot de uma **cor** ou em **Mix** (requer FFmpeg no PATH / instalado).
- O MP4 gerado precisa ser revisado de novo na aprovacao (~15s, 9:16).
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
- O app **não** publica sozinho no TikTok (sem automação de post/tag).


### Performance, Insights e preview 9:16
- No **Studio** (status pronto/publicado): painel **Performance & Insights** por cor — informe views, watch%, likes, saves, pedidos etc. e salve em `checklist.performance`.
- **Gerar insights** roda um crítico local (`services/insights.py`) e grava `checklist.insights` (Hook / Desenvolvimento / CTA + ações). Sem dados inventados do TikTok.
- **Preview 9:16** na aprovação de vídeo: telefone, scrubber e beats Hook (0–4s) · Desenvolvimento (4–12s) · CTA (12–15s) com overlay do roteiro.
- **Analisar vídeo (Critico)** usa a mesma API local e mostra o caminho do MP4 para revisão visual profunda com o agente Critico de Vendas (não dispara SendToAgent pelo Flask).

### Renomear campanha
- Controle **Renomear** (lápis) perto do título da campanha.
- PATCH só de `name` — não invalida etapas nem dispara guards de busy/discard de forma agressiva.

### Navegação e campanhas
- Três áreas: **Início** (checklist de setup, fila de 5 posts do dia, biblioteca de fotos), **Produzir** (stepper das etapas) e **Resultados** (Studio, lote, playbook, histórico, campanha).
- Endereços internos: `#/inicio`, `#/produzir/<id>/<etapa>`, `#/resultados/<aba>` — dá para salvar o link de uma etapa específica.
- Pipeline: modelo → look → imagem → aprovação → roteiro → vídeo → aprovação → Studio → performance.
- Campanhas com **renomear**, editar, copiar e excluir; versão editável a partir de campanha publicada.
- Reuso da referência da mesma modelo entre campanhas.
- Até 8 fotos de produto por campanha; movimentos do produto no prompt de vídeo.
- Exportação TXT/ZIP do pacote (só mídias aprovadas no ZIP).

### Local-first e privacidade
- Tudo fica no PC: banco, mídia, perfis de navegador.
- Rascunhos de texto são **determinísticos e locais** (sem API paga de LLM para gerar prompts).
- Geração de imagem/vídeo é **manual** no Flow ou Grok Imagine (sua assinatura).
- `.gitignore` exclui `data/`, `media/`, `browser_profiles/`, `.venv/`, etc.

## Stack

| Camada | Tecnologia |
|---|---|
| UI | React + Vite (stepper de etapas, navegação por hash) |
| API | Flask (Python) |
| Banco | SQLite (`data/fabrica_tiktok.db`) |
| Mídia | Pasta `media/campanha-XXXX/` |
| Navegador | Chrome/Edge + Playwright (Flow/Studio); Grok em processo normal |

## Abrir no Windows

Dois cliques em **`iniciar.vbs`**: sobe o servidor e abre `http://127.0.0.1:5050`. Se a porta estiver ocupada, tenta `5051`–`5059`.

Pelo terminal:

```powershell
cd C:\Users\Admin\Documents\Codex\2026-09-10\Fabrica TikTok
.\.venv\Scripts\python.exe app.py
```

Fechar a aba do navegador **não** encerra o servidor. No terminal, use Ctrl+C. Com o iniciador, finalize o Python no Gerenciador de Tarefas se precisar.

### Se o servidor travar

Duplo clique em **`reiniciar-fabrica.bat`**: encerra o processo do app naquela pasta e sobe de novo.

### Usar pelo celular (mesmo Wi-Fi)

O iniciador imprime o endereço de LAN (algo como `http://192.168.0.10:5050`). Abra esse endereço no celular conectado à mesma rede. A interface se adapta à tela, e os botões de Grok / Flow / TikTok viram links nativos, abrindo o app instalado em vez do perfil de Chrome do PC.

Isso **não** é hospedagem na nuvem: o servidor continua sendo o seu PC, que precisa estar ligado. Para restringir o acesso a `127.0.0.1`, defina `FABRICA_LAN=0`.

### Instalação em outro computador

Requer **Python 3.11+**, **Node.js** compatível com Vite 7 (20.19+ ou 22.12+) e **Chrome ou Edge**. Na pasta do projeto:

```powershell
.\instalar.ps1
```

Instala dependências e compila a interface. Rascunhos de texto funcionam offline; Flow/Grok/Studio precisam de internet e login.

## Pipeline

**referência → personagem → roteiro → imagem (por cor) → vídeo (por cor) → Studio/publicação**

## Fluxo de uso (resumo)

1. **Nova campanha** — briefing + Flow (1080p) ou Grok (720p).
2. **Modelo fixa** — anexe a referência (ou reutilize de outra campanha).
3. **Definir look** — produto, cores (vírgulas), movimentos, fotos do produto → **Gerar prompts e roteiro**.
4. **Criar imagem** — uma geração/anexo por cor.
5. **Aprovar imagens** — todas as cores.
6. **Roteiro** — revise falas; use refresh se não gostar.
7. **Criar vídeo** — um MP4 de 15s por cor (Grok/Flow no topo).
8. **Aprovar vídeos** — lote com checagem de duração/resolução.
9. **Preparar publicação** — fila por cor: legenda (≤5 hashtags) + MP4 + Studio + registrar.
10. **Editar / copiar / excluir** campanhas na fila lateral.

Identidade da modelo é guiada por prompt + revisão humana (sem reconhecimento facial automático).

## Variáveis e privacidade

Copie `.env.example` para `.env` se existir no projeto. Chaves típicas (nunca commitar `.env`):

- Credenciais/tokens só em `.env` local
- Opcionais: `FABRICA_MICAELA_PROFILE`, `FABRICA_CHROME_USER_DATA`

`.gitignore` deve cobrir: `data/`, `media/`, `.venv/`, `browser_profiles/`, `.env`, secrets e caches.

## Persistência e arquivos

- Estado: `data/fabrica_tiktok.db` (com backups em `data/backups/`).
- Mídia por campanha:

```text
media/campanha-0001/
  reference-*.jpg
  image-*.png          # uma (ou mais) por cor (slot)
  video-*.mp4          # uma por cor (slot)
  downloads/
```

- Alterar briefing/referência invalida etapas seguintes conforme regras do app.
- Uploads: imagens até 40 MB / 40 MP; MP4 até 250 MB.
- Controle de versão evita sobrescrita silenciosa entre janelas.
- Por padrão o servidor prioriza uso local; mutações de outras origens são bloqueadas.

## Perfis de navegador

| Perfil | Uso |
|---|---|
| `browser_profiles/flow-maaiquels` | Google Flow e Grok (`maaiquels@gmail.com`) |
| `browser_profiles/tiktok-micaela` | TikTok Studio (conta da Micaela) |

- Confirmação antes de abrir serviços externos.
- Grok abre em Chrome/Edge comum (sem Playwright). Feche o Flow desse perfil antes do Grok e vice-versa.
- O app **não** clica em gerar, **não** escolhe produto no Shop e **não** publica.
- Variáveis opcionais: `FABRICA_MICAELA_PROFILE`, `FABRICA_CHROME_USER_DATA`.

## Desenvolvimento

```powershell
# API
.\.venv\Scripts\python.exe app.py

# UI com hot reload
cd frontend
npm run dev

# Build servido pelo Flask
npm run build

# Testes
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Rotas úteis: `/` e `/creator` (nova campanha). A documentação completa do projeto — propósito, escopo, arquivo por arquivo, banco de dados, as 60 rotas da API e o histórico de mudanças — está em [`DOCUMENTACAO-PROJETO.md`](DOCUMENTACAO-PROJETO.md).

## O que este projeto deliberadamente NÃO faz

- Não chama API paga de imagem/vídeo sozinho (usa Flow/Grok da sua assinatura, manualmente).
- Não automatiza publicação, tag de produto ou login no TikTok.
- Não é um deploy Vercel “serverless”: depende de disco local, SQLite e Chrome no Windows.
- Para usar no celular na mesma Wi‑Fi, acesse `http://IP-DO-PC:5050` com o servidor liberado na rede (não confundir com hospedar no Vercel).

## Empacotamento futuro

EXE (PyInstaller), Tauri/Electron e montagem automática de vídeo ficam para depois. O iniciador Windows já isola dados locais.

## Referências

- [React Flow](https://reactflow.dev/learn)
- [Vite](https://vite.dev/guide/)
- [Playwright persistent context](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context)
