r"""
Testes do Checkpoint 1.5 — `sigft/app/file_dialogs.py` (a memória de pastas
dos diálogos de arquivo, lado UI de `sigft.core.prefs`).

O diálogo de verdade vem de quem chama (`dialog_fn`; na produção, o
`QFileDialog` de `sigft/app_qt/file_dialogs.py`). Aqui TODO teste passa um
`dialog_fn` FAKE (`_DialogSpy`, uma função Python simples que devolve um
resultado fixo e grava os kwargs recebidos). A seção E prova que, sem
`dialog_fn`, as funções falham alto em vez de pular o diálogo em silêncio.

Cobre, para as 4 funções (`ask_open_file`, `ask_open_files`, `ask_save_file`,
`ask_directory`): `initialdir` resolvido por `prefs.get_initial_dir` é
repassado ao `dialog_fn`; seleção bem-sucedida chama `remember_dir` com a
PASTA certa (não o caminho de arquivo cru) na chave/categoria certas;
cancelamento (resultado vazio) NÃO chama `remember_dir` e devolve o vazio no
tipo certo (`""` singular, `()` para `ask_open_files`); `ask_open_files` usa
o dirname do PRIMEIRO arquivo selecionado; e (seção F, 2ª metade do CP 1.5) o
parâmetro `initialdir` — override CONTEXTUAL explícito de quem chama, usado
pela tela do PDM (`_op1_modificados`) — vence a resolução via `prefs`
quando aponta para uma pasta válida, e cai integralmente para a resolução
normal via `prefs` quando ausente/inválido.

Todos os testes usam `config_path=<tmp_path>/user_prefs.json` — nunca tocam
no `user_prefs.json` real do repositório.
"""
from __future__ import annotations

import json

import pytest

from sigft.app import file_dialogs
from sigft.core import prefs

_TODAS_AS_FUNCOES = ("ask_open_file", "ask_open_files", "ask_save_file", "ask_directory")


def _resultado_cancelado(metodo: str):
    """Forma "vazia" que um `dialog_fn` devolveria ao cancelar, para cada
    função — `()` só para `ask_open_files`, `""` para as demais."""
    return () if metodo == "ask_open_files" else ""


@pytest.fixture()
def config_path(tmp_path):
    return tmp_path / "user_prefs.json"


class _DialogSpy:
    """`dialog_fn` fake: devolve `resultado` (fixo, definido no construtor)
    e GRAVA os kwargs recebidos em `kwargs_recebidos`, para o teste
    inspecionar depois — nunca abre diálogo de verdade."""

    def __init__(self, resultado):
        self.resultado = resultado
        self.kwargs_recebidos: dict | None = None
        self.chamadas = 0

    def __call__(self, **kwargs):
        self.chamadas += 1
        self.kwargs_recebidos = kwargs
        return self.resultado


# =============================================================================
# A. `initialdir` resolvido por prefs.get_initial_dir é repassado ao dialog_fn
# =============================================================================

@pytest.mark.parametrize("metodo", _TODAS_AS_FUNCOES)
def test_initialdir_resolvido_e_repassado_a_todas_as_funcoes(tmp_path, config_path, metodo):
    pasta = tmp_path / "pasta_lembrada"
    pasta.mkdir()
    prefs.remember_dir("chave.x", "cat", str(pasta), config_path=config_path)

    spy = _DialogSpy(_resultado_cancelado(metodo))
    funcao = getattr(file_dialogs, metodo)
    funcao("chave.x", "cat", config_path=config_path, dialog_fn=spy)

    assert spy.chamadas == 1
    assert spy.kwargs_recebidos["initialdir"] == str(pasta)


@pytest.mark.parametrize("metodo", _TODAS_AS_FUNCOES)
def test_initialdir_e_none_quando_prefs_nao_tem_nada_salvo(config_path, metodo):
    spy = _DialogSpy(_resultado_cancelado(metodo))
    funcao = getattr(file_dialogs, metodo)
    funcao("chave.nunca.usada", "cat_nunca_usada", config_path=config_path, dialog_fn=spy)

    assert spy.kwargs_recebidos["initialdir"] is None


@pytest.mark.parametrize("metodo", _TODAS_AS_FUNCOES)
def test_titulo_e_repassado_como_title_em_todas_as_funcoes(config_path, metodo):
    spy = _DialogSpy(_resultado_cancelado(metodo))
    funcao = getattr(file_dialogs, metodo)
    funcao("chave.x", "cat", titulo="Meu Título", config_path=config_path, dialog_fn=spy)

    assert spy.kwargs_recebidos["title"] == "Meu Título"


