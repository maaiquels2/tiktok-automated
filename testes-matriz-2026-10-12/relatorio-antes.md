# Matriz de cenários — produtos que não são roupa

Gerado sem API: o mesmo gerador do site (`generate`), com a auditoria de honestidade do app.

- Combinações: **420** (14 produtos × 10 bases/formatos × 3 estilos)
- Geraram pacote sem erro: **420**
- Cabem no limite do Grok (3940): **420**
- Aprovadas pela auditoria de honestidade: **351**

## Vocabulário de roupa em produto que não é roupa

Cada célula: combinações com pelo menos uma palavra inequívoca de roupa (caimento, veste, blusinha, barra, agachar, provador, cintura, jaqueta, girar...) naquele campo. "No corpo" e "tecido" ficam de fora por serem ambíguos. Na roupa de controle essas palavras estão certas.

| Grupo | Combinações | Na fala | Na tela | No prompt do vídeo | No prompt da imagem |
|---|---|---|---|---|---|
| Beleza | 180 | 180 (100%) | 48 (26%) | 180 (100%) | 180 (100%) |
| Acessórios | 180 | 180 (100%) | 36 (20%) | 180 (100%) | 180 (100%) |
| Roupa (controle) | 60 | 60 (100%) | 24 (40%) | 60 (100%) | 60 (100%) |

## Por base/formato (beleza + acessórios)

| Base / formato | Combinações | Com palavra de roupa na fala | No prompt do vídeo | Palavras mais frequentes (vídeo) |
|---|---|---|---|---|
| com fala | 36 | 36 | 36 | barra (36), blusinha (36), veste/vestir (36), caimento (26), provador/fit check (18) |
| espelho | 36 | 36 | 36 | barra (36), blusinha (36), provador/fit check (36), veste/vestir (36), caimento (26) |
| pov | 36 | 36 | 36 | blusinha (36), caimento (36), veste/vestir (36) |
| movimento | 36 | 36 | 36 | barra (36), caimento (36), cintura/cós (36), giro/voltinha (36), peça vestida/inteira (36) |
| comentario | 36 | 36 | 36 | barra (36), blusinha (36), veste/vestir (36), caimento (26), provador/fit check (18) |
| teste | 36 | 36 | 36 | agachar (36), barra (36), blusinha (36), giro/voltinha (36), veste/vestir (36) |
| troca_cor | 36 | 36 | 36 | barra (36), blusinha (36), veste/vestir (36), caimento (26), provador/fit check (18) |
| tres_jeitos | 36 | 36 | 36 | barra (36), looks/jaqueta (36), caimento (21), provador/fit check (18), cintura/cós (12) |
| unboxing | 36 | 36 | 36 | blusinha (36), veste/vestir (36), peça vestida/inteira (33), cintura/cós (3) |
| asmr | 36 | 36 | 36 | barra (36), caimento (36), cintura/cós (36), giro/voltinha (36), peça vestida/inteira (36) |

## Por produto (todas as bases e estilos)

| Produto | Família detectada | Fala com palavra de roupa | Vídeo com palavra de roupa | Reprovados na auditoria |
|---|---|---|---|---|
| creme-facial | beleza | 30/30 | 30/30 | 3 |
| serum | beleza | 30/30 | 30/30 | 3 |
| batom | beleza | 30/30 | 30/30 | 3 |
| protetor-solar | beleza | 30/30 | 30/30 | 3 |
| perfume | beleza | 30/30 | 30/30 | 3 |
| esmalte | beleza | 30/30 | 30/30 | 3 |
| brinco-argola | moda | 30/30 | 30/30 | 3 |
| colar-ponto-de-luz | moda | 30/30 | 30/30 | 3 |
| pulseira | moda | 30/30 | 30/30 | 3 |
| anel | moda | 30/30 | 30/30 | 3 |
| oculos-sol | moda | 30/30 | 30/30 | 3 |
| bolsa | moda | 30/30 | 30/30 | 3 |
| controle-legging | moda | 30/30 | 30/30 | 3 |
| controle-vestido | moda | 30/30 | 30/30 | 30 |

## Exemplos de gancho gerado para produto que não é roupa (modo com fala, sem técnica)

- **creme-facial** (família `beleza`): "Achei esse produto e não esperava o caimento e os detalhes visíveis"
- **serum** (família `beleza`): "Achei esse produto e não esperava o caimento e os detalhes visíveis"
- **batom** (família `beleza`): "O que me fez escolher esse produto foi o acabamento"
- **protetor-solar** (família `beleza`): "Achei esse produto e não esperava o caimento e os detalhes visíveis"
- **perfume** (família `beleza`): "Achei esse produto e não esperava o caimento e os detalhes visíveis"
- **esmalte** (família `beleza`): "O que me fez escolher esse produto foi o acabamento"
- **brinco-argola** (família `moda`): "O que me fez escolher essa peça foram as argolas"
- **colar-ponto-de-luz** (família `moda`): "Achei essa peça e não esperava o caimento e os detalhes visíveis"
- **pulseira** (família `moda`): "O que me fez escolher essa peça foi o elástico"
- **anel** (família `moda`): "Achei essa peça e não esperava o caimento e os detalhes visíveis"
- **oculos-sol** (família `moda`): "Achei essa peça e não esperava o caimento e os detalhes visíveis"
- **bolsa** (família `moda`): "O que me fez escolher essa peça foi a alça regulável"
