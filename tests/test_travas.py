r"""
`sigft/core/excel/travas.py` -- por que um arquivo não pôde ser gravado, o que
fazer, e se Repetir adianta. Ver
`docs/superpowers/specs/2026-10-06-gravacao-com-retry-design.md`.

  A. o diagnóstico, linha a linha da tabela do §3 do spec;
  B. o arquivo de dono do Excel (`~$nome.xlsx`), que dá NOME a quem abriu;
  C. a conferência de antes (`conferir`): abre para escrita sem escrever nada;
  D. o laço da lista de antes (`conferir_antes`);
  E. o laço da lista do fim da etapa (`repetir_falhas`);
  F. o resumo do fim da rodada.

Rodando como root (o contêiner), `chmod 444` não impede a escrita: o "somente
leitura" é simulado no `os.access`, que é a pergunta que o código faz ao
sistema.
"""
from __future__ import annotations

import errno
import zipfile

import pytest

from sigft.core.excel import travas


def _consumir(gerador):
    """Roda um generator até o fim: (linhas de log, valor do `return`)."""
    linhas = []
    while True:
        try:
            linhas.append(next(gerador))
        except StopIteration as fim:
            return linhas, fim.value


def _dono_do_excel(pasta, nome_planilha, usuario):
    """O `~$` que o Excel cria ao abrir: tamanho + nome (ANSI) até o byte 54,
    depois tamanho (2 bytes) + nome em UTF-16."""
    ansi = usuario.encode("cp1252")
    unicode_ = usuario.encode("utf-16-le")
    dados = bytes([len(ansi)]) + ansi.ljust(53, b" ")
    dados += len(usuario).to_bytes(2, "little") + unicode_
    dados = dados.ljust(165, b" ")
    (pasta / f"~${nome_planilha}").write_bytes(dados)


@pytest.fixture
def planilha(tmp_path):
    caminho = tmp_path / "#ST00=X&MPB020_STATUS_PMIB.xlsx"
    caminho.write_bytes(b"PK conteudo qualquer")
    return caminho


# ===========================================================================
# A. O diagnóstico
# ===========================================================================
def test_permissao_negada_com_o_dono_do_excel_ao_lado_e_aberto_no_excel_por_quem(planilha):
    _dono_do_excel(planilha.parent, planilha.name, "Luan Cozer")

    d = travas.diagnosticar(planilha, PermissionError(13, "Permission denied"))

    assert d.tipo == travas.ABERTO_NO_EXCEL
    assert "aberto no Excel por Luan Cozer" in d.motivo
    assert "feche" in d.o_que_fazer.lower()
    assert d.repetir_adianta is True


def test_dono_do_excel_ilegivel_ainda_diz_aberto_no_excel_sem_inventar_nome(planilha):
    (planilha.parent / f"~${planilha.name}").write_bytes(b"\x00\xff\x00")

    d = travas.diagnosticar(planilha, PermissionError(13, "Permission denied"))

    assert d.tipo == travas.ABERTO_NO_EXCEL
    assert d.motivo == "está aberto no Excel"


def test_somente_leitura_ganha_do_dono_do_excel(planilha, monkeypatch):
    # Excel aberto em modo leitura deixa o `~$`, mas não trava: quem impede a
    # escrita é o atributo. Dizer "feche o Excel" mandaria a pessoa para o
    # lugar errado.
    _dono_do_excel(planilha.parent, planilha.name, "Luan")
    monkeypatch.setattr(travas.os, "access", lambda caminho, modo: False)

    d = travas.diagnosticar(planilha, PermissionError(13, "Permission denied"))

    assert d.tipo == travas.SOMENTE_LEITURA
    assert "Somente leitura" in d.o_que_fazer
    assert d.repetir_adianta is True


def test_permissao_negada_sem_sinal_nenhum_e_em_uso_por_outro_programa(planilha):
    d = travas.diagnosticar(planilha, PermissionError(13, "Permission denied"))

    assert d.tipo == travas.EM_USO
    assert d.repetir_adianta is True


def test_sharing_violation_do_windows_tambem_e_trava(planilha):
    erro = OSError(errno.EACCES, "used by another process")
    erro.winerror = 32

    assert travas.diagnosticar(planilha, erro).tipo == travas.EM_USO


def test_arquivo_que_sumiu_de_pasta_acessivel_nao_adianta_repetir(tmp_path):
    d = travas.diagnosticar(tmp_path / "foi_embora.xlsx", FileNotFoundError(2, "No such file"))

    assert d.tipo == travas.SUMIU
    assert d.repetir_adianta is False


