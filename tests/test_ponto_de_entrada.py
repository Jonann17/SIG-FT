# -*- coding: utf-8 -*-
"""As flags de diagnostico funcionam pelo ponto de entrada QUE O BUNDLE RODA.

O DEFEITO QUE ORIGINOU ESTE ARQUIVO (2026-09-21, run #2 do Release)
--------------------------------------------------------------------
O passo `--conferir-pacote` ficou PENDURADO. Nao falhou: pendurou, e ia
consumir os 90 minutos de `timeout-minutes` do job sem publicar nada.

A causa e de uma linha. O despacho precoce morava assim no `main.py`:

    if __name__ == "__main__" and "--conferir-pacote" in sys.argv:
        ...

E o `SIG-FT.spec` empacota `frontend.py`, nao `sigft/app/main.py`. Entao, no
`.exe`, quem e `"__main__"` e o `frontend.py`; o `main.py` entra IMPORTADO,
com `__name__ == "sigft.app.main"`, e a condicao e sempre falsa. O `.exe`
ignorava a flag, caia no `main()` e ABRIA A JANELA -- e o
`Start-Process -Wait` do workflow esperava para sempre por um app que estava
la, aberto, esperando o usuario.

O mesmo valia para `--smoke`: o `if __name__ == "__main__"` do fim do
`main.py` tambem nunca roda no bundle. As duas conferencias que o Release faz
do proprio `.exe` estavam DESLIGADAS, e a forma de descobrir era um passo
pendurado.

POR QUE OS TESTES ANTIGOS DERAM VERDE
--------------------------------------
Porque mediam o arquivo errado. `test_conferencia_do_pacote.py` lia
`sigft/app/main.py` e confirmava que a flag estava tratada la -- e estava. So
que o bundle nao roda aquele arquivo. E a quarta vez nesta frente que um guard
mede a coisa AO LADO da coisa, e a segunda em que o defeito so aparece no
Windows.

Por isso o teste central aqui nao escolhe o arquivo: ele LE O `SIG-FT.spec`,
pega o script que o `Analysis(...)` empacota e roda AQUELE. Trocar o ponto de
entrada no spec passa a arrastar o teste junto, automaticamente.

E por isso ele roda o processo DE VERDADE, com `subprocess`, em vez de ler o
fonte: um despacho precoce so vale se acontecer antes dos imports pesados, e
isso nenhuma leitura de AST prova.

[2026-10-15] A interface e so a Qt: o `main.py` de que este arquivo fala virou
`sigft/app_qt/main.py`, e os testes abaixo olham ele.
"""
import ast
import pathlib
import subprocess
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SPEC = RAIZ / "SIG-FT.spec"

TEMPO_LIMITE_S = 90   # generoso: o que se quer pegar e o pendurado, nao lentidao


def _entrada_do_spec() -> str:
    """O script que o `Analysis(...)` do `SIG-FT.spec` empacota.

    Lido do spec, nunca escrito a mao: e justamente a distancia entre "o
    arquivo que eu testei" e "o arquivo que o bundle roda" que produziu o
    defeito deste arquivo.
    """
    arvore = ast.parse(SPEC.read_text(encoding="utf-8"))

    for no in ast.walk(arvore):
        if (isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
                and no.func.id == "Analysis" and no.args):
            scripts = no.args[0]
            assert isinstance(scripts, ast.List) and scripts.elts, (
                "o primeiro argumento do Analysis deixou de ser uma lista "
                "literal de scripts -- este teste precisa saber qual arquivo o "
                "bundle roda"
            )
            return ast.literal_eval(scripts.elts[0])

    pytest.fail("nao achei a chamada `Analysis(...)` no SIG-FT.spec")


def _rodar(*argumentos: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *argumentos],
        cwd=RAIZ, capture_output=True, text=True, timeout=TEMPO_LIMITE_S,
    )


# =============================================================================
# A. O teste que teria pego o defeito
# =============================================================================

