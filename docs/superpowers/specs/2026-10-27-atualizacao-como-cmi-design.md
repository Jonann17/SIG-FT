# Atualização como a do CMI Suite (2026-10-27)

Pedido do Jonathan, depois de a atualização pequena da 1.3.1-rc.1 falhar na
máquina do Luan (caiu no completo): *"copia el mismo método que tiene el cmi
suite para sus actualizaciones, ahí funciona super bien"*. Escolhida a opção
**híbrida**: o método do CMI onde ele cabe, o pequeno de hoje onde não cabe.

Referência: `Jonann17/CMI-SUITE`, `cmi_suite/core/pacote.py`,
`autoatualizacao.py` e `installer/cmi_suite.iss` (o `/SINAL`).

## O que muda para quem usa

1. **Pasta do programa gravável** (instalação "só para mim", em
   `AppData\Local\Programs`): a atualização baixa um `.zip` só com os arquivos
   que mudaram e o **próprio SIG-FT o aplica, aberto**, e se reabre. Sem
   instalador, sem UAC, sem `.exe` dentro de `.zip` para o proxy cortar.
2. **Pasta não gravável** (Program Files, "para todos") ou o passo 1 falhou: o
   instalador pequeno de hoje (`.zip` → `.exe` → `.bin`) e, por fim, o completo.
3. **Instalador (pequeno ou completo)**: o SIG-FT só fecha depois que o
   instalador avisa que subiu (`/SINAL`). Se ele morrer antes (antivírus,
   política da empresa, UAC recusado), o SIG-FT continua aberto e diz por quê,
   em vez de fechar sem atualizar.

Os apps já instalados (1.3.0, rcs) continuam recebendo os mesmos arquivos de
hoje: o formato novo é uma chave nova do `latest.json` que eles ignoram.

## Formato (igual ao do CMI)

`SIG-FT_Itaipu_Arquivos_<de>_para_<para>.zip`:

    manifesto.json   {"de": ..., "para": ..., "alterados": [...], "removidos": [...]}
    arquivos/<caminho relativo>   (cada arquivo novo ou alterado)

A diferença é a mesma que o `tools/gerar_atualizacao.py` já calcula para o
instalador pequeno (`diferenca(base, novo)`), a partir dos `arquivos.json`
publicados. No `latest.json`, a entrada de cada base ganha
`"arquivos": {"arquivo", "sha256", "tamanho"}`. O nome não começa com
`SIG-FT_Itaipu_Atualizacao_` nem `SIG-FT_Itaipu_Update_` e não é `.exe`: o app
antigo, que escolhe "o primeiro `.exe`" ou pelo prefixo, nunca o pega.

A verificação depois de aplicar é contra o `arquivos.json` **da versão nova**
(publicado em todo Release): cada arquivo listado nele tem de existir com o
SHA256 dele. O `arquivos.json` é baixado e conferido pelo `digest` do asset.

## Aplicar com o programa aberto (`sigft/services/pacote_arquivos.py`)

Copiado do `pacote.py` do CMI, uma implementação só que **monta** (no Release)
e **aplica** (no app):

- cada arquivo a trocar é **renomeado** para `<nome>.sigft-old` (o Windows
  deixa renomear `.exe`/DLL em uso, não sobrescrever) e o novo é escrito;
- removidos também viram `.sigft-old`;
- no fim, confere a pasta contra o `arquivos.json` novo;
- qualquer falha **desfaz na ordem inversa** e levanta `ErroPacote`: a pasta
  fica como estava;
- caminho do zip fora da pasta (zip-slip, absoluto, `..`) é recusado;
- os `.sigft-old` são apagados na abertura seguinte (`limpar_restos`); o que
  ainda estiver em uso fica para a próxima.

## Escolha do caminho (`sigft/services/updater.py`)

`Atualizacao` ganha o pacote de arquivos (quando o `latest.json` traz e o
Release tem o asset) e a URL do `arquivos.json`. O fluxo:

1. tem pacote de arquivos **e** `pasta_instalacao()` é gravável (teste de
   escrita de verdade, como `precisa_elevacao`) **e** o app está empacotado →
   baixa o `arquivos.json` e o `.zip`, confere os SHA256, aplica. Sucesso →
   grava a versão nova em `DisplayVersion` (HKCU, melhor esforço, como o
   `_registrar_versao` do CMI: o instalador pequeno seguinte confere ali) e
   reabre o `.exe` (processo novo, desacoplado) e fecha;
2. falhou o passo 1 (`ErroPacote`, download, SHA): log com o motivo, e segue
   para a corrente de hoje (pequeno em zip → exe → bin → completo);
