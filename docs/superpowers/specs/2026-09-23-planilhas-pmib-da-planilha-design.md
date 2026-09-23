# Planilhas PMIB direto da planilha de PDMs, e as pastas regeneradas com a revisão no nome

**Data:** 2026-09-23 · **Frente:** Luan · **Módulo:** 2. Planilhas PMIB
(`sigft/services/pdm.py` + `sigft/app/views/pdm.py`)
**Origem:** pedido do usuário, com a exportação `PDMs_SAM-GM_23.09.26.xlsx`
**Fecha:** a pendência de 2026-08-18 *"Módulo de atualização dos PDMs formatados"*
(`docs/refatoracao/PENDENCIAS.md`)

---

## 1. O problema

O módulo monta a ficha em três passos, com duas pastas no meio:

```
PDMs_SAM-GM.xlsx ─(1 fatiar)─► PDMs From Itaipu/ ─(2 formatar)─► PDMs Modificados/ ─(3 criar planilhas PMIB)─► fichas
```

Os passos 1 e 2 **pulam o que já existe na pasta**. Quando a Itaipu revisa um PDM, a pasta
não se atualiza: é preciso apagar o arquivo à mão nas duas pastas e rodar de novo. Hoje todos
os arquivos das pastas do usuário vêm de uma planilha desatualizada, e há muitos PDMs para
revisar.

Rodando o fluxo antigo na planilha nova (amostra de 10 PDMs, 2026-09-23), apareceram quatro
defeitos, todos medidos:

| Defeito | Medido na planilha | O que sai na ficha |
|---|---|---|
| `(nan)` no lugar da ajuda | 78 PDMs têm ajuda vazia; em 68, todas | `"1 - APLICACAO (nan):"` |
| Dois PDMs com o mesmo código | `PDM.3010.007`, `PDM.5945.026` | os dois misturados numa ficha: 19 perguntas, "NORMAS TECNICAS APLICAVEIS" duas vezes |
| Ordem das perguntas | 1.140 de 1.199 PDMs | numeração pela ordem do arquivo, não pela `SECUENCIA` |
| `/` no título | 3 PDMs | o fatiamento falha: no Windows a barra é separador de pasta |

## 2. A planilha

Aba `TEMPLATE_PDM`: 21.317 linhas de dados, 1.199 PDMs, **uma linha por característica**.
Cabeçalho de verdade na **linha 6**; dados a partir da 7. A linha 2 traz a data da exportação
(`Exportado el:` em A2, `23/09/2026 11:02:02` em B2).

| Coluna | Campo | Uso |
|---|---|---|
| A | `CÓDIGO PDM` | chave |
| B | `N° CLASE - FSC` | (catálogo) |
| D / C | `TÍTULO - PDM - PT` / `ES` | nome do arquivo; conferência com o STATUS |
| F / H | `NOMBRE BASE - PT` / `NOMBRE MODIFICADOR - PT` | detecção de código duplicado (regra 6) |
| J | `REVISIÓN` | revisão vigente; nome do arquivo; conferência com o portal |
| N | `SECUENCIA` | ordem das perguntas |
| Q | `CARACTERÍSTICA - DESCRIPCIÓN PT` | a pergunta |
| S | `TEXTO DE AYUDA PT` | entre parênteses, depois do nome |

Fatos medidos que o desenho usa:

- **Esta exportação já traz só a revisão vigente** em 1.197 dos 1.199 PDMs. As duas exceções são
  os códigos duplicados: `PDM.3010.007` é ACOPLAMENTO ROSCADO (R1, 18/07/2024) **e** FIXADOR
  (R0, 23/04/2026); `PDM.5945.026` é UNIDADE RESISTOR (R1) **e** RELE SEGURANCA (R0). O nome
  base muda (ACOPLAMENTO × FIXADOR, UNIDADE × RELE), e a revisão menor tem a data MAIS NOVA:
  são PDMs diferentes, não histórico.