def test_a_conferencia_funciona_PELO_PONTO_DE_ENTRADA_DO_BUNDLE(tmp_path):
    """O caso exato que pendurou o Release.

    Roda o script que o spec empacota, com a flag, e exige que ele RESPONDA.
    Antes do conserto este teste morria com `ModuleNotFoundError: Tk`,
    que e o mesmo defeito que no Windows vira janela aberta e passo eterno.
    """
    entrada = _entrada_do_spec()

    saida = subprocess.run(
        [sys.executable, str(RAIZ / entrada), "--conferir-pacote"],
        cwd=tmp_path, capture_output=True, text=True, timeout=TEMPO_LIMITE_S,
    )

    assert "Conferencia do pacote SIG-FT" in saida.stdout, (
        f"`{entrada} --conferir-pacote` nao produziu o relatorio.\n"
        f"codigo: {saida.returncode}\nstdout: {saida.stdout[-500:]}\n"
        f"stderr: {saida.stderr[-800:]}"
    )


def test_pelo_ponto_de_entrada_do_bundle_NENHUM_import_pesado_acontece():
    """A propriedade que faz a conferencia servir para alguma coisa.

    Ela existe para dizer O QUE FALTA num bundle quebrado. Se ela paga o
    `import Tk` antes de responder, ela quebra junto com o bundle que
    deveria diagnosticar -- e o CI recebe um traceback no lugar do relatorio.

    Neste container nao ha Tk: se o despacho chegar tarde, aparece aqui.
    """
    entrada = _entrada_do_spec()

    saida = _rodar(str(RAIZ / entrada), "--conferir-pacote")

    assert "ModuleNotFoundError" not in saida.stderr, (
        f"`{entrada} --conferir-pacote` chegou nos imports pesados antes de "
        f"responder:\n{saida.stderr[-800:]}"
    )
    assert "Traceback" not in saida.stderr, saida.stderr[-800:]


def test_a_conferencia_tambem_funciona_pelo_modulo(tmp_path):
    """`python -m sigft.app_qt.main` abre a interface direto. Nao pode regredir."""
    saida = subprocess.run(
        [sys.executable, "-m", "sigft.app_qt.main", "--conferir-pacote"],
        cwd=tmp_path, capture_output=True, text=True, timeout=TEMPO_LIMITE_S,
        env={**__import__("os").environ, "PYTHONPATH": str(RAIZ)},
    )

    assert "Conferencia do pacote SIG-FT" in saida.stdout, (
        f"codigo: {saida.returncode}\nstderr: {saida.stderr[-800:]}"
    )


def test_a_conferencia_GRAVA_o_arquivo_pelo_ponto_de_entrada(tmp_path):
    """`console=False`: a saida nao chega pelo terminal, so pelo arquivo.

    E o arquivo que o passo do workflow le. Se o despacho gravasse em outro
    lugar, o CI ficaria sem o relatorio justamente no build quebrado.
    """
    entrada = _entrada_do_spec()

    subprocess.run(
        [sys.executable, str(RAIZ / entrada), "--conferir-pacote"],
        cwd=tmp_path, capture_output=True, text=True, timeout=TEMPO_LIMITE_S,
    )

    assert (tmp_path / "conferencia-do-pacote.txt").is_file(), (
        "o relatorio nao foi gravado no diretorio de trabalho -- e de la que o "
        "workflow o le"
    )


# =============================================================================
# B. `--smoke` tambem sai pelo ponto de entrada do bundle
# =============================================================================
# Abrir a janela exige um display, e nenhum CI em Linux tem um. Entao aqui se
# prova o que da para provar sem display: que a flag CHEGA ao tratamento, em
# vez de ser engolida pelo `main()`. A janela em si e o passo 12 do Release,
# no Windows.

def _fontes_dos_pontos_de_entrada() -> dict[str, str]:
    caminhos = {_entrada_do_spec(), "sigft/app_qt/main.py"}
    return {c: (RAIZ / c).read_text(encoding="utf-8") for c in sorted(caminhos)}


def test_o_ponto_de_entrada_do_bundle_nao_chama_main_direto():
    """O defeito irmao do `--conferir-pacote`, e pela mesma causa.

    O `frontend.py` fazia `main()` no seu `__main__`, e o tratamento de
    `--smoke` estava no `__main__` do `main.py` -- que no bundle nao roda.
    Resultado: `SIG-FT.exe --smoke` abria a janela e pendurava, igual.
    """
    entrada = _entrada_do_spec()
    fonte = (RAIZ / entrada).read_text(encoding="utf-8")
    arvore = ast.parse(fonte)

    chamadas = [
        no.func.id for no in ast.walk(arvore)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
    ]

    assert "main" not in chamadas, (
        f"{entrada} chama `main()` direto. No bundle e ELE o `__main__`, "
        f"entao as flags tratadas no `__main__` do main.py nunca rodam. "
        f"Use o despachante que trata `--smoke` antes de abrir a janela."
    )


