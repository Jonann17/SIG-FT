# Lastro documental — nenhum valor entra na ficha sem estar no documento

**Data:** 2026-08-13 · **Frente:** AutoSpecAI (Rafael)
**Origem:** *"não gostei do ato de aceitar uma informação errada. Isto não deve acontecer."*

---

## 1. O que dá e o que não dá para garantir

A frase acima é a exigência certa, e merece uma resposta honesta sobre o que é alcançável.

**"Correto" não é verificável por código.** Se o próprio datasheet do fabricante estiver errado,
ou se for de outra peça, nenhuma verificação automática descobre. Prometer isso seria mentira.

**"Rastreável ao documento" é 100% verificável.** Se a IA responde `175 bar`, dá para conferir se
`175` aparece no texto que foi lido. Se não aparece, o valor foi inventado — e isso o código
detecta com certeza, sem probabilidade envolvida.

Este documento implementa a segunda garantia, que é a mais forte que existe aqui, e a encaixa
num arranjo de três camadas:

| Camada | Pergunta que responde | Onde |
|---|---|---|
| 1. Filtro anti-intruso (§4.3) | o documento é **deste material**? | `_resultado_e_relevante` |
| 2. **Lastro documental** | o valor **saiu mesmo do documento**? | `valor_tem_lastro` |
| 3. Conferência humana | o documento **está certo**? | lista de origens por campo |

Nenhuma sozinha basta. Juntas, para um dado errado entrar na ficha é preciso que o documento
seja do material certo **e** que o valor esteja escrito nele — restando o caso em que o
fabricante publicou errado, que é o que a camada 3 existe para pegar.

## 2. Regra de lastro

Aplicada a todo campo técnico antes de escrever na célula:

1. **Se o valor tem número, TODOS os números precisam estar no contexto.**
   Basta um inventado para reprovar: `"entre 175 e 999 bar"` cai mesmo com o `175` correto.
   Meia verdade num campo técnico é pior que campo vazio — passa na conferência por parecer certa.

2. **Se não tem número**, exige que alguma palavra de 4+ letras apareça no contexto (`NBR`,
   `Nitrile`). Valor curto sem palavra longa (`N/A`, `X`) passa: não há o que verificar.

Números são normalizados antes de comparar: `25,4` e `25.40` são o mesmo `25.4`. Fabricante
escreve decimal com ponto, planilha brasileira com vírgula, e a IA copia ora um ora outro — sem
normalizar, o valor certo seria descartado por pontuação.

### Consequência assumida: conversão de unidade reprova

`0,4 MPa` quando o documento diz `4 bar` não tem o `0.4` escrito em lugar nenhum. O campo fica
vazio e o console diz o que foi bloqueado. É o comportamento pedido: **na dúvida, vazio.**

### Exceção deliberada: os campos gerativos

Os 12 `GENERATIVE_FIELDS` (embalagem, transporte, preservação, descarte, legislação…) existem
para serem **gerados de conhecimento técnico** — é o que as regras de negócio §3.2 pedem. Não há
datasheet de onde saírem. Exigir lastro deles esvaziaria metade da ficha por desenho. Eles são
isentos, e o console já os rotula como `conhecimento tecnico` na lista de origens.

## 3. Fonte citada que não existe

Separadamente, toda fonte que a IA cita é conferida contra os marcadores `--- LOCAL DOC: x ---`
e `--- WEB DOC: y ---` do contexto. Uma URL que nunca foi lida é sinal de invenção.

**Isto avisa, não descarta.** Se o valor tem lastro, o dado está no documento e só a etiqueta
veio errada — apagar um valor verificável por causa do rótulo seria estrito demais. Mas quem vai
homologar precisa saber.

## 4. Demonstração

Contexto com `IP67`, `350 bar`, `50 to 400 ml/min`. A IA respondeu seis campos, três deles com
problemas plausíveis:

```
[warn] 1 campo(s) citam uma fonte que NAO esta entre os documentos lidos:
       · var_row_88: https://www.hydac.com/manual-generico.pdf
[warn] 3 campo(s) ficaram VAZIOS porque o valor respondido nao aparece no documento lido:
       · 13 - GRAU DE PROTECAO      -> a IA respondeu 'IP65'
       · 10 - PRECISAO              -> a IA respondeu '+/- 1 codigo ISO'
       · 17 - FAIXA DE TENSAO (CC)  -> a IA respondeu '35 MPa'

ESCRITO NA FICHA (3 de 6):
  6 - PRESSAO MAXIMA DE TRABALHO = 350 bar
  4 - FAIXA DE VAZAO             = 50 a 400 ml/min
  7 - FAIXA DE TEMPERATURA DE USO = 0 a +70 C
```

`IP65` contra um documento que diz `IP67` é exatamente o erro que passaria na conferência
humana por ser plausível. Ele não chega à célula.

## 5. Rastreabilidade — já existia, e continua

A lista `-> Origem dos dados (N campos)`, com a URL por campo, é do P-04 (2026-08-11) e é a que
apareceu no console do teste do Luan. Agora ela ganhou duas vizinhas: a lista de campos que a IA
não respondeu, e a de campos bloqueados por falta de lastro. As três juntas descrevem o destino
de **todo** campo que faltava — nenhum some em silêncio.

## 6. Glossário multilíngue

Motivo separado, mesma entrega. O parque gerador de Itaipu não é abastecido por fornecedores de
língua inglesa:

| Idioma | Quem |
|---|---|
| Alemão | Voith Hydro (turbinas, reguladores), Siemens (geradores), HYDAC, Bosch Rexroth, Andritz, SEW, FAG |
| Espanhol | a própria Itaipu é **binacional** — espanhol é idioma oficial da entidade; mais fornecedores latino-americanos |
| Francês | Alstom (turbinas e geradores, hoje GE Hydro), Schneider |
| Italiano | fabricantes de válvulas, bombas e hidráulica |

Antes disto, um datasheet alemão passava pelo BM25 sem casar termo nenhum — `pressao` não casa
com `Druck` — e o trecho com a resposta era recortado fora, o mesmo furo que o inglês tinha
antes de 2026-08-11.

56 termos, **318 equivalentes**. Escritos sem acento de propósito: `tokenizar` normaliza por
NFKD, então `Länge` no documento vira `lange`, e é assim que o glossário precisa guardar.

Verificado com datasheets sintéticos nos quatro idiomas, cada um com 6 dados-alvo diluídos em 25
páginas de enchimento: **6/6 preservados em todos**, mais um caso misto (catálogo alemão com
resumo em inglês).

## 7. Verificação

- `tests/test_autospec_lastro.py` — 26 testes
- `tests/test_autospec_rag_multilingue.py` — 28 testes
- Suíte completa: **1698 passed, 3 skipped**

O caminho do cache passa pela mesma verificação do caminho vivo (`_conferir_e_filtrar`): um
acerto de cache não pode ser porta de entrada para valor sem lastro.

## 8. O que continua fora

- **Datasheet correto mas com erro de fábrica.** Camada 3, conferência humana.
- **Valor presente no documento mas lido do lugar errado** — a IA pega `210 bar` (pressão de
  pico) e responde na pergunta de pressão de trabalho. Tem lastro e está errado. A lista de
  origens por campo é o que permite pegar isso.
- **Idioma fora dos cinco.** Datasheet chinês ou japonês passa sem expansão.
