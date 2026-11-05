# Lista de Preços — o arquivo da lista com preço de cada sistema

Módulo 8.3 do menu (Gestão), desde 2026-11-05. Pedido do Jonathan: a lista com preço saiu do
DocPack (o agente do webhook não olha para ela) e virou módulo próprio.

| Onde | O quê |
|---|---|
| `sigft/services/lista_precos_arquivo.py` | achar, criar, preencher, conferir e atualizar (sem Qt) |
| `sigft/app_qt/views/lista_precos.py` | `ModuloListaPrecos` (a seção) com `ModuloListaPrecosCriar` e `ModuloListaPrecosConferir` em abas, um console e uma barra |
| `sigft/app/como_funciona.py` | `ListaPrecos.criar` e `ListaPrecos.conferir` |

Não confundir: `services/lista_precos.py` é o **pareamento no Aconex** (que lista de
sobressalentes cada lista de preços copia) e `services/lista_precos_planilha.py` é a aba
"Lista de preços Follow-up" da mapeadora. Este módulo é o **arquivo** `.xlsm` da pasta.

## Criar / preencher (varredura)

- Pasta raiz (padrão `SOBRESSALENTES - PMIB`) e o template (padrão `Box/15 - PDM/Templates/Lista
  de Sobressalentes com preço.xlsm`; lembrado em `lista_precos.template`).
- **Procurar sistemas** (`varrer`): um sistema por `_STATUS_PMIB` vivo
  (`status_pmib_arquivos.listar`). Na pasta dele, a lista com preço é o `<código PB021>` ou,
  senão, qualquer arquivo com `PB021`/`PB020-0x` no nome que não seja `_STATUS_PMIB` (a regra do
  `painel.ler_listas_precos`); `PB020-0x` aparece como **legado**.
- Só os sistemas **sem** lista ganham caixa (marcada). **Criar listas com preço** (`criar_listas`):
  - copia o template como `<código PB021>.xlsm` com `open(..., "xb")`: **nunca sobrescreve**;
  - Capa **F37** = código PB021; **E27** = DESCRIÇÃO da mapeadora (se a mapeadora lembrada abrir),
    senão o nome da pasta, + `" - LISTA DE SOBRESSALENTE COM PREÇO"`;
  - os materiais do `_STATUS_PMIB` vão para a aba "Lista de Materiais", um por linha, ITEM
    renumerado; **VALOR UNITÁRIO vazio** (preço nunca se inventa); arquivo que falha no meio é
    apagado.
- Colunas: `_STATUS_PMIB` (ITEM, QTD., UNID., DESCRIÇÃO, CÓDIGO DO MATERIAL, MARCA/MODELO, CÓDIGO
  PMIB, TIPO DE ENTREGA) → lista (ITEM, QTD., UNID., DESCRIÇÃO, FABRICANTE / MODELO, CÓDIGO DE
  MATERIAL, CÓDIGO GE, CÓDIGO PMIB, VALOR UNITÁRIO, TIPO DE ENTREGA). O cabeçalho se acha pelo
  texto (`docpack_etapa2.achar_cabecalho`).

## Conferir (UMA pasta)

- **Pasta do sistema** (com um `_STATUS_PMIB` só) → **Conferir** (`conferir`):
  - os itens casam pela **chave** (`Item.chave`): CÓDIGO PMIB normalizado; sem ele, o código de
    material; sem os dois, a descrição;
  - divergências: `falta na lista`, `sobra na lista` e `diferente` (QTD., UNID., DESCRIÇÃO);
  - **Abrir a pasta** (`plataforma.abrir_no_sistema`): a conferência humana é no Excel, ali.
- **Lista valorizada** (algum VALOR UNITÁRIO preenchido) **e** com divergências: aviso fixo na
  tela ("Lista já valorizada e com divergências com o _STATUS_PMIB").
- **Atualizar a lista** (`atualizar`): pede confirmação (mais forte se valorizada) e reescreve os
  materiais pelo `_STATUS_PMIB`:
  - o item que continua **mantém** VALOR UNITÁRIO, CÓDIGO GE e TIPO DE ENTREGA da lista;
  - item novo entra sem preço (➕ no log); o que saiu do `_STATUS_PMIB` sai da lista (➖ no log);
  - as linhas antigas que sobram são limpas (menos o ITEM numerado do template);
  - planilha aberta no Excel: pergunta para fechar (`perguntar_retry_excel`).

## Regras

- **Escrita no XML** (`core/excel/cirurgico.py`): o openpyxl só lê; o VBA (`xl/vbaProject.bin`)
  sai byte a byte (teste).
- **Uma implementação por conceito:** `codigo_lista_de_precos` mora aqui (saiu do DocPack); a
  leitura das abas reusa `docpack_etapa2` (`_ler_aba`, `achar_cabecalho`, `_normalizar`).
- Tabelas com a barra de rolagem horizontal (`dialogos_selecao.ajustar_ao_conteudo`).

## Não verificado aqui

Os templates reais do Box e os arquivos gerados abertos no Excel do Windows (só openpyxl e
comparação do zip). A Capa usa as células do template do repositório (F37/E27): se o do Box
for outro, conferir.
