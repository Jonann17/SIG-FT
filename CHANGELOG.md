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

## 1.0.0 - 2026-09-22

- O SIG-FT passa a ser gerado e publicado pelo GitHub, com instalador próprio. Acabou o passo a passo manual de compilar, zipar e copiar o arquivo para o Box.
- Atualização automática: quando sai uma versão nova, o app avisa, mostra o que mudou e se atualiza com um clique.
- As chamadas de IA e a busca de documentos do AutoSpec passam a funcionar com a VPN da empresa ligada. Antes o programa tentava sair direto para a internet, e a VPN descartava os pacotes em silêncio - a busca simplesmente não achava nada, sem dizer por quê.
- Quando a rede não deixa o programa conectar, o log passa a dizer o motivo real (o nome não resolve, a porta não abre, o proxy recusou) em vez de só "sem conexão".
- As chaves de API e as suas preferências saem da pasta do programa e passam a ficar em `Documentos\SIG-FT`. Com isso a atualização não encosta mais nelas, e não é preciso recadastrar nada depois de atualizar.
- O programa passa a encontrar sozinho o Chrome ou o Edge instalado na máquina para os módulos que usam o portal. Antes quem fazia isso era o arquivo `.bat` de atalho.
- A versão aparece na barra de título e na tela inicial, e fica sempre certa depois de atualizar.
- A escolha de PDM na criação de fichas ficou mais certeira: o programa passa a pré-filtrar os PDMs candidatos a partir da planilha-mestra, em vez de mandar a lista inteira para a IA, e confere no portal antes de gravar. Quando não tem certeza, ele avisa em vez de escolher sozinho.
