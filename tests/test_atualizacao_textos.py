"""Os textos do aviso de atualização (`sigft/app/atualizacao_textos.py`) e o
que o Release promete a quem está nas versões antigas.

Portado das seções E e G de `tests/test_atualizacao_na_abertura.py`, que
testava a atualização na interface antiga (saiu em 2026-10-15). O
comportamento na interface (a abertura pergunta calada, o botão sempre
responde, o aviso baixa, instala e só então fecha) está em
`tests/test_qt_atualizacao.py`; o botão e a caixa "Versões de teste" da Home,
em `tests/test_qt_home_paineis.py` e `tests/test_qt_home.py`. Aqui ficam as
funções puras, que valem para qualquer interface.
"""
import importlib.util
import pathlib

import pytest

from sigft.app import atualizacao_textos as textos
from sigft.services import updater


def _info(**extra):
    base = dict(
        versao="1.2.0",
        notas="- **Upload:** agora salva `sozinho`\n- segundo item",
        nome_arquivo="SIG-FT_Itaipu_Setup_1.2.0.exe",
        url_asset="https://api.github.com/repos/luanccozer/SIG-FT/releases/assets/1",
        tamanho=110_201_576,
        sha256="ab" * 32,
        url_pagina="https://github.com/luanccozer/SIG-FT/releases/tag/v1.2.0",
        publicado_em="2026-09-25",
    )
    base.update(extra)
    return updater.Atualizacao(**base)


def test_as_notas_perdem_o_markdown_e_ganham_marcador():
    texto = textos.notas_para_exibir("- **Upload:** agora salva `sozinho`\n* segundo item\n")

    assert texto == "• Upload: agora salva sozinho\n\n• segundo item"


def test_o_rodape_como_instalar_do_corpo_do_release_e_cortado():
    """Sem o `latest.json`, as notas vem do corpo do Release -- que termina
    com as instrucoes de instalacao manual, inuteis para quem atualiza pelo app."""
    corpo = ("## O que mudou na v1.2.0\n\n- item\n\n---\n\n### Como instalar\n\n"
             "Baixe o SIG-FT_Itaipu_Setup_*.exe abaixo")

    texto = textos.notas_para_exibir(corpo)

    assert "Como instalar" not in texto
    assert texto == "O que mudou na v1.2.0\n\n• item"


@pytest.mark.parametrize("vazio", [None, "", "   \n  "])
def test_notas_vazias_viram_uma_frase(vazio):
    assert textos.notas_para_exibir(vazio) == "(Esta versão não trouxe notas.)"


def test_o_resumo_diz_de_onde_para_onde_com_data_e_tamanho_brasileiros():
    resumo = textos.resumo_da_versao(_info(), "1.1.0")

    assert resumo == "Você está na v1.1.0. A v1.2.0 saiu em 25/09/2026 e tem 105,1 MB."


def test_o_resumo_sem_data_nem_tamanho_nao_inventa():
    resumo = textos.resumo_da_versao(_info(publicado_em="", tamanho=0), "1.1.0")

    assert resumo == "Você está na v1.1.0. A v1.2.0."


def _com_arquivos(tamanho=12_900_000):
    zipado = _info(nome_arquivo="SIG-FT_Itaipu_Arquivos_1.1.0_para_1.2.0.zip", tamanho=tamanho)
    return _info(tamanho=316_017_517, arquivos=zipado, manifesto_arquivos=_info(nome_arquivo="arquivos.json"))


def test_o_resumo_da_atualizacao_por_arquivos_compara_com_o_completo():
    # [2026-10-07] O que a pessoa ganha com a atualizacao pequena tem de
    # aparecer; desde 2026-10-30 ela e o .zip de arquivos.
    resumo = textos.resumo_da_versao(_com_arquivos(), "1.1.0")

    assert resumo == ("Você está na v1.1.0. A v1.2.0 saiu em 25/09/2026. A atualização tem 12,3 MB: "
                      "só o que mudou (o instalador completo tem 301,4 MB).")


def test_baixando_diz_o_tamanho_do_que_vai_mesmo_ser_baixado():
    info = _com_arquivos()

    assert textos.msg_baixando(info) == "Baixando a v1.2.0 (12,3 MB)..."
    assert textos.msg_baixando(info, so_completo=True) == "Baixando a v1.2.0 (301,4 MB)..."
    assert textos.msg_baixando(_info()) == "Baixando a v1.2.0 (105,1 MB)..."


def test_as_notas_do_release_NAO_prometem_atualizacao_a_quem_esta_na_1_0_ou_1_1():
    """O rodape fixo das notas dizia "quem ja tem o SIG-FT instalado nao
    precisa baixar nada" -- falso para a 1.0.0 e a 1.1.0, que nunca
    perguntaram ao GitHub. Quem acreditasse ficaria esperando um aviso que
    nao vem."""
    caminho = pathlib.Path(__file__).resolve().parent.parent / "tools" / "gerar_manifesto.py"
    spec = importlib.util.spec_from_file_location("gerar_manifesto", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)

    rodape = " ".join(modulo.COMO_INSTALAR.split())
    assert "1.0.0" in rodape and "1.1.0" in rodape, (
        "o rodape tem de dizer que a 1.0.0 e a 1.1.0 precisam instalar a mao")
