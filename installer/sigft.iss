; ============================================================================
;  SIG-FT Itaipu -- Instalador (Inno Setup 6+)
;
;  Normalmente NAO e compilado a mao: o workflow .github/workflows/release.yml
;  roda o build e o ISCC a cada tag v*.
;
;  Compilar localmente (precisa do dist\SIG-FT\ pronto pelo Gerar-Executavel):
;      iscc /DMyAppVersion=1.0.0 installer\sigft.iss
;  Saida: installer\Output\SIG-FT_Itaipu_Setup.exe
;
;  ⚠️ Este arquivo tem testes: tests/test_instalador.py le as diretivas daqui
;  e reprova as quatro armadilhas que ja custaram caro a alguem (o mutex
;  divergente, a versao com sufixo, o [InstallDelete] largo demais e o
;  AppUserModelID divergente). Verde nele nao prova que o instalador COMPILA
;  -- so o Windows com o Inno Setup diz isso.
; ============================================================================

; A versao vem do build (`iscc /DMyAppVersion=...`). O valor abaixo e so o
; padrao de quem compila a mao sem passar nada.
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

; VersionInfoVersion e o numero de versao BINARIO do Windows (o que aparece
; nas Propriedades do arquivo) e SO ACEITA DIGITOS: "1.0.0-rc.1" faz o Inno
; abortar com 'Value of [Setup] section directive "VersionInfoVersion" is
; invalid'. Por isso um pre-lancamento tem DUAS versoes: a de exibicao, com o
; sufixo, e esta, so numerica. O workflow calcula e passa
; /DMyVersionInfo=1.0.0; quem compilar a mao um pre-lancamento precisa passar
; tambem.
#ifndef MyVersionInfo
  ; Corta o sufixo de pre-lancamento aqui dentro, em vez de exigir que quem
  ; compila passe as DUAS versoes. O workflow ja passa /DMyVersionInfo; esta
  ; conta existe para quem compila a mao: sem ela, um
  ; `iscc /DMyAppVersion=1.0.0-rc.1` abortaria, e a mensagem do Inno nao diz
  ; que o problema e o sufixo.
  #if Pos("-", MyAppVersion) > 0
    #define MyVersionInfo Copy(MyAppVersion, 1, Pos("-", MyAppVersion) - 1)
  #else
    #define MyVersionInfo MyAppVersion
  #endif
#endif

#define AppName "SIG-FT Itaipu"
#define AppExe "SIG-FT.exe"

[Setup]
AppId={{9F2C4A18-51D7-4E0B-9A3C-5B7E1D6A2C40}
AppName={#AppName}
AppVersion={#MyAppVersion}
AppVerName={#AppName} {#MyAppVersion}
VersionInfoVersion={#MyVersionInfo}
AppPublisher=CMI - Consorcio Itaipu
AppUpdatesURL=https://github.com/luanccozer/SIG-FT/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=SIG-FT_Itaipu_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; O pacote passa de 400 MB; em 32 bits a compressao estoura a memoria.
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\assets\icone-sig-ft.ico
UninstallDisplayIcon={app}\{#AppExe}

; --- Escopo da instalacao -------------------------------------------------
; O padrao continua sendo "para todos" (Program Files, com admin), mas o
; instalador PERGUNTA -- pedido do usuario. Quem nao tem senha de
; administrador escolhe "somente para mim" e vai para %LOCALAPPDATA%\Programs;
; ai a atualizacao automatica roda sem nenhum popup do UAC.
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog commandline

; --- Atualizacao por cima da versao anterior ------------------------------
; AppMutex e a peca que faz a atualizacao funcionar: o app cria este mutex
; nomeado ao abrir (sigft/core/instancia.py, NOME_MUTEX). Com ele o Inno
; DESCOBRE que o SIG-FT esta rodando e o fecha antes de trocar os arquivos --
; sem isso a instalacao falha com "arquivo em uso", o sintoma classico de
; auto-update quebrado.
;
; OS DOIS NOMES TEM QUE SER IGUAIS, e a divergencia nao da erro nenhum: so faz
; a atualizacao falhar. tests/test_instalador.py le os dois e reprova se
; divergirem.
AppMutex=SIGFTItaipu_AppMutex
CloseApplications=yes
RestartApplications=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Area de Trabalho"; GroupDescription: "Atalhos:"; Flags: checkedonce

[InstallDelete]
; O Inno sobrescreve o que esta em [Files], mas NAO apaga o que sumiu entre
; uma versao e outra. Sem isto, `_internal\` acumula modulo orfao de build
; antigo -- e modulo orfao continua sendo encontrado pelo Python.
;
; ⚠️ NUNCA ponha `{app}` sozinho (nem `{app}\*`) aqui. Ali mora o
; `unins000.dat`, o registro do que o instalador escreveu: apagando-o, a
; entrada em Programas e Recursos fica orfa e o SIG-FT deixa de ser
; desinstalavel pelo caminho normal. tests/test_instalador.py reprova isso.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
; Toda a pasta onedir gerada pelo PyInstaller.
Source: "..\dist\SIG-FT\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
; O CHANGELOG viaja junto: e dele que sai o "o que ha de novo" depois de
; atualizar. Sem ele no pacote, a janela de novidades abre vazia.
Source: "..\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; O AppUserModelID e o MESMO que o programa declara em
; sigft/core/instancia.py, antes de a primeira janela existir. Divergindo, o
; Windows trata o atalho fixado e a janela aberta como DOIS aplicativos e
; mostra dois botoes lado a lado. E a versao nao entra no ID: muda-lo a cada
; atualizacao quebraria o atalho que a pessoa fixou.
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; \
    AppUserModelID: "GEVernova.SIGFT.Itaipu"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; \
    AppUserModelID: "GEVernova.SIGFT.Itaipu"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir o {#AppName}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Restos do build que nao constam no manifesto de instalacao.
;
; A pasta de dados do usuario (Documentos\SIG-FT: chaves de API, preferencias,
; logs) NAO e alcancada por nenhuma secao deste arquivo, e e de proposito: a
; frente que a moveu para fora do programa existe justamente para que instalar,
; atualizar e desinstalar nao encostem nela.
Type: filesandordirs; Name: "{app}\_internal\__pycache__"
Type: dirifempty; Name: "{app}"

[Messages]
; As chaves de API ficam em Documentos\SIG-FT e sobrevivem a atualizacao. Quem
; ja usava o SIG-FT tem a importacao feita sozinha na primeira abertura; quem
; e novo precisa cadastra-las uma vez.
brazilianportuguese.FinishedLabel=Instalacao concluida.%n%nPRIMEIRO USO: se os modulos de IA (AutoSpec, Analyzer, PDM) reclamarem de chave, abra o SIG-FT e va em "Configuracao de Chaves API", na tela inicial. E uma vez so -- os dados ficam em Documentos\SIG-FT e continuam valendo depois das atualizacoes.%n%nQuem ja usava o SIG-FT nao precisa fazer nada: as chaves antigas sao importadas sozinhas na primeira abertura.%n%nOs modulos que mexem no portal PMIB usam o Chrome ou o Edge ja instalado nesta maquina.
