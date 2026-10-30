# Caderno do módulo Upload de Fotos (RPA no PMIB)

> Aberto em 2026-10-30, numa sessão na web. O desenho abaixo foi combinado com
> o usuário; a parte de portal fica para uma sessão LOCAL com o navegador
> ligado por MCP (`docs/OLHAR_O_PORTAL.md`). Nenhum código foi escrito ainda.

## O que o módulo faz

Sobe as fotos dos materiais de um subsistema nas fichas do PMIB (aba
"Documentos e imagens", em edição) e atualiza a coluna `DOCUMENTOS E IMAGENS`
(`config.COL_DOCS_IMAGENS`) da `_STATUS_PMIB` daquele sistema.

## Decisões do usuário

1. **Fotos:** uma pasta por subsistema. O NOME do arquivo já é a legenda:
   4 últimos dígitos do código PMIB + letra em ordem alfabética --
   `0052.jpg`, `0052a.jpg`, `0052b.png`, depois `0053.jpg`… A ordem de subida
   é `0052`, `0052a`, `0052b`.
2. **Ligação foto → ficha:** os 4 dígitos casam com o fim do código PMIB na
   `_STATUS_PMIB` escolhida. Dois códigos com os mesmos 4 dígitos (contratos
   diferentes) = ambíguo: vai para o relatório, NUNCA se adivinha.
3. **Descrição da foto no portal:** o nome sem extensão (`0052a`), em PT e ES.
4. **Fichas que já têm foto -- opção por sistema, escolhida na tela:**
   - *Excluir todas antes*: apaga as fotos existentes e sobe as da pasta;
   - *Perguntar por ficha*: pausa (callback `ask`) e oferece excluir e subir /
     adicionar mesmo assim / pular.
5. **STATUS PMIB:** o usuário escolhe o arquivo na tela (seletor com memória,
   `sigft/app_qt/file_dialogs.py`).
6. **Coluna `DOCUMENTOS E IMAGENS`:**

   | Fotos | Documentos na ficha | Grava |
   |---|---|---|
   | todas subiram | há | `COMPLETO` |
   | todas subiram | não há | `INCOMPLETO` + **nota de célula** "Faltam documentos" |
   | alguma falhou | -- | não toca; a falha vai para o log |

   Nota de célula REAL (o balão do Excel), escolha do usuário. O editor
   cirúrgico (`core/excel/cirurgico.py`) ainda não sabe criar nota -- ensiná-lo
   sem estragar os comentários em thread que as planilhas já têm. `wb.save`
   do openpyxl está proibido aqui (apaga esses comentários; ver
   `core/excel/status_sheet.py`, "Gravação sem perda").

## O que já existe e se reaproveita

- `services/duplicadas_imagens.py`: `subir_uma`, `esperar_processamento`,
  `fechar_formulario`, `extensao_de` -- o upload pelo FilePond, já validado no
  portal real.
- `core/rpa/seletores_duplicada.py`: `XPATH_IMAGENS_*`, `ABA_DOCUMENTOS_EDICAO`.
- `services/duplicadas_extrator.py`: `abrir_secao`, `id_do_painel`.
- `services/duplicadas_documentos.py`: `ja_associados(portal, escopo)` -- lê os
  documentos da ficha em edição.
- `PMIBPortal.pesquisar_e_abrir`, `aguardar_login_manual`, `clicar_e_confirmar`.
- `core/excel/status_sheet.StatusPMIB` (+ `VALOR_COMPLETO`/`VALOR_INCOMPLETO`).

## O que só o portal responde (primeira tarefa da sessão local)

Na ficha aberta em EDIÇÃO, aba "Documentos e imagens", com foto E documento:

1. Como as fotos que já existem aparecem em edição (lista? tabela? carrossel?)
   e qual seletor as conta.
2. Como se exclui uma foto: o botão/lixeira e o diálogo de confirmação
   (`role='dialog'`, §3 de `PORTAL_COMO_ELE_SE_COMPORTA.md`) e a mensagem de
   sucesso -- para entrar em `PALAVRA_DA_SECAO` se for outra.
3. Se as fotos têm coluna "Descrição" no mesmo painel: aí `ja_associados`
   contaria foto como documento, e o escopo precisa separar as duas tabelas.
4. A legenda da foto existente é legível (para o modo *Perguntar* mostrar
   quais fotos a ficha já tem)?

## Ordem sugerida

1. Sessão local: responder as 4 perguntas acima no DOM real.
2. Serviço `sigft/services/upload_fotos.py` com TDD: montar o lote (parse dos
   nomes, ligação pela STATUS, ambíguos), regra da coluna, depois o laço RPA.
3. Nota de célula no `cirurgico.py`, com teste que prova que os comentários em
   thread existentes sobrevivem.
4. Tela `sigft/app_qt/views/upload_fotos.py` + registro em `TELAS`,
   `catalogo.MENU`, `catalogo.MODULOS`, `conferencia.MODULOS_ESSENCIAIS`;
   textos em `t()` com tradução es/en.
5. Execução real numa ficha de teste antes de declarar pronto.
