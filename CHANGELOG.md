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

## 1.2.1 - 2026-10-16

- Cria Fichas: a leitura do que cada material é (a primeira passada da IA) passa a usar o **mesmo modelo escolhido para o Cria Fichas** no painel "Modelos de IA". Antes ela ia sempre pelo Gemini direto, que a VPN da empresa derruba ("Connection aborted"), e o lote seguia só com a busca por palavras.
- Modelos de IA: o modo avançado do painel passa a mostrar também **"Interpretar material (Cria Fichas)"** e **"Traduzir PDM (Planilhas PMIB)"**, que antes não apareciam e por isso não tinham como receber um modelo próprio.
- Cria Fichas: na revisão dos PDMs, o item que a IA não respondeu mostra as colunas vazias, em vez de "nan" em Descrição Curta, UN e Tipo.
- Cria Fichas: o item sem marca não vai mais para a IA (nem para a busca no catálogo) com a palavra "nan" no lugar da marca.
- Atualização automática: o Release passa a publicar a atualização pequena também em **.zip**, e o app tenta o .zip, depois o .bin e só então o instalador completo. Na rede da empresa o .bin chegava cortado no fim; o .zip é outra tentativa de a atualização pequena passar. Vale a partir da versão seguinte a esta.
- Atualização automática: nas versões de teste, a atualização pequena sai também como **.exe** — o tipo que ela de fato é, igual ao instalador completo, que a rede da empresa deixa passar. O app tenta o .exe, depois o .zip, depois o .bin e só então o completo.
- Atualização automática: na 1.2.1-rc.4, um app de teste anterior a ela tomava a atualização pequena em .exe pelo instalador completo; quando a pequena não chegava inteira, a atualização falhava (o SHA256 barrava o arquivo, nada errado era instalado). O .exe pequeno agora tem outro nome, e o completo é reconhecido pelo nome.
- Atualização automática: o app passa a apagar os instaladores que as atualizações anteriores deixavam na pasta temporária do Windows (`%TEMP%\SIG-FT_Update`) — até 326 MB por atualização, que se acumulavam versão após versão. A limpeza acontece ao abrir o app e antes de cada download.
- Atualização automática: quem está na versão anterior volta a receber a **atualização pequena** (só o que mudou), em vez do instalador completo. Desde a 1.2.0-rc.5 o Release só montava o pequeno a partir da versão mais antiga da lista.
- Cria Fichas: num erro fatal do robô de criação, o navegador fecha, como já fazia o robô de edição.
- Gestão PMIB: uma aba "Atividades" com outras colunas na planilha de mapeamento não derruba mais o painel; ele sai sem a seção de atividades, como quando a aba não existe.
- Instalação: aberto pelo `SIG-FT.bat` ou `SIG-FT.command` com o Python 3.12.0, o SIG-FT avisa que essa versão tem um defeito que impede algumas telas de abrir, e diz qual instalar.
- Upload Tech Specs: o "Continuar" depois de salvar o JSON abre a janela para escolher quais fichas enviar ao portal, como no Upload Condições, em vez de mandar todas. E um JSON que não abre mostra a caixa "Erro de Leitura", além do aviso no console.
- AutoSpecAI: as tabelas de especificações do PDF chegam à IA também como tabelas, com cada valor na linha do seu parâmetro. Antes, lido como texto, cada célula vinha numa linha solta, e a IA podia trocar um valor de parâmetro.
- AutoSpecAI: quando o documento vai à IA como texto, as páginas sem texto (escaneadas, desenhos cotados) vão como imagem, até 8 por ficha. Antes chegavam vazias. Um modelo que não lê imagem recusa, e a ficha segue só com o texto, como antes.
- Todos os módulos com IA: uma resposta com o JSON um pouco fora do formato (raciocínio antes, vírgula sobrando no fim) passa a ser lida, em vez de gastar uma nova chamada ou devolver a ficha vazia.
- Cria Fichas: mandar ao portal um lote que o robô já levou pergunta antes ("Enviar o mesmo lote de novo?", com Não como padrão). Antes, um segundo clique no "4. Robô Web" criava as mesmas fichas outra vez.
- Aplicação LMR: o Upload e a Exclusão não rodam mais ao mesmo tempo. Com um robô rodando, o outro não começa e o console diz qual está rodando (os dois usam a mesma página do portal).
- Gestão PMIB: uma aba "Atividades" em outro formato não é mais alterada; o passo das atividades é pulado, sem gravar nada, e o log diz por quê. Antes, os totais podiam ser gravados por cima de outras colunas.
- Cria Fichas: antes de abrir o navegador, o robô confere o que o portal vai recusar (texto breve com mais de 40 caracteres, com acento, ç ou começando sem letra; texto breve ou código do projeto vazios). Com problema, a janela **"Revisão antes do portal"** mostra a ficha, o campo, o valor e o motivo, e deixa seguir sem as fichas com erro, seguir com todas ou cancelar. Nada é corrigido sozinho.
- Upload Condições: a mesma **revisão antes do portal**: medidas, pesos, umidade, temperaturas e empilhamento com mais de 30 caracteres, medida, peso ou umidade negativos, cuidados com mais de 500 caracteres ou só num idioma, textos com mais de 1000, legislação e descarte vazios, e logística reversa que se aplica sem o texto.
- Upload Tech Specs: a mesma **revisão antes do portal**: texto com mais de 1000 caracteres, número com mais de 15 e intervalo sem mínimo ou máximo (ou com um deles com mais de 15).
- Upload LMR: a mesma **revisão antes do portal**: código do equipamento com mais de 200 caracteres, tag vazia (ou a célula vazia que viraria "nan" no portal) e tag com mais de 150.

