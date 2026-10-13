"""Os TEXTOS dos diálogos de ação manual -- sem tkinter, sem customtkinter.

Saíram de `sigft/app/widgets/dialogs.py` para que a interface Qt
(`sigft/app_qt/`) use as mesmas palavras sem puxar o Tk para dentro do processo
(e sem falhar num Python sem Tk, como o do Homebrew no macOS). Texto de
interface é aparência: continua palavra por palavra como estava.

`sigft.app.widgets.dialogs` reexporta tudo daqui, então os nomes antigos
(`dialogs.MSG_EXCEL_BLOQUEADO` etc.) seguem valendo para a interface
CustomTkinter e para os testes dela.

Só biblioteca padrão.
"""
from __future__ import annotations

# Sentinela que as três telas já usavam para escolher a mensagem de login em
# vez da mensagem de "confira e salve". Era uma string solta repetida em três
# arquivos-classe; aqui é uma constante, e quem compara importa daqui.
LOGIN_NECESSARIO = "LOGIN_NECESSARIO"

# Rótulo padrão do botão que solta o robô. É constante porque a tela de
# exclusão de LMR troca o dela: numa ação destrutiva, o botão dizer o que vai
# acontecer ("COMEÇAR A EXCLUSÃO") é mais honesto que um rótulo genérico.
TEXTO_CONTINUAR = "CONTINUAR AUTOMAÇÃO"

# As mensagens, palavra por palavra como estavam. A Fase 7 é zero redesign, e
# texto de interface é aparência: mudar "solte o robô" para "iniciar" seria
# uma alteração de produto sem pedido.
MSG_LOGIN_SOLTAR_ROBO = (
    "O navegador foi aberto.\n\n"
    "1. Faça o LOGIN no site.\n"
    "2. Navegue até a tela inicial do PMIB.\n"
    "3. Clique abaixo para soltar o robô."
)
MSG_LOGIN_LOTE = (
    "O navegador foi aberto.\n\n"
    "1. Faça o LOGIN no site.\n"
    "2. Navegue até a tela inicial do PMIB.\n"
    "3. Clique abaixo para iniciar a automação em lote."
)
MSG_EXCEL_BLOQUEADO = (
    "O arquivo _STATUS_PMIB está aberto no Excel.\n\n"
    "Por favor, FECHE O ARQUIVO e clique em 'Tentar Novamente' para salvar o "
    "status da ficha concluída."
)


def msg_excel_bloqueado(caminho: object) -> str:
    """A mesma mensagem, NOMEANDO o arquivo travado.

    [CP D] Quando a janela passou a servir os 7 pontos de gravação que antes
    falhavam calados, "o arquivo _STATUS_PMIB" deixou de bastar: o `pdm` grava
    ficha e template, o `analyzer` grava relatório, o `autospec` grava a ficha
    preenchida. Dizer QUAL arquivo fechar é a diferença entre o usuário
    resolver em 5 segundos e ficar procurando.
    """
    # `ntpath`, e nao `os.path`: ele corta as DUAS barras (`\\` e `/`) em
    # qualquer sistema. Com `os.path`, um caminho do Windows rodando fora do
    # Windows volta inteiro -- e a janela de 450px, que esta mensagem existe
    # para caber, mostra `C:\Users\...\ficha.xlsx` de ponta a ponta. Em
    # producao o app so roda no Windows e o defeito nao aparece; quem paga e o
    # portao de testes, que roda em Linux (CI) e reprovava a mensagem certa.
    import ntpath

    nome = ntpath.basename(str(caminho)) or str(caminho)
    return (
        f"O arquivo '{nome}' está aberto em outro programa (provavelmente o "
        "Excel), e por isso não pôde ser salvo.\n\n"
        "FECHE O ARQUIVO e clique em 'Tentar Novamente'."
    )


