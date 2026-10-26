# Aconex ao vivo — caderno da frente

Para quem continuar esta frente, gente ou Claude. Diz onde ela parou, o que
falta, o que já foi decidido e onde se tropeça. O comportamento de cada peça está
em `docs/base-conhecimento/14-aconex-e-conferencia-de-revisoes.md`; o porquê, no
desenho.

| Documento | O quê |
|---|---|
| `docs/superpowers/specs/2026-10-26-aconex-ao-vivo-design.md` | o desenho aprovado pelo Luan (a autoridade) |
| `docs/superpowers/plans/2026-10-26-aconex-ao-vivo.md` | o plano: 12 tarefas, com os testes de cada uma |
| `docs/base-conhecimento/14-aconex-e-conferencia-de-revisoes.md` | o que o código faz hoje |
| `docs/ROTEIRO_DE_TESTE.md`, Etapa 5b | o teste na GE (portões G1 e G2) |
| `docs/refatoracao/PENDENCIAS.md`, seção 2026-10-26 | pendências desta frente |

## O que é

A peça 1 do workflow que avisa quando uma lista de sobressalentes muda entre
revisões. A peça 2, que lê os PDFs e diz o que mudou, roda no AMP da GE (IA
interna + n8n), porque documento do projeto não pode ir para IA de fora. A ordem
combinada com o Luan: (1) cliente do Aconex no SIG-FT, (2) leitura no AMP, (3)
aplicar as mudanças.

## Onde parou (2026-10-26)