def test_pasta_que_sumiu_e_box_ou_rede_fora_e_adianta_repetir(tmp_path):
    caminho = tmp_path / "Box desconectado" / "x_STATUS_PMIB.xlsx"

    d = travas.diagnosticar(caminho, FileNotFoundError(2, "No such file"))

    assert d.tipo == travas.SEM_ACESSO
    assert "Box" in d.o_que_fazer
    assert d.repetir_adianta is True


@pytest.mark.parametrize("winerror", [53, 67, 1231, 362])
def test_erros_de_rede_e_de_nuvem_do_windows_sao_sem_acesso(planilha, winerror):
    erro = OSError(errno.EINVAL, "rede")
    erro.winerror = winerror

    assert travas.diagnosticar(planilha, erro).tipo == travas.SEM_ACESSO


def test_nome_novo_ja_existente_na_renomeacao(planilha):
    d = travas.diagnosticar(planilha, FileExistsError(17, "File exists"))

    assert d.tipo == travas.JA_EXISTE
    assert "OBSOLETO" in d.o_que_fazer
    assert d.repetir_adianta is False


def test_disco_cheio_pelo_errno(planilha):
    d = travas.diagnosticar(planilha, OSError(errno.ENOSPC, "No space left on device"))

    assert d.tipo == travas.DISCO_CHEIO
    assert d.repetir_adianta is True


def test_disco_cheio_pelo_codigo_do_windows(planilha):
    erro = OSError(errno.EINVAL, "disk full")
    erro.winerror = 112

    assert travas.diagnosticar(planilha, erro).tipo == travas.DISCO_CHEIO


def test_zip_ilegivel_e_corrompido_e_manda_restaurar_pelo_box(planilha):
    d = travas.diagnosticar(planilha, zipfile.BadZipFile("File is not a zip file"))

    assert d.tipo == travas.CORROMPIDO
    assert "Box" in d.o_que_fazer
    assert d.repetir_adianta is False


def test_xml_ilegivel_do_lxml_e_corrompido_sem_importar_o_lxml(planilha):
    class XMLSyntaxError(Exception):
        pass

    assert travas.diagnosticar(planilha, XMLSyntaxError("bad xml")).tipo == travas.CORROMPIDO


def test_aba_que_sumiu_e_fora_do_padrao_e_diz_qual(planilha):
    d = travas.diagnosticar(planilha, KeyError("aba não encontrada: Lista de Materiais"))

    assert d.tipo == travas.FORA_DO_PADRAO
    assert "Lista de Materiais" in d.motivo
    assert "'aba" not in d.motivo  # sem as aspas do repr do KeyError
    assert d.repetir_adianta is False


def test_celula_mestra_de_formula_e_fora_do_padrao(planilha):
    d = travas.diagnosticar(planilha, NotImplementedError("S6 é a célula-mestra de uma fórmula shared"))

    assert d.tipo == travas.FORA_DO_PADRAO
    assert "S6" in d.motivo


def test_erro_inesperado_mostra_tipo_e_texto_e_deixa_tentar(planilha):
    d = travas.diagnosticar(planilha, RuntimeError("deu ruim no meio"))

    assert d.tipo == travas.DESCONHECIDO
    assert "RuntimeError" in d.motivo and "deu ruim no meio" in d.motivo
    assert d.repetir_adianta is True


def test_os_textos_nao_usam_travessao():
    # Regra da casa para texto de tela e de log (ver tests/test_texto_da_ui.py).
    erros = [PermissionError(13, "x"), FileNotFoundError(2, "x"), FileExistsError(17, "x"),
             OSError(errno.ENOSPC, "x"), zipfile.BadZipFile("x"), KeyError("x"), RuntimeError("x")]
    for erro in erros:
        d = travas.diagnosticar("C:/inexistente/x.xlsx", erro)
        assert "—" not in d.motivo + d.o_que_fazer, erro


# ===========================================================================
# B. O dono do Excel
# ===========================================================================
def test_dono_do_excel_le_o_nome_unicode(planilha):
    _dono_do_excel(planilha.parent, planilha.name, "João Ação")

    assert travas.dono_do_excel(planilha) == "João Ação"