@pytest.mark.parametrize("flag", ["--conferir-pacote", "--smoke"])
def test_as_duas_flags_sao_tratadas_no_ponto_de_entrada(flag):
    """Guard contra a volta do defeito por qualquer um dos dois caminhos."""
    entrada = _entrada_do_spec()
    fonte = (RAIZ / entrada).read_text(encoding="utf-8")

    tratada = flag in fonte or "executar_da_linha_de_comando" in fonte

    assert tratada, (
        f"{entrada} e o que o bundle roda, e nao trata `{flag}`. "
        f"A flag seria ignorada e o .exe abriria a janela -- no CI isso nao "
        f"falha, PENDURA."
    )


# =============================================================================
# C. O guard que impede a volta da causa raiz
# =============================================================================

def test_o_despacho_precoce_NAO_depende_de_dunder_name_no_modulo_importado():
    """A causa raiz, nomeada.

    `__name__ == "__main__"` responde "este arquivo foi chamado direto?". Num
    bundle com outro ponto de entrada, a resposta e sempre nao -- e o codigo
    protegido por essa condicao vira codigo morto, em silencio.
    """
    fonte = (RAIZ / "sigft" / "app_qt" / "main.py").read_text(encoding="utf-8")
    arvore = ast.parse(fonte)

    for no in ast.walk(arvore):
        if not isinstance(no, ast.If):
            continue
        trecho = ast.unparse(no.test)
        if "__name__" not in trecho:
            continue
        assert "--conferir-pacote" not in trecho, (
            "o despacho de `--conferir-pacote` voltou para tras de um "
            "`if __name__ == '__main__'` no main.py. No bundle o `__main__` e "
            f"o `{_entrada_do_spec()}`, entao essa condicao nunca e "
            "verdadeira e a flag e ignorada -- o .exe abre a janela e o passo "
            "do CI PENDURA ate o timeout de 90 minutos."
        )


def test_o_spec_e_a_fonte_de_verdade_do_ponto_de_entrada():
    """Se isto falhar, os testes acima estao medindo outro arquivo."""
    entrada = _entrada_do_spec()

    assert (RAIZ / entrada).is_file(), (
        f"o `Analysis(...)` do spec aponta para `{entrada}`, que nao existe"
    )


# =============================================================================
# D. `--smoke` chega ao lugar certo -- comportamento, nao leitura de fonte
# =============================================================================
# As secoes acima provam que a flag nao e ignorada pelo ponto de entrada. Falta
# provar para ONDE ela vai, e isso pede executar o despachante. Da para fazer
# sem display: o que se troca e o `_smoke`, nao o Tk.

def test_smoke_vai_para_o_smoke_e_NAO_abre_a_janela(monkeypatch):
    """A metade do defeito que nao penduraria o CI: abriria a janela.

    Com `--smoke`, o despachante tem de chamar `_smoke()` e sair com o codigo
    dele. Se cair no `main()`, o `.exe` abre a janela e o passo espera para
    sempre -- o mesmo sintoma do `--conferir-pacote`.
    """
    from sigft.app_qt import main as modulo

    chamou = []
    monkeypatch.setattr(sys, "argv", ["SIG-FT.exe", "--smoke"])
    monkeypatch.setattr(modulo, "_smoke", lambda: chamou.append("smoke") or 0)
    monkeypatch.setattr(
        modulo, "main",
        lambda: pytest.fail("abriu a janela em vez de rodar o --smoke"))

    with pytest.raises(SystemExit) as saida:
        modulo.executar_da_linha_de_comando()

    assert chamou == ["smoke"]
    assert saida.value.code == 0


def test_o_codigo_de_falha_do_smoke_chega_ao_processo(monkeypatch):
    """Sem isto o CI ficaria verde com a janela quebrada."""
    from sigft.app_qt import main as modulo

    monkeypatch.setattr(sys, "argv", ["SIG-FT.exe", "--smoke"])
    monkeypatch.setattr(modulo, "_smoke", lambda: 1)

    with pytest.raises(SystemExit) as saida:
        modulo.executar_da_linha_de_comando()

    assert saida.value.code == 1