3. instalador: `instalar()` passa `/SINAL=<arquivo>` e **espera** o arquivo
   existir (ou o processo sair, ou 10 min). Saiu antes → `InstaladorNaoIniciou`
   com o código e o caminho do log (`instalacao.log`), e a janela mostra o erro
   com o app aberto.

### O escopo do instalador e os apps antigos (revisão de 2026-10-27)

O instalador COMPLETO é sempre "só para mim" (`PrivilegesRequired=lowest`,
`PrivilegesRequiredOverridesAllowed=commandline`), e quem estava em Program
Files é migrado por ele (`MigrarDaInstalacaoParaTodos`). O PEQUENO, não: ele
volta ao que saiu até a 1.3.1-rc.4 (`admin` + `dialog commandline`). Os apps
1.2.0 a 1.3.1-rc.4 em Program Files escolhem o pequeno sempre que o `de` dele
é a versão deles, e não passam `/CURRENTUSER` nem `/SINAL`; com `lowest`, o
`VersaoInstalada` leria HKCU, não acharia nada, recusaria e reabriria o app
velho, que ofereceria a mesma atualização de novo, sem fim. Com `dialog`
permitido, o `UsePreviousPrivileges` do Inno reaproveita o escopo da
instalação existente: Program Files atualiza em Program Files, a do usuário no
perfil. O app novo passa sempre `/CURRENTUSER`. A cópia de Program Files que o
pequeno levar à 1.3.1-rc.6 ou depois tem a pasta sem escrita, e a atualização
seguinte dela é o completo (`checar`), que migra.

Dois cuidados a mais na escolha:

- `checar` (no Windows, app empacotado, pasta gravável) lê o `DisplayVersion`
  de HKCU; diferente da versão que roda (ou ausente), vai só o completo, com o
  motivo no log. O pequeno o confere e recusaria; os arquivos deixariam
  registro e pasta em versões diferentes.
- `_registrar_versao` só regrava HKCU quando o `InstallLocation` dele (ou o
  `Inno Setup: App Path`) é a pasta atualizada, comparada sem caixa e sem a
  barra do fim; o resultado vai para o log.
- O pacote de arquivos não depende do pequeno: faltando o asset do pequeno, a
  atualização é o completo com os arquivos por cima (`interpretar_release`).

A migração recusada (UAC negado, sem a senha) mostra uma caixa só, fora do
modo silencioso: a cópia nova funciona, a antiga continua em Program Files, e
sai por Configurações > Aplicativos > SIG-FT Itaipu, com a senha de
administrador. No silencioso, só o log.

## Inno (`installer/sigft.iss`)

`InitializeSetup` cria o arquivo de `/SINAL` (se passado) logo ao subir, nos
dois modos (pequeno e completo). Nada mais muda: `CloseApplications=force`
continua fechando o app se ele ainda estiver aberto na hora de copiar.

## Interface (`sigft/app_qt/atualizacao.py`)

Mesma janela. Textos novos (com `t()`): "Aplicando a atualização…", "Atualizado.
Reabrindo o SIG-FT…", e a explicação do `InstaladorNaoIniciou`. Cada passo
escreve `[atualizacao] …` no `sigft.log`. No diário (`diario.log`), na thread,
logo antes de mandar fechar (o arquivo do `/SINAL` apareceu, ou os arquivos
foram aplicados): `ATUALIZACAO <por arquivos | pelo instalador pequeno |
pelo instalador completo> v<de> -> v<para>`, com `(exe=..., log=...)` no
instalador, e o `FECHAMENTO` -- ali, e não só na thread da interface, porque o
`CloseApplications=force` pode matar o app antes. O diário grava o
`FECHAMENTO` uma vez por sessão.

## Fora do escopo

Atualizar o DocManager ou o Corella; o canal de testes. (O padrão do
instalador mudou depois, no mesmo dia, a pedido do usuário: sempre "só para
mim", sem pergunta, com a migração de quem estava em Program Files -- ver o
comentário do escopo em `installer/sigft.iss` e `MigrarDaInstalacaoParaTodos`.
Pasta sem escrita recebe direto o instalador completo, nunca o pequeno nem os
arquivos: `updater.checar`. O pequeno ficou com o escopo de antes, por causa
dos apps antigos: ver "O escopo do instalador e os apps antigos".)

## O que não dá para provar aqui

Renomear o `.exe` em uso, o `winreg`, o Inno com `/SINAL` e a reabertura só
existem no Windows. Aqui: montar/aplicar/desfazer o zip em pasta temporária,
a escolha do caminho, a espera do sinal com processo falso, o `latest.json`
gerado e o `release.yml`. A prova é uma rc instalada "só para mim" (deve vir
pelo zip de arquivos) e outra em Program Files (deve vir pelo pequeno de hoje,
com `/SINAL`).
