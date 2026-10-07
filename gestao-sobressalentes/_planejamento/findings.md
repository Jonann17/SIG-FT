# findings.md — o que o levantamento revelou

## Documentos-fonte localizados
| O que | Onde | Observacao |
|---|---|---|
| ET Geral | `01 - Ger. Integracao/01 - Edital/02 ANEXO II .../ANEXO II - A - ET GERAL/604720T0018P(1)R1.pdf` | 312 páginas. **Não** está na pasta 15 - PDM |
| Apresentação do fluxo | `15 - PDM/Apresentacao PMIB (PDM) R5 - Em desenvolvimento.pptx` | 24 slides |
| Ata das duas listas | `15 - PDM/AR-EN.DT-001-2026.pdf` | reunião 23/06/2026, aprovada até 30/06/2026 |
| Fichas duplicadas | `15 - PDM/Procedimiento - Fichas PMIB Duplicadas PDM_9900_000.pdf` | 4 páginas, espanhol |
| Revisão da Aplicação LMR | `15 - PDM/Revision Propuesta CMI AplicacionLMR.pdf` | 20/08/2026 |
| Mapeadora | `15 - PDM/SOBRESSALENTES - PMIB/Mapeamento Listas de Sobressalentes.xlsx` | 94 listas, 35 colunas, 3 abas |
| Dashboard | `15 - PDM/SOBRESSALENTES - PMIB/Sobressalentes - Dashboard.pbix` | Power BI, não inspecionado |
| Catalogo de PDMs | `15 - PDM/PDMs SAM-GM (1193).xlsx`, `1174 - PDMs - SAMGM PMIB.xlsx` | duas versões, contagens diferentes |
| SIG-FT | github.com/luanccozer/SIG-FT | ~36k linhas em `sigft/`, 1327 testes |

## Achados que mudam o entendimento

### 1. A ET Geral não descreve a Aplicação LMR
O Capítulo 18 e o Anexo I falam de classificação de material, ficha técnica e PDM.
O conceito de "onde este sobressalente e aplicado dentro do projeto" **não esta
escrito na ET**. A Aplicação LMR e construção posterior, negociada, cujo desenho
vive na apresentação PMIB (slide 18) e na proposta de revisão de 20/08/2026.
Isso explica por que é o ponto mais instável do processo: não ha texto contratual
para ancorar a discussão. Ver [[Secao - Aplicacao LMR]].

### 2. A pasta local `_python_pdm/SIG-FT` esta defasada
A copia no Box tem os `*_backend.py` monoliticos (app.py com 225 KB). O GitHub já
tem o pacote `sigft/` com os backends reduzidos a shims de compatibilidade.
Quem for mexer no código deve usar o GitHub.

### 3. As duas listas são decisão de 23/06/2026
Antes da ata AR/EN.DT/001/2026 o CMI já emitia duas listas semelhantes, mas sem
fluxo Aconex formalmente separado. A ata resolveu o problema de dominio: preço e
código PMIB **não são dominio da EN.DT**, e sim da SM.DT.

### 4. O menor indicador da cadeia inteira e a Aplicação LMR
93 fichas com LMR finalizada contra 1219 fichas existentes. Ver
[[Diagnostico - Deficiencias]] e [[Indicadores e Como Ler]].

## Divergencias a confirmar
- ~~**Prazo de autorização de entrega**~~ — **RESOLVIDO 30/09/2026 (Luan)**: vale
  **15 dias úteis** (antes, 14 dias corridos). O SIG-FT ainda calcula com 14 dias corridos
  (`pmib_manager.py`). Calendário de feriados a confirmar — ver [[Plano - Sistema de Gestao v2]].
- ~~**`ATRASO DE AUTORIZACAO DE ENTREGA ITAIPU`**: fichas ou dias?~~ — **RESOLVIDO 30/09/2026**:
  conta **fichas** (PMIB distinto, sem DUPLICADO), pelo código do SIG-FT.
- **Fichas duplicadas**: o procedimento pede referência com `"D1"` entre aspas.
  Confirmar se as aspas fazem parte do valor gravado ou são notacao do documento.
- ~~**Catalogo de PDMs**: 1174 ou 1193?~~ — **RESOLVIDO**: os dois foram para `0 - Obsoleto/`;
  vigente é `PDMs SAM-GM 23.09.26.xlsx`.
- ~~**Dashboard Power BI**: lê a mapeadora ou os `_STATUS_PMIB`?~~ — **RESOLVIDO 30/09/2026**:
  só a aba principal da mapeadora, por caminho fixo de uma máquina.

## Achados de 30/09–01/10/2026 (sessão Gestão v2)
- **Lista de preços mudou de código**: DCC `PB021` (revisão do ITAIPU-REF-0013) no lugar de
  `PB020-0x`. Ver [[Lista de Precos]].
- **Listas suspensas do `_STATUS_PMIB` somem ao salvar pelo SIG-FT** (validação por
  referência a outra aba = extensão, que o openpyxl apaga). 21 planilhas ainda tinham.
