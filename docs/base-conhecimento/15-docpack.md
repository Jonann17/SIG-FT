# DocPack — a pasta de cada lista nova de sobressalentes

Aba **DocPack** do PMIB Manager (`sigft/app_qt/views/docpack.py`), sobre o serviço
`sigft/services/docpack.py`. Pedido do Jonathan em 2026-11-03; desenho em
`docs/superpowers/specs/2026-11-03-docpack-design.md`.

## O que faz

Para cada lista de sobressalentes que ainda não tem `_STATUS_PMIB`, cria a pasta (o
"dossiê") com os templates que ela vai precisar:

```
<raiz>/<capítulo>/[<sistema>/]<pasta final>/
    <código>_STATUS_PMIB.xlsx            A3 = ET / CAPÍTULO / SUBSISTEMA | CÓDIGO / CMI | EVENTOS
                                         A4 = linha da revisão em uso, com a data de hoje
    <código PB021>.xlsm                  Capa F37 = código PB021; E27 = título + " - LISTA DE SOBRESSALENTE COM PREÇO"
    LMR/Aplicação LMR - <pasta>.xlsx     DOCS DE REFERENCIA: lista, ET / capítulo, subsistema
    IMAGENS/
    DATASHEETS/
```

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
- **Código da lista com preço** (`codigo_lista_de_precos`): o DCC PB020 do fim vira
  PB021; o `-0x` antigo sai.
- **Nunca sobrescreve**: arquivo que já existe fica (⚠️); lista com `_STATUS_PMIB` vivo
  é pulada (❌). Pasta com nome inválido no Windows é recusada antes de criar.
- **Template copiado byte a byte e editado no XML** (`core/excel/cirurgico.py`): as
  validações em extensão e os nomes definidos do `_STATUS_PMIB`, e o VBA da lista com
  preço, saem intactos.
- **A mapeadora não é gravada**: o log manda rodar o Gestão PMIB, que liga o
  `_STATUS_PMIB` novo (LINK DA PLANILHA).
- Pasta dentro de `00 - OBSOLETO`, testes ou backup: cria, com o aviso de que ali o
  `_STATUS_PMIB` não conta como vivo.

## A tela

Mapeadora e pasta raiz; os três templates; **Listar sem _STATUS_PMIB**; a tabela
(marcar a lista; capítulo, sistema e pasta final com dois cliques, com as pastas que já
existem como sugestão); **Sugerir com IA** (tarefa `docpack_pasta`, prompt
`prompts.montar_docpack_pasta`: preenche os campos das linhas marcadas, nunca cria);
**Pré-visualizar** (o plano no console, sem tocar no disco); **Criar dossiês** (o plano,
a pergunta Sim/Não e a criação, com o log ✅/⚠️/❌ e o resumo); **Parar** (entre as listas).

## O que vem depois

Com o workflow do AMP ativo: baixar a última revisão da lista e preencher o
`_STATUS_PMIB` e a lista com preço pela análise da IA (PENDENCIAS, 2026-11-03).

## Não verificado aqui

Os templates reais do Box (o da Aplicação LMR não tem cópia no repositório: os rótulos
da aba DOCS DE REFERENCIA vêm da documentação) e o Excel/Windows abrindo os arquivos.