def test_filetypes_e_repassado_a_ask_open_file(config_path):
    spy = _DialogSpy("")
    file_dialogs.ask_open_file(
        "chave.x", "excel", filetypes=[("Excel", "*.xlsx")], config_path=config_path, dialog_fn=spy
    )
    assert spy.kwargs_recebidos["filetypes"] == [("Excel", "*.xlsx")]


def test_ask_save_file_repassa_filetypes_e_defaultextension(config_path):
    spy = _DialogSpy("")
    file_dialogs.ask_save_file(
        "chave.x",
        "json",
        filetypes=[("JSON", "*.json")],
        defaultextension=".json",
        config_path=config_path,
        dialog_fn=spy,
    )
    assert spy.kwargs_recebidos["filetypes"] == [("JSON", "*.json")]
    assert spy.kwargs_recebidos["defaultextension"] == ".json"


def test_ask_directory_nao_aceita_filetypes():
    # ask_directory não tem parâmetro filetypes (pastas não têm "tipo de
    # arquivo") -- confirma que a assinatura não aceita esse kwarg.
    with pytest.raises(TypeError):
        file_dialogs.ask_directory("chave.x", "pasta", filetypes=[("Excel", "*.xlsx")])


# =============================================================================
# B. Seleção bem-sucedida -> remember_dir com a PASTA certa (nunca o
#    caminho de arquivo cru), na chave/categoria certas.
# =============================================================================

def test_ask_open_file_sucesso_grava_dirname_do_arquivo_nao_o_arquivo_cru(tmp_path, config_path):
    pasta = tmp_path / "pasta_do_arquivo"
    pasta.mkdir()
    arquivo = str(pasta / "ficha.xlsx")

    resultado = file_dialogs.ask_open_file(
        "autospec.ficha", "excel", config_path=config_path, dialog_fn=_DialogSpy(arquivo)
    )

    assert resultado == arquivo
    lembrado = prefs.get_initial_dir("autospec.ficha", "excel", config_path=config_path)
    assert lembrado == str(pasta)
    assert lembrado != arquivo  # a PASTA foi lembrada, não o caminho de arquivo cru


def test_ask_save_file_sucesso_grava_dirname_do_arquivo(tmp_path, config_path):
    pasta = tmp_path / "pasta_salvar"
    pasta.mkdir()
    destino = str(pasta / "resultado.json")

    resultado = file_dialogs.ask_save_file(
        "modulo.resultado", "json", config_path=config_path, dialog_fn=_DialogSpy(destino)
    )

    assert resultado == destino
    assert prefs.get_initial_dir("modulo.resultado", "json", config_path=config_path) == str(pasta)


def test_ask_directory_sucesso_grava_a_propria_pasta_sem_aplicar_dirname(tmp_path, config_path):
    pasta = tmp_path / "pasta_escolhida"
    pasta.mkdir()

    resultado = file_dialogs.ask_directory(
        "pdm.destino_fichas", "pasta", config_path=config_path, dialog_fn=_DialogSpy(str(pasta))
    )

    assert resultado == str(pasta)
    assert prefs.get_initial_dir("pdm.destino_fichas", "pasta", config_path=config_path) == str(pasta)


def test_remember_dir_e_gravado_na_chave_e_categoria_certas(tmp_path, config_path):
    pasta = tmp_path / "pasta"
    pasta.mkdir()
    arquivo = str(pasta / "arq.xlsx")

    file_dialogs.ask_open_file(
        "modulo_x.campo_y", "excel", config_path=config_path, dialog_fn=_DialogSpy(arquivo)
    )

    bruto = json.loads(config_path.read_text(encoding="utf-8"))
    assert bruto["ultimos"]["modulo_x.campo_y"] == str(pasta)
    assert bruto["categorias"]["excel"] == str(pasta)
    # Nenhuma outra chave/categoria foi tocada.
    assert bruto["ultimos"] == {"modulo_x.campo_y": str(pasta)}
    assert bruto["categorias"] == {"excel": str(pasta)}


def test_selecoes_sucessivas_atualizam_a_memoria(tmp_path, config_path):
    pasta_1 = tmp_path / "pasta_1"
    pasta_1.mkdir()
    pasta_2 = tmp_path / "pasta_2"
    pasta_2.mkdir()

    file_dialogs.ask_open_file(
        "chave.x", "excel", config_path=config_path, dialog_fn=_DialogSpy(str(pasta_1 / "a.xlsx"))
    )
    assert prefs.get_initial_dir("chave.x", "excel", config_path=config_path) == str(pasta_1)

    file_dialogs.ask_open_file(
        "chave.x", "excel", config_path=config_path, dialog_fn=_DialogSpy(str(pasta_2 / "b.xlsx"))
    )
    assert prefs.get_initial_dir("chave.x", "excel", config_path=config_path) == str(pasta_2)


