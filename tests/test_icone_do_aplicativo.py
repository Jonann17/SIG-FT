# -*- coding: utf-8 -*-
"""O icone do SIG-FT: um arquivo so, e com os tamanhos que o Windows usa.

DOIS PAPEIS QUE E FACIL CONFUNDIR (e o comentario do main.py ja avisava):

    ICONE  -> barra de tarefas, barra de titulo, o .exe, o instalador.
              NUNCA aparece dentro da tela.
    LOGO   -> imagem desenhada DENTRO da janela.

Em 2026-09-22 o usuario trocou o icone e, junto, pediu que a SPLASH (a tela
de abertura) passasse a mostrar o mesmo desenho. A barra lateral continua
com o simbolo da GE Vernova -- a decisao dele, em duas metades:

    "esse svg para ficar no icone do windows e no aplicativo quando vai
     inicializar. A logo interna do app ainda pode ser o png da GE vernova."

O PROBLEMA QUE ESTA TROCA TAMBEM CONSERTA
------------------------------------------
O `.ico` anterior tinha UM tamanho so: 256x256. O `Gerar-Executavel.bat`
reescrevia um multi-resolucao em `build/SIG-FT.ico` antes de chamar o
PyInstaller -- mas **o workflow de Release nao roda o .bat**. Entao o `.exe`
publicado caia no fallback do spec, que e o arquivo do repositorio, e o
Windows tinha de reduzir 256 -> 16 sozinho para a barra de tarefas. O
resultado e o icone borrado, e so aparece na maquina de quem instalou.

Por isso o `.ico` versionado agora ja nasce com todos os tamanhos: o build
local e o do CI passam a entregar a mesma coisa.
"""
import pathlib
import struct


RAIZ = pathlib.Path(__file__).resolve().parent.parent

ICONE = RAIZ / "assets" / "icone-sig-ft.ico"
LOGO_DA_SPLASH = RAIZ / "assets" / "icone-sig-ft.png"
LOGO_DA_GE = RAIZ / "assets" / "logo.png"

# O que o Windows pede em cada lugar: 16 na barra de titulo e na lista de
# arquivos, 32 no atalho, 48 no Explorer em icones medios, 256 em icones
# extra-grandes. Sem o tamanho exato, ele reduz o maior que achar -- e reduzir
# 256 para 16 borra.
TAMANHOS_QUE_O_WINDOWS_USA = {16, 24, 32, 48, 64, 128, 256}


def _tamanhos_do_ico(caminho: pathlib.Path) -> set[int]:
    """As larguras declaradas no diretorio do `.ico`, lidas na mao.

    Sem PIL de proposito: e o mesmo padrao de `test_distribuicao_box.py`, e
    um guard que depende de dependencia opcional e um guard que um dia some.

    Formato: 6 bytes de cabecalho (reservado, tipo, quantidade) e depois uma
    entrada de 16 bytes por imagem, comecando pela largura. Largura 0
    significa 256 -- o campo tem um byte so.
    """
    dados = caminho.read_bytes()
    _reservado, _tipo, quantidade = struct.unpack("<HHH", dados[:6])
    larguras = set()
    for i in range(quantidade):
        largura = dados[6 + i * 16]
        larguras.add(largura if largura else 256)
    return larguras


# =============================================================================
# A. O arquivo do icone
# =============================================================================

def test_o_icone_existe():
    assert ICONE.is_file(), f"nao achei {ICONE}"


def test_o_icone_e_um_ico_de_verdade():
    """Extensao nao faz formato. Um PNG renomeado faz o ISCC abortar."""
    reservado, tipo, quantidade = struct.unpack("<HHH", ICONE.read_bytes()[:6])

    assert reservado == 0 and tipo == 1, "cabecalho de .ico invalido"
    assert quantidade > 0, "o .ico nao tem nenhuma imagem dentro"


def test_o_icone_tem_TODOS_os_tamanhos_que_o_windows_usa():
    """O conserto do icone borrado na barra de tarefas.

    Com um tamanho so, o Windows reduz sozinho, e 256 -> 16 fica ilegivel.
    Este teste roda no CI, que e onde o `.exe` publicado e montado.
    """
    faltando = TAMANHOS_QUE_O_WINDOWS_USA - _tamanhos_do_ico(ICONE)

    assert not faltando, (
        f"faltam os tamanhos {sorted(faltando)} no {ICONE.name}. O Windows vai "
        f"reduzir o maior que achar, e o icone sai borrado na barra de tarefas."
    )