## 1.2.0 - 2026-10-15

**Interface nova**

- Interface nova: o SIG-FT abre com a **interface nova (Qt)**, com a mesma aparência e os mesmos botões de antes. A interface antiga saiu do SIG-FT. Se a nova não abrir, aparece uma mensagem com o motivo e o caminho do arquivo de log (`Documentos\SIG-FT\logs\sigft.log`), para mandar a quem cuida do SIG-FT.
- Interface nova: **todas as telas** estão nela (Cria Fichas, Planilhas PMIB, Analyzer, Upload Condições, Tradutor, Upload Specs, Correção de PDM, Upload duplicadas, AutoSpec, Aplicação LMR, PMIB Manager e Search; a Correção de PDM continua bloqueada no menu, como antes), e a tela inicial traz os painéis de chaves de API, modelos de IA, gastos, mural, "Atualizações" e "Versões de teste".
- Interface nova: lançadores para **Windows** (`SIG-FT.bat`) e **macOS** (`SIG-FT.command`, novo), que preparam o ambiente sozinhos. Se a instalação das dependências falhar numa máquina que já tinha o SIG-FT, ele abre com as de antes.
- Instalação: o instalador passa a levar a interface nova.
- Interface nova: nas perguntas que **apagam ou descartam** trabalho (Apagar LMR, troca de PDM na Correção de PDM, fechar com tarefa rodando), Enter responde **"Não"**. Esc não fecha mais a revisão de PDMs, as seleções nem os campos de edição: para cancelar, use o "X".
- Interface nova: **um robô por vez** no portal. Na Cria Fichas (criação ou edição do código do projeto) e nos uploads, um segundo clique com o robô trabalhando não abre outro robô: o log avisa para esperar o primeiro terminar.
- Interface nova: cada botão usa os **valores do momento do clique** (projeto, linhas selecionadas, planilha). Trocar a seleção com a IA ou o robô rodando não mistura mais um lote com o outro.

**Gestão PMIB**