def test_sem_flag_nenhuma_o_app_abre_normalmente(monkeypatch):
    """O caminho do usuario: clicar no atalho tem de abrir o aplicativo."""
    from sigft.app_qt import main as modulo

    abriu = []
    monkeypatch.setattr(sys, "argv", ["SIG-FT.exe"])
    monkeypatch.setattr(modulo, "main", lambda: abriu.append("janela"))
    monkeypatch.setattr(
        modulo, "_smoke",
        lambda: pytest.fail("rodou o --smoke sem ninguem pedir"))

    modulo.executar_da_linha_de_comando()

    assert abriu == ["janela"]


# =============================================================================
# E. O despachante precoce, isolado
# =============================================================================

def test_despachar_cedo_SAI_quando_a_flag_esta_presente():
    from sigft.app import conferencia

    with pytest.raises(SystemExit):
        conferencia.despachar_cedo(["SIG-FT.exe", "--conferir-pacote"])


def test_despachar_cedo_NAO_atrapalha_quem_so_quer_abrir_o_app():
    """Ele roda no topo de todo ponto de entrada: nao pode custar nada."""
    from sigft.app import conferencia

    assert conferencia.despachar_cedo(["SIG-FT.exe"]) is None


def test_a_flag_tem_UM_dono():
    """O texto `--conferir-pacote` mora em `conferencia.FLAG`.

    Dois literais em dois pontos de entrada divergem na primeira pressa, e a
    divergencia e invisivel: a flag simplesmente deixa de ser reconhecida por
    um dos caminhos, que foi exatamente o defeito.
    """
    from sigft.app import conferencia

    assert conferencia.FLAG == "--conferir-pacote"

    with pytest.raises(SystemExit):
        conferencia.despachar_cedo(["x", conferencia.FLAG])


# =============================================================================
# F. O workflow nao pode voltar a esperar para sempre
# =============================================================================

WORKFLOW = RAIZ / ".github" / "workflows" / "release.yml"

PASSOS_QUE_RODAM_O_EXE = [
    "O .exe consegue importar o que precisa (--conferir-pacote)",
    "A janela principal monta (--smoke)",
]


def _bloco_do_passo(nome: str) -> list[str]:
    """As linhas de UM passo do workflow, do seu `- name:` ao do proximo.

    Sem PyYAML de proposito. Ele nao esta no `requirements-dev.txt`, entao um
    `importorskip("yaml")` aqui daria SKIP no CI -- e um guard que nao roda e
    pior do que nenhum, porque parece protecao. Este container tem o PyYAML
    instalado por acaso, que e exatamente a contaminacao que ja custou um run
    nesta frente (ver o aviso do CLAUDE.md sobre venv limpo).

    O recorte por bloco tambem e o que faz o teste medir o PASSO e nao o
    arquivo: um `timeout-minutes` em outro passo qualquer nao serve.
    """
    linhas = WORKFLOW.read_text(encoding="utf-8").splitlines()

    inicio = next((i for i, linha in enumerate(linhas)
                   if linha.strip() == f"- name: {nome}"), None)
    assert inicio is not None, f"o passo `{nome}` sumiu do workflow"

    fim = next((i for i in range(inicio + 1, len(linhas))
                if linhas[i].strip().startswith("- name:")), len(linhas))

    return linhas[inicio:fim]


@pytest.mark.parametrize("nome_do_passo", PASSOS_QUE_RODAM_O_EXE)
def test_os_passos_que_abrem_o_exe_tem_limite_de_tempo(nome_do_passo):
    """A rede de seguranca por baixo do conserto.

    Estes dois passos chamam o `.exe` com `Start-Process -Wait`. Se por
    qualquer motivo ele abrir a janela em vez de responder a flag, o passo nao
    FALHA -- ele PENDURA, esperando um aplicativo que esta la, aberto. Sem
    limite proprio, o job leva os 90 minutos de `timeout-minutes` para nao
    publicar nada, e o sintoma ("ainda rodando") nao parece defeito.

    Com limite, o mesmo defeito vira uma falha em 5 minutos, com nome.
    """
    bloco = _bloco_do_passo(nome_do_passo)

    assert any(linha.strip().startswith("timeout-minutes:") for linha in bloco), (
        f"o passo `{nome_do_passo}` roda o .exe e perdeu o `timeout-minutes`. "
        f"Um .exe que abre a janela pendura o `-Wait` ate o limite do job:\n  "
        + "\n  ".join(bloco)
    )


