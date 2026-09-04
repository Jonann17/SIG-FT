# -*- coding: utf-8 -*-
"""A distribuição pelo Box: o ícone, o caminho e o que viaja no pacote.

Nada aqui roda o PyInstaller — isso leva minutos e precisa do Windows com o
ambiente montado. O que dá para provar sem compilar é o que mais quebra na
prática: caminho errado, arquivo faltando, e o `.bat` que morre por causa de
um acento. Os três já custaram uma rodada cada.
"""
import pathlib
import struct

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
LAUNCHER = RAIZ / "SIG-FT Itaipu.bat"
PACOTE = RAIZ / "Gerar-Pacote.bat"
ICONE = RAIZ / "assets" / "SIG-FT-logo-2.ico"


# =============================================================================
# O .bat e o acento
# =============================================================================

# Um `.bat` só pode conter ASCII IMPRIMÍVEL. As duas metades da regra
# custaram uma rodada cada, e por motivos diferentes.
_PERMITIDOS = {0x09, 0x0A, 0x0D}  # tab, LF, CR


def _bytes_proibidos(dados):
    """`[(posição, byte)]` do que não pode estar num .bat."""
    return [
        (i, b) for i, b in enumerate(dados)
        if b > 126 or (b < 0x20 and b not in _PERMITIDOS)
    ]


@pytest.mark.parametrize(
    "bat", sorted(RAIZ.glob("*.bat")), ids=lambda p: p.name
)
def test_bat_so_tem_ascii_imprimivel(bat):
    r"""Nem acento, nem caractere de CONTROLE. São dois defeitos reais.

    **Acima de 126 — o acento.** Um `.bat` é lido na PÁGINA DE CÓDIGO do
    console (850 ou 437 no Windows em português), nunca em UTF-8. Um "ó"
    gravado em UTF-8 chega lá como bytes de lixo: um caminho deixa de casar e
    o `if exist` falha em silêncio, mandando o script pelo galho errado. O
    caminho do Box tem acento ("CMI - Consórcio Itaipu"), e por isso ele
    entra por curinga (`Cons*rcio`): o acento existe na PASTA, nunca aqui.

    **Abaixo de 0x20 — o escape que virou byte.** Em 2026-09-04 o
    `Gerar-Executavel.bat` tinha um **0x08 (backspace)** no lugar de
    `\build-exe`: um script Python escreveu o `.bat` com a string não-crua
    `"...\SIG-FT\build-exe"`, e o `\b` virou backspace. O resultado foi o
    build morrendo com

        OSError: [WinError 123] ... 'C:\...\SIG-FT\build-exe'

    A primeira versão deste teste só olhava `> 127` e passou por cima — 0x08
    é ASCII. As duas metades são a mesma família (byte errado num arquivo que
    ninguém relê), e agora as duas estão cobertas.

    O byte é INVISÍVEL num editor: só uma varredura de bytes o denuncia.
    """
    ruins = _bytes_proibidos(bat.read_bytes())
    assert not ruins, (
        f"{bat.name} tem {len(ruins)} byte(s) proibido(s); o primeiro na "
        f"posicao {ruins[0][0]} e 0x{ruins[0][1]:02X}. Acima de 0x7E: use "
        f"curinga para nomes acentuados e escreva as mensagens sem acento. "
        f"Abaixo de 0x20: e um escape de Python que virou byte -- gere o "
        f"arquivo com string CRUA (r\"...\")."
    )


def test_o_spec_do_build_nao_tem_caractere_de_controle():
    """Mesmo cuidado no `.spec`, que também é gerado/editado por script."""
    ruins = [
        (i, b) for i, b in enumerate((RAIZ / "SIG-FT.spec").read_bytes())
        if b < 0x20 and b not in _PERMITIDOS
    ]
    assert not ruins, f"SIG-FT.spec tem byte de controle: {ruins[:3]}"


# =============================================================================
# O launcher
# =============================================================================

def test_launcher_aponta_para_a_pasta_do_box_escolhida():
    """`_python_pdm`, dentro de 15 - PDM. Decisão do usuário em 2026-09-04."""
    texto = LAUNCHER.read_text(encoding="ascii")

    assert "Cons*rcio Itaipu" in texto, "o nome acentuado tem que entrar por curinga"
    assert "11 - Ger. Engenharia" in texto
    assert "15 - PDM" in texto
    assert "_python_pdm" in texto


