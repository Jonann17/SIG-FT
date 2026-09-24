# Histórico de versões

Este arquivo é a **fonte única** das novidades. O app mostra o bloco da versão
instalada, e o GitHub Actions usa o mesmo bloco como descrição do Release.

**Ao preparar uma versão, acrescente o bloco dela aqui ANTES de criar a tag.**
`tests/test_novidades.py` reprova um commit em que `_build_info.VERSAO` não
tenha bloco correspondente — é o que evita publicar um Release com o corpo
vazio, defeito que só apareceria com a tag já criada.

Escreva cada linha pensando em quem usa o SIG-FT, não em quem o programa:
"a busca do AutoSpec passa a funcionar com a VPN ligada" é útil; "refatorado o
cliente HTTP para usar WinHttpGetProxyForUrl" não.

## 1.1.0 - 2026-09-24

**AutoSpec AI**

- AutoSpec AI: a IA passa a receber o **documento inteiro** — e, com Gemini, o **próprio PDF**, com tabelas, desenhos cotados e gráficos. Antes ia só um recorte de uns 24 mil caracteres: no manual de 166 páginas de um ventilador, 87% do documento nunca chegava à IA. O arquivo vai para o provedor escolhido no painel "Modelos de IA".
- AutoSpec AI: cada valor técnico agora vem com **a prova** — o trecho e a página do documento de onde saiu —, e o programa confere a prova antes de gravar. Cotas de desenho sem o "mm" ao lado (ex.: `ø 36`) deixam de ser descartadas, e respostas traduzidas do inglês também.
- AutoSpec AI: material, norma, uso e tipo construtivo podem ser preenchidos por **dedução técnica**, marcada com um **comentário na célula** explicando o porquê. Confira esses antes de homologar. Números continuam só com documento.
- AutoSpec AI: a rotação do motor não é mais "corrigida" a partir da frequência da rede (`2860 rpm` virava `3600 rpm`), e vazão em `m³/h` deixou de ser lida como comprimento em metros.
- AutoSpec AI: quando a planilha não informa o fabricante, vale o que o **manual anexado** declara, e a busca na web, que antes era pulada, passa a acontecer.
- AutoSpec AI: ficha em que a IA não respondeu passa a contar como **falha** no resumo e não gera o `_completed`. Antes ela era contada como sucesso e salva vazia. A espera pela resposta subiu para até 5 minutos por tentativa, porque o documento agora vai inteiro.

**Upload de características técnicas**

- Upload de características técnicas: o robô agora **salva sozinho e confere se o portal aceitou**. Antes ele parava em toda ficha esperando você conferir e salvar; agora só chama você na ficha que o portal recusou — nas outras, segue direto para a próxima.
- Upload de características técnicas: quando o portal recusa ("Por favor, verifique os campos"), o log passa a dizer **quais características travaram o salvamento**, e nas de texto **em qual idioma** (português, espanhol, ou os dois). Antes era procurar o campo vermelho na tela, linha por linha.
- Upload de características técnicas: se você corrigir e salvar à mão, o robô **reconfere ao continuar**: apareceu a mensagem de salvo com sucesso, a ficha é marcada como COMPLETO na planilha de status. Antes ela ficava pendente mesmo tendo dado certo, e era preciso marcar na mão.
- Upload de características técnicas: numa ficha traduzida num PDM de revisão antiga, as **características que só existem na revisão nova do portal, e que por isso ficariam em branco, são apagadas** antes de finalizar — com aviso no log de qual foi apagada e por quê (não estava no JSON de origem).

**Planilhas PMIB**