- Gestão PMIB: novo bloco **"Autorizações de entrega de Itaipu"**. Escolha o export que Itaipu manda (`sobressalentes_autorizados_AAAAMMDDhhmm.xlsx`) e clique em **APLICAR AUTORIZAÇÕES**: cada PMIB dele vira AUTORIZADO nos `_STATUS_PMIB` da Pasta Raiz, com os dias de atraso até a data do export. Antes era um script à parte, com os caminhos fixos no código.
- Gestão PMIB: novo **painel de sobressalentes** em HTML. O botão **"Gerar painel"** (e a caixa "Gerar painel ao terminar") grava o `Painel de Sobressalentes.html` na Pasta Raiz e o abre no navegador, sem Power BI e sem internet. Os números batem com os do Power BI, que continua sendo o painel oficial.
- Gestão PMIB: cada `_STATUS_PMIB` passa a ter a **SITUAÇÃO DA AUTORIZAÇÃO** e os **DIAS DE ATRASO** de cada linha recalculados e gravados pela regra de **15 dias úteis** a contar do e-mail (antes eram 14 dias corridos, contados só na planilha de mapeamento). AUTORIZADO nunca é desfeito, e DOCUMENTAL e TÍTULO ficam N/A.
- Gestão PMIB: gravar no `_STATUS_PMIB` **não apaga mais os comentários** (os de conversa) nem as listas suspensas. Só as células que mudaram são regravadas, e o Box guarda a versão anterior.
- Gestão PMIB: pastas de teste, obsoletas e cópias (`testes_autospec`, `00 - OBSOLETO`, `BACKUP`, "- Copy"...) ficam de fora, e cada arquivo ignorado aparece no log com o motivo. Antes o link "Abrir Box" de uma lista podia apontar para a cópia de teste.
- Gestão PMIB: a planilha de mapeamento vira cadastro. O SIG-FT grava nela só o link, a SITUAÇÃO NO PMIB e a REVISÃO EM USO, lida da linha de revisão do `_STATUS_PMIB`. As contagens vêm dos `_STATUS_PMIB`, pelo Power BI.
- Gestão PMIB: arquivo aberto no Excel **não interrompe mais o processo a cada arquivo**. Antes de gravar, o SIG-FT mostra **uma lista** com os arquivos travados e o motivo de cada um (aberto no Excel e por quem, somente leitura, Box desconectado, disco cheio...): feche e clique em **Repetir**, ou **Seguir sem eles**. No fim da etapa, outra lista com o que não gravou e o botão **Repetir só estes**. O log termina com "Não gravados nesta rodada", dizendo o que fazer em cada caso. Vale também para o "Aplicar autorizações".
- Gestão PMIB: com a planilha de mapeamento aberta, **Repetir** relê a planilha antes de gravar, então o que você salvou nela antes de fechar continua lá. Antes o SIG-FT gravava por cima. **Seguir sem ela** não cancela mais o processo: os `_STATUS_PMIB` continuam sendo atualizados.
- Gestão PMIB: renomear um `_STATUS_PMIB` que está aberto no Excel não deixa mais uma cópia com o nome novo ao lado do antigo.
- Gestão PMIB: novo botão **CONFERIR NO PORTAL**, no bloco das autorizações. O SIG-FT abre o PMIB (você faz o login), procura cada ficha FÍSICA E DOCUMENTAL ainda sem AUTORIZADO e lê o **código SAP de recebimento**, que aparece na ficha quando a Itaipu autoriza a entrega. As que têm o código viram AUTORIZADO, com os dias de atraso contados até o dia da conferência, sem esperar o export de autorizados (que continua funcionando como antes). O fim do log lista as fichas que não foram achadas no portal e as que ficaram sem resposta. O SIG-FT só navega no portal como uma pessoa: não consulta o banco de dados da Itaipu.

**Atualização automática**

- Atualização automática: passa a baixar **só os arquivos que mudaram** desde a versão instalada, em vez do instalador completo (mais de 300 MB). O aviso mostra o tamanho da atualização ao lado do tamanho do completo. Quem pulou versões recebe o completo, como antes, e se a atualização pequena falhar no download (a rede da empresa às vezes corta o arquivo no fim), o SIG-FT baixa o completo na hora, em vez de parar com erro. Vale da próxima versão em diante: quem está na 1.1.1 recebe esta ainda pelo instalador completo.
- Atualização automática: caixa nova **"Versões de teste"** ao lado do botão "Atualizações", na tela inicial. Desmarcada, nada muda. Marcada, o aviso oferece também os pré-lançamentos, para testar uma versão antes de ela chegar a todo mundo.
- Atualização automática: **"Atualizar agora" com um robô ou uma tradução rodando pergunta antes**, como o "X" da janela já fazia. O SIG-FT fecha sozinho para instalar, e a tarefa seria interrompida no meio, com risco de deixar uma planilha gravada pela metade. Enter responde "Não".

**Cria Fichas**