# =============================================================================
# [CP B] As 4 pausas de login que eram `messagebox.showinfo`
# =============================================================================
# Textos PRESERVADOS: cada um diz o que já dizia. Só a forma mudou, para a dos
# passos numerados do modelo. Duas delas carregam instrução específica de qual
# página abrir — isso é informação, não ruído, e some se uniformizarmos.
MSG_LOGIN_APAGAR_LMR = (
    "O navegador foi aberto.\n\n"
    "1. Faça o LOGIN no site.\n"
    "2. Clique abaixo para começar a EXCLUSÃO."
)
MSG_LOGIN_LMR = (
    "O navegador foi aberto.\n\n"
    "1. Faça o LOGIN no site.\n"
    "2. Clique abaixo para começar."
)
MSG_LOGIN_NOVA_FICHA = (
    "O navegador foi aberto.\n\n"
    "1. Faça o LOGIN no portal.\n"
    "2. Navegue até a página com o botão 'Nova Ficha'.\n"
    "3. Clique abaixo quando estiver pronto."
)
MSG_LOGIN_PAGINA_PRINCIPAL = (
    "O navegador foi aberto.\n\n"
    "1. Faça o LOGIN no portal.\n"
    "2. Navegue até a página PRINCIPAL (onde fica a barra de pesquisa).\n"
    "3. Clique abaixo quando estiver pronto."
)

# Rótulo do botão na tela de exclusão de LMR — ação destrutiva.
TEXTO_COMECAR_EXCLUSAO = "COMEÇAR A EXCLUSÃO"


def msg_falha_ao_salvar(nome_secao: str) -> str:
    """Mensagem do `ModuloUploadConditions` quando uma aba não salva."""
    return (
        f"Falha ao salvar a aba '{nome_secao}'. Ocorreu um erro no site.\n\n"
        "1. Resolva o problema no navegador.\n"
        "2. Clique em SALVAR no site.\n"
        "3. Clique no botão abaixo para continuar."
    )


def msg_ficha_preenchida(pmib: str) -> str:
    """Mensagem do `ModuloCopiaFichas` ao terminar uma ficha."""
    return (
        f"Ficha {pmib} preenchida!\n\n"
        "Verifique na tela e copie as pendências (se houverem) do painel ao "
        "lado.\nApós clicar em SALVAR no site, clique no botão abaixo."
    )


# =============================================================================
# [2026-10-06] A lista de arquivos travados
# =============================================================================
# Ver `docs/superpowers/specs/2026-10-06-gravacao-com-retry-design.md`. Pedido
# do Luan: *"identificar qual está travado, deu erro e o motivo. E pedir pra
# fechar e dar retry nessa parte."* O Gestão PMIB pergunta em três momentos
# (`core/excel/travas.py`), e cada um diz nos botões o que vai acontecer.
TEXTOS_TRAVADOS = {
    "antes": {
        "titulo": "Arquivos travados",
        "explicacao": "Antes de gravar, o SIG-FT conferiu os arquivos. Estes não podem ser gravados agora:",
        "rodape": ("Feche-os (salvando o que for seu) e clique em Repetir. Se seguir sem eles, o processo "
                   "roda e lê esses arquivos, mas não grava neles nesta rodada."),
        "repetir": "Repetir",
        "seguir": "Seguir sem eles",
    },
    "depois": {
        "titulo": "Arquivos não gravados",
        "explicacao": "Estes arquivos não foram gravados:",
        "rodape": ("Resolva o motivo e clique em Repetir só estes: o SIG-FT relê cada um e grava de novo. "
                   "Se seguir, eles ficam para a próxima rodada."),
        "repetir": "Repetir só estes",
        "seguir": "Seguir",
    },
    "na_hora": {
        "titulo": "Arquivo travado",
        "explicacao": "Este arquivo não pôde ser gravado:",
        "rodape": ("Feche-o e clique em Repetir: o SIG-FT relê o arquivo antes de gravar, então o que você "
                   "salvou nele continua lá. Se seguir sem ele, o processo continua e o que faltava gravar "
                   "nele fica para a próxima rodada."),
        "repetir": "Repetir",
        "seguir": "Seguir sem ele",
    },
}