# =============================================================================
# C. Cancelamento (vazio) NÃO chama remember_dir e devolve o vazio no tipo
#    certo ("" para os 3 singulares, () para ask_open_files).
# =============================================================================

@pytest.mark.parametrize(
    "metodo,args,resultado_do_dialogo,vazio_esperado",
    [
        ("ask_open_file", ("chave.x", "excel"), "", ""),
        ("ask_save_file", ("chave.x", "excel"), "", ""),
        ("ask_directory", ("chave.x", "pasta"), "", ""),
        ("ask_open_files", ("chave.x", "excel"), (), ()),
        ("ask_open_files", ("chave.x", "excel"), [], ()),
        ("ask_open_files", ("chave.x", "excel"), "", ()),  # vazio em forma de str
        ("ask_open_file", ("chave.x", "excel"), None, ""),  # tolerância extra (fake mal comportado)
    ],
)
def test_cancelamento_nao_grava_prefs_e_devolve_vazio_no_tipo_certo(
    config_path, metodo, args, resultado_do_dialogo, vazio_esperado
):
    assert not config_path.exists()
    spy = _DialogSpy(resultado_do_dialogo)
    funcao = getattr(file_dialogs, metodo)

    resultado = funcao(*args, config_path=config_path, dialog_fn=spy)

    assert resultado == vazio_esperado
    assert type(resultado) is type(vazio_esperado)
    # Nenhum arquivo de prefs foi criado -- remember_dir nunca foi chamado.
    assert not config_path.exists()


def test_cancelamento_preserva_prefs_ja_existentes_sem_sobrescrever(tmp_path, config_path):
    pasta = tmp_path / "pasta"
    pasta.mkdir()
    prefs.remember_dir("chave.x", "excel", str(pasta), config_path=config_path)

    resultado = file_dialogs.ask_open_file(
        "chave.x", "excel", config_path=config_path, dialog_fn=_DialogSpy("")
    )

    assert resultado == ""
    # O que já estava salvo continua exatamente igual -- cancelar não apaga
    # nem sobrescreve a memória anterior.
    assert prefs.get_initial_dir("chave.x", "excel", config_path=config_path) == str(pasta)


# =============================================================================
# D. ask_open_files usa o dirname do PRIMEIRO arquivo selecionado.
# =============================================================================

def test_ask_open_files_usa_dirname_do_primeiro_arquivo(tmp_path, config_path):
    pasta_1 = tmp_path / "pasta_1"
    pasta_1.mkdir()
    pasta_2 = tmp_path / "pasta_2"
    pasta_2.mkdir()
    arquivo_1 = str(pasta_1 / "a.pdf")
    arquivo_2 = str(pasta_2 / "b.pdf")  # pasta DIFERENTE, de propósito

    resultado = file_dialogs.ask_open_files(
        "autospec.manuais", "pdf", config_path=config_path, dialog_fn=_DialogSpy((arquivo_1, arquivo_2))
    )

    assert resultado == (arquivo_1, arquivo_2)
    # dirname do PRIMEIRO (pasta_1), não do segundo (pasta_2).
    assert prefs.get_initial_dir("autospec.manuais", "pdf", config_path=config_path) == str(pasta_1)


def test_ask_open_files_normaliza_lista_para_tupla_de_str(tmp_path, config_path):
    pasta = tmp_path / "pasta"
    pasta.mkdir()
    arquivos = [str(pasta / "a.pdf"), str(pasta / "b.pdf"), str(pasta / "c.pdf")]  # list, não tuple

    resultado = file_dialogs.ask_open_files(
        "autospec.manuais", "pdf", config_path=config_path, dialog_fn=_DialogSpy(arquivos)
    )

    assert resultado == tuple(arquivos)
    assert isinstance(resultado, tuple)


def test_ask_open_files_string_unica_de_tk_antigo_nao_itera_caracteres(tmp_path, config_path):
    pasta = tmp_path / "pasta"
    pasta.mkdir()
    arquivo_unico = str(pasta / "unico.pdf")

    # Um diálogo pode devolver uma STRING única (não uma
    # sequência de 1 elemento) quando só 1 arquivo é escolhido -- não pode
    # virar uma tupla de CARACTERES do caminho.
    resultado = file_dialogs.ask_open_files(
        "autospec.manuais", "pdf", config_path=config_path, dialog_fn=_DialogSpy(arquivo_unico)
    )

    assert resultado == (arquivo_unico,)
    assert prefs.get_initial_dir("autospec.manuais", "pdf", config_path=config_path) == str(pasta)