- Planilhas PMIB: as fichas passam a sair **direto da planilha de PDMs da Itaipu**, sem precisar manter as pastas "From Itaipu" e "PDMs Modificados" em dia. Na aba "Criar planilhas PMIB", a fonte "Planilha de PDMs" já vem marcada: basta escolher a planilha no painel de cima (o seletor que ficava na aba "Processar PDMs" subiu para lá e vale para as duas abas). A pasta continua disponível como método antigo, e é por ela que sai a ficha em inglês.
- Planilhas PMIB: as perguntas saem **na ordem oficial do PDM** e **sem o "(nan)"** que aparecia quando a Itaipu não escrevia o texto de ajuda.
- Planilhas PMIB: o log avisa quando o PDM do portal está numa **revisão diferente** da planilha, e no fim lista quais PDMs precisam subir de revisão no portal (e, quando é a planilha que está atrás, pede uma exportação nova).
- Planilhas PMIB: quando a planilha traz **dois PDMs diferentes com o mesmo código** (acontece em 2 códigos da exportação de 23/09/2026), a ficha não sai misturando os dois: o log mostra os dois nomes para conferir com a Itaipu.
- Planilhas PMIB: botão novo **"Regenerar as pastas"**: refaz as duas pastas a partir da planilha, com a **revisão do PDM no nome do arquivo** (`PDM_1650_001 - ACUMULADOR - R2_formatado.xlsx`). A versão antiga de cada PDM vai para a subpasta `_versoes_antigas`; nada é apagado.
- Planilhas PMIB: no método antigo, quando a pasta tem mais de um arquivo do mesmo PDM, vale o de **revisão mais alta no nome**, com aviso no log. Antes valia o primeiro que aparecesse.
- Planilhas PMIB: a tela funciona em **janela menor**: o formulário ganhou barra de rolagem e o log de saída mantém o tamanho padrão. Antes, fora da janela maximizada, o log encolhia até sumir e o fim das abas ficava cortado.

**Organização**

- Organização: na barra lateral, **"Aplicação LMR" saiu da Gestão** e foi para a seção de dados técnicos e upload, que é o que ela é.

**Criação de fichas**

- Criação de fichas: a escolha de PDM passa a conferir a REVISÃO do PDM, que é o que a Itaipu cobra, e deixou de confundir peça DE um componente com o componente.

**Correção de PDM — a tela existe, mas está DESLIGADA nesta versão**

- A tela "4.4. Correção de PDM" aparece na barra lateral **em cinza** e não abre. Ela está pronta e testada, mas **nunca rodou contra o portal de verdade** — e é um módulo que apaga características técnicas para repô-las depois. Liberar antes da validação real seria arriscar fichas suas. Fica desligada até essa execução acontecer.

## 1.0.0 - 2026-09-22

- O SIG-FT passa a ser gerado e publicado pelo GitHub, com instalador próprio. Acabou o passo a passo manual de compilar, zipar e copiar o arquivo para o Box.
- Atualização automática: quando sai uma versão nova, o app avisa, mostra o que mudou e se atualiza com um clique.
- As chamadas de IA e a busca de documentos do AutoSpec passam a funcionar com a VPN da empresa ligada. Antes o programa tentava sair direto para a internet, e a VPN descartava os pacotes em silêncio - a busca simplesmente não achava nada, sem dizer por quê.
- Quando a rede não deixa o programa conectar, o log passa a dizer o motivo real (o nome não resolve, a porta não abre, o proxy recusou) em vez de só "sem conexão".
- As chaves de API e as suas preferências saem da pasta do programa e passam a ficar em `Documentos\SIG-FT`. Com isso a atualização não encosta mais nelas, e não é preciso recadastrar nada depois de atualizar.
- O programa passa a encontrar sozinho o Chrome ou o Edge instalado na máquina para os módulos que usam o portal. Antes quem fazia isso era o arquivo `.bat` de atalho.
- A versão aparece na barra de título e na tela inicial, e fica sempre certa depois de atualizar.
- A escolha de PDM na criação de fichas ficou mais certeira: o programa passa a pré-filtrar os PDMs candidatos a partir da planilha-mestra, em vez de mandar a lista inteira para a IA, e confere no portal antes de gravar. Quando não tem certeza, ele avisa em vez de escolher sozinho.