- Está atualizada: os três PDMs cobrados no relatório da Itaipu de 23/09 subiram de revisão
  (`PDM.5925.001` está na R5, `PDM.5920.020` na R2, `PDM.5925.008` na R1).
- `SECUENCIA` é 1..N em todos os PDMs, sem buraco nem repetição.
- Nenhum PDM repete nome de característica dentro da mesma revisão.
- Nome e ajuda têm espaço duplo (1.147 ajudas) e quebra de linha (54 ajudas). O método antigo
  os mantinha como estão, e o Upload Specs (4.3) casa o nome da característica por
  **igualdade exata** com o Master: o nome tem de sair verbatim.
- 6 nomes de característica têm parênteses no próprio nome (`FAIXA DE TENSAO DE ALIMENTACAO (CA)`).
- 3 títulos têm `/` (`EXTENSAO/TRONCO TORRE`, `BLOCO CAPACITOR/RESISTOR`,
  `MODULO DEFASADOR/SINCRONIZADOR`).
- Formatação da aba: mescladas `A1:X1` e `A5:X5`; painel congelado em `A6`; autofiltro
  `A6:X<última>`; 21 larguras de coluna; alturas próprias nas linhas do cabeçalho.
- Custos medidos neste contêiner: ler a planilha só com valores (`pdm_catalogo.carregar`),
  **2,3 a 2,7 s**; ler com formatação (como o fatiamento faz), **7,1 s**; gravar 1.199
  PDMs formatados, **~18 s**.

## 3. Decisões do usuário (2026-09-23)

| # | Decisão |
|---|---|
| D1 | A planilha vira a **fonte padrão** da aba 2. A pasta continua como alternativa: o método antigo não sai. |
| D2 | Os arquivos das pastas são saída automática do app; ninguém os edita à mão. |
| D3 | A ficha em inglês continua **só pela pasta traduzida** ("quase não usamos EN"). |
| D4 | Portal à frente da planilha: **gera e avisa** (não recusa). |
| D5 | Opção de **regenerar as duas pastas** (From Itaipu e Modificados) a partir da planilha, **com a revisão do PDM no nome**. |

## 4. Componentes

```
PDMs_SAM-GM.xlsx ──► core/pdm_catalogo.py      (estendido)
                         │
_STATUS_PMIB ──► services/pdm.processar_pastas_fichas()   (sem mudança)
                         │
                         ▼
             services/pdm_planilha.py            (novo: as regras da seção 5)
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
services/pdm.py                 services/pdm_regeneracao.py   (novo: seção 6)
 montagem da ficha, com a
 FONTE das perguntas injetada:
   pasta    → código de hoje
   planilha → pdm_planilha
                         ▲
             app/views/pdm.py            (tela: seção 7)
```

### 4.1 `core/pdm_catalogo.py`: estendido, sem mudar o que já faz

É o único leitor da planilha-mestra na camada `core/` (o módulo 1 já o usa). Ganha, sem
tocar no ranqueamento nem no que o módulo 1 lê:

- **`Caracteristica`** (dataclass congelada): `nome`, `ajuda`, `sequencia`, `linha`.
  - `nome`: coluna Q verbatim, só sem espaço nas pontas; cai na coluna P (ES) se Q vier vazia.
  - `ajuda`: coluna S verbatim, só sem espaço nas pontas. **Não** cai no espanhol: ajuda em
    espanhol numa ficha em português é pior que ajuda nenhuma.
  - `sequencia`: coluna N como inteiro, ou `None` se ilegível.
  - `linha`: a linha da aba `TEMPLATE_PDM` de onde veio. É o que o fatiador usa para copiar a
    formatação.
- **`PDM.caracteristicas_em_ordem: tuple[Caracteristica, ...] = ()`**: as da revisão vigente,
  ordenadas por `(sequencia is None, sequencia, linha)`. O campo `caracteristicas` que já existe
  (nomes normalizados, na ordem do arquivo, usados no ranqueamento) **não muda**.
