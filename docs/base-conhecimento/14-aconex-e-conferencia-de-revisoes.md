# Aconex no SIG-FT e a Conferência de Revisões

> Escrito em 2026-10-26, na 1.3.1-rc.1. Desenho:
> `docs/superpowers/specs/2026-10-26-aconex-ao-vivo-design.md`. Plano e o que
> falta: `docs/superpowers/plans/2026-10-26-aconex-ao-vivo.md` e
> `docs/ACONEX_AO_VIVO.md`.

## Propósito

É a peça 1 do workflow que avisa quando uma lista de sobressalentes muda entre
revisões (a peça 2, a leitura dos PDFs, roda no AMP da GE). Esta peça faz três
coisas:

1. lê o Aconex **ao vivo**, com o perfil que o DocManager já guarda;
2. calcula o **STATUS REAL** de cada lista pela batalha de versões do DocManager e
   o grava na mapeadora (Gestão PMIB, ver `11-pmib-manager-backend.md`);
3. **confere as revisões**: aponta as listas cuja REVISÃO EM USO ficou para trás
   da ÚLTIMA REVISÃO EMITIDA e baixa os PDFs para a pasta de cada uma.

## Onde mora

| Camada | Arquivo | O quê |
|---|---|---|
| core | `sigft/core/aconex/_docmanager/` | **cópia fiel** de `docmanager/core/` (DocManager@c9683d2): `constants`, `normalize`, `comissionamento`, `excecoes`, `truth_line`, `status_engine`. Não edite aqui sem levar ao DocManager (PENDENCIAS 2026-10-26: trocar por pacote compartilhado) |
| core | `sigft/core/aconex/status_real.py` | a fachada do motor: `status_real_do_documento`, `eh_aprovacao`, `categoria`, `revisoes_iguais`, `ORDEM_DAS_CATEGORIAS`, `colunas_que_faltam` |
| core | `sigft/core/aconex/credenciais.py` | leitura do cofre do DocManager (`PerfilAconex`, `ler_perfis`, `escolher_perfil`, `PREFERENCIA_PERFIL`) |
| core | `sigft/core/aconex/cliente.py` | `ClienteAconex`: token, busca paginada, versões de um código, download; `tabela` monta o extrato do DocManager |
| core | `sigft/core/aconex/diagnostico.py` | as sondas das buscas (`sondar`, `linha`) e a linha de comando |
| core | `sigft/core/rede.py` | `abrir(..., data=)`: o formulário do token passa pela mesma cascata de rede (PAC, Zscaler) |
| core | `sigft/core/prefs.py` | `ultima_pasta(chave)`: a pasta raiz do Gestão PMIB, sem cair em pasta de outra coisa |
| serviço | `sigft/services/conferencia_revisoes.py` | a mapeadora, a regra da conferência e os downloads |
| serviço | `sigft/services/pmib_manager.py` | STATUS REAL e regra PB020 (ver `11-pmib-manager-backend.md`) |
| serviço | `sigft/services/painel.py` | o painel marca `aprov` por lista com `eh_aprovacao` |
| tela | `sigft/app_qt/views/conferencia_revisoes.py` | `ModuloConferenciaRevisoes` (menu 10) e `perfil_do_aconex` |

## Credenciais

- O SIG-FT **só lê** `Documentos\DocManager_Itaipu\credenciais.json` (ou
  `DOCMANAGER_DADOS_DIR`), o mesmo arquivo que o DocManager grava. Esquema:
  `{"usuarios": {nome: {"client_id", "user_id", "secret", "cifrado"}}}`.
- O segredo vem cifrado pela **DPAPI** do Windows, que só decifra na conta que
  cifrou. Perfil de outra conta, incompleto ou ilegível fica de fora, calado:
  `ler_perfis` nunca levanta.
- Um perfil: usa esse. Vários: o preferido (`aconex.perfil` nas preferências do
  SIG-FT); sem preferido, a tela pergunta numa janela (`perfil_do_aconex`) e grava
  a escolha. O DocManager não guarda um perfil "atual" no cofre (a escolha dele é
  só da tela).
- O segredo e o token não vão para log, mensagem de erro, `repr` nem
  preferência. O `rede.abrir` não registra cabeçalho nem formulário.

## O cliente (`ClienteAconex`)

A navegação é a do DocManager (`docmanager/aconex_backend.py`, KB §18.2 e §28).
Não invente outra: ver o mural do `CLAUDE.md`.

- **Token:** `POST https://constructionandengineering.oraclecloud.com/auth/token`,
  `client_credentials`, `Authorization: Basic base64(client_id:secret)` e o
  formulário `grant_type`, `user_id`, `user_site=https://us1.aconex.com`. Projeto
  `1207975853`. O token é pedido na primeira chamada (`conectar`) e reaproveitado.
- **Página** (`_baixar_pagina`): 5 tentativas, com 5, 15, 30 e 60 s entre elas
  (HTTP fora do esperado, XML truncado, rede). O 401 renova o token **sem gastar
  tentativa**, até 3 vezes por página: o token expira no meio de uma extração
  longa. O 400 é o fim normal da paginação. Depois da 5ª tentativa,
  `ErroAconex`: resultado parcial nunca passa por completo.
- **Paginação** (`buscar`): 500 por página, ordenada por `docno`. Acaba no 400, na
  página vazia ou na página com menos itens que o `page_size`. `historico=True`
  manda `show_document_history=true`; sem histórico, o parâmetro nem vai, e o
  register devolve só a versão corrente.
- **Versão vigente** (`versao_vigente`): a busca exata do download do DocManager
  (`_buscar_doc_atual`): código **entre aspas** (sem aspas o register devolve 0),
  sem histórico, uma página de 25. Fica com a `Current`; sem ela, a primeira.