def test_dono_do_excel_cai_para_o_nome_ansi_quando_o_unicode_falta(planilha):
    (planilha.parent / f"~${planilha.name}").write_bytes(bytes([4]) + b"Luan")

    assert travas.dono_do_excel(planilha) == "Luan"


def test_sem_arquivo_de_dono_e_none(planilha):
    assert travas.dono_do_excel(planilha) is None


def test_dono_de_outra_planilha_nao_conta(planilha):
    _dono_do_excel(planilha.parent, "outra.xlsx", "Luan")

    assert travas.dono_do_excel(planilha) is None


# ===========================================================================
# C. A conferência de antes
# ===========================================================================
def test_conferir_arquivo_livre_e_none_e_nao_mexe_em_nada(planilha):
    antes = (planilha.read_bytes(), planilha.stat().st_mtime_ns)

    assert travas.conferir(planilha) is None
    assert (planilha.read_bytes(), planilha.stat().st_mtime_ns) == antes


def test_conferir_um_orfao_do_excel_com_o_arquivo_livre_nao_acusa_trava(planilha):
    # Excel que fechou à força deixa o `~$` para trás: sozinho, não prova nada.
    _dono_do_excel(planilha.parent, planilha.name, "Luan")

    assert travas.conferir(planilha) is None


def test_conferir_arquivo_travado_devolve_o_diagnostico(planilha, monkeypatch):
    _dono_do_excel(planilha.parent, planilha.name, "Luan")

    def _travado(caminho, modo="r", *a, **k):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(travas, "open", _travado, raising=False)

    d = travas.conferir(planilha)

    assert d is not None and d.tipo == travas.ABERTO_NO_EXCEL


def test_conferir_arquivo_que_nao_existe(tmp_path):
    d = travas.conferir(tmp_path / "nao_existe.xlsx")

    assert d is not None and d.tipo == travas.SUMIU


# ===========================================================================
# D. A lista de antes
# ===========================================================================
TRAVADO = travas.Diagnostico(travas.ABERTO_NO_EXCEL, "está aberto no Excel", "Feche.", True)


class _Conferencia:
    """`conferir` de mentira: os caminhos em `travados` estão travados até
    serem soltos; conta quantas vezes cada um foi conferido."""

    def __init__(self, *travados):
        self.travados = set(travados)
        self.vezes = {}

    def __call__(self, caminho):
        self.vezes[caminho] = self.vezes.get(caminho, 0) + 1
        return TRAVADO if caminho in self.travados else None


def test_antes_sem_nenhum_travado_nao_pergunta_nada():
    perguntas = []

    linhas, pulados = _consumir(travas.conferir_antes(
        [("a.xlsx", None), ("b.xlsx", None)], lambda falhas, momento: perguntas.append(1) or True,
        conferir=_Conferencia()))

    assert pulados == {}
    assert perguntas == []
    assert linhas  # diz que conferiu


def test_antes_sem_callback_segue_sem_os_travados_e_diz():
    linhas, pulados = _consumir(travas.conferir_antes(
        [("a.xlsx", None), ("b.xlsx", None)], None, conferir=_Conferencia("b.xlsx")))

    assert list(pulados) == ["b.xlsx"]
    assert pulados["b.xlsx"].diagnostico is TRAVADO
    assert any("b.xlsx" in linha for linha in linhas)


def test_antes_repetir_depois_de_fechar_libera_e_reconfere_so_os_travados():
    conferencia = _Conferencia("b.xlsx", "mapa.xlsx")
    perguntas = []

    def _perguntar(falhas, momento):
        perguntas.append((momento, [(f.caminho, f.nome) for f in falhas]))
        conferencia.travados.clear()  # a pessoa fechou tudo
        return True

    _, pulados = _consumir(travas.conferir_antes(
        [("a.xlsx", None), ("b.xlsx", None), ("mapa.xlsx", "Planilha de mapeamento")], _perguntar,
        conferir=conferencia))

    assert pulados == {}
    assert perguntas == [(travas.ANTES, [("b.xlsx", "b.xlsx"),
                                         ("mapa.xlsx", "Planilha de mapeamento (mapa.xlsx)")])]
    assert conferencia.vezes == {"a.xlsx": 1, "b.xlsx": 2, "mapa.xlsx": 2}