- **`PDM.identidades: tuple[Identidade, ...] = ()`**: uma `Identidade(revisao, titulo, nome_base)`
  por revisão vista na planilha, da maior para a menor. É o que permite detectar o código
  duplicado (regra 6) sem reler a planilha.
- **`CatalogoPDM.exportado_em: str = ""`**: o texto de `B2`, quando `A2` começa com `Exportado`.
- **`CatalogoPDM.origem: str = ""`**: o caminho passado a `carregar`. Serve para o serviço
  escrever a linha de início do log sem a tela ter de repassar o caminho.
- No formato manipulado antigo (abas `PDMs`/`Instruções PDMs`), `caracteristicas_em_ordem`,
  `identidades` e `exportado_em` ficam vazios. É o sinal que a regra 8 usa.

### 4.2 `services/pdm_planilha.py` (novo): as regras

Funções puras sobre o catálogo, testáveis sem Excel:

- `montar_pergunta(numero, nome, ajuda) -> str`: `"N - NOME (AJUDA):"`, ou `"N - NOME:"` quando
  a ajuda é vazia. Vazia = `None`, `NaN`, `""`, só espaços, ou os textos `"nan"`/`"None"` que o
  `str()` do pandas produz. **Também passa a ser usada pelo método antigo** (seção 4.3).
- `perguntas_do_pdm(catalogo, pdm_usado, pmib="") -> PerguntasDoPDM`: aplica as regras 1 a 9. Devolve
  `PerguntasDoPDM(pdm, linhas, avisos)`, ou levanta **`PDMRecusado`** (subclasse de
  `ValueError`) com a mensagem pronta para o log.
- `conferir_catalogo(catalogo)`: levanta `PDMRecusado` quando a planilha não traz característica
  nenhuma (regra 8).
- `nome_de_arquivo(pdm, sufixo="") -> str`: `"PDM_1650_001 - ACUMULADOR - R2" + sufixo + ".xlsx"`.
  Troca `\ / : * ? " < > |` por `-`, colapsa espaços, tira ponto e espaço do fim. Sem revisão
  legível, fica sem o `" - R<n>"`.
- `revisao_no_nome(nome_arquivo) -> int | None`: o `n` de `" - R<n>"` antes da extensão ou do
  `_formatado`.
- Revisão e código do "PDM usado": `revisao_do_pdm` e `codigo_do_pdm` de
  `services/cria_fichas.py`, importados de lá como `correcao_pdm_planilha.py` já faz. **Não**
  ganham cópia.

### 4.3 `services/pdm.py`: alterado

- **`aplicar_templates_fichas` continua com a mesma assinatura, as mesmas mensagens e o mesmo
  retorno.** Por dentro, o laço de montagem (template da memória, aba resolvida uma vez,
  renomear a aba no inglês, linha 79, mesclas `C:L`/`M:V`, fonte 8, altura 32, bordas, salvar
  com `retry_lock`) sai para uma função interna que recebe **de onde vêm as linhas de cada
  PDM**. A montagem da ficha continua sendo uma só.
- **Nova `aplicar_templates_fichas_da_planilha(lista_dados, catalogo, path_template,
  log_callback=None, retry_lock=None)`**: usa esse mesmo laço, com as linhas vindas de
  `perguntas_do_pdm`. Sempre em português (D3). Devolve `(mensagem, log)` como a outra.
- **Método antigo, escolha do arquivo:** quando mais de um arquivo da pasta casar com o PDM,
  vence o de **maior `revisao_no_nome`**. Sem revisão conta como a menor; empate fica com o
  primeiro, que é o comportamento de hoje. O log avisa quantos havia e qual foi usado. O filtro
  por substring do id (`PDM_1234_001`) não muda.
- **`processar_arquivo_pdm`** passa a montar o texto com `montar_pergunta`: o `(nan)` some do
  passo "Formatar" também. O resto do passo não muda.

