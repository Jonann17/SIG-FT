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
;  [2026-10-07] MODO ATUALIZACAO -- o instalador PEQUENO, so com o que mudou:
;      iscc /DAtualizacao=1 /DVersaoDe=1.2.0-rc.3 /DMyAppVersion=1.2.0-rc.4 installer\sigft.iss
;  Quem chama e o tools/gerar_atualizacao.py (no release.yml), depois de gerar
;  ao lado deste arquivo as duas listas que ele inclui. Saida:
;  installer\Output\SIG-FT_Itaipu_Atualizacao.exe. Ver
;  docs/superpowers/specs/2026-10-07-atualizacao-incremental-design.md.
;
;  ⚠️ Este arquivo tem testes: tests/test_instalador.py le as diretivas daqui
;  e reprova as armadilhas que ja custaram caro a alguem (o AppMutex que
;  travava a instalacao, a versao com sufixo, o [InstallDelete] largo demais,
;  o AppUserModelID divergente e o app que nao reabria depois de atualizar).
;  Verde nele nao prova que o instalador COMPILA -- so o Windows com o Inno
;  Setup diz isso.
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

; O instalador pequeno so serve para a versao de onde a diferenca saiu: sem
; ela, nao ha o que conferir antes de copiar (ver PrepareToInstall, no [Code]).
#ifdef Atualizacao
  #ifndef VersaoDe
    #error Modo atualizacao sem /DVersaoDe=<a versao instalada que ele atualiza>
  #endif
#endif

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
#ifdef Atualizacao
OutputBaseFilename=SIG-FT_Itaipu_Atualizacao
; Vai para onde o SIG-FT ja esta (UsePreviousAppDir, padrao do Inno).
DisableDirPage=yes
DisableReadyPage=yes
#else
OutputBaseFilename=SIG-FT_Itaipu_Setup
#endif
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
; O Windows nao deixa sobrescrever um .exe em execucao: o SIG-FT aberto tem de
; ser fechado antes de trocar os arquivos. Quem faz isso e o Restart Manager
; (CloseApplications): ele pergunta QUEM esta usando os arquivos desta pasta,
; mostra o SIG-FT na pagina "Preparando para instalar" e o fecha com um
; clique. Em /SILENT (a atualizacao automatica) fecha sozinho.
;
; `force`, e nao `yes`: um SIG-FT sem janela (o "fantasma", ver abaixo) nao
; tem como receber o pedido educado de fechar; sem forcar, o Restart Manager
; desiste dele e a troca dos arquivos falha.
;
; [2026-09-25] SEM AppMutex, de proposito. Ele travou a instalacao da
; 1.1.1-rc.1: "o instalador detectou que o SIG-FT Itaipu esta atualmente em
; execucao", com o SIG-FT fechado. Havia um SIG-FT.exe vivo e SEM JANELA (um
; robo parado numa pausa quando a pessoa fechou o app). O AppMutex so pergunta
; "existe um mutex com esse nome?": nao distingue app aberto de fantasma, nem
; da copia do ZIP do Box rodando de OUTRA pasta, e nao oferece fechar -- so
; "feche e clique OK", que a pessoa nao tinha como atender. Em /SILENT ainda
; abortava sozinho. tests/test_instalador.py (secao A) reprova a volta dele.
CloseApplications=force
RestartApplications=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

