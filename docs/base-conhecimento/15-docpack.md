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

**Uma pasta, um dossiê** (decisão do Luan, 2026-11-09): duas listas nunca dividem a pasta
final. `docpack.planejar` recusa a pasta que já tem o `_STATUS_PMIB` de outra lista
("cada lista tem a sua pasta"; o `~$` do Excel aberto não conta), venha o destino da IA
ou da mão; dividindo, as duas misturariam LMR, IMAGENS e DATASHEETS.

## Entradas

- **Mapeadora** (`conferencia_revisoes.ler_mapeadora`, que desde 2026-11-03 lê também
  `N° DOCUMENTO CMI`, `DESCRIÇÃO`, `ESPECIFICAÇÃO TÉCNICA`, `CAPÍTULO` e `EVENTOS DE
  PAGAMENTOS RELACIONADOS`, quando existem).
- **Pasta raiz** (`SOBRESSALENTES - PMIB`; padrão `prefs.get_default_dir("sobressalentes_pmib")`).
- **Templates** do Box `15 - PDM/Templates`, achados pelo nome conhecido
  (`docpack.NOMES_TEMPLATE`) ou escolhidos na tela; cada um é lembrado.

## Regras

- **Quais listas** (`listas_sem_status_pmib`): PB020 no código (com ou sem o `-0x` do
  SMF), sem PREÇO no título, sem LINK DA PLANILHA, sem `_STATUS_PMIB` vivo com o mesmo
  código na raiz (`status_pmib_arquivos.listar`) e **já saída no Aconex**.
- **Só a lista que já saiu no Aconex** (2026-11-09, pedido do Luan, depois de criar
  dossiês de listas que nem tinham saído: "se a lista de sobressalentes ainda nem foi
  emitida, não quero criar o DocPack dela"). `docpack.motivo_nao_emitida` lê o que o
  último Gestão PMIB deixou na mapeadora e deixa de fora, nesta ordem:
  1. STATUS REAL **NÃO EMITIDO** (`status_real.eh_nao_emitido`, sem acento e sem caixa):
     a batalha de versões do DocManager não achou emissão que valha, por exemplo a lista
     que só passou pela integração ou cuja primeira emissão foi cancelada;
  2. STATUS DA REVISÃO **LISTA NÃO EMITIDA** (`pmib_manager.LISTA_NAO_EMITIDA`, a marca
     que a cascata da SITUAÇÃO NO PMIB já conhecia);
  3. sem ÚLTIMA REVISÃO EMITIDA;
  4. sem STATUS REAL: não dá para saber, e a lista espera o Gestão PMIB (um dossiê a mais
     custa apagar as pastas e o link; esperar custa rodar o Gestão).

  A ÚLTIMA REVISÃO EMITIDA sozinha não basta: ela vem da versão corrente do Aconex, mesmo
  quando o status dela é de integração. Em processo ou não aprovada, a lista saiu e entra.
  As que ficam de fora vão para o console do **Listar**, uma linha por lista com o motivo
  (`listas_nao_emitidas`), e o total da tela diz quantas foram.
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

Mapeadora e pasta raiz; os três templates; **Listar sem _STATUS_PMIB** (com as que ainda
não saíram no Aconex contadas no total e listadas no console); a tabela
(marcar a lista; ET, capítulo, sistema, subsistema e pasta final com dois cliques, numa
lista editável com as pastas que já existem naquele nível, dentro das escolhidas à
esquerda (`docpack.arvore_existente` + `opcoes_do_nivel`), ou com um nome novo); **Sugerir com IA** (tarefa `docpack_pasta`, prompt
`prompts.montar_docpack_pasta`, que devolve `{et, capitulo, sistema, subsistema, pasta}`
-- a resposta do formato de antes, sem `et`, ainda é lida -- e preenche os campos das
linhas marcadas, nunca cria. Desde 2026-11-09 a IA não vê só os nomes das pastas (que não
têm nada a ver com a mapeadora: "SERVIÇOS AUXILIARES ELÉTRICOS" / "CONVERSORES ESTÁTICOS
DE FREQUÊNCIA" mora em `03 - EBOP/SFC`): o **Listar** faz UM levantamento da raiz
(`docpack.levantar`) e guarda o **mapa** de como as listas já estão organizadas
(`docpack.mapa_das_listas`: especificação | capítulo -> a pasta-mãe dos dossiês) e, de
cada lista, as **vizinhas** (`docpack.listas_vizinhas`: a mesma especificação, já com
dossiê; primeiro o mesmo capítulo, depois o mesmo ramo, até 15), que o **Sugerir** manda
junto; o motivo da sugestão diz qual vizinha ela seguiu. A IA dessa tarefa se escolhe no botão **Configurar IA** do
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