# =============================================================================
# E. dialog_fn ausente -> falha alto (o diálogo é da interface)
# =============================================================================
# Até 2026-10-15, sem `dialog_fn` o módulo abria o diálogo da interface antiga.
# Ela saiu do SIG-FT; o diálogo vem sempre de quem chama.

def test_modulo_e_importavel_sem_biblioteca_grafica():
    assert file_dialogs is not None


@pytest.mark.parametrize("metodo", _TODAS_AS_FUNCOES)
def test_sem_dialog_fn_falha_alto_e_diz_onde_esta_o_dialogo(config_path, metodo):
    """Nunca pular o diálogo em silêncio nem devolver um valor "chute"."""
    with pytest.raises(TypeError, match="sigft.app_qt.file_dialogs"):
        getattr(file_dialogs, metodo)("x.y", "excel", config_path=config_path)


@pytest.mark.parametrize("metodo", _TODAS_AS_FUNCOES)
def test_dialog_fn_injetado_e_o_usado(metodo):
    sentinela = object()

    assert file_dialogs._resolver_dialog_fn(metodo, sentinela) is sentinela


# =============================================================================
# F. `initialdir` -- override CONTEXTUAL explícito (2ª metade do CP 1.5).
#
# Caso de uso real (único hoje): a tela do PDM (`_op1_modificados`) passa
# `initialdir=origem`, onde `origem` é a pasta que o usuário ACABOU de
# escolher em OUTRO campo da mesma tela ("Pasta (PDMs From Itaipu)") --
# informação contextual da sessão atual, não memória de sessões anteriores.
# =============================================================================

@pytest.mark.parametrize("metodo", _TODAS_AS_FUNCOES)
def test_initialdir_override_valido_tem_prioridade_sobre_prefs(tmp_path, config_path, metodo):
    pasta_lembrada = tmp_path / "pasta_lembrada_por_prefs"
    pasta_lembrada.mkdir()
    prefs.remember_dir("chave.x", "cat", str(pasta_lembrada), config_path=config_path)

    pasta_override = tmp_path / "pasta_override_contextual"
    pasta_override.mkdir()

    spy = _DialogSpy(_resultado_cancelado(metodo))
    funcao = getattr(file_dialogs, metodo)
    funcao(
        "chave.x", "cat",
        initialdir=str(pasta_override),
        config_path=config_path,
        dialog_fn=spy,
    )

    # O override vence -- NÃO é a pasta lembrada por `prefs`.
    assert spy.kwargs_recebidos["initialdir"] == str(pasta_override)


@pytest.mark.parametrize("metodo", _TODAS_AS_FUNCOES)
def test_initialdir_override_pasta_inexistente_cai_para_resolucao_normal(tmp_path, config_path, metodo):
    pasta_lembrada = tmp_path / "pasta_lembrada_por_prefs"
    pasta_lembrada.mkdir()
    prefs.remember_dir("chave.x", "cat", str(pasta_lembrada), config_path=config_path)

    pasta_override_inexistente = tmp_path / "nunca_foi_criada"  # nunca criada no disco

    spy = _DialogSpy(_resultado_cancelado(metodo))
    funcao = getattr(file_dialogs, metodo)
    funcao(
        "chave.x", "cat",
        initialdir=str(pasta_override_inexistente),
        config_path=config_path,
        dialog_fn=spy,
    )

    # Override inválido (pasta não existe) é ignorado -- cai para a
    # resolução normal via prefs, exatamente como se initialdir não tivesse
    # sido passado.
    assert spy.kwargs_recebidos["initialdir"] == str(pasta_lembrada)


@pytest.mark.parametrize("metodo", _TODAS_AS_FUNCOES)
def test_initialdir_ausente_resolve_normalmente_via_prefs_sem_mudanca(tmp_path, config_path, metodo):
    # Sem passar `initialdir` -- comportamento da 1ª metade do CP 1.5,
    # preservado integralmente: resolve 100% via prefs.get_initial_dir.
    pasta_lembrada = tmp_path / "pasta_lembrada_sem_override"
    pasta_lembrada.mkdir()
    prefs.remember_dir("chave.y", "cat", str(pasta_lembrada), config_path=config_path)

    spy = _DialogSpy(_resultado_cancelado(metodo))
    funcao = getattr(file_dialogs, metodo)
    funcao("chave.y", "cat", config_path=config_path, dialog_fn=spy)

    assert spy.kwargs_recebidos["initialdir"] == str(pasta_lembrada)