- Cria Fichas: a IA passa a **ler o que cada material é** antes de escolher o PDM ("DISPLAY CRISTAL LIQUIDO" é um INDICADOR DIGITAL), e a busca no catálogo usa essa leitura junto com as palavras da descrição. PDM bom que antes nem chegava à IA passa a ser oferecido a ela. Se essa leitura falhar, o lote segue como antes.
- Cria Fichas: **NENHUM só quando precisa de PDM novo.** Na dúvida, a IA dá o melhor palpite com confiança BAIXA, que você corrige com um clique, em vez do NENHUM, que obrigava a procurar à mão entre todos os PDMs. A marca que vem depois de "PARA" (uma plaqueta PARA válvula) não puxa mais a escolha para a família da válvula.
- Cria Fichas: a **revisão dos PDMs** ganha a coluna **Confiança** (ALTA, MÉDIA ou BAIXA; no NENHUM, PDM NOVO?, SEM RESPOSTA ou FORA DO CATÁLOGO), mostra **primeiro o que precisa de atenção**, explica **por que** a IA escolheu cada PDM e, ao trocar o PDM, abre a busca com o **2º e o 3º lugar** da IA no topo. Um ALTA que as conferências do SIG-FT não confirmam aparece como "MÉDIA ↓".
- Cria Fichas: cada revisão confirmada fica registrada em `Documentos\SIG-FT\logs\escolha_pdm.jsonl` (o que a IA escolheu e o que ficou), para medir com o tempo quanto a confiança acerta.

**Aplicação LMR**

- Aplicação LMR: **mais rápida** em fichas com muitos códigos. Cada código é confirmado pela resposta do portal ao CONFIRMAR, em vez de esperar a mensagem do código anterior sair da tela (até 15 s por código), e uma recusa vem com o motivo dado pelo próprio portal. Se a resposta não vier, aquele código é conferido pela mensagem na tela e o resto do lote segue como antes.
- Aplicação LMR: cada TAG é conferida. Depois do ENTER, o SIG-FT espera a tag sair do campo, que é o sinal de que ela entrou na lista, em vez de uma pausa fixa, e avisa no log a tag que não saiu.

## 1.1.1 - 2026-09-28

**Atualização automática**

- Atualização automática: agora funciona de verdade. **Toda vez que o SIG-FT abre**, ele confere no GitHub se saiu versão nova; se saiu, mostra o que mudou e oferece **"Atualizar agora"**, que baixa, confere e instala, e o SIG-FT **abre de novo sozinho** já atualizado. Até a 1.1.0 esse aviso nunca aparecia: o programa não chegava a perguntar.
- Atualização automática: **esta versão precisa ser instalada à mão uma última vez**, pelo instalador da página do Release. A 1.0.0 e a 1.1.0 não sabem procurar atualização; da 1.1.1 em diante, as próximas chegam pelo aviso.
- Atualização automática: botão novo **"Atualizações"** na tela inicial, para procurar versão nova na hora. Quando não dá para atualizar, ele diz por quê (sem conexão, token do build recusado, ou uma cópia que se atualiza pelo `.bat` do Box).
- Atualização automática: com o SIG-FT instalado para todos os usuários, o Windows pede a senha de administrador para atualizar, e o aviso diz isso antes. O programa reabre **na sua conta**, com as suas chaves de API e preferências, mesmo quando quem digita a senha é outra pessoa.

**Tradutor Técnico**

- Tradutor Técnico: a tradução das características passa a rodar **no próprio computador**. Nenhuma resposta sai mais para o Google Tradutor ou o MyMemory, e não precisa de internet, VPN nem chave.
- Tradutor Técnico: **muito mais rápido**. A ficha inteira vai ao tradutor de uma vez, sem a espera de 1 segundo por resposta que havia antes, e um Excel só abre para o lote todo. Antes cada ficha deixava um Excel invisível aberto até o SIG-FT fechar.
- Tradutor Técnico: o vocabulário técnico da casa sai certo (mancal: cojinete, porca: tuerca, arruela: arandela, gaxeta: empaquetadura, conforme desenho: según plano). Termo que sair errado você corrige de vez no **glossário** (botão "Abrir glossário" na tela).
- Tradutor Técnico: resposta que o tradutor não garantiu aparece no log como **[CONFERIR]**, com a pergunta e o motivo; se a tradução mudasse um número, fica o original. Antes, quando o Google falhava, o português ia para a coluna do espanhol sem aviso.
- Tradutor Técnico: número sai como na ficha (`220`, e não `220.0`), e característica com parênteses no nome (`FAIXA DE TENSAO DE ALIMENTACAO (CA)`) passa inteira para o Upload quando a pergunta traz texto de ajuda.
- Instalação: o instalador fica cerca de 200 MB maior, porque o tradutor vem dentro dele.

**Modelos de IA**