### 4.4 `services/pdm_regeneracao.py` (novo): regenerar as pastas (D5)

Detalhado na seção 6.

### 4.5 `app/views/pdm.py`: alterado

Detalhado na seção 7. A tela não ganha regra de negócio: valida campos, chama o serviço numa
thread e mostra o log.

## 5. Regras da montagem pela planilha

| # | Situação | O que acontece |
|---|---|---|
| 1 | Qual revisão | A **vigente**: a maior `REVISIÓN` do código. Mesma regra do módulo 1 e do 4.3. |
| 2 | Ordem e numeração | Por `SECUENCIA`, numeradas de 1 a N nessa ordem. Sem sequência legível, vai para o fim, na ordem da planilha. |
| 3 | Texto | `montar_pergunta`: `"N - NOME (AJUDA):"`, ou `"N - NOME:"` sem ajuda. Nome e ajuda verbatim (só sem espaço nas pontas). |
| 4 | STATUS com revisão **menor** que a planilha | Gera com a vigente. Aviso: `"PMIB <pmib>: <codigo> esta na R<a> no portal e na R<b> na planilha. A ficha saiu com a R<b>; o PDM precisa subir de revisao no portal."` |
| 5 | STATUS com revisão **maior** que a planilha (D4) | Gera com a vigente. Aviso: `"PMIB <pmib>: <codigo> esta na R<a> no portal, mas a planilha so tem a R<b>. A ficha saiu com a R<b>; exporte uma planilha nova da Itaipu."` |
| 6 | Código com **mais de um nome base** na planilha | Pega o título do "PDM usado" (entre o código e o `", R<n>"`, sem acento, maiúsculo, vírgula vira espaço, espaços colapsados). Se ele começar pelo nome base da revisão vigente (palavra inteira), gera. Se não, **`PDMRecusado`**: `"<codigo> aparece na planilha com mais de um nome base: <TITULO> (R<n>), <TITULO> (R<m>). O STATUS pede '<titulo>'. Confira com a Itaipu; a ficha nao foi gerada."` |
| 7 | PDM ausente | `"PDM usado"` sem código: `PDMRecusado("o 'PDM usado' esta vazio ou sem codigo de PDM: '<texto>'")`. Código fora da planilha: `PDMRecusado("<codigo> nao esta na planilha de PDMs (exportada em <data>)")`. PDM sem característica: `PDMRecusado("<codigo> nao tem nenhuma caracteristica na planilha")`. |
| 8 | Planilha sem característica nenhuma (formato manipulado antigo) | O lote **para antes de começar**: `"Esta planilha nao traz as caracteristicas dos PDMs (e o formato antigo, com as abas 'PDMs' e 'Instrucoes PDMs'). Use a exportacao da Itaipu, com a aba TEMPLATE_PDM."` |
| 9 | STATUS sem revisão (formato antigo `PDM.X - TITULO`) | Sem conferência de revisão. Gera com a vigente. |

A regra 6 usa o **nome base**, e não o título inteiro, de propósito. Numa planilha exportada
com histórico, o modificador muda entre revisões (`PDM.7010.018`: `SERVIDOR CONSOLE` na R0,
`SERVIDOR` na R2), e isso não pode recusar ficha. Nos dois duplicados reais o nome base é
outro.

**Log do lote** (quem escreve é o serviço, não a tela):
- **Início:** `"Planilha de PDMs: <arquivo>, exportada em <data>: <n> PDMs."`, logo depois de
  `conferir_catalogo` (regra 8).
- **Por ficha:** `"ficha gerada: <pmib>.xlsx (<codigo> R<rev>, <n> perguntas)"`.
- **Fim:** o resumo padrão do `RelatorioLote` (geradas, falhas com motivo) e, separadas, as
  duas listas de revisão: "PDM precisa subir de revisão no portal" (regra 4) e "planilha
  atrás do portal" (regra 5).

