"""DocPack, Etapa 1: a IA vê onde já estão as listas parecidas, e uma pasta é um dossiê (2026-11-09).

Pedido do Luan: o prompt da Estrutura dava à IA só os NOMES das pastas, e os nomes não têm nada a ver
com a mapeadora. A lista `#ST00=B01BMU10&EPB020` é, na mapeadora, "SERVIÇOS AUXILIARES ELÉTRICOS" /
"CONVERSORES ESTÁTICOS DE FREQUÊNCIA", e mora em `03 - EBOP/SFC/SFC HF-01 e HF-02`. Nenhuma IA tira
"03 - EBOP" de "SERVIÇOS AUXILIARES ELÉTRICOS" pelo nome; ela aprende vendo onde estão as listas da
mesma especificação e capítulo. E, decisão do Luan: duas listas nunca dividem a pasta final.

As listas são as da mapeadora real (as 5 primeiras linhas); a pasta da A é a real, as das outras
são ilustrativas.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sigft.services import conferencia_revisoes as cr
from sigft.services import docpack

SAE = "SERVIÇOS AUXILIARES ELÉTRICOS"
CEF = "CONVERSORES ESTÁTICOS DE FREQUÊNCIA"


def _lista(codigo, descricao, especificacao, capitulo):
    return cr.ListaNaMapeadora(codigo=codigo, ultima_revisao="0", status_da_revisao="", status_real="",
                               revisao_em_uso="0", link=None, descricao=descricao,
                               especificacao=especificacao, capitulo=capitulo)


A = _lista("#ST00=B01BMU10&EPB020", f"ATUALIZAÇÃO TECNOLÓGICA - PAT_OBJ1 - ENG. ELÉTRICA - {SAE} - {CEF} - "
           "50Hz e 60Hz - LISTA DE SOBRESSALENTES", SAE, CEF)
B = _lista("#ST00=B01BMU10TA010&EPB020", f"ATUALIZAÇÃO TECNOLÓGICA - PAT_OBJ1 - ENG. ELÉTRICA - {SAE} - {CEF} - "
           "THF - 50Hz e 60Hz - LISTA DE SOBRESSALENTES", SAE, CEF)
C = _lista("#ST00=B01BMU10EQ010-EP901&MPB020", f"ATUALIZAÇÃO TECNOLÓGICA - PAT_OBJ1 - ENG. MECÂNICA - {SAE} - {CEF} - "
           "TROCADORES DE CALOR ÁGUA-ÁGUA - 50Hz e 60Hz - LISTA DE SOBRESSALENTES", SAE,
           f"{CEF} / MECÂNICA / TROCADOR DE CALOR")
D = _lista("#ST50=X00XAA11&MPB020", "ATUALIZAÇÃO TECNOLÓGICA - PAT_OBJ1 - ENG. MECÂNICA  - CASA DE FORÇA - SISTEMA "
           "DE VENTILAÇÃO E EXAUSTÃO PARA SALA DG - 50 HZ - LISTA DE SOBRESSALENTES", SAE,
           "GRUPO GERADOR DIESEL / MECÂNICA / SISTEMA DE VENTILAÇÃO SALA DO GD")
E = _lista("#ITA0=Y01TF001&BPB020", "ATUALIZAÇÃO TECNOLÓGICA - PAT_OBJ1 - ENG. ELETRÔNICA - CASA DE FORÇA - "
           "CONTROLE CENTRALIZADO - RTA / TELECOM E SISTEMAS INFORMÁTICOS - LISTA DE SOBRESSALENTES",
           "CONTROLE CENTRALIZADO", "RTA / TELECOM E SISTEMAS INFORMÁTICOS")

PASTAS = {
    A.codigo.upper(): "03 - EBOP/SFC/SFC HF-01 e HF-02",
    C.codigo.upper(): "03 - EBOP/SFC/MECANICA/TROCADOR DE CALOR",
    D.codigo.upper(): "03 - EBOP/GRUPO GERADOR DIESEL/MECANICA/VENTILACAO SALA DO GD",
    E.codigo.upper(): "04 - CONTROLE CENTRALIZADO/RTA",
}
LISTAS = [A, B, C, D, E]


# -- as listas vizinhas -----------------------------------------------------------------------

def test_vizinhas_mesmo_capitulo_primeiro_depois_o_ramo_depois_a_especificacao():
    vizinhas = docpack.listas_vizinhas(B, LISTAS, PASTAS)
    assert [v.codigo for v in vizinhas] == [A.codigo, C.codigo, D.codigo]
    assert vizinhas[0].pasta == "03 - EBOP/SFC/SFC HF-01 e HF-02"
    assert vizinhas[0].descricao == A.descricao and vizinhas[0].capitulo == CEF


def test_vizinhas_sem_acento_e_sem_caixa_continuam_vizinhas():
    sem_acento = _lista("#NOVA&EPB020", "LISTA NOVA", "servicos auxiliares eletricos",
                        "conversores estaticos de frequencia")
    assert docpack.listas_vizinhas(sem_acento, LISTAS, PASTAS)[0].codigo == A.codigo


def test_lista_sem_pasta_nao_e_vizinha_e_a_propria_lista_tambem_nao():
    vizinhas = docpack.listas_vizinhas(A, LISTAS, PASTAS)
    assert A.codigo not in [v.codigo for v in vizinhas]
    assert B.codigo not in [v.codigo for v in vizinhas]   # B ainda não tem _STATUS_PMIB


def test_vizinhas_tem_limite():
    assert [v.codigo for v in docpack.listas_vizinhas(B, LISTAS, PASTAS, limite=2)] == [A.codigo, C.codigo]


def test_sem_especificacao_nao_ha_vizinhas():
    assert docpack.listas_vizinhas(_lista("#X&EPB020", "LISTA", "", ""), LISTAS, PASTAS) == []


def test_pastas_dos_dossies_sai_do_levantamento_da_raiz(tmp_path):
    pasta = tmp_path / "03 - EBOP" / "SFC" / "SFC HF-01 e HF-02"
    pasta.mkdir(parents=True)
    (pasta / f"{A.codigo}_STATUS_PMIB.xlsx").write_bytes(b"x")
    assert docpack.pastas_dos_dossies(tmp_path) == {A.codigo.upper(): "03 - EBOP/SFC/SFC HF-01 e HF-02"}


# -- o prompt -----------------------------------------------------------------------------------

def _llm():
    llm = SimpleNamespace(prompts=[])

    def generate(prompt, **_kw):
        llm.prompts.append(prompt)
        return SimpleNamespace(parsed_json={"et": "03 - EBOP", "capitulo": "SFC", "subsistema": "SFC THF"}, text="")

    llm.generate = generate
    return llm


def test_a_ia_recebe_as_vizinhas_com_a_pasta_de_cada_uma():
    llm = _llm()
    vizinhas = docpack.listas_vizinhas(B, LISTAS, PASTAS)
    destino, _motivo = docpack.sugerir_destino(B, {"03 - EBOP": {"SFC": {"SFC HF-01 e HF-02": {}}}}, llm,
                                               vizinhas=vizinhas)
    assert destino == docpack.Destino(et="03 - EBOP", capitulo="SFC", subsistema="SFC THF")
    prompt = llm.prompts[0]
    assert A.codigo in prompt and "03 - EBOP/SFC/SFC HF-01 e HF-02" in prompt
    assert C.codigo in prompt and E.codigo not in prompt


def test_o_prompt_diz_que_cada_lista_tem_a_sua_pasta():
    llm = _llm()
    docpack.sugerir_destino(B, {}, llm, vizinhas=docpack.listas_vizinhas(B, LISTAS, PASTAS))
    prompt = llm.prompts[0]
    assert "nunca" in prompt.lower() and "dossiê de outra lista" in prompt
    assert '"et"' in prompt and '"subsistema"' in prompt and '"motivo"' in prompt   # o JSON não mudou


def test_sem_vizinhas_o_prompt_diz_que_nao_ha():
    llm = _llm()
    docpack.sugerir_destino(B, {}, llm)
    assert "nenhuma lista desta especificação tem pasta ainda" in llm.prompts[0]


# -- uma pasta, um dossiê ---------------------------------------------------------------------------

def _templates(tmp_path):
    modelo = tmp_path / "modelo_STATUS_PMIB.xlsx"
    modelo.write_bytes(b"x")
    return docpack.Templates(status_pmib=str(modelo))


def test_a_pasta_de_outro_dossie_nao_recebe_esta_lista(tmp_path):
    raiz = tmp_path / "raiz"
    ocupada = raiz / "03 - EBOP" / "SFC" / "SFC HF-01 e HF-02"
    ocupada.mkdir(parents=True)
    (ocupada / f"{A.codigo}_STATUS_PMIB.xlsx").write_bytes(b"x")
    destino = docpack.Destino(et="03 - EBOP", capitulo="SFC", subsistema="SFC HF-01 e HF-02")
    with pytest.raises(docpack.ErroDocPack, match="B01BMU10&EPB020"):
        docpack.planejar(B, raiz, destino, _templates(tmp_path))


def test_a_pasta_do_capitulo_sem_status_pmib_aceita(tmp_path):
    raiz = tmp_path / "raiz"
    (raiz / "03 - EBOP" / "SFC").mkdir(parents=True)
    destino = docpack.Destino(et="03 - EBOP", capitulo="SFC", subsistema="SFC THF")
    assert docpack.planejar(B, raiz, destino, _templates(tmp_path))


# -- o mapa da organização (sugestão do Luan, 2026-11-09: "toda vez mandar como estão estruturadas") --

def test_mapa_diz_onde_ficam_os_dossies_de_cada_especificacao_e_capitulo():
    mapa = docpack.mapa_das_listas(LISTAS, PASTAS)
    assert [(r.especificacao, r.capitulo, r.pastas) for r in mapa] == [
        ("CONTROLE CENTRALIZADO", "RTA / TELECOM E SISTEMAS INFORMÁTICOS", (("04 - CONTROLE CENTRALIZADO", 1),)),
        (SAE, CEF, (("03 - EBOP/SFC", 1),)),
        (SAE, f"{CEF} / MECÂNICA / TROCADOR DE CALOR", (("03 - EBOP/SFC/MECANICA", 1),)),
        (SAE, "GRUPO GERADOR DIESEL / MECÂNICA / SISTEMA DE VENTILAÇÃO SALA DO GD",
         (("03 - EBOP/GRUPO GERADOR DIESEL/MECANICA", 1),)),
    ]


def test_mapa_junta_a_mesma_especificacao_e_capitulo_escritos_diferente():
    outra = _lista("#ST00=B01BMU20&EPB020", "LISTA", "servicos auxiliares eletricos",
                   "conversores estaticos de frequencia")
    pastas = dict(PASTAS, **{outra.codigo.upper(): "03 - EBOP/SFC/SFC HF-03"})
    linha = next(r for r in docpack.mapa_das_listas(LISTAS + [outra], pastas) if r.capitulo == CEF)
    assert linha.pastas == (("03 - EBOP/SFC", 2),)


def test_a_ia_recebe_o_mapa_mesmo_sem_vizinhas():
    """Especificação nova, sem lista com pasta: o mapa ainda mostra como as outras viram pasta."""
    llm = _llm()
    nova = _lista("#NOVA&EPB020", "LISTA NOVA", "TURBINA", "REGULADOR DE VELOCIDADE")
    docpack.sugerir_destino(nova, {}, llm, mapa=docpack.mapa_das_listas(LISTAS, PASTAS))
    prompt = llm.prompts[0]
    assert "nenhuma lista desta especificação tem pasta ainda" in prompt
    assert "CONTROLE CENTRALIZADO | RTA / TELECOM E SISTEMAS INFORMÁTICOS -> 04 - CONTROLE CENTRALIZADO" in prompt