# =============================================================================
# G. O `--smoke` tem de dizer POR QUE falhou
# =============================================================================
# O run #3 reprovou aqui com "codigo 1" e mais nada. O `_smoke` imprime o
# traceback, mas o `SIG-FT.spec` usa `console=False`: um .exe sem console nao
# se prende ao terminal, entao a saida NAO chega ao PowerShell. O passo sabia
# dizer "falhou" e nao sabia dizer por que -- e cada hipotese custa um build
# inteiro.
#
# E a mesma armadilha que o `--conferir-pacote` ja resolvia gravando um
# arquivo. A regra tem um dono agora (`conferencia.gravar_relatorio`), em vez
# de estar implementada num lugar e esquecida no outro.

# [2026-10-15] Os dois testes que ficavam aqui (o motivo gravado na falha e o
# arquivo gravado tambem no sucesso) dublavam a janela da interface antiga. Na
# Qt eles estao em `tests/test_qt_smoke.py`:
# test_grava_o_motivo_quando_a_janela_nao_monta e
# test_grava_o_relatorio_tambem_quando_da_certo.


def test_o_workflow_IMPRIME_o_relatorio_da_janela():
    """De nada adianta gravar se o passo nao mostrar."""
    bloco = "\n".join(_bloco_do_passo("A janela principal monta (--smoke)"))

    assert "conferencia-da-janela.txt" in bloco, (
        "o passo do --smoke nao imprime o relatorio -- uma falha ali volta a "
        "ser so `codigo 1`, sem diagnostico"
    )


def test_os_dois_relatorios_sobem_como_artefato():
    """Quando o passo falha, o arquivo e a unica testemunha do que houve."""
    texto = WORKFLOW.read_text(encoding="utf-8")

    for arquivo in ("conferencia-do-pacote.txt", "conferencia-da-janela.txt"):
        assert arquivo in texto, f"{arquivo} nao e guardado como artefato"


# =============================================================================
# H. O `--smoke` monta a janela COMO O USUARIO a vê
# =============================================================================
# O run #3 reprovou aqui, e o motivo (reproduzido em Linux com xvfb, com o
# traceback inteiro) foi:
#
#     File "sigft/app/views/translator.py", line 34, in __init__
#       self.backend = backends.translator_backend.TechnicalTranslator()
#     AttributeError: 'NoneType' object has no attribute 'TechnicalTranslator'
#
# Ou seja: o defeito estava no CHECADOR, nao no aplicativo. O caminho real de
# abertura e `main()` -> SplashScreen -> `backends.carregar_todos()` -> e so
# entao a janela. O `_smoke` construia `SIG_FT_App()` direto, com o registro de
# backends ainda em `None`, e a primeira view que usa o backend no `__init__`
# estourava.
#
# Um checador que nao reproduz a ordem de abertura reprova o que funciona -- e
# vale menos que nenhum, porque manda consertar o que nao esta quebrado.

def test_o_smoke_CARREGA_os_backends_antes_de_montar_a_janela(qt_interface, monkeypatch, tmp_path):
    """A ordem que o splash faz, e que o `_smoke` tem de repetir."""
    from sigft.app_qt import main as modulo

    ordem = []

    def _janela():
        ordem.append("janela")
        raise RuntimeError("so a ordem interessa aqui")

    monkeypatch.chdir(tmp_path)
    # Sem a folha de estilo do app na QApplication da suíte: ela ficaria para
    # os testes seguintes (as medidas dos diálogos mudam com ela).
    # 2026-10-20: o smoke passa o `--tema` da linha de comando (None sem ele).
    monkeypatch.setattr(modulo, "_preparar_qt", lambda *_: None)
    monkeypatch.setattr(modulo, "SIG_FT_App", _janela)
    monkeypatch.setattr(modulo.backends, "carregar_todos", lambda **kw: ordem.append("backends"))

    modulo._smoke()

    assert ordem == ["backends", "janela"], (
        f"a ordem foi {ordem}. Montar a janela antes dos backends reproduz o "
        f"defeito do run #3: as views leem `backends.x` e acham None."
    )


# O backend que nao carregou vira AVISO no relatorio, sem reprovar (o contrato
# de `carregar_todos`): na Qt, `tests/test_qt_smoke.py::test_aviso_de_backend_vai_para_o_relatorio`.
