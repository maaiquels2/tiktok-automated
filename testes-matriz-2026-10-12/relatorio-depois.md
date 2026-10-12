# Matriz de cenários — produtos que não são roupa

Gerado sem API: o mesmo gerador do site (`generate`), com a auditoria de honestidade do app.

- Combinações: **462** (14 produtos × 11 bases/formatos × 3 estilos)
- Geraram pacote sem erro: **462**
- Cabem no limite do Grok (3940): **462**
- Aprovadas pela auditoria de honestidade: **426**

## Vocabulário de roupa em produto que não é roupa

Cada célula: combinações com pelo menos uma palavra inequívoca de roupa (caimento, veste, blusinha, barra, agachar, provador, cintura, jaqueta, girar...) naquele campo. "No corpo" e "tecido" ficam de fora por serem ambíguos. Na roupa de controle essas palavras estão certas.

| Grupo | Combinações | Na fala | Na tela | No prompt do vídeo | No prompt da imagem |
|---|---|---|---|---|---|
| Beleza | 198 | 0 (0%) | 0 (0%) | 126 (63%) | 126 (63%) |
| Acessórios | 198 | 0 (0%) | 0 (0%) | 126 (63%) | 126 (63%) |
| Roupa (controle) | 66 | 66 (100%) | 27 (40%) | 66 (100%) | 66 (100%) |

## Por base/formato (beleza + acessórios)

| Base / formato | Combinações | Com palavra de roupa na fala | No prompt do vídeo | Palavras mais frequentes (vídeo) |
|---|---|---|---|---|
| com fala | 36 | 0 | 0 | - |
| espelho | 36 | 0 | 36 | barra (36), provador/fit check (36), caimento (12), peça vestida/inteira (12) |
| pov | 36 | 0 | 36 | caimento (36) |
| movimento | 36 | 0 | 36 | barra (36), caimento (36), cintura/cós (36), giro/voltinha (36), peça vestida/inteira (36) |
| comentario | 36 | 0 | 36 | barra (36), caimento (12), peça vestida/inteira (12) |
| teste | 36 | 0 | 0 | - |
| troca_cor | 36 | 0 | 36 | barra (36), caimento (12), peça vestida/inteira (12) |
| tres_jeitos | 36 | 0 | 0 | - |
| unboxing | 36 | 0 | 36 | veste/vestir (36), cintura/cós (3) |
| asmr | 36 | 0 | 36 | barra (36), caimento (36), cintura/cós (36), giro/voltinha (36), peça vestida/inteira (36) |
| mesa | 36 | 0 | 0 | - |

## Por produto (todas as bases e estilos)

| Produto | Família detectada | Fala com palavra de roupa | Vídeo com palavra de roupa | Reprovados na auditoria |
|---|---|---|---|---|
| creme-facial | beleza | 0/33 | 21/33 | 0 |
| serum | beleza | 0/33 | 21/33 | 0 |
| batom | beleza | 0/33 | 21/33 | 0 |
| protetor-solar | beleza | 0/33 | 21/33 | 0 |
| perfume | beleza | 0/33 | 21/33 | 0 |
| esmalte | beleza | 0/33 | 21/33 | 0 |
| brinco-argola | acessorio | 0/33 | 21/33 | 0 |
| colar-ponto-de-luz | acessorio | 0/33 | 21/33 | 0 |
| pulseira | acessorio | 0/33 | 21/33 | 0 |
| anel | acessorio | 0/33 | 21/33 | 0 |
| oculos-sol | acessorio | 0/33 | 21/33 | 0 |
| bolsa | acessorio | 0/33 | 21/33 | 0 |
| controle-legging | moda | 33/33 | 33/33 | 3 |
| controle-vestido | moda | 33/33 | 33/33 | 33 |

## Exemplos de gancho gerado para produto que não é roupa (modo com fala, sem técnica)

- **creme-facial** (família `beleza`): "A textura do creme me ganhou assim que eu abri"
- **serum** (família `beleza`): "O que me fez escolher esse sérum foi a textura leve"
- **batom** (família `beleza`): "O que me fez escolher esse batom foi o acabamento"
- **protetor-solar** (família `beleza`): "O toque seco do protetor solar me chamou atenção na hora"
- **perfume** (família `beleza`): "O que me fez escolher esse perfume foi o pote de vidro"
- **esmalte** (família `beleza`): "O que me fez escolher esse esmalte foi o acabamento"
- **brinco-argola** (família `acessorio`): "O que me fez escolher esse brinco foram as argolas"
- **colar-ponto-de-luz** (família `acessorio`): "O que me fez escolher esse colar foi a pedra"
- **pulseira** (família `acessorio`): "O que me fez escolher essa pulseira foi o elástico"
- **anel** (família `acessorio`): "O que me fez escolher esse anel foi a pedra"
- **oculos-sol** (família `acessorio`): "O que me fez escolher esse óculos foi a proteção uv"
- **bolsa** (família `acessorio`): "O que me fez escolher essa bolsa foi a alça regulável"