O texto de tela e de log **não leva travessão** (`tests/test_texto_da_ui.py`).

## 6. Regeneração das pastas (D5)

`regenerar_pastas(caminho_planilha, pasta_modificados, pasta_from_itaipu=None,
log_callback=None, retry_lock=None)`.

**Entrada:** a planilha, lida duas vezes: `pdm_catalogo.carregar` para valores, regras e ordem
(~2,7 s), e `load_workbook` com formatação, uma vez só, para o fatiador copiar estilo (~7,1 s).
A pasta Modificados é obrigatória; a From Itaipu é opcional (sem ela, só a Modificados é
regenerada, e o log e o resumo dizem isso). **As duas pastas não podem ser a mesma**: a busca de
versões antigas moveria os arquivos de uma para dentro da outra.

**Para cada PDM do catálogo** (1.199 na planilha atual):

| | Pasta From Itaipu | Pasta Modificados |
|---|---|---|
| Nome | `PDM_1650_001 - ACUMULADOR - R2.xlsx` | `PDM_1650_001 - ACUMULADOR - R2_formatado.xlsx` |
| Conteúdo | Aba `TEMPLATE_PDM` com as linhas 1 a 6 da planilha + as linhas das características vigentes, **na ordem da `SECUENCIA`**, cada célula com valor, fonte, borda, preenchimento, formato de número e alinhamento copiados | A tabela de duas colunas de hoje (1–10 e 11–20 mescladas, fonte 8, quebra de texto, altura 32, bordas), com as linhas de `montar_pergunta` e a resposta vazia |
| Formatação da aba | larguras de coluna; mescladas que caem inteiras nas linhas 1–6; altura de cada linha copiada (cabeçalho e dados); painel congelado; autofiltro `A6:<última coluna><última linha>` | a de hoje |

Os dois arquivos de um PDM são coerentes entre si: o passo antigo "Formatar", aplicado ao
arquivo novo da From Itaipu, produz as mesmas perguntas do arquivo novo da Modificados (mesmas
linhas, mesma ordem, `montar_pergunta` nos dois).

**Versões antigas.** Um arquivo da pasta é versão antiga de um PDM quando `extrair_pdm_id` do
nome é o código do PDM (na forma do nome de arquivo, `PDM_1650_001`), ele é do mesmo tipo (tem
`_formatado` na Modificados; não tem na From Itaipu) e o nome difere do nome novo. Versão antiga
**vai para a subpasta `_versoes_antigas`** da própria pasta, e não é apagada. Nome repetido lá
ganha ` (2)`, ` (3)`... antes da extensão. A mudança usa o canal `retry_lock` (adaptador
`SimpleNamespace(save=...)` sobre `shutil.move`, o mesmo padrão dos adaptadores de
`locking.save_with_retry`): arquivo aberto no Excel faz a janela "feche e tente de novo"
aparecer. Se o usuário desistir, o PDM vira **falha** e o arquivo novo **não** é gravado, para a
pasta não ficar com duas versões.

**Já em dia.** Se o arquivo com o nome novo já existe, ele **não é regravado**. As versões
antigas que ainda estiverem na pasta vão para `_versoes_antigas` do mesmo jeito. Sem nenhuma
versão antiga para mover, o PDM conta como "já em dia". Um arquivo feito pelo passo antigo nunca
tem `" - R<n>"` no nome, então é sempre substituído uma vez.

**Os dois códigos duplicados** são regenerados com a identidade vigente, com um aviso:
`"<codigo>: a planilha traz tambem <TITULO> (R<n>), que ficou de fora. Confira com a Itaipu."`

