# Aconex no SIG-FT, a Conferência de Revisões e a Revisão no AMP

> Escrito em 2026-10-26, na 1.3.1-rc.1; a peça 2 (Revisão no AMP) entrou em
> 2026-10-27, na 1.3.1-rc.2, foi refeita em 2026-11-03 (v2: o agente do AMP recebe os
> arquivos) e está na última seção. Desenho da peça 1:
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
título (`title:SOBRESSALENTES`, página de 500, com `docno` e `title`) e as listas
novas que ela traz (`e_lista_de_sobressalentes`, conferida no SIG-FT). Uma sintaxe
que o Aconex ignora devolve o register inteiro e falha com "a sintaxe não filtrou".
O detalhe só tem contagens e status HTTP, nunca título nem dado de documento. O
cliente do diagnóstico tenta cada sonda 2 vezes (a extração tenta 5).

Até 2026-10-27 a última sonda era `docno:*PB020*`: no teste do Luan na GE ela voltou
HTTP 500 em 5 de 5 tentativas (o Aconex não aceita o coringa no código; o limite de
frequência seria 503), e as cinco tentativas com espera custavam quase 2 minutos.
O mesmo teste mostrou que o Tracking ID traz 15 versões onde a busca exata traz 7.
O guia da API, com o que o DocManager já validou, está em `docs/ACONEX_API.md`.

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

> **v2 desde 2026-11-03:** o agente do AMP recebe os arquivos. Desenho:
> `docs/superpowers/specs/2026-11-03-amp-revisao-com-arquivos-design.md`; plano:
> `docs/superpowers/plans/2026-11-03-amp-revisao-com-arquivos.md`. A v1, de 2026-10-27, mandava o
> texto extraído; o desenho dela (`2026-10-27-amp-revisao-de-listas-design.md`) ainda vale para o
> porquê e para quais listas e arquivos vão. O AMP (a IA da GE) só existe dentro da rede da GE:
> nenhum teste daqui chama a rede.

Para cada lista **marcada** na aba, o agente do AMP recebe três arquivos, como estão na pasta da
lista:
- o PDF da revisão em uso;
- o PDF da revisão atual;
- o `_STATUS_PMIB.xlsx`.

O agente é o *Spare Parts Document Reviewer*, criado no AMP: as instruções moram lá, e
`amp/revisao_de_listas/agente.md` é a cópia. Ele devolve um HTML com o que mudou entre as revisões e
as ações no controle: criar, excluir (mover para a `SEM_LISTA_STATUS_PMIB`) e substituir. O SIG-FT
**não lê o conteúdo** dos arquivos e não aplica nada no Excel: o Luan confere o HTML e aplica.

| Camada | Arquivo | O quê |
|---|---|---|
| AMP + n8n | `amp/revisao_de_listas/` | `agente.md` (a cópia do agente), o gerador do workflow e o `LEIA-ME.md` (criar o agente, ligar o workflow, testar pelo PowerShell, sintomas) |
| core | `sigft/core/amp/cliente.py` | `ClienteAmp` genérico (`ping` e `enviar(campos, arquivos)` em multipart) e `RespostaAmp` (`html`, `execucao`, `versao_workflow`, `arquivos`); a chave vai no cabeçalho `X-SIGFT-Chave`, e nenhuma falha levanta |
| serviço | `sigft/services/revisao_amp.py` | as listas e os arquivos (`listas_para_amp`), a mensagem e o pedido (`PedidoAmp`), a rodada com o log, o diagnóstico e o teste de conexão |
| widget | `sigft/app_qt/widgets/webhook_amp.py` | o webhook de um workflow dentro do módulo: `ChavesDoWebhook`, `ler`/`gravar` (com a adoção dos nomes antigos), `problema_do_endereco` e a `JanelaDoWebhook` |
| tela | `sigft/app_qt/views/revisao_amp.py` | `ModuloRevisaoAmp`, a aba Revisão no AMP |

**O contrato do webhook** (`POST` para a Production URL, com a chave no cabeçalho):
- **O ping:** `{"modo": "ping"}` em JSON (ou `modo=ping` no formulário). Volta
  `{ok, modo, versao_workflow, execucao}` sem chamar o agente.
