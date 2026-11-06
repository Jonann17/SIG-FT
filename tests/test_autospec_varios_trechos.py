"""AutoSpec: mais de um trecho de prova por campo, e as regras de certificado e proteção
(2026-11-06, pedido do Luan).

Execução 393441 (AutoSpec pelo Workflow AMP, acoplador WAGO 750-362): o agente juntou num valor
dados de mais de uma linha do datasheet ("2 x RJ-45 (Ethernet 10/100 Mbit/s)") e citou uma linha
só. A conferência exige que todo número do valor saia do trecho citado, e o campo ficou vazio,
com o valor certo. Agora a prova pode trazer uma LISTA de trechos: cada um tem de existir no
documento, e os números do valor podem sair de qualquer um deles.
"""
from __future__ import annotations

from sigft.services import autospec_evidencia as ev
from sigft.services.autospec import AutoSpecCore

# As linhas do datasheet da WAGO como a IA as citou na execução 393441. Como no datasheet de
# verdade, as portas e a taxa ficam em seções diferentes: os dois trechos juntos não se acham
# como um trecho só, nem pela janela de palavras.
_OUTRA_SECAO = ("Technical data. The fieldbus coupler connects the WAGO I/O System to the fieldbus. "
                "It detects all connected I/O modules and creates a local process image, which may "
                "include analog, digital and specialty modules arranged in any order on the node. "
                "Configuration and diagnostics are available through the integrated web server and "
                "the service interface, for commissioning and maintenance of the station.\n")
DOC_WAGO = (
    "--- WEB DOC: Data sheet 750-362.pdf ---\n"
    "[página 2]\n"
    "Communication\nModbus (TCP, UDP): 2 x RJ-45\n"
    + _OUTRA_SECAO +
    "Transmission rate\n10/100 Mbit/s\n"
    "Connection technology: system supply\n2 x CAGE CLAMP®\n"
    "[página 3]\n"
    "Mounting type\nDIN-35 rail\n"
)
PERGUNTA_PORTAS = ("5 - PORTAS DE COMUNICACAO (Indicar as portas de comunicação do item ex: RS485, "
                   "fibra otica, outros)")
PERGUNTA_CONEXAO = ("23 - CONEXAO ELETRICA (Indique o tipo de conexão elétrica (entrada do cabo) ex.: "
                    "conector M12, P2, P3, outros)")
DOIS_LUGARES = ("Modbus (TCP, UDP): 2 x RJ-45", "Transmission rate 10/100 Mbit/s")


def _core(evidencias):
    core = AutoSpecCore.__new__(AutoSpecCore)
    core.ultimas_evidencias_por_campo = evidencias
    core._modelo_do_item = ""
    return core


def _logs():
    linhas = []

    class _Cb:
        def log(self, msg, nivel="info", contexto=None):
            linhas.append((nivel, str(msg)))

    return _Cb(), linhas


# -- a prova, lida da resposta ------------------------------------------------------------

def test_a_prova_le_uma_lista_de_trechos():
    provas = ev.extrair_evidencias({"var_row_83": {
        "valor": "x", "tipo": "documento", "trecho": [DOIS_LUGARES[0], "  ", DOIS_LUGARES[1]]}})
    assert provas["var_row_83"].trechos == DOIS_LUGARES
    assert provas["var_row_83"].trecho == " | ".join(DOIS_LUGARES)


def test_um_trecho_so_continua_como_antes():
    provas = ev.extrair_evidencias({"var_row_87": {"valor": "x", "trecho": "Mounting type DIN-35 rail"}})
    assert provas["var_row_87"].trechos == ("Mounting type DIN-35 rail",)
    assert provas["var_row_87"].trecho == "Mounting type DIN-35 rail"


def test_a_evidencia_montada_com_um_trecho_tem_a_lista_de_um():
    """Quem monta a `Evidencia` à mão (os testes de antes) continua com o `trecho` só."""
    assert ev.Evidencia(trecho="ø 36").trechos == ("ø 36",)
    assert ev.Evidencia().trechos == ()


# -- a conferência ------------------------------------------------------------------------

def test_valor_de_dois_lugares_passa_com_os_dois_trechos():
    core = _core({"var_row_83": ev.Evidencia(trechos=DOIS_LUGARES, fonte="Data sheet 750-362.pdf", pagina=2)})
    aprovados = core._filtrar_por_lastro(
        {"var_row_83": "2 x RJ-45 (Ethernet 10/100 Mbit/s)"}, {"var_row_83": {"desc": PERGUNTA_PORTAS}}, DOC_WAGO)
    assert aprovados == {"var_row_83": "2 x RJ-45 (Ethernet 10/100 Mbit/s)"}


def test_com_um_trecho_so_o_mesmo_valor_continua_reprovado():
    """O caso da execução 393441: o 10/100 não está no trecho citado. A regra não afrouxou."""
    core = _core({"var_row_83": ev.Evidencia(trecho=DOIS_LUGARES[0], fonte="Data sheet 750-362.pdf")})
    aprovados = core._filtrar_por_lastro(
        {"var_row_83": "2 x RJ-45 (Ethernet 10/100 Mbit/s)"}, {"var_row_83": {"desc": PERGUNTA_PORTAS}}, DOC_WAGO)
    assert "var_row_83" not in aprovados


def test_trecho_da_lista_que_nao_existe_deixa_o_item_dele_de_fora_e_diz_qual():
    """O trecho inventado não prova nada: o item dele fica de fora, e o console diz qual trecho
    não está no documento. Até a rc.5 o campo inteiro ficava vazio; desde 2026-11-06 os itens
    que os outros trechos provam ficam (`test_autospec_itens_provados.py`, decisão do Luan)."""
    core = _core({"var_row_101": ev.Evidencia(
        trechos=("Connection technology: system supply 2 x CAGE CLAMP", "Fieldbus connection 4 x RJ-45"),
        fonte="Data sheet 750-362.pdf")})
    cb, linhas = _logs()
    aprovados = core._filtrar_por_lastro(
        {"var_row_101": "2 x CAGE CLAMP; 4 x RJ-45"}, {"var_row_101": {"desc": PERGUNTA_CONEXAO}}, DOC_WAGO, cb)
    assert aprovados == {"var_row_101": "2 x CAGE CLAMP"}
    assert any("Fieldbus connection 4 x RJ-45" in mensagem for _nivel, mensagem in linhas)


def test_numero_que_nao_esta_em_nenhum_trecho_continua_reprovado():
    core = _core({"var_row_83": ev.Evidencia(trechos=DOIS_LUGARES, fonte="Data sheet 750-362.pdf")})
    aprovados = core._filtrar_por_lastro(
        {"var_row_83": "3 x RJ-45 (Ethernet 10/100 Mbit/s)"}, {"var_row_83": {"desc": PERGUNTA_PORTAS}}, DOC_WAGO)
    assert "var_row_83" not in aprovados
