"""Os últimos arquivos de cada diálogo (2026-10-21, etapa 1b)."""
import pytest

from sigft.core import prefs


@pytest.fixture
def config_path(tmp_path):
    return tmp_path / "user_prefs.json"


def _arquivo(tmp_path, nome):
    caminho = tmp_path / nome
    caminho.write_text("x", encoding="utf-8")
    return str(caminho)


def test_guarda_cinco_o_mais_novo_primeiro(tmp_path, config_path):
    arquivos = [_arquivo(tmp_path, f"f{i}.xlsx") for i in range(7)]
    for caminho in arquivos:
        prefs.lembrar_recente("k", caminho, config_path=config_path)
    assert prefs.recentes("k", config_path=config_path) == list(reversed(arquivos))[:prefs.LIMITE_RECENTES]


def test_repetido_sobe_e_nao_duplica(tmp_path, config_path):
    a, b = _arquivo(tmp_path, "a.xlsx"), _arquivo(tmp_path, "b.xlsx")
    for caminho in (a, b, a):
        prefs.lembrar_recente("k", caminho, config_path=config_path)
    assert prefs.recentes("k", config_path=config_path) == [a, b]


def test_o_que_sumiu_nao_aparece_e_as_chaves_sao_separadas(tmp_path, config_path):
    a = _arquivo(tmp_path, "a.xlsx")
    prefs.lembrar_recente("k", a, config_path=config_path)
    prefs.lembrar_recente("k", str(tmp_path / "sumiu.xlsx"), config_path=config_path)
    assert prefs.recentes("k", config_path=config_path) == [a]
    assert prefs.recentes("outra", config_path=config_path) == []


def test_nao_apaga_as_outras_secoes(tmp_path, config_path):
    prefs.gravar_preferencia("tema", "claro", config_path=config_path)
    prefs.lembrar_recente("k", _arquivo(tmp_path, "a.xlsx"), config_path=config_path)
    assert prefs.ler_preferencia("tema", "escuro", config_path=config_path) == "claro"


@pytest.mark.parametrize("bruto", ['{"recentes": {"k": "a.xlsx"}}', '{"recentes": []}',
                                   '{"recentes": {"k": [1, null]}}', "nao e json"])
def test_ilegivel_e_vazio(config_path, bruto):
    config_path.write_text(bruto, encoding="utf-8")
    assert prefs.recentes("k", config_path=config_path) == []


def test_arquivo_antigo_sem_a_secao_carrega_e_guarda_o_resto(tmp_path, config_path):
    """Um `user_prefs.json` de antes de 2026-10-21 (sem "recentes") abre sem
    erro, e lembrar um recente não apaga a pasta, o tema nem o nome."""
    pasta = tmp_path / "pasta"
    pasta.mkdir()
    config_path.write_text(
        '{"ultimos": {"k": "%s"}, "preferencias": {"tema": "claro", "nome": "Ana"}}'
        % str(pasta).replace("\\", "\\\\"), encoding="utf-8")
    assert prefs.recentes("k", config_path=config_path) == []
    prefs.lembrar_recente("k", _arquivo(tmp_path, "a.xlsx"), config_path=config_path)
    assert prefs.get_initial_dir("k", "excel", config_path=config_path) == str(pasta)
    assert prefs.ler_preferencia("tema", "escuro", config_path=config_path) == "claro"
    assert prefs.ler_preferencia("nome", "", config_path=config_path) == "Ana"


def test_sem_conferir_disco_devolve_os_gravados(tmp_path, config_path):
    sumido = str(tmp_path / "sumiu.xlsx")
    prefs.lembrar_recente("k", sumido, config_path=config_path)
    assert prefs.recentes("k", config_path=config_path) == []
    assert prefs.recentes("k", conferir_disco=False, config_path=config_path) == [sumido]
