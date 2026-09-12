# Protótipo de uso compartilhado e vídeo no dispositivo

Este protótipo mantém a Fábrica TikTok atual e testa as duas mudanças necessárias antes da migração para a nuvem.

## Vídeo mantido no iPhone

Na etapa **Criar vídeo**, existem duas opções:

- **Anexar vídeo MP4**: envia e arquiva o arquivo como no fluxo original.
- **Usar vídeo da galeria**: o navegador lê duração e dimensões, mas envia ao servidor somente nome, tamanho e metadados.

O segundo modo permite aprovar o vídeo e avançar para o TikTok sem manter uma cópia do MP4 na Fábrica. Se a página for recarregada, a aprovação continua registrada, mas será necessário selecionar novamente o arquivo para assisti-lo. O pacote ZIP inclui um aviso com o nome do vídeo que ficou no dispositivo.

## Dois acessos

Execute `iniciar-prototipo-compartilhado.bat`. No primeiro acesso:

1. Crie o usuário principal com uma senha de pelo menos oito caracteres.
2. Clique no nome do usuário no cabeçalho.
3. Crie o segundo acesso.

Os dois usuários enxergam o mesmo estúdio e as mesmas campanhas. O protótipo limita o cadastro a dois acessos. As senhas são armazenadas como hashes; o texto original da senha não é salvo.

Para voltar ao modo local sem login, execute `reiniciar-fabrica.bat`.

## O que falta para publicar na Vercel

A interface e o fluxo estão preparados, mas esta versão ainda usa SQLite e pastas locais. Antes do deploy público será necessário:

- substituir SQLite por PostgreSQL;
- enviar referências e imagens para armazenamento de objetos;
- configurar `FABRICA_CLOUD=1` e `FABRICA_SECRET_KEY`;
- desligar ou separar as rotas que controlam o perfil Chrome do Windows;
- configurar domínio, HTTPS e segredos no provedor.

O vídeo no dispositivo já evita a migração dos arquivos mais pesados. Apenas campanhas, textos, metadados, referências e imagens aprovadas precisam permanecer na nuvem.
