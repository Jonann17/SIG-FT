# Diário de quedas, colunas lembradas e menu recolhível (2026-10-26)

Tanda A das ideias trazidas do Corella Automation (`rafhagmm/Corella_automation`,
o projeto do Rafael), pedidas pelo Jonathan em 2026-10-26. As tandas B (ajuda
para quem começa) e C (o lote que sobrevive ao app fechar) têm spec própria.

Três peças independentes, num PR só: nenhuma toca robô, portal ou serviço, e
todas se provam inteiras aqui (pytest-qt, offscreen).

## 1. Diário de quedas

### Para quê

Quando alguém diz "o SIG-FT fechou sozinho", hoje não há como saber se a
pessoa fechou a janela, se o app caiu ou se foi encerrado de fora. O
`sigft.log` (`core/saida_log.py`) só guarda o `print` do `.exe`.

### Comportamento

- `sigft/core/diario.py` (novo, só biblioteca padrão, nenhum import de
  interface) escreve em `Documentos\SIG-FT\logs\diario.log`
  (`dados_usuario.pasta_logs()`), uma linha por evento, com data e hora:
  - `ABERTURA` na abertura, com a versão (`_build_info.VERSAO`), o idioma e o
    sistema;
  - `FECHAMENTO pela janela` quando a janela principal fecha
    (`SIG_FT_App.closeEvent` aceito);
  - `ERRO NAO TRATADO` com o traceback, por `sys.excepthook` e
    `threading.excepthook` (os robôs rodam em threads).
- Queda dura (o processo morre sem passar pelo Python): `faulthandler` grava o
  rastro em `logs\queda.log`, aberto na abertura e mantido aberto.
- Tamanho: passou de 1 MB, o arquivo vira `diario.log.1` (uma cópia só) e
  recomeça.
- **A sessão anterior** é lida na abertura, ANTES de gravar a nova `ABERTURA`:
  - última `ABERTURA` com `FECHAMENTO` depois dela → **fechou normal**;
  - sem `FECHAMENTO`, e com `ERRO NAO TRATADO` ou `queda.log` não vazio → **caiu**;
  - sem `FECHAMENTO` e sem rastro → **encerrado de fora** (Gerenciador de
    Tarefas, desligamento, falta de luz).
  O `queda.log` da sessão anterior vira `queda.log.anterior` antes de o novo
  ser aberto.
- **Nunca impede a abertura**: pasta sem permissão, disco cheio ou arquivo
  estragado = o diário fica desligado nesta sessão e o SIG-FT abre igual. Nada
  dele levanta.
- Fora do `.exe` (rodando do `.py`) o diário também grava: é lá que se
  reproduz uma queda.
- Nos testes, desligado pelo `conftest` (variável de ambiente, como o aviso do
  Windows); quem testa o diário a tira e usa uma pasta temporária.

### Na Home

Se a sessão anterior **caiu** ou foi **encerrada de fora**, aparece um aviso
no topo da Home (sem janela modal):

- caiu: "Da última vez, o SIG-FT fechou de forma inesperada.";
- encerrado de fora: "Da última vez, o SIG-FT foi encerrado sem fechar a
  janela (pelo Gerenciador de Tarefas ou ao desligar o computador).";
- botões **Abrir o registro** (abre a pasta de logs, `pasta_de_logs.abrir`) e
  **Entendido** (some até a próxima queda).

O aviso aparece uma vez por queda: some ao clicar em "Entendido" ou na abertura
seguinte que fechar normal. Textos por `t()`, com tradução `es`/`en`.

### Testes

Sessão anterior com `FECHAMENTO` → nada na Home; sem `FECHAMENTO` e com
`ERRO NAO TRATADO` → aviso de queda; sem nada → aviso de encerramento de fora;
pasta sem permissão → o app abre e o diário não levanta; arquivo maior que
1 MB → rotação; `threading.excepthook` grava o traceback de uma thread; o
`closeEvent` recusado (tarefa rodando, "Não") não grava `FECHAMENTO`.

## 2. Colunas lembradas

### Onde

As duas tabelas de verdade do SIG-FT: a de seleção de fichas
(`widgets/dialogos_selecao.py`, `TabelaSelecaoDialog`) e a do Resumo do lote
(`widgets/resumo_lote.py`).

### Comportamento

- Largura: arrastar a borda do cabeçalho (já é assim onde não há `Stretch`;
  onde houver, a última coluna continua esticando).
- Ordem: arrastar o cabeçalho (`setSectionsMovable`).
- Esconder: clique direito no cabeçalho abre um menu com cada coluna (marcar /
  desmarcar) e **Restaurar colunas**. A última coluna visível não se esconde.
- Fica lembrado nas preferências (`core/prefs`), pela **chave da tabela** e
  pela **chave interna de cada coluna** (não pelo texto mostrado, que muda com
  o idioma).
- Coluna que deixou de existir é ignorada; coluna nova aparece no fim, visível.
  Preferência estragada = o padrão.

### Como

`sigft/app_qt/widgets/colunas.py` (novo): `instalar_colunas(tabela, chave,
colunas_internas)` liga tudo numa linha; as duas tabelas chamam. Lógica de
juntar a preferência com as colunas de agora em função pura, testada sem Qt.

### Testes

Reordenar e mudar largura → fechar → reabrir igual; esconder → reabrir
escondida; não esconde a última; coluna sumida ignorada; coluna nova no fim;
trocar o idioma não perde o que foi guardado; "Restaurar colunas" volta ao
padrão.

## 3. Menu lateral recolhível

### Comportamento

- Botão no pé do menu (ícone de seta, `icones`) recolhe a barra para só os
  ícones (largura `estilo.LARGURA_BARRA_RECOLHIDA`, ~60 px); clicado de novo,
  volta à largura de hoje.
- Recolhida: a marca vira só o logo; os botões mostram só o ícone, com o nome
  da tela na dica (a dica de hoje vem depois do nome); as seções viram um
  traço fino.
- O item da tela aberta continua destacado.
- Fica lembrado (preferência `menu_recolhido`).
- Ctrl+K ganha "Recolher menu" / "Expandir menu" (nos três idiomas, com as
  palavras em português também buscáveis, como as outras ações).
- A área das telas ocupa o espaço ganho (o layout já estica).

### Testes

Recolher → reabrir recolhido; expandir → todos os nomes inteiros (a varredura
de corte das telas, em pt/es/en e letra Grande); item ativo destacado nos dois
estados; Ctrl+K alterna; cor só por papel (`test_qt_sem_cor_crua`).

## Fora do escopo

Robôs, portal, serviços, a tanda B e a tanda C. Nada muda no `sigft.log`.

## Entrega

Um PR, uma linha no CHANGELOG por peça (bloco da próxima versão, pela skill
`sigft-lancar-versao`), suíte verde em 3.10 e 3.12, smoke em pt/es/en.
