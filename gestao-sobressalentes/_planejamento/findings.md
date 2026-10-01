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
- **Excel desta máquina (pessoal) está "Produto Não Licenciado"**: automação via Excel não
  roda aqui; a migração v2 usa openpyxl. O LibreOffice está instalado e serve para
  recalcular fórmulas em teste.
