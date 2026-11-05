# DocPack — a pasta de cada lista nova de sobressalentes

Aba **Etapa 1 — Estrutura** do módulo DocPack (menu 8.2, `sigft/app_qt/views/docpack_secao.py`, desde 2026-11-04; antes era a aba DocPack do PMIB Manager). A tela é `sigft/app_qt/views/docpack.py`, sobre o serviço
`sigft/services/docpack.py`. Pedido do Jonathan em 2026-11-03; desenho em
`docs/superpowers/specs/2026-11-03-docpack-design.md`.

## O que faz

Para cada lista de sobressalentes que ainda não tem `_STATUS_PMIB`, cria a pasta (o
"dossiê") com os templates que ela vai precisar:

```
<raiz>/<ET>/[<capítulo>/][<sistema>/][<subsistema>/][<pasta final>/]
    <código>_STATUS_PMIB.xlsx            A3 = ET / CAPÍTULO / SUBSISTEMA | CÓDIGO / CMI | EVENTOS
                                         A4 = linha da revisão em uso, com a data de hoje
    LMR/Aplicação LMR - <subsistema>.xlsx DOCS DE REFERENCIA: lista, ET / capítulo, subsistema
    IMAGENS/
    DATASHEETS/
```

**A hierarquia das pastas** (corrigida pelo Luan em 2026-11-04): a primeira pasta da raiz
é a **ET** (`03 - EBOP`, `05 - UNIDADE GERADORA`); dentro dela o **capítulo**; dentro do
capítulo, o **sistema** e o **subsistema**; a pasta final é opcional. Só a ET é
obrigatória, com mais uma pasta qualquer abaixo dela; nível vazio é pulado. `/` numa
célula põe **mais uma pasta naquele passo** (`MANCAIS/GUIA`). O dossiê é a última pasta
do caminho. O SUBSISTEMA do A3 e da Aplicação LMR é a pasta do subsistema; sem ela, a
pasta final; sem as duas, a última pasta (`docpack.nome_do_subsistema`). A ET e o
capítulo do A3 vêm da mapeadora (colunas I e J), que é a fonte de verdade: o nome da
pasta nem sempre é o da ET.

## Entradas

- **Mapeadora** (`conferencia_revisoes.ler_mapeadora`, que desde 2026-11-03 lê também
  `N° DOCUMENTO CMI`, `DESCRIÇÃO`, `ESPECIFICAÇÃO TÉCNICA`, `CAPÍTULO` e `EVENTOS DE
  PAGAMENTOS RELACIONADOS`, quando existem).
- **Pasta raiz** (`SOBRESSALENTES - PMIB`; padrão `prefs.get_default_dir("sobressalentes_pmib")`).
- **Templates** do Box `15 - PDM/Templates`, achados pelo nome conhecido
  (`docpack.NOMES_TEMPLATE`) ou escolhidos na tela; cada um é lembrado.

## Regras

- **Quais listas** (`listas_sem_status_pmib`): PB020 no código (com ou sem o `-0x` do
  SMF), sem PREÇO no título, sem LINK DA PLANILHA e sem `_STATUS_PMIB` vivo com o mesmo
  código na raiz (`status_pmib_arquivos.listar`).
- **A lista com preço não é do DocPack** (2026-11-05, pedido do Jonathan: o agente do
  webhook não olha para ela). Ela é criada e preenchida pelo módulo **Lista de Preços**
  (`16-lista-de-precos.md`), que também tem o `codigo_lista_de_precos`.
- **Nunca sobrescreve**: arquivo que já existe fica (⚠️); lista com `_STATUS_PMIB` vivo
  é pulada (❌). Pasta com nome inválido no Windows é recusada antes de criar.
- **Template copiado byte a byte e editado no XML** (`core/excel/cirurgico.py`): as
  validações em extensão e os nomes definidos do `_STATUS_PMIB` saem intactos.
- **Da mapeadora, só o LINK DA PLANILHA vazio** (2026-11-05, `docpack.gravar_links`): depois de criar, o
  DocPack grava o "Abrir Box" (relativo à pasta da mapeadora, como o Gestão PMIB) de cada dossiê novo, para a
  Conferência de Listas achá-lo já. Link que existe não é trocado; mapeadora aberta no Excel pede para fechar.
  SITUAÇÃO NO PMIB e REVISÃO EM USO continuam com o Gestão PMIB.
- **As tabelas das duas etapas rolam de lado** (2026-11-05): cada coluna cresce até caber o texto
  (`dialogos_selecao.ajustar_ao_conteudo`), e o que não cabe na tela tem a barra horizontal.
- Pasta dentro de `00 - OBSOLETO`, testes ou backup: cria, com o aviso de que ali o
  `_STATUS_PMIB` não conta como vivo.

## A tela

Mapeadora e pasta raiz; os três templates; **Listar sem _STATUS_PMIB**; a tabela
(marcar a lista; ET, capítulo, sistema, subsistema e pasta final com dois cliques, numa
lista editável com as pastas que já existem naquele nível, dentro das escolhidas à
esquerda (`docpack.arvore_existente` + `opcoes_do_nivel`), ou com um nome novo); **Sugerir com IA** (tarefa `docpack_pasta`, prompt
`prompts.montar_docpack_pasta`, que devolve `{et, capitulo, sistema, subsistema, pasta}`
-- a resposta do formato de antes, sem `et`, ainda é lida -- e preenche os campos das
linhas marcadas, nunca cria; a IA dessa tarefa se escolhe no botão **Configurar IA** do
cabeçalho do DocPack, entrada "Etapa 1: Estrutura" -- a "Etapa 2: Conteúdo" é o webhook
do workflow da Etapa 2 (2026-11-05) --, o mesmo da janela "Modelos de IA": `sigft/app/ia_por_modulo.py`);
**Pré-visualizar** (o plano no console, sem tocar no disco); **Criar dossiês** (o plano,
a pergunta Sim/Não e a criação, com o log ✅/⚠️/❌ e o resumo); **Parar** (entre as listas).

## O que vem depois

A Etapa 2 (`15b-docpack-etapa2.md`) baixa a última revisão da lista e preenche o
`_STATUS_PMIB` pela análise do AMP. A lista com preço vem depois, no módulo Lista de Preços.

## Não verificado aqui

Os templates reais do Box (o da Aplicação LMR não tem cópia no repositório: os rótulos
da aba DOCS DE REFERENCIA vêm da documentação) e o Excel/Windows abrindo os arquivos.
