r"""
`config.resumo_dos_motores()` — o texto que responde "estou no motor novo?".

Nasceu de uma pergunta do usuário: ele rodou o `SIG-FT.bat` e o antigo
`SIG-FT-Playwright.bat` na mesma planilha e obteve o mesmo resultado. Estava
CERTO que fosse igual -- o Playwright já é o padrão dos módulos portados desde
2026-08-11 -- mas não havia como saber disso sem abrir o código.

O que se protege aqui é a honestidade do texto: ele é derivado do mapa, não
escrito à mão, porque um aviso que mente sobre o motor é pior do que nenhum.
"""
import pytest

from sigft import config


@pytest.fixture(autouse=True)
def _sem_override(monkeypatch):
    monkeypatch.delenv(config.ENV_RPA_ENGINE, raising=False)


def _texto():
    return "\n".join(config.resumo_dos_motores())


def test_lista_cada_modulo_no_motor_que_ele_de_fato_usa():
    texto = _texto()
    for modulo in config.RPA_ENGINE:
        assert modulo in texto


def test_o_modulo_que_ignora_a_configuracao_e_marcado_como_tal():
    """`ficha_duplicada` constrói o Selenium direto, sem passar pela fábrica.
    Listá-lo junto dos outros faria o usuário achar que trocar a configuração o
    afeta -- e atribuir ao motor um resultado que o motor não produziu."""
    linha = [l for l in config.resumo_dos_motores() if "ficha_duplicada" in l]

    assert len(linha) == 1
    assert "ignora" in linha[0]


def test_sem_a_variavel_de_ambiente_nao_ha_linha_de_forcado():
    assert "forcando" not in _texto()


def test_com_a_variavel_o_texto_diz_que_esta_forcado(monkeypatch):
    """Sem esta linha, quem abrisse pelo atalho de rollback veria "selenium" e
    não saberia se é o padrão ou uma imposição do atalho."""
    monkeypatch.setenv(config.ENV_RPA_ENGINE, "selenium")

    texto = _texto()

    assert "forcando" in texto
    assert config.ENV_RPA_ENGINE in texto


def test_o_override_muda_o_motor_reportado_dos_modulos_da_fabrica(monkeypatch):
    monkeypatch.setenv(config.ENV_RPA_ENGINE, "selenium")

    assert "playwright" not in _texto()


def test_o_texto_e_derivado_do_mapa_e_nao_escrito_a_mao(monkeypatch):
    """Promover um módulo tem de mudar o texto sozinho. Se alguém trocar isto
    por uma string fixa num `.bat`, ela envelhece na primeira promoção -- em
    silêncio, que é o modo de falhar que este resumo existe para evitar."""
    monkeypatch.setitem(config.RPA_ENGINE, "ficha_duplicada", config.ENGINE_PLAYWRIGHT)
    monkeypatch.setattr(config, "MODULOS_SEM_SELETOR_DE_MOTOR", ())

    assert "ficha_duplicada" in [
        l.split(":")[1].strip() for l in config.resumo_dos_motores()
        if l.strip().startswith("playwright")
    ][0]