- **`APTO PARA ENTREGA` da mapeadora = apto e ainda não entregue.**
- **STATUS `DUPLICADO` ≠ ficha duplicada** (correção do Luan, 04/10): DUPLICADO = item repetido na
  mesma lista; ficha duplicada de outro sistema = `PDM.9900.000` + PMIB da original em OBSERVAÇÕES.
- **O openpyxl apaga comentários em thread** (04/10, testado): 16 `_STATUS_PMIB` têm. Migrar esses
  pelo Excel; blindar o SIG-FT.
- **Lista de preços vigente da Sala Segura só existe como `ST00=U01&MPB021 - Copy.xlsm`** (04/10).
- **Excel desta máquina (pessoal) está "Produto Não Licenciado"**: automação via Excel não
  roda aqui; a migração v2 usa openpyxl. O LibreOffice está instalado e serve para
  recalcular fórmulas em teste.

## Achados de 04/10/2026 (noite) — aplicação do layout v2
- **O SIG-FT acha as colunas do `_STATUS_PMIB` pelo nome** — inserir colunas no meio não o faz gravar
  na coluna errada. Exceção: o módulo **PDM** (`app/views/pdm.py` ≈ 438, modo "selecionar códigos")
  lê o cabeçalho **fixo na linha 4** (`skiprows=3`): com a linha de revisão, dá "Coluna 'CÓDIGO PMIB'
  não encontrada" (já dava nas 5 listas que tinham a linha). Tarefa T0 do SIG-FT.
- **`apto_para_entrega_att.py` não está no repositório**: vive no Box em `15 - PDM/_python_pdm/SIG-FT/`
  (cópia antiga em `AMP/`). Procura `APTO PARA ENTREGA` pelo nome e salva com openpyxl.
- **Sem a coluna APTO, o Gestão PMIB escreve "Atualizar template"** nas colunas APTO e ATRASO da
  mapeadora (não quebra). Até a T2.
- **Uma lista tinha "Fornecedor" à direita de OBSERVAÇÕES** (#ST00=M00MEU10&MPB020, 99 valores):
  movida para a FORNECEDOR nova.
- **A `DATA DE ATUALIZAÇÃO` da mapeadora não é a "DATA DE ALTERAÇÃO" da linha de revisão** (é a do
  Aconex): por isso a linha foi semeada com "—" na data.
- **53 fichas com autorização atrasada** em 04/10 (55 linhas); nenhuma consta no export de autorizados
  de 18/08/2026. A mais antiga: e-mail de 24/06/2025 (446 dias).
- **Ficha DOCUMENTAL não precisa de autorização de Itaipu** (correção do Luan, 05/10): só o pai físico é
  entregue. As 61 "aguardando" de #ST00=M00MEU10&MPB020 eram componentes da Hydac → `N/A`. TÍTULO (agrupamento
  feito errado) e TIPO vazio também não contam — **só FÍSICA E DOCUMENTAL**.
- **Inserir coluna herda o formato da vizinha**: DIAS DE ATRASO nasceu com formato de data em 33 arquivos (a
  coluna à esquerda, o antigo APTO, tinha). Corrigido; e o openpyxl lê número com formato de data como `datetime`
  — quem lê DIAS tem de converter (`to_excel`).
- **O Gestão PMIB não ignora pastas de teste**: `os.walk` entra em `testes_autospec/`; o link "Abrir Box" de
  #ST00=B01BMU10&EPB020 na mapeadora aponta para a cópia de teste. Vai na T3-a do roteiro.
- **A suíte de testes do SIG-FT stuba pandas/openpyxl sempre** (`tests/conftest.py`): teste com `.xlsx` de verdade
  tem de rodar fora dela — por isso o validador do kit.
- **O rodapé da lista de preços é escrito por macro** (`ConfigurarRodapeCompleto`, disparada por
  `Worksheet_Change` em Capa!D37/F37/I37). Gerar o arquivo por fora do Excel não dispara a macro — o SIG-FT tem de
  regravar essas células pelo Excel (xlwings). O template tem ainda o carimbo de Itaipu embutido (objeto Word).
- **Power BI Project (.pbip) dá para gerar como texto e testar sem a interface**: TMDL validado pela biblioteca
  oficial (TOM, via pythonnet) e atualização/consultas DAX no motor local do Desktop (porta em
  `msmdsrv.port.txt`). "Ignorar níveis de privacidade" = `fastCombine` no `dataAccessOptions` do modelo.
- **PBIR à mão — o que precisa ir explícito**:
  - largura de coluna de tabela (`columnWidth` com `selector.metadata` = queryRef), senão a primeira coluna longa
    empurra as outras para fora;
  - `imageScaling = Fit` no logotipo;
  - `padding` zero em caixa de texto e cartão pequeno;
  - `maxMarginFactor` no eixo das barras, para nomes longos;
  - filtros sincronizados entre páginas: `syncGroup` dentro de `visual`.
- **Power BI acha a pasta do Box sozinho**: listar `Folder.Contents("C:\Users")` e testar
  `<usuário>\Box\...\SOBRESSALENTES - PMIB` funciona com "ignorar níveis de privacidade" (`fastCombine`).
- **5 fichas aparecem em duas listas** (mesmo PMIB): por isso "Fichas" no Power BI (PMIB distinto) dá 1.352 e a
  soma por lista dá 1.357.