- Modelos de IA: o botão **"Atualizar lista de modelos"** volta a trazer o catálogo do **OpenRouter** no SIG-FT instalado para todos os usuários (a instalação padrão). A lista chegava da internet, mas o programa tentava guardá-la na própria pasta, onde o Windows não deixa gravar, e ela era descartada sem aviso — parecia que a chave do OpenRouter não funcionava.
- Gastos de IA: o painel volta a mostrar as chamadas de IA no SIG-FT instalado para todos os usuários, e o botão da pasta de logs abre a pasta certa (`Documentos\SIG-FT\logs`). O registro de cada chamada ia para a pasta do programa, onde o Windows não deixa gravar, e o painel ficava sempre vazio.

**Cria Fichas**

- Cria Fichas: trocar o PDM na revisão volta a funcionar. O PDM escolhido em **"USAR ESTE PDM"** passa a aparecer na tabela e a valer na automação; antes a escolha era ignorada e ficava o PDM que a IA sugeriu.

**Upload de características técnicas**

- Upload de características técnicas: o log passa a dizer **qual provedor e modelo de IA** cada ficha usou (`Enviando … para IA (openrouter / google/gemini-…)`), também na mensagem de erro. Antes um erro de conexão não dizia se a chamada tinha ido pelo Gemini direto ou pelo OpenRouter.
- Upload de características técnicas: característica do tipo **LISTA** passa a sair com **uma opção só**. A IA juntava duas opções numa resposta ("Proteção contra descargas atmosféricas, etc.") e nenhuma casava com a lista do portal. Agora cada vírgula do PDM conta como separador de opções; quando a IA junta duas ou escreve uma que não existe, o SIG-FT pergunta de novo só sobre aquela característica, e se ainda assim não vier uma opção válida, o log avisa e o campo fica para escolher à mão. JSON gerado antes desta versão não é corrigido: rode a IA de novo nas fichas afetadas.

**Aplicação LMR**

- Aplicação LMR: depois de colocar as TAGs, o robô clica **SALVAR**, depois **CONFIRMAR**, e só passa para o próximo código quando o portal mostra "As informações da aplicação LMR foram adicionadas com sucesso!". Antes ele procurava os botões pela posição na tela e marcava o código como inserido sem conferir nada. Sem a mensagem, o código vai para o `erros_lmr.csv`, a ficha fica INCOMPLETA no `_STATUS_PMIB`, e o SIG-FT para e diz o motivo antes de seguir.

**Fichas duplicadas**

- Fichas duplicadas: o **log de auditoria** passa a ser gravado em `Documentos\SIG-FT\logs` no SIG-FT instalado. Antes ele tentava gravar na pasta do programa e o arquivo não era criado.

**Instalação e fechamento do SIG-FT**

- Instalação: o instalador não trava mais com "o SIG-FT Itaipu está atualmente em execução" quando o programa está fechado. Se o SIG-FT tiver ficado rodando escondido, sem janela, o instalador o mostra na tela "Preparando para instalar" e o fecha sozinho. Antes, a única saída era encerrar o `SIG-FT.exe` pelo Gerenciador de Tarefas.
- Fechar o SIG-FT: fechar a janela passa a encerrar o programa de verdade. Antes, fechar no meio de uma pausa do robô (esperando o login no portal, por exemplo) deixava o SIG-FT rodando escondido, e era isso que travava a instalação. Com uma tarefa em andamento (robô, tradução ou consulta à IA), ele **pergunta antes de fechar**, porque ela é interrompida no ponto em que está.
- Abertura: quando a janela principal não consegue abrir, aparece uma mensagem com o erro e o caminho do log, em vez de o programa ficar rodando escondido.

**AutoSpec**

- AutoSpec: a IA passa a **conferir as respostas do fornecedor** contra o datasheet, na tabela de especificações. Quando o fornecedor respondeu **"Não se aplica"** (ou N/A, "não informado", "-") e o datasheet traz o valor, com a prova conferida (trecho e página), o valor do documento entra na ficha em azul, e a resposta original fica num comentário da célula.
- AutoSpec: resposta do fornecedor **com valor nunca é alterada**. Se ela diverge do datasheet, o log mostra os dois valores, a página e o trecho do documento, para você conferir. Diferença só de unidade ou de escrita (24 Vcc e 24 VDC) não é apontada.
- AutoSpec: ficha já toda preenchida pelo fornecedor deixa de ser pulada: ela é conferida, e só gera o `_completed` se algum "Não se aplica" for corrigido.
- AutoSpec: caixa nova **"Conferir as respostas do fornecedor contra o datasheet"**, marcada. Ela usa uma consulta de IA a mais por ficha que tenha resposta do fornecedor; desmarque no lote em que você só quer preencher. Reprocessar a mesma ficha não gasta de novo.

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