# =============================================================================
# B. Um icone so, para os tres consumidores
# =============================================================================
# O icone aparece em tres lugares, e cada um tem o seu jeito de apontar para
# ele. Se um ficar para tras numa troca, o .exe, a janela e o instalador
# passam a mostrar desenhos diferentes -- e ninguem percebe ate instalar.

def test_a_janela_usa_o_icone_novo():
    main = (RAIZ / "sigft" / "app" / "main.py").read_text(encoding="utf-8")

    assert f'ARQUIVO_DO_ICONE = os.path.join("assets", "{ICONE.name}")' in main


def test_o_executavel_usa_o_MESMO_icone():
    """O fallback do spec e o que o CI usa -- `build/SIG-FT.ico` nao existe la."""
    spec = (RAIZ / "SIG-FT.spec").read_text(encoding="utf-8")

    assert ICONE.name in spec, (
        f"o SIG-FT.spec nao aponta para {ICONE.name}; o .exe sairia com o "
        f"icone antigo"
    )


def test_o_instalador_usa_o_MESMO_icone():
    iss = (RAIZ / "installer" / "sigft.iss").read_text(encoding="utf-8")

    assert ICONE.name in iss, (
        f"o instalador nao aponta para {ICONE.name}; o Setup.exe sairia com o "
        f"icone antigo"
    )


def test_o_script_de_build_local_parte_do_MESMO_icone():
    """Senao o build local e o do CI entregam icones diferentes."""
    bat = (RAIZ / "Gerar-Executavel.bat").read_text(encoding="utf-8", errors="replace")

    assert ICONE.name in bat


# =============================================================================
# C. Splash x barra lateral -- a decisao do usuario, travada
# =============================================================================

def test_a_splash_mostra_o_logo_NOVO():
    """"...e no aplicativo quando vai inicializar" -- a tela de abertura.

    Em dois passos porque o nome do arquivo mora numa constante: o corpo da
    splash aponta para ela, e ela aponta para o arquivo novo. Medir so o
    literal reprovaria a versao com constante, que e a melhor das duas.
    """
    main = (RAIZ / "sigft" / "app" / "main.py").read_text(encoding="utf-8")
    splash = main[main.index("class SplashScreen"):main.index("class SIG_FT_App")]

    assert "ARQUIVO_DO_LOGO_DA_SPLASH" in splash, (
        "a splash nao usa a constante do logo de abertura"
    )
    assert (f'ARQUIVO_DO_LOGO_DA_SPLASH = os.path.join("assets", '
            f'"{LOGO_DA_SPLASH.name}")') in main, (
        f"a constante nao aponta para {LOGO_DA_SPLASH.name}"
    )
    assert "logo.png" not in splash, (
        "a splash continua com o logo da GE -- era o que a troca mudou"
    )


def test_a_barra_lateral_CONTINUA_com_a_GE_vernova():
    """"A logo interna do app ainda pode ser o png da GE vernova."

    A metade da decisao que e facil atropelar ao trocar a outra.
    """
    main = (RAIZ / "sigft" / "app" / "main.py").read_text(encoding="utf-8")
    app = main[main.index("class SIG_FT_App"):]

    assert "logo.png" in app, (
        "a barra lateral perdeu o simbolo da GE Vernova"
    )


def test_o_logo_da_splash_existe_e_tem_transparencia():
    """Fundo branco num icone vira um quadrado branco na barra de tarefas.

    Le o IHDR do PNG na mao: o byte 25 e o tipo de cor, e 6 = RGBA.
    """
    assert LOGO_DA_SPLASH.is_file(), f"nao achei {LOGO_DA_SPLASH}"
    dados = LOGO_DA_SPLASH.read_bytes()

    assert dados[:8] == b"\x89PNG\r\n\x1a\n", "nao e um PNG"
    largura, altura = struct.unpack(">II", dados[16:24])
    assert largura == altura, f"o icone nao e quadrado ({largura}x{altura})"
    assert dados[25] == 6, "o PNG nao tem canal alfa -- o fundo sairia opaco"


def test_o_logo_da_GE_continua_no_repositorio():
    """Quem some por engano numa troca de asset e o que ficou para tras."""
    assert LOGO_DA_GE.is_file()