- **Revisão em uso** (`versao`): o histórico do código (aspas, com histórico) e a
  maior versão da revisão pedida, comparada sem caixa nem espaço.
- **Download** (`baixar`): `GET .../register/{DocumentId}/markedup`, 180 s. O 401
  renova o token uma vez.
- **Contar sem paginar** (`primeira_pagina`): a página 1 e o `TotalResults`, como a
  sonda `tools/probe_download_aconex.py` do DocManager.
- A extração completa do projeto leva cerca de **30 min** no DocManager. O SIG-FT
  não tem o checkpoint de retomada dele.

## STATUS REAL e categorias

- `status_real_do_documento(historico)`: o histórico são **todas** as linhas de um
  Tracking ID (a lista renomeada continua no mesmo Tracking ID). A linha da
  verdade diz `nao_emitido` → `NÃO EMITIDO`; senão, `calcular_status_real`. Os
  valores são os do motor: `Aprovado`, `Aprovado com Comentários`,
  `Para Assinatura`, `Em Processo`, `Não Aprovado`...
- **Família de aprovação** (`eh_aprovacao`): Aprovado, Aprovado com Comentários e
  Para Assinatura (e o antigo `APROVADO`). Comparação sem acento e sem caixa: a
  mapeadora com os valores antigos também se encaixa.
- `categoria(status)`: `aprovada`, `em_processo`, `nao_aprovada` ou `outros`
  (NÃO EMITIDO, Cancelado, vazio, desconhecido).

## A Conferência de Revisões

**Entrada:** a mapeadora, aba `Acompanhamento Sobressalente` (achada pelo nome ou
pela coluna `N° DOCUMENTO ITAIPU`), cabeçalho na linha 2, colunas
`N° DOCUMENTO ITAIPU`, `ÚLTIMA REVISÃO EMITIDA`, `STATUS DA REVISÃO`,
`STATUS REAL`, `REVISÃO EM USO` e `LINK DA PLANILHA`. Faltou uma, `ValueError`
dizendo qual. A mapeadora é **só lida**, sem `read_only`, porque o hyperlink do
link só vem com a planilha inteira.

**A regra** (`conferir`), nesta ordem:

1. sem `LINK DA PLANILHA` → conta em "Sem `_STATUS_PMIB`";
2. sem ÚLTIMA REVISÃO EMITIDA → `outros`, "sem revisão emitida no Aconex";
3. `revisoes_iguais(revisão em uso, última)` → conta em "Em dia". Revisão em uso
   vazia é divergência (arquivo sem marca é arquivo não conferido);
4. o resto entra pela categoria do STATUS REAL. Sem pasta → `outros`,
   "_STATUS_PMIB não encontrado".

**A pasta** (`resolver_pasta`): a do arquivo do link, relativo à pasta da
mapeadora (o Gestão grava `os.path.relpath`); se ele não existir, a do
`_STATUS_PMIB` vivo com o mesmo código na pasta raiz (`status_pmib_arquivos.listar`,
uma varredura por conferência, só no primeiro link quebrado).

**O download** (`baixar`), para toda lista com pasta:

1. a versão vigente, com o nome `<código>[<revisão>].pdf` (só os reservados do
   Windows viram `_`; `#`, `&` e `=` ficam), com a revisão **que o Aconex
   devolveu**. Se for outra que não a da mapeadora: "mapeadora desatualizada: o
   Aconex está na X";
2. o PDF da revisão em uso, se faltar na pasta (a peça 2 compara os dois). Fora do
   histórico: aviso no log e segue;
3. arquivo que já existe: "ja_existia", sem baixar. A gravação usa `open(..., "xb")`:
   **nunca sobrescreve**;
4. `ErroAconex`, código fora do Aconex ou erro ao gravar: linha "falhou", e o resto
   continua. `cancelado_cb` para o laço entre as listas.

**A tela:** mapeadora e pasta raiz começam nas do Gestão PMIB; mostra quando a
mapeadora foi salva e avisa se não foi hoje; totais por categoria, "Em dia" e
"Sem `_STATUS_PMIB`"; uma aba por categoria (código, revisão em uso, última
revisão emitida, status da revisão, STATUS REAL e PDF). Sem perfil, ou com o login
recusado, as listas aparecem e o console avisa
"[AVISO] Sem conexão com o Aconex: as listas aparecem, mas nada foi baixado.".

## O diagnóstico

`python -m sigft.core.aconex.diagnostico "<código>" [--perfil NOME]`, ou o botão
"Testar conexão com o Aconex" (usa o primeiro código da mapeadora). Sete sondas,
cada uma com uma página só: login, register inteiro (busca vazia, a referência),
busca exata com histórico, Tracking ID (`trackingid:<id>` e `trackingid:"<id>"`),
título (`title:SOBRESSALENTES`) e código (`docno:*PB020*`). Uma sintaxe que o
Aconex ignora devolve o register inteiro e falha com "a sintaxe não filtrou". O
detalhe só tem contagens e status HTTP, nunca título nem dado de documento.

## Testes

`tests/test_aconex_cliente.py`, `test_aconex_credenciais.py`,
`test_aconex_diagnostico.py`, `test_aconex_status_real.py`,
`test_aconex_status_engine_docmanager.py` (os 14 testes portados do motor),
`test_conferencia_revisoes.py` (mapeadora real pelo openpyxl de verdade, com o
hyperlink relativo), `test_qt_tela_conferencia_revisoes.py`,
`test_pmib_manager_status_real.py`, `test_pmib_manager_lista_nova.py` e
`test_painel.py`. Nenhum toca a rede: o `abrir` e o cliente são dublês. O
`tests/_historico_aconex.py` monta históricos sintéticos (`HistoricoBuilder`).