#ifndef Atualizacao
; Atalhos so no completo: no pequeno eles ja existem, e o [Tasks] perguntaria de novo.
[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Area de Trabalho"; GroupDescription: "Atalhos:"; Flags: checkedonce
#endif

[InstallDelete]
; O Inno sobrescreve o que esta em [Files], mas NAO apaga o que sumiu entre
; uma versao e outra. Sem isto, `_internal\` acumula modulo orfao de build
; antigo -- e modulo orfao continua sendo encontrado pelo Python.
;
; ⚠️ NUNCA ponha `{app}` sozinho (nem `{app}\*`) aqui. Ali mora o
; `unins000.dat`, o registro do que o instalador escreveu: apagando-o, a
; entrada em Programas e Recursos fica orfa e o SIG-FT deixa de ser
; desinstalavel pelo caminho normal. tests/test_instalador.py reprova isso.
#ifdef Atualizacao
; O PEQUENO apaga so o que sumiu desde a VersaoDe, arquivo por arquivo. Limpar
; o _internal inteiro, como o completo faz, apagaria tudo o que ele nao traz --
; e ele so traz o que mudou. tests/test_instalador.py (secao I) reprova isso.
#include "atualizacao_remover.iss"
#else
Type: filesandordirs; Name: "{app}\_internal"
#endif

[Files]
#ifdef Atualizacao
; So os arquivos que mudaram desde a VersaoDe (o CHANGELOG entra quando muda).
#include "atualizacao_arquivos.iss"
#else
; Toda a pasta onedir gerada pelo PyInstaller.
Source: "..\dist\SIG-FT\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
; O CHANGELOG viaja junto: e dele que sai o "o que ha de novo" depois de
; atualizar. Sem ele no pacote, a janela de novidades abre vazia.
Source: "..\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion
#endif

#ifndef Atualizacao
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
#endif

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir o {#AppName}"; \
    Flags: nowait postinstall skipifsilent
; [2026-09-25] A atualizacao automatica roda este instalador em /SILENT, e a
; linha de cima (skipifsilent) NAO roda nesse modo: o app fechava para
; atualizar e nao voltava. Esta o reabre, com duas condicoes:
;   - SO quando o proprio app pediu (/REABRIR=1, ARG_REABRIR em
;     sigft/services/updater.py): a TI instalando em massa com /SILENT nao ve
;     o SIG-FT abrir sozinho na maquina de todo mundo;
;   - na conta de QUEM ESTAVA USANDO (runasoriginaluser): o UAC pode ter sido
;     respondido com a senha de outra pessoa, e o app aberto como ela nao
;     acharia as chaves de API nem as preferencias.
; tests/test_instalador.py (secao H) confere os dois lados.
Filename: "{app}\{#AppExe}"; Flags: nowait runasoriginaluser; \
    Check: ReabrirDepoisDeAtualizar

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

[Code]
// Verdadeiro so quando quem disparou o instalador foi a atualizacao automatica
// do proprio app, que passa /REABRIR=1 (ARG_REABRIR em
// sigft/services/updater.py). O nome do parametro tem de bater com o de la:
// divergindo, nao ha erro nenhum -- o app so deixa de reabrir.
function ReabrirDepoisDeAtualizar: Boolean;
begin
  Result := ExpandConstant('{param:REABRIR|0}') = '1';
end;

#ifdef Atualizacao
// [2026-10-07] O instalador PEQUENO so serve para a versao de onde a
// diferenca foi calculada (VersaoDe): sobre outra, ele deixaria uma mistura
// das duas. A versao instalada e a do registro do desinstalador
// (DisplayVersion, que o Inno grava a partir do AppVersion -- do completo e
// do pequeno), na mesma visao em que esta instalacao vai gravar. Diferente:
// nada e copiado, e o app volta a abrir; na abertura seguinte o app escolhe o
// arquivo pelo que de fato esta instalado.
const
  ChaveDesinstalar = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{9F2C4A18-51D7-4E0B-9A3C-5B7E1D6A2C40}_is1';

function VersaoInstalada: String;
begin
  Result := '';
  if IsAdminInstallMode then
  begin
    if IsWin64 then
      RegQueryStringValue(HKLM64, ChaveDesinstalar, 'DisplayVersion', Result);
    if Result = '' then
      RegQueryStringValue(HKLM32, ChaveDesinstalar, 'DisplayVersion', Result);
  end
  else
    RegQueryStringValue(HKCU, ChaveDesinstalar, 'DisplayVersion', Result);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Instalada: String;
  Codigo: Integer;
begin
  Result := '';
  Instalada := VersaoInstalada;
  if Instalada <> '{#VersaoDe}' then
  begin
    if Instalada = '' then
      Instalada := '(nenhuma)';
    Log('Atualizacao recusada: instalada ' + Instalada + ', esperada {#VersaoDe}.');
    Result := 'Esta atualizacao leva o SIG-FT da v{#VersaoDe} para a v{#MyAppVersion}, mas a versao ' +
              'instalada e ' + Instalada + '. Nada foi alterado: use o instalador completo, na pagina de Releases.';
    if ReabrirDepoisDeAtualizar then
      ExecAsOriginalUser(ExpandConstant('{app}\{#AppExe}'), '', '', SW_SHOWNORMAL, ewNoWait, Codigo);
  end;
end;
#endif
