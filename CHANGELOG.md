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

## 1.1.0 - 2026-09-23

**Upload de características técnicas**

- O robô agora **salva sozinho e confere se o portal aceitou**. Antes ele parava em toda ficha esperando você conferir e salvar; agora só chama você na ficha que o portal recusou — nas outras, segue direto para a próxima.
- Quando o portal recusa ("Por favor, verifique os campos"), o log passa a dizer **quais características travaram o salvamento**, e nas de texto **em qual idioma** (português, espanhol, ou os dois). Antes era procurar o campo vermelho na tela, linha por linha.
- Se você corrigir e salvar à mão, o robô **reconfere ao continuar**: apareceu a mensagem de salvo com sucesso, a ficha é marcada como COMPLETO na planilha de status. Antes ela ficava pendente mesmo tendo dado certo, e era preciso marcar na mão.
- Ficha traduzida num PDM de revisão antiga: as **características que só existem na revisão nova do portal, e que por isso ficariam em branco, são apagadas** antes de finalizar — com aviso no log de qual foi apagada e por quê (não estava no JSON de origem).

**Tela inicial**

- Botão **"Interromper tudo"**, para sair no meio de uma lista sem esperar ela acabar. Cada robô termina a ficha que está na mão e para. Nada do que já foi feito se perde: só as fichas que o portal confirmou viram COMPLETO.

**Organização**

- A barra lateral foi corrigida: **"Aplicação LMR" saiu da Gestão** e foi para a seção de dados técnicos e upload, que é o que ela é.

**Criação de fichas**

- A escolha de PDM passa a conferir a REVISÃO do PDM, que é o que a Itaipu cobra, e deixou de confundir peça DE um componente com o componente.

**Correção de PDM — a tela existe, mas está DESLIGADA nesta versão**

- A tela "4.4. Correção de PDM" aparece na barra lateral marcada **"(em obras)"** e não abre. Ela está pronta e testada, mas **nunca rodou contra o portal de verdade** — e é um módulo que apaga características técnicas para repô-las depois. Liberar antes da validação real seria arriscar fichas suas. Fica desligada até essa execução acontecer.

## 1.0.0 - 2026-09-22

- O SIG-FT passa a ser gerado e publicado pelo GitHub, com instalador próprio. Acabou o passo a passo manual de compilar, zipar e copiar o arquivo para o Box.
- Atualização automática: quando sai uma versão nova, o app avisa, mostra o que mudou e se atualiza com um clique.
- As chamadas de IA e a busca de documentos do AutoSpec passam a funcionar com a VPN da empresa ligada. Antes o programa tentava sair direto para a internet, e a VPN descartava os pacotes em silêncio - a busca simplesmente não achava nada, sem dizer por quê.
- Quando a rede não deixa o programa conectar, o log passa a dizer o motivo real (o nome não resolve, a porta não abre, o proxy recusou) em vez de só "sem conexão".
- As chaves de API e as suas preferências saem da pasta do programa e passam a ficar em `Documentos\SIG-FT`. Com isso a atualização não encosta mais nelas, e não é preciso recadastrar nada depois de atualizar.
- O programa passa a encontrar sozinho o Chrome ou o Edge instalado na máquina para os módulos que usam o portal. Antes quem fazia isso era o arquivo `.bat` de atalho.
- A versão aparece na barra de título e na tela inicial, e fica sempre certa depois de atualizar.
- A escolha de PDM na criação de fichas ficou mais certeira: o programa passa a pré-filtrar os PDMs candidatos a partir da planilha-mestra, em vez de mandar a lista inteira para a IA, e confere no portal antes de gravar. Quando não tem certeza, ele avisa em vez de escolher sozinho.