- **A revisão:** multipart com os campos:
  - `modo=revisar`;
  - `mensagem`;
  - `revisao_em_uso`, só quando há revisão em uso;
  - `revisao_atual`;
  - `status_pmib`.

  Volta `{ok, modo, html, arquivos, versao_workflow, execucao}`. `arquivos` são os nomes dos
  arquivos que chegaram ao agente.
- **As falhas do workflow:**
  - **400, etapa `arquivos`:** chegaram menos de 2 arquivos, e o agente não é chamado;
  - **502, etapa `agente`:** o agente falhou;
  - **`ok: false`:** o agente não devolveu HTML.

**A mensagem** (`mensagem_da_lista`), montada pelo SIG-FT com o que a conferência sabe:
`Lista: <código>. Revisão em uso: <rev> (arquivo <nome>). Revisão atual: <rev> (arquivo <nome>).
Controle: <nome>. Data de hoje: <dd/mm/aaaa>. Faça a revisão.` Sem revisão em uso, o trecho vira
"nenhuma (a lista ainda não tem revisão em uso: compare só a revisão atual com o controle)", e vão
dois arquivos. A data vai porque a linha de revisão nova leva a DATA DE ALTERAÇÃO, e o agente não
sabe que dia é.

O envio vai **uma vez só**, pela rota que o `ping` achou. A cascata do `rede.abrir` mandaria de novo
pela rota seguinte quando o tempo esgota ou a conexão cai, e cada repetição seria outra execução do
agente. Por isso o tempo esgotado ("o AMP não respondeu em 45 min"; era 15 até 2026-11-04, quando uma lista levou 17) e a conexão cortada ("caiu
depois de N s") viram erro. O teste de 03/11 mostrou que a rede da GE segura a chamada de minutos.

**A resposta chega depois** (desde 2026-11-04):
- **O workflow responde ao envio na hora** com `{estado: "aceito", pedido, arquivos}` e roda o
  agente em seguida.
- **O resultado fica nos dados estáticos do workflow:** `estado` `pronto` ou `erro`, os 30 mais
  novos, por 7 dias.
- **A busca:** `modo=buscar` com o `pedido` devolve o resultado guardado, ou `pendente`
  (`ClienteAmp.buscar`).
- **A espera:** a rodada pergunta a cada 30 s, até 60 min (`_esperar_o_resultado`). O pedido fica
  em `Documentos\SIG-FT\amp_pendentes.json` (`registrar_pendente`) até o HTML ser gravado.
- **Parar ou passar do máximo** deixa a lista "no AMP", na situação `pendente`.
- **Ao abrir, a aba chama o `buscar_pendentes`,** no máximo a cada 5 min. Ele grava o HTML pronto,
  tira o erro e desiste do pedido com mais de 7 dias.
- **O workflow antigo,** que devolve o HTML na mesma chamada, continua aceito.

**As listas** (`listas_para_amp`, sem mudança desde a v1):
- são as da conferência que têm pasta, na ordem das categorias;
- a revisão atual é a do download desta sessão (a que o Aconex devolveu); sem download, é a ÚLTIMA
  REVISÃO EMITIDA, achada pelo nome do padrão na pasta;
- sem o `_STATUS_PMIB`, sem o PDF da revisão atual ou sem o da revisão em uso (quando há revisão em
  uso), a lista fica com a falta e não é mandada.

**A rodada** (`revisar_listas`):
1. **O ping antes.** Falhando, nada vai: as listas voltam "falhou" com o motivo, e o diagnóstico
   vai só na primeira.
2. **Uma lista por vez.** A lista com falta não é chamada.
3. **Resposta boa:**
   - o HTML vai para `<código>[<em uso>-<atual>] revisao AMP.html`, na pasta da lista;
   - a gravação usa `open(..., "x")` e **nunca sobrescreve**: o nome que existe ganha " (2)",
     " (3)"...
4. **Também é falha:**
   - a resposta sem HTML;
   - o workflow dizer que recebeu menos arquivos do que os mandados ("o workflow recebeu N de M
     arquivo(s)").
5. **A falha de uma lista não para as outras.** O diagnóstico vai para
   `Documentos\SIG-FT\logs\amp\<AAAAMMDD-HHMMSS> <código>.txt`.
6. **O ritmo:**
   - `cancelado_cb` é lido entre as listas, e as que sobram ficam "parado";
   - `resultado_cb` recebe cada lista quando ela acaba, e a tabela da aba anda junto.

**O log** (o Luan, em 03/11: "precisamos ver o que está acontecendo"):
- **o começo:** as listas marcadas, as desmarcadas e as com falta que ficam fora, o webhook (e só se
  a chave está posta) e o ping;
- **cada lista:**
  - `[n/N] <código> · em uso X → atual Y`;
  - `vai:`, com o nome e o tamanho de cada arquivo;
  - um batimento a cada 30 s enquanto o agente trabalha (`… 1:30 esperando o AMP`);
  - `resposta:`, com o HTTP, o tempo, a execução do n8n e os arquivos recebidos;
  - o `✓` com o HTML gravado, ou o `✗` com o motivo;
- **o fim:** a contagem e o tempo total.

A aba grava as mesmas linhas, com a hora, em `Documentos\SIG-FT\logs\amp\amp_revisao_*.log`, e o
teste de conexão em `amp_teste_*.log` (`core/log_execucao.py`). Nunca vão para o log a chave e o
conteúdo dos documentos.

**O diagnóstico** (`diagnostico`; o botão usa `diagnosticos_para_copiar`) é para colar numa conversa
nova com o Claude, no PC da GE, com o repositório. Leva:
- a versão e a hora, a lista e as revisões;
- o endereço, e só se a chave está posta;
- o que foi mandado: o nome e o tamanho de cada arquivo e o tamanho da mensagem;
- o HTTP, o tempo, o número da execução do n8n e os arquivos que chegaram ao agente;
- o erro, cortado em 300 caracteres;
- o corpo da resposta, até 1500 caracteres: do JSON do workflow, só os campos dele, e do `html` só o
  tamanho;
- os arquivos do repositório.

**Nunca leva conteúdo de documento:** o SIG-FT não extrai texto, e o conteúdo só existe no `html`,
que fica de fora. A chave sai do corpo e do erro já no cliente.

**O teste de conexão** (`testar_conexao`) faz só o `ping`, que vê a rede, a chave e o workflow
publicado, sem chamar o agente: `OK      Ping: workflow 2026-11-03 (HTTP 200, 0,8 s, execução N)`.
O eco da v1 saiu: o agente lê o arquivo original, e os códigos voltaram intactos nos testes de 03/11.

**A aba:**
- **As listas.** Ao abrir a aba, se há uma conferência que a tabela não mostra, as listas aparecem
  (`atualizar_listas`, numa tarefa). Elas vêm **todas marcadas**; a com falta fica sem caixa, com a
  falta na coluna AMP. Há Marcar todas e Desmarcar todas.
- **A rodada.**
  - O **Revisar no AMP** manda só as marcadas, na ordem da tabela, e trava as caixas durante a
    rodada.
  - No fim, as que voltaram com HTML se desmarcam: um segundo clique manda só as que faltaram.
  - Se a Conferência rodou de novo, o clique refaz a tabela e não manda nada até o próximo clique.
  - Com a Conferência ainda rodando, aparece um aviso, e nada é chamado.
- **O webhook.** O **Webhook…** abre a janela do endereço e da chave deste workflow, guardados no
  `api_config.json` como `AMP_REVISAO_LISTAS_URL` e `AMP_REVISAO_LISTAS_CHAVE` (variáveis
  `SIGFT_AMP_REVISAO_LISTAS_*`).
  - A janela recusa endereço sem `https://` e o de teste (`/webhook-test/`).
  - Os nomes antigos (`AMP_WEBHOOK_URL` e `AMP_WEBHOOK_CHAVE`, de Configuração → Chaves de API até
    a v1) são adotados uma vez.
  - Cada workflow do AMP tem o seu par: um módulo novo usa a mesma janela com outros nomes.
- **Os botões e a tabela.** A coluna AMP diz "na fila", "HTML pronto: ...", "falhou: ...", a falta
  ou "parado". Dois cliques abrem o HTML. "Copiar diagnóstico" só liga com falha na rodada.

**Testes:**
- `test_amp_workflow.py`: o `.json` sai do gerador; os nós e o contrato;
- `test_amp_cliente.py`;
- `test_revisao_amp_pedido.py`;
- `test_revisao_amp_rodada.py`: inclui o log e o batimento;
- `test_qt_webhook_amp.py`;
- `test_qt_tela_revisao_amp.py`;
- `test_qt_tela_gestao_sobressalentes.py`.

O que só a GE prova está na Etapa 5c do roteiro: o agente de verdade e o tamanho máximo de arquivo.