def test_antes_repetir_com_um_ainda_travado_pergunta_de_novo_so_por_ele():
    conferencia = _Conferencia("b.xlsx", "c.xlsx")
    respostas = iter([True, False])
    perguntas = []

    def _perguntar(falhas, momento):
        perguntas.append([f.caminho for f in falhas])
        conferencia.travados.discard("c.xlsx")  # só fechou um
        return next(respostas)

    _, pulados = _consumir(travas.conferir_antes(
        [("b.xlsx", None), ("c.xlsx", None)], _perguntar, conferir=conferencia))

    assert perguntas == [["b.xlsx", "c.xlsx"], ["b.xlsx"]]
    assert list(pulados) == ["b.xlsx"]


# ===========================================================================
# E. A lista do fim da etapa
# ===========================================================================
SUMIU = travas.Diagnostico(travas.SUMIU, "não está mais na pasta", "Confira a pasta.", False)


def _falhas(**diagnosticos):
    return {caminho: travas.Falha(caminho, d) for caminho, d in diagnosticos.items()}


def test_fim_sem_callback_nao_repete_nada():
    refeitos = []

    def _refazer(caminho):
        refeitos.append(caminho)
        return None
        yield  # generator

    falhas = _falhas(a=TRAVADO)
    _, sobra = _consumir(travas.repetir_falhas(falhas, None, _refazer))

    assert list(sobra) == ["a"]
    assert refeitos == []


def test_fim_so_os_que_repetir_resolve_vao_para_a_janela_e_sao_refeitos():
    refeitos, perguntas = [], []

    def _refazer(caminho):
        refeitos.append(caminho)
        yield f"refazendo {caminho}"
        return None  # gravou

    _, sobra = _consumir(travas.repetir_falhas(
        _falhas(a=TRAVADO, b=SUMIU),
        lambda falhas, momento: perguntas.append((momento, [f.caminho for f in falhas])) or True,
        _refazer))

    assert perguntas == [(travas.DEPOIS, ["a"])]
    assert refeitos == ["a"]
    assert list(sobra) == ["b"]  # o que Repetir não resolve fica para o resumo


def test_fim_falhou_de_novo_volta_para_a_janela_ate_seguir():
    respostas = iter([True, False])
    perguntas = []

    def _refazer(caminho):
        return travas.Falha(caminho, TRAVADO)  # continua travado
        yield

    linhas, sobra = _consumir(travas.repetir_falhas(
        _falhas(a=TRAVADO), lambda falhas, momento: perguntas.append(1) or next(respostas), _refazer))

    assert perguntas == [1, 1]
    assert list(sobra) == ["a"]
    assert any("a" in linha for linha in linhas)


def test_fim_seguir_na_primeira_nao_refaz_nada():
    refeitos = []

    def _refazer(caminho):
        refeitos.append(caminho)
        return None
        yield

    _, sobra = _consumir(travas.repetir_falhas(_falhas(a=TRAVADO), lambda falhas, momento: False, _refazer))

    assert refeitos == []
    assert list(sobra) == ["a"]


# ===========================================================================
# F. O resumo
# ===========================================================================
def test_resumo_vazio_nao_escreve_nada():
    assert travas.resumo([]) == []


def test_resumo_uma_linha_de_aviso_e_uma_por_arquivo_com_motivo_e_o_que_fazer():
    linhas = travas.resumo([
        travas.Falha("C:/Box/a_STATUS_PMIB.xlsx", TRAVADO, consequencia="situação não gravada"),
        travas.Falha("C:/Box/mapa.xlsx", SUMIU, rotulo="Planilha de mapeamento"),
    ])

    assert len(linhas) == 3
    assert linhas[0].startswith("[AVISO]") and travas.TITULO_RESUMO in linhas[0] and "(2)" in linhas[0]
    assert "[AVISO]" not in linhas[1] + linhas[2]  # um aviso só, para a contagem da tela
    assert "a_STATUS_PMIB.xlsx" in linhas[1] and "situação não gravada" in linhas[1]
    assert "está aberto no Excel" in linhas[1] and "Feche." in linhas[1]
    assert "Planilha de mapeamento (mapa.xlsx)" in linhas[2] and "Confira a pasta." in linhas[2]


def test_quantos_no_resumo_le_o_total_do_cabecalho():
    linhas = travas.resumo([travas.Falha("a.xlsx", TRAVADO), travas.Falha("b.xlsx", SUMIU)])

    assert travas.quantos_no_resumo(linhas[0]) == 2
    assert travas.quantos_no_resumo(linhas[1]) is None
    assert travas.quantos_no_resumo(" -> Conferi 3 arquivo(s) antes de gravar: nenhum travado.") is None