**Feito e lançado na 1.3.1-rc.1** (pré-lançamento; PR #24):

| Tarefa | Entregou |
|---|---|
| 1 | Power BI conta a família de aprovação (fora do repositório, ver abaixo) |
| 2 | motor do STATUS REAL copiado do DocManager (`core/aconex/_docmanager/`) e a fachada `status_real.py` |
| 3 | painel de sobressalentes conta a família de aprovação |
| 4 | Gestão PMIB grava o STATUS REAL pela batalha de versões |
| 5 | lista nova só com PB020 no código |
| 6 | leitura do cofre de credenciais do DocManager |
| 7 | cliente do Aconex (token, busca paginada, download) sobre `core/rede` |
| 8 | navegação de páginas igual à do DocManager e o diagnóstico das buscas |
| 9 | serviço da Conferência de Revisões |
| 10 | tela "10. Conferência de Revisões" e o botão "Testar conexão com o Aconex" |

Validação só de leitura na mapeadora real, em 26/10: 95 listas, 47 com link (46
resolvem direto, nenhum codificado com `%`); a conferência deu 4 aprovadas e 1 não
aprovada com divergência, 42 em dia e 48 sem `_STATUS_PMIB`.

**Falta:**

- **Tarefa 11**, Gestão PMIB com o histórico ao vivo. **Parada no portão G1.**
- **Tarefa 12**, fechamento e validação ao vivo (G2). Parte dela já saiu na rc.1:
  o bloco do CHANGELOG, a base de conhecimento e a Etapa 5b do roteiro.
- A peça 2 (AMP), com desenho próprio. O que passa para ela está na §5.6 do
  desenho.

## Como continuar

1. **Rodar a Etapa 5b do roteiro na GE**, com a 1.3.1-rc.1 instalada e o perfil do
   Aconex cadastrado no DocManager **naquela conta do Windows**. A máquina pessoal
   do Luan tem a pasta do DocManager, mas não o `credenciais.json`. O 5b.1 é o G1;
   o resto, a parte do G2 que já dá para testar.
2. **Decidir a Tarefa 11 com as 7 linhas do G1.** O plano manda anotar no topo da
   Tarefa 11 as sintaxes que funcionaram e **avisar o Luan antes de seguir** se a do
   Tracking ID ou a das listas falhar (§4.2 do desenho):
   - funcionaram: o `FonteAoVivo.carregar` usa a busca exata de cada código, segue o
     Tracking ID e traz as candidatas a lista nova pelas sintaxes do G1;
   - falharam: o `carregar` usa a extração completa (`cliente.buscar("",
     historico=True)`), com a mesma interface. Custa cerca de **30 min por
     rodada** (medido no DocManager), e o SIG-FT não tem o checkpoint de retomada
     dele: uma queda no meio recomeça do zero.

   No meio da Tarefa 8 o Luan pediu "aplicar o conhecimento que já existe no
   DocManager" em vez de testar função nova. Isso pode querer dizer pular o G1 e
   ir direto para a extração completa. **Pergunte antes de decidir.**
3. **Tarefa 11**, como está no plano: `sigft/services/historico_aconex.py`
   (`FonteHistorico`, `FonteExtrato`, `FonteAoVivo`, `fonte_padrao`),
   `PMIBManager.executar_fluxo(..., fonte=)`, o Passo 1 opcional na tela do Gestão.
   Reaproveite `perfil_do_aconex` (`app_qt/views/conferencia_revisoes.py`), o
   `ClienteAconex` e o `cliente.tabela`, que já monta o extrato do DocManager com as
   colunas e a ordem dele. Sem conexão, o fluxo para **antes de gravar** qualquer
   coisa e pede o extrato.
4. **Tarefa 12**: os itens 2 (ao vivo e extrato dão a mesma mapeadora, em cópias) e
   7 (máquina sem cofre pede o extrato) do G2 entram na Etapa 5b; a
   `11-pmib-manager-backend.md` ganha a fonte ao vivo; o bloco da próxima versão
   vai no CHANGELOG.
5. **Release:** `.claude/skills/sigft-lancar-versao/`. O próximo pré-lançamento
   desta versão é a `1.3.1-rc.2`. Release normal só com o "sim" explícito do Luan.

## Decisões já tomadas

Cada uma com o que custa se estiver errada. Desfazer qualquer uma é uma mudança
pequena.

- **Navegação de páginas = a do DocManager** (pedido do Luan): sem limite de
  páginas; 5 tentativas com 5/15/30/60 s; 401 renova sem gastar tentativa; fim no
  400, na página vazia ou curta. Trocou o que o plano tinha fixado (401 uma vez;
  503 com 5/15/45 s). *Custo:* um 401 permanente leva cerca de 2 min para virar erro.
- **O download renova o token uma vez no 401.** O DocManager baixa logo depois de
  autenticar; aqui o cliente pode durar mais que o token. *Custo:* nenhum.
- **Diagnóstico no molde da sonda do DocManager:** uma página e o `TotalResults`
  por sonda, e a sonda "Register inteiro" como referência para dizer se a sintaxe
  filtrou. A busca exata vazia pula só as sondas do Tracking ID. *Custo:* uma
  requisição a mais.
- **A Home rola com 13 cartões** numa janela de 1280x850. Os 12 cabiam sem rolar
  (decisão de 07/10). `test_medidas_da_home` foi atualizado com o porquê. **Está
  para rever com o Luan:** encolher os cartões, ou juntar a Conferência ao PMIB
  Manager. *Custo:* a Home rola.
- **Sem perfil, ou com o login recusado,** a conferência mostra as listas e só
  avisa no console (`[AVISO]`, que entra no resumo do fim do lote). *Custo:* o
  aviso não salta numa caixa.
- **A mapeadora sem uma das 6 colunas não abre na conferência**, e a mensagem diz
  qual falta. Sem o STATUS REAL, tudo cairia calado em "outros".
- **Lista sem ÚLTIMA REVISÃO EMITIDA também tenta baixar**, porque a mapeadora pode
  estar atrasada. *Custo:* uma linha "falhou" por lista NÃO EMITIDO com
  `_STATUS_PMIB`.
- **STATUS REAL com histórico incompleto** (sem `Versão` ou `Status da Revisão`):
  `[AVISO]`, e o STATUS REAL não é gravado; os metadados seguem. O extrato sintético
  do kit de teste do Gestão (`gestao-sobressalentes/_gestao_v2/gerar_kit_teste_sigft.py`
  e a cópia no cofre) ganhou essas duas colunas.
- **`prefs.ultima_pasta(chave)`**: a conferência começa na pasta raiz do Gestão
  PMIB sem cair "na última pasta qualquer", porque a varredura do Box seria nela.
- **Power BI, entrega cirúrgica no Box:** foi remendado só o `Listas.tmdl` (a
  coluna "Lista Aprovada" e as medidas "Listas Aprovadas EN.DT" e "Listas Aprovadas
  sem Fichas"), porque o modelo do Box foi salvo pelo Desktop e tem edições que o
  `entregar_no_box.py` apagaria. Validado: 93 listas, 67 aprovadas, 25 aprovadas sem
  fichas, antes e depois. *Custo:* o `.pbix` do Box continua com as medidas antigas
  até alguém reexportá-lo.
- **Revisão do ramo:** feita pelo próprio autor, sem subagente (o Luan pediu
  execução direta); nada crítico nem importante. O código copiado do DocManager não
  foi relido linha a linha: é cópia fiel, coberta pelos 14 testes portados.

## Pendências menores

Também em `PENDENCIAS.md` (2026-10-26). Nenhuma impede o uso.

- `pmib_manager.historico_do_documento`: Tracking ID vazio na linha do código dá
  histórico vazio, e o STATUS REAL vira NÃO EMITIDO; devia cair nas linhas do
  próprio código.
- Tela da Conferência: a barra de progresso não volta a zero entre rodadas; "Parar"
  fica habilitado sem download rodando; a escolha de perfil pode aparecer mesmo sem
  nada a baixar; em "Testar conexão", desistir da escolha cai na mensagem "Nenhum
  perfil do Aconex neste Windows".
- Cliente: as esperas do backoff (5 a 60 s) não são interrompidas pelo "Parar", que
  age entre as listas.

## Onde se tropeça

- **O CI roda o `ruff` antes do pytest.** Duas tarefas desta frente quebraram o CI
  com f-string sem campo (F541), com a suíte local verde. Antes de subir:
  `python -m ruff check .` além do `bash scripts/check.sh`.
- **Tela nova mexe em guardas espalhadas.** Além de `main.TELAS` e do `catalogo.py`
  (menu, ícone, cartão): `tests/test_qt_catalogo.py` (valores travados),
  `tests/test_tela_correcao_pdm.py` (as telas da seção Gestão),
  `tests/test_textos_da_interface.py` (`CONVERTIDOS`),
  `sigft/app/conferencia.py` (`MODULOS_ESSENCIAIS`, a conferência do pacote),
  `tests/test_qt_home_paineis.py` (medidas da Home, se o número de cartões muda),
  as traduções (`python tools/textos_da_interface.py --faltando es` e `en`) e
  nenhuma área rolando de lado (`test_qt_idioma_varredura.py`, `test_qt_letra.py`).
  Termine com `QT_QPA_PLATFORM=offscreen python frontend.py --smoke`.
- **`core/aconex/_docmanager/` é cópia.** Mudança no motor nasce no DocManager e vem
  copiada, com o cabeçalho de origem. O pacote compartilhado está nas pendências.
- **O `conftest.py` dubla pandas e openpyxl.** Teste que precisa dos de verdade usa
  `tests/_pandas_de_verdade.py` ou `tests/_openpyxl_de_verdade.py`; módulo que
  calcula algo do pandas no import (o `constants.py` copiado) é recarregado dentro
  do bloco.
- **O Release no Windows roda sem o teste de medidas da Busca PMIB** (`--deselect`
  no `release.yml`, desde 26/10): o worker do runner caía nele (access violation no
  `MenuDeOpcoes.paintEvent`) em toda tentativa da 1.3.1-rc.1, e uma vez no CI do
  Ubuntu. A causa está em
  aberto no `PENDENCIAS.md`; antes de um release normal, o `--deselect` sai.
- **Na máquina pessoal do Luan:** os venvs do `%TEMP%` são corrompidos pela limpeza
  do Windows; os testes rodam num Python 3.13 com PySide6 fora do `%TEMP%`. Dois
  testes do tradutor (`test_caminho_longo_*`) falham lá por caminho longo e passam
  no CI.
- **O Aconex:** a busca exata exige o código **entre aspas**; sem
  `show_document_history`, o register devolve só a versão corrente; os limites de
  uso voltam como HTTP 503. Antes de inventar uma chamada, procure no DocManager
  (`docmanager/aconex_backend.py`, `knowledge_base_docmanager.md` §18.2 e §28,
  `tools/probe_*.py`). Basic Auth e Integration IDs saem no começo de 2027; o
  DocManager e o SIG-FT já usam OAuth.

## Fora do repositório

- **DocManager** (`luanccozer/DocManager`, privado): de onde vieram o motor, o
  cofre e a navegação (commit `c9683d2`).
- **Power BI v2:** no cofre Obsidian do Luan (`_gestao_v2/powerbi/`) e, entregue, no
  Box, em `SOBRESSALENTES - PMIB\Sobressalentes (Power BI)`.
- **Segurança:** o repositório ficou público por um tempo para o Release. Ao voltar
  a privado, troque o `UPDATE_TOKEN` (`docs/BUILD.md`, "Rotação do token") e confira
  que ele é fine-grained, só de leitura e só deste repositório: quem guardou um
  `.exe` desse período consegue tirar o token de dentro dele. A varredura de 26/10
  não achou chave nenhuma no histórico.