def test_launcher_fixa_o_diretorio_de_trabalho():
    """`start /d`, e não `start` seco.

    Sem o `/d` o .exe herda o diretório de onde o .bat foi clicado — a pasta
    do BOX. Como `api_config.json` e `user_prefs.json` são resolvidos pelo
    diretório de trabalho, o app procuraria as chaves no Box e gravaria as
    preferências de cada usuário lá, uma por cima da outra.
    """
    linhas = [
        l.strip()
        for l in LAUNCHER.read_text(encoding="ascii").splitlines()
        if l.strip().startswith("start ")
    ]

    assert linhas, "nenhum `start` no launcher"
    for linha in linhas:
        assert "/d " in linha, f"`start` sem /d: {linha}"


# =============================================================================
# O que viaja no pacote
# =============================================================================

def test_o_pacote_leva_as_chaves_de_api():
    """Decisão do usuário: *"quero que todos quem usa tenha acesso as mesmas
    chaves"*. O `api_config.json` vai para o lado do .exe, que é onde o app o
    procura."""
    texto = PACOTE.read_text(encoding="ascii")

    assert "api_config.json" in texto
    # String CRUA: sem o r, o \\a de "api_config" vira BELL (0x07) e o
    # teste procura um texto que nao existe em lugar nenhum.
    assert r"dist\SIG-FT\api_config.json" in texto


def test_o_pacote_avisa_que_o_zip_carrega_segredo():
    """Um pacote com chave em texto claro não pode sair sem o aviso.

    Quem gera o ZIP precisa saber, na hora de copiar para o Box, que a
    permissão daquela pasta virou o controle de acesso às chaves.
    """
    texto = PACOTE.read_text(encoding="ascii").upper()

    assert "TEXTO CLARO" in texto
    assert "ROTACIONE" in texto


# =============================================================================
# O ícone
# =============================================================================

def test_o_icone_existe_e_e_um_ico_de_verdade():
    assert ICONE.exists(), f"{ICONE.name} sumiu — o build cai no ícone padrão"

    dados = ICONE.read_bytes()
    reservado, tipo, quantas = struct.unpack("<HHH", dados[:6])

    assert reservado == 0 and tipo == 1, "cabecalho de .ico invalido"
    assert quantas >= 1


def test_o_icone_do_app_nao_e_o_logo_da_ge():
    """São dois arquivos com papéis diferentes, e trocá-los é o erro fácil.

    Decisão do usuário: o ícone da barra de tarefas é o do SIG-FT; DENTRO da
    janela continua o símbolo da GE Vernova (*"não quero que apareça dentro
    do APP, por hora mantemos o símbolo da GE VERNOVA"*).
    """
    main = (RAIZ / "sigft" / "app" / "main.py").read_text(encoding="utf-8")

    assert 'ARQUIVO_DO_ICONE = os.path.join("assets", "SIG-FT-logo-2.ico")' in main
    assert "def definir_icone(" in main
    # O logo da GE continua sendo o desenhado na tela.
    assert 'os.path.join("assets", "logo.png")' in main


def test_o_build_prepara_os_tamanhos_pequenos_do_icone():
    """O .ico do repositório tem só 256x256; o Windows usa 16/32/48 na barra
    de tarefas e na barra de título. Sem gerá-los, ele reduz o 256 na hora e
    o ícone sai borrado."""
    bat = (RAIZ / "Gerar-Executavel.bat").read_text(encoding="ascii")

    assert "SIG-FT-logo-2.ico" in bat, "o build tem que partir do .ico do SIG-FT"
    for medida in ("(16,16)", "(32,32)", "(48,48)"):
        assert medida in bat, f"falta a medida {medida}"


# =============================================================================
# O spec do build tem que estar VERSIONADO
# =============================================================================

def test_o_spec_do_build_esta_no_repositorio():
    """`*.spec` no .gitignore quase levou o build junto.

    A regra é o padrão do PyInstaller — e faz sentido lá, porque ele GERA
    specs com `pyi-makespec`, descartáveis. O `SIG-FT.spec` não é gerado: é
    escrito à mão e carrega as decisões do build (por que `--onedir`, os
    `hiddenimports` que a análise estática não enxerga, o tratamento do
    Playwright).

    Ele nunca chegou a ser rastreado: existia só na máquina de quem
    compilava. Num clone novo o `Gerar-Executavel.bat` chamaria
    `pyinstaller SIG-FT.spec` e pararia ali, sem arquivo nenhum.
    """
    spec = RAIZ / "SIG-FT.spec"
    assert spec.exists(), "SIG-FT.spec sumiu — sem ele nao ha como compilar"

    gitignore = (RAIZ / ".gitignore").read_text(encoding="utf-8")
    assert "!SIG-FT.spec" in gitignore, (
        "a excecao `!SIG-FT.spec` saiu do .gitignore: a regra `*.spec` volta "
        "a barrar o spec e o build some do repositorio sem ninguem notar"
    )
