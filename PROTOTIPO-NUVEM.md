# Protótipo de uso compartilhado e vídeo no dispositivo — CONCLUÍDO

> **Status (2026-09-13): tudo o que este documento descrevia como plano já foi implementado e está em produção.** Este arquivo fica como registro histórico do protótipo que testou as ideias antes da migração para nuvem. Para a arquitetura atual, veja `README.md` (visão geral) e `DOCUMENTACAO-PROJETO.md` (seções 4.2, 10.7 e 10.8).

Este protótipo mantinha a Fábrica TikTok local e testava as duas mudanças necessárias antes da migração para a nuvem: vídeo que fica no aparelho e acesso compartilhado por login. As duas viraram funcionalidade definitiva do app.

## Vídeo mantido no iPhone → hoje: "vídeo da galeria"

Na etapa **Criar vídeo** existem duas opções, disponíveis nas duas versões (local e nuvem):

- **Anexar vídeo MP4**: envia e arquiva o arquivo como no fluxo original.
- **Usar vídeo da galeria**: o navegador lê duração e dimensões, mas envia ao servidor somente nome, tamanho e metadados (tabela `device_videos`, rota `/api/campaigns/<id>/device-video`).

O segundo modo permite aprovar o vídeo e avançar para o TikTok sem manter uma cópia do MP4 na Fábrica. Se a página for recarregada, a aprovação continua registrada, mas é preciso selecionar novamente o arquivo para assisti-lo. O pacote ZIP inclui um aviso com o nome do vídeo que ficou no dispositivo.

## Dois acessos → hoje: login com conta principal e editora

O protótipo testava `iniciar-prototipo-compartilhado.bat` com um cadastro limitado a dois acessos. Isso virou o sistema de contas definitivo da versão em nuvem (tabela `users`, rotas `/api/auth/*` e `/api/users`):

1. No primeiro acesso, cria-se a conta principal (**owner**) com uma senha de pelo menos oito caracteres.
2. Pelo ícone **Acessos do estúdio** no cabeçalho, a owner cria a segunda conta (**editor**) e pode redefinir a senha dela.
3. As duas contas enxergam o mesmo estúdio e as mesmas campanhas.

As senhas são armazenadas como hashes; o texto original da senha não é salvo. Diferente do protótipo, o login hoje só existe (e só é exigido) na versão em nuvem — a versão local continua sem login, usando PIN apenas para acesso pela rede Wi-Fi.

## O que foi feito para publicar na Vercel

Tudo que este protótipo listava como pendência foi resolvido:

- SQLite substituído por Postgres (Supabase) quando `FABRICA_CLOUD=1`, mantendo SQLite como padrão local.
- Referências, imagens e vídeos passaram a ir para o Supabase Storage, com upload direto do navegador (link assinado).
- `FABRICA_CLOUD=1` e `FABRICA_SECRET_KEY` configurados no deploy.
- As rotas que controlam o perfil Chrome do Windows (Playwright/CDP) foram desligadas por completo no modo nuvem.
- Domínio, HTTPS e segredos configurados no provedor (Vercel) — o app está no ar no domínio padrão; um domínio próprio segue como possível próximo passo.

Detalhes completos da migração estão em `DOCUMENTACAO-PROJETO.md`, seção 10.7.