**Relatório** (`RelatorioLote`, um por pasta): novos; atualizados (`R1 -> R2`, ou "arquivo sem
revisão no nome"); já em dia; falhas com motivo; e onde ficaram as versões antigas.

**A pasta EN não é tocada** (D3). Quem precisar dela roda o passo "Traduzir" depois; o arquivo
traduzido herda o nome com a revisão, e a escolha por revisão mais alta (seção 4.3) resolve a
convivência com os arquivos traduzidos antigos.

**Os passos antigos "Fatiar" e "Formatar" continuam como estão.** O "Fatiar" antigo e o fatiador
novo convivem até a regeneração ser validada numa máquina real. A aposentadoria do antigo fica
registrada em `PENDENCIAS.md`. Os nomes novos são compatíveis com as duas guardas antigas: o
"Fatiar" reconhece o código em `"PDM_1650_001 - ACUMULADOR - R2"` (ele parte no primeiro
`" - "`), e o "Formatar" reconhece o `_formatado` correspondente (casa por substring).

## 7. Tela

**Painel "Configuração Global":**
- Ganha **"Planilha de PDMs (SAM-GM):"**, com botão "Selecionar" e o nome do arquivo escolhido.
  É o seletor que hoje fica no passo 1 da aba 1. Ele sobe porque as duas abas passam a usar.
  A chave de diálogo continua `pdm.sam_gm`, então a memória da pasta não se perde. O caminho
  não é lembrado entre sessões: a convenção da tela é não pré-preencher campo de arquivo.

**Aba 1 "Processar PDMs":**
- Seção nova, no topo: **"Regenerar as pastas a partir da planilha"**. Um texto explica o nome
  com revisão e a subpasta `_versoes_antigas`, e o botão é **"Executar: Regenerar as pastas"**.
  Usa a planilha e a "Pasta dos PDMs Modificados" do painel, e a "Pasta (PDMs From Itaipu)"
  da própria aba, se preenchida.
- Validações: planilha escolhida; pasta Modificados escolhida; as duas pastas diferentes entre
  si.
- As seções antigas ("1. Fatiar", "2. Formatar", "3. Traduzir") continuam. A seção 1 perde
  o próprio botão de planilha e diz que usa a do painel.

**Aba 2 "Criar planilhas PMIB":**
- Linha nova no topo: **"Fonte das características: (•) Planilha de PDMs ( ) Pasta de PDMs
  Modificados (método antigo)"**. O padrão é a planilha.
- Validações:
  - fonte Planilha sem planilha escolhida: `"Selecione a planilha de PDMs no painel de cima."`
  - fonte Planilha com idioma English: `"A ficha em ingles usa a pasta traduzida. Escolha a fonte 'Pasta de PDMs Modificados' ou o idioma Portugues."`
  - fonte Pasta: exatamente as validações de hoje.
- Com fonte Planilha, a thread faz: `pdm_catalogo.carregar` (erro de leitura vira mensagem de
  erro na tela, não exceção solta), depois `processar_pastas_fichas` (sem mudança), depois
  `aplicar_templates_fichas_da_planilha` (que escreve a linha de início e confere a regra 8),
  depois o resumo.

## 8. O que não muda

- A montagem da ficha: template, linha 79, mesclas, fonte, altura, bordas, renomear a aba no
  inglês, salvar com `retry_lock`.
- `processar_pastas_fichas`, a leitura do `_STATUS_PMIB`, os modos de seleção (todos/manual) e
  de saída (planilhas/subpastas).
- O método antigo da aba 2, com as mesmas mensagens, salvo a escolha por revisão quando há
  mais de um arquivo do mesmo PDM.
- A tradução para inglês e a aba "Excluir Duplicados".
- O ranqueamento e tudo que o módulo 1 lê do `pdm_catalogo`.

## 9. Verificação

**Suíte (`bash scripts/check.sh`, verde antes de cada commit):**
- `pdm_catalogo`: características da vigente, na ordem da `SECUENCIA`; nome e ajuda verbatim;
  ajuda vazia vira `""`; `linha` certa; identidades de um código duplicado; `exportado_em`;
  `origem`; formato manipulado sem características, identidades nem data; `caracteristicas` do
  ranqueamento idêntico ao de antes.
- `pdm_planilha`: `montar_pergunta` com ajuda presente, `None`, `NaN`, `""`, `"nan"`; cada uma
  das regras 1 a 9; `nome_de_arquivo` com `/` e sem revisão; `revisao_no_nome` nos dois tipos
  de arquivo e em nome sem revisão.
- `pdm` (openpyxl real, pelo mesmo fixture de `test_pdm_montador_idioma.py`): a ficha pela
  planilha tem as perguntas a partir da C79, mescladas, na ordem da `SECUENCIA`, sem `(nan)`;
  o PDM recusado vira falha no resumo e o lote segue; os avisos de revisão aparecem no fim; no
  método antigo, com dois arquivos do mesmo PDM, vence o de revisão mais alta, com aviso.
- `pdm_regeneracao` (openpyxl real): nomes com revisão; conteúdo da From Itaipu (cabeçalho,
  linhas em ordem, estilo copiado, larguras, mescladas, painel, autofiltro); conteúdo da
  Modificados; versão antiga movida para `_versoes_antigas`; nome repetido lá; já em dia é
  pulado; desistência do `retry_lock` não grava o novo; pastas iguais recusadas.
- Tela (por AST, como os testes de tela de hoje): o rádio de fonte existe com o padrão
  planilha; planilha + English é recusado; a tela chama os serviços novos; nenhuma regra de
  negócio na tela.
- Os testes de hoje do módulo (`test_pdm_io`, `test_pdm_montador_idioma`,
  `test_pdm_relatorio_lote`, `test_traducao_pdm`) passam **sem alteração**.

**Com a planilha real (fora da suíte; a planilha da Itaipu não entra no repositório):**
- Montar fichas de uma amostra de PDMs pelos dois métodos e comparar: mesmas perguntas, só a
  ordem e o `(nan)` diferentes; os dois duplicados tratados pela regra 6.
- Regenerar as duas pastas inteiras e medir o tempo. Conferir, pela impressão digital de
  `scripts/gerar_baseline_pdm.py`, que cada arquivo novo da From Itaipu tem as mesmas células
  (valor e estilo) que o fatiamento antigo produzia para aquele PDM, a menos da ordem das
  linhas.

**Tela:** `compileall` e `pyflakes` nos arquivos tocados. Abrir o app, se o contêiner tiver
tkinter e tela virtual; se não tiver, o passo entra no roteiro manual e o relato diz que não foi
aberto.

## 10. Documentação e registros

- `docs/base-conhecimento/02-pdm-backend.md` e `13-montagem-da-ficha-tecnica.md`: a fonte
  planilha, a regeneração, as regras.
- `docs/refatoracao/PENDENCIAS.md`:
  - fechar a pendência de 2026-08-18;
  - registrar os 6 nomes com parênteses (o Tradutor 4.2 corta no primeiro `(`, e o 4.3 não
    casa `(CA)`/`(CC)`; é defeito anterior a este trabalho);
  - registrar os 2 códigos duplicados na exportação da Itaipu;
  - registrar a aposentadoria futura do "Fatiar" antigo;
  - registrar que o `tech_specs` segue com um leitor próprio da planilha.
- `docs/ROTEIRO_DE_TESTE.md`: o passo 3.4 ganha os dois caminhos novos.
- `CHANGELOG.md`: linhas no bloco 1.1.0 (ainda não publicada; `VERSAO` é 1.0.0), escritas
  para quem usa.

## 11. Fora do escopo

- Ficha em inglês direto da planilha (D3).
- Aposentar os passos antigos "Fatiar"/"Formatar".
- Corrigir o corte no primeiro `(` do Tradutor (4.2) e do Upload Specs (4.3).
- Levar o `tech_specs` a ler a planilha pelo `pdm_catalogo`.
- Gravar a revisão dentro da ficha (numa célula do template).
- Resolver os códigos duplicados. É dado da Itaipu; o app só não os mistura mais.
