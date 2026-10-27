# Aconex no SIG-FT, a Conferência de Revisões e a Revisão no AMP

> Escrito em 2026-10-26, na 1.3.1-rc.1; a peça 2 (Revisão no AMP) entrou em
> 2026-10-27, na 1.3.1-rc.2, e está na última seção. Desenho da peça 1:
> `docs/superpowers/specs/2026-10-26-aconex-ao-vivo-design.md`. Plano e o que
> falta: `docs/superpowers/plans/2026-10-26-aconex-ao-vivo.md` e
> `docs/ACONEX_AO_VIVO.md`.

## Propósito

É a peça 1 do workflow que avisa quando uma lista de sobressalentes muda entre
revisões (a peça 2, a leitura dos PDFs pelo AMP da GE, está em "Peça 2: revisão no
AMP", no fim). Esta peça faz três coisas:

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
| tela | `sigft/app_qt/views/conferencia_revisoes.py` | `ModuloConferenciaRevisoes` (a aba Conferência de Revisões do PMIB Manager), `UltimaConferencia` e `perfil_do_aconex` |
| tela | `sigft/app_qt/views/gestao_sobressalentes.py` | a seção do PMIB Manager (menu 8): Gestão PMIB, Conferência de Revisões e Revisão no AMP em abas, com um console e uma barra |

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

**A tela** é a aba Conferência de Revisões do PMIB Manager (era o item 10 do menu
até a rc.1). Mapeadora e pasta raiz começam nas do Gestão PMIB; mostra quando a
mapeadora foi salva e avisa se não foi hoje; totais por categoria, "Em dia" e
"Sem `_STATUS_PMIB`"; uma aba por categoria, em `widgets/abas` (código, revisão em
uso, última revisão emitida, status da revisão, STATUS REAL e PDF; as larguras somam
850 para caber na aba a 1280x850). Cada rodada fica em `ultima`
(`UltimaConferencia`: mapeadora, conferência, downloads e pasta raiz), de onde a
Revisão no AMP parte. Sem perfil, ou com o login
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

## Peça 2: revisão no AMP

> Desde a 1.3.1-rc.2. Desenho: `docs/superpowers/specs/2026-10-27-amp-revisao-de-listas-design.md`;
> plano: `docs/superpowers/plans/2026-10-27-amp-revisao-de-listas.md`. O AMP (a IA da GE) só
> existe dentro da rede da GE: nenhum teste daqui chama a rede.

Para cada lista com divergência da última conferência, o agente do AMP lê o PDF da revisão em uso,
o da revisão atual e o `_STATUS_PMIB`, e devolve um HTML com o que mudou e o `_STATUS_PMIB`
remontado. Ele roda num workflow do n8n do AMP; o SIG-FT manda **texto**: os arquivos não vão (o nó
de modelo trabalha com texto, e o n8n não precisa ler o Box). Nada é aplicado no Excel: o Luan
confere o HTML e cola.

| Camada | Arquivo | O quê |
|---|---|---|
| n8n | `amp/revisao_de_listas/` | o pedido ao agente (`pedido.md`, onde se melhora o agente), o gerador do `.json` e o `LEIA-ME.md` (ligar no n8n, sintomas de falha, o texto para a conversa nova) |
| core | `sigft/core/amp/cliente.py` | `ClienteAmp` (`ping`, `eco`, `revisar`) e `RespostaAmp`; a chave vai no cabeçalho `X-SIGFT-Chave`, e nenhuma falha levanta |
| serviço | `sigft/services/revisao_amp.py` | as listas e os arquivos (`listas_para_amp`), o texto do PDF e o `_STATUS_PMIB` em tabulação, o pedido, a rodada, o diagnóstico e o teste de conexão |
| tela | `sigft/app_qt/views/revisao_amp.py` | `ModuloRevisaoAmp`, a aba Revisão no AMP |

**O contrato do webhook** (`POST` com JSON; a chave no cabeçalho):

- `{"modo": "ping"}` → `{ok, modo, versao_workflow, execucao}`, sem chamar o modelo;
- `{"modo": "eco", "codigos": [...]}` → `{ok, modo, texto, versao_workflow, execucao}`: o modelo
  devolve os códigos, e o SIG-FT confere se voltaram iguais (mascaramento);
- `{"modo": "revisar", "lista", "revisao_em_uso" (ou `null`), "revisao_atual", "status_pmib",
  "origem"}` → `{ok, modo, html, versao_workflow, execucao}`. Cada revisão é `{arquivo, paginas,
  texto}`; o `_STATUS_PMIB` é `{arquivo, aba, linha_de_revisao, linhas, tsv}`.
- Falha do agente: HTTP 502 com `{ok: false, modo, etapa, erro, execucao}`.

A revisão vai **uma vez só**, pela rota que o `ping` achou (`ClienteAmp.revisar`; o ping vai antes
na primeira lista). A cascata do `rede.abrir` manda de novo pela rota seguinte quando o tempo esgota
ou a conexão cai, e na revisão cada repetição seria outra execução do agente; por isso o tempo
esgotado ("o AMP não respondeu em 15 min") e a conexão cortada ("caiu depois de N s") viram erro.

O texto de cada PDF sai do PyMuPDF com `--- página N ---` antes de cada página (o agente cita a
página). PDF sem texto em nenhuma página é "falta: PDF sem texto (só imagem)". O `_STATUS_PMIB` vai
inteiro: a linha de revisão, o cabeçalho e as linhas, com as colunas separadas por tabulação. A
`lista` leva a `data_de_hoje` (dd/mm/aaaa, do computador): a linha de revisão nova tem a DATA DE
ALTERAÇÃO, e o modelo não sabe que dia é.

A aba só começa com a Conferência parada (`ModuleFrame.rodando()`): no meio do download, a última
conferência ainda está sem os PDFs, e um deles pode estar pela metade.

**As listas** (`listas_para_amp`): as da conferência que têm pasta, na ordem das categorias. A
revisão atual é a do download desta sessão (a que o Aconex devolveu); sem download, a ÚLTIMA
REVISÃO EMITIDA, pelo nome do padrão na pasta. Faltando o `_STATUS_PMIB`, o PDF da revisão atual
ou o da revisão em uso (quando há revisão em uso), a lista fica com a falta e não é chamada.

**A rodada** (`revisar_listas`), uma lista por vez:

1. falta, ou erro ao ler (`ValueError`, `OSError`, `BadZipFile`): "falta: <motivo>", sem chamar;
2. outra exceção ao montar o pedido (PDF corrompido: o PyMuPDF levanta `RuntimeError`): "falhou",
   com o traceback no diagnóstico;
3. resposta boa: o HTML vai para `<código>[<em uso>-<atual>] revisao AMP.html`, na pasta da lista,
   com `open(..., "x")`. **Nunca sobrescreve:** o nome que existe ganha " (2)", " (3)"...;
4. resposta ruim: "falhou", e o diagnóstico vai para
   `Documentos\SIG-FT\logs\amp\<AAAAMMDD-HHMMSS> <código>.txt`;
5. `cancelado_cb` é lido entre as listas, e as que sobram ficam "parado". `resultado_cb` recebe
   cada lista quando ela acaba: a tabela da aba anda junto.

**O diagnóstico** (`diagnostico`; o botão usa `diagnosticos_para_copiar`) é para colar numa conversa
nova com o Claude, no PC da GE, com o repositório. Leva a versão e a hora, a lista e as revisões, o
endereço (e só se a chave está posta), o que foi mandado **só em números** (páginas e caracteres de
cada texto, linhas do `_STATUS_PMIB`, o tamanho do pedido), o HTTP, o tempo, o número da execução do
n8n, o erro, o corpo da resposta (até 1500 caracteres: do JSON do workflow, só os campos dele, e do
`html` e do `texto` só o tamanho) e os arquivos do repositório. **Nunca leva texto de documento:**
além do filtro de campos, toda linha dos PDFs e célula do `_STATUS_PMIB` com 20 caracteres ou mais
que volte no erro ou no corpo vira `<trecho do documento>`. A chave sai do corpo e do erro já no
cliente.

**O teste de conexão** (`testar_conexao`): o `ping`; passando, o `eco` com os códigos das listas e
até 10 CÓDIGOS DO MATERIAL do primeiro `_STATUS_PMIB` que se lê. Sem conferência na sessão, só o
ping (`--      Eco: não mandado`).

**A aba:** o endereço e a chave saem de Configuração → Chaves de API (`AMP_WEBHOOK_URL` e
`AMP_WEBHOOK_CHAVE`; variáveis `SIGFT_AMP_WEBHOOK_URL` e `SIGFT_AMP_WEBHOOK_CHAVE`). Sem os dois, um
aviso, e nada é chamado; sem conferência, "Confira as revisões antes.". A tabela tem uma linha por
lista e a coluna AMP ("na fila", "HTML pronto: ...", "falhou: ...", a falta, "parado"); dois
cliques abrem o HTML. "Copiar diagnóstico" só liga com falha na rodada.

**Testes:** `test_amp_workflow.py` (o `.json` sai do pedido; os nós e o contrato),
`test_amp_cliente.py`, `test_revisao_amp_pedido.py`, `test_revisao_amp_rodada.py`,
`test_qt_tela_revisao_amp.py` e `test_qt_tela_gestao_sobressalentes.py`. O que só a GE prova (o
modelo do AMP num workflow, PDF grande) está na Etapa 5c do roteiro.