@pytest.mark.parametrize("metodo", _TODAS_AS_FUNCOES)
def test_initialdir_none_explicito_e_equivalente_a_omitir(tmp_path, config_path, metodo):
    pasta_lembrada = tmp_path / "pasta_lembrada_none_explicito"
    pasta_lembrada.mkdir()
    prefs.remember_dir("chave.z", "cat", str(pasta_lembrada), config_path=config_path)

    spy = _DialogSpy(_resultado_cancelado(metodo))
    funcao = getattr(file_dialogs, metodo)
    funcao("chave.z", "cat", initialdir=None, config_path=config_path, dialog_fn=spy)

    assert spy.kwargs_recebidos["initialdir"] == str(pasta_lembrada)


@pytest.mark.parametrize("metodo", _TODAS_AS_FUNCOES)
def test_initialdir_override_string_vazia_e_tratado_como_ausente(config_path, metodo):
    spy = _DialogSpy(_resultado_cancelado(metodo))
    funcao = getattr(file_dialogs, metodo)
    funcao(
        "chave.nunca.usada", "cat_nunca_usada", initialdir="", config_path=config_path, dialog_fn=spy
    )

    # Sem nada salvo em prefs e override vazio -- cai para None (mesma
    # situação da seção A, sem initialdir nenhum).
    assert spy.kwargs_recebidos["initialdir"] is None


@pytest.mark.parametrize("metodo", _TODAS_AS_FUNCOES)
def test_initialdir_override_apontando_para_arquivo_nao_pasta_e_ignorado(tmp_path, config_path, metodo):
    # os.path.isdir() de um ARQUIVO (não uma pasta) é False -- tratado como
    # override inválido, mesma regra de "pasta inexistente".
    arquivo = tmp_path / "isto_e_um_arquivo.txt"
    arquivo.write_text("conteudo", encoding="utf-8")

    spy = _DialogSpy(_resultado_cancelado(metodo))
    funcao = getattr(file_dialogs, metodo)
    funcao(
        "chave.arquivo.nao.pasta", "cat", initialdir=str(arquivo), config_path=config_path, dialog_fn=spy
    )

    assert spy.kwargs_recebidos["initialdir"] is None


def test_initialdir_override_nao_afeta_remember_dir_na_saida(tmp_path, config_path):
    # `remember_dir` continua gravando a pasta REALMENTE escolhida pelo
    # usuário no diálogo, mesmo quando `initialdir` foi usado para abrir o
    # diálogo em outro lugar (caso real: o seletor do "PDM específico" abre
    # na pasta "PDMs From Itaipu", mas o usuário pode navegar e escolher um
    # arquivo em qualquer outra pasta).
    pasta_override = tmp_path / "pasta_de_origem_contextual"
    pasta_override.mkdir()

    pasta_escolhida = tmp_path / "pasta_que_o_usuario_de_fato_escolheu"
    pasta_escolhida.mkdir()
    arquivo_escolhido = str(pasta_escolhida / "pdm_especifico.xlsx")

    resultado = file_dialogs.ask_open_file(
        "pdm.arquivo_especifico",
        "excel",
        initialdir=str(pasta_override),
        config_path=config_path,
        dialog_fn=_DialogSpy(arquivo_escolhido),
    )

    assert resultado == arquivo_escolhido
    # A pasta lembrada é a do ARQUIVO ESCOLHIDO, não a do override contextual.
    assert prefs.get_initial_dir("pdm.arquivo_especifico", "excel", config_path=config_path) == str(
        pasta_escolhida
    )


def test_initialdir_override_convive_com_titulo_e_filetypes(tmp_path, config_path):
    # Confirma que `initialdir` não interfere nos demais kwargs já cobertos
    # na seção A.
    pasta_override = tmp_path / "pasta_override_com_outros_kwargs"
    pasta_override.mkdir()

    spy = _DialogSpy("")
    file_dialogs.ask_open_file(
        "chave.x",
        "excel",
        titulo="Selecione o arquivo PDM específico",
        filetypes=[("Excel", "*.xlsx *.xls")],
        initialdir=str(pasta_override),
        config_path=config_path,
        dialog_fn=spy,
    )

    assert spy.kwargs_recebidos["initialdir"] == str(pasta_override)
    assert spy.kwargs_recebidos["title"] == "Selecione o arquivo PDM específico"
    assert spy.kwargs_recebidos["filetypes"] == [("Excel", "*.xlsx *.xls")]
