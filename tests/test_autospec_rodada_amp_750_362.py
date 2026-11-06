r"""A resposta REAL do agente do AMP, inteira, pelo caminho de produção (2026-11-06).

Rodada da 1.4.0-rc.5 pelo Workflow AMP, acoplador WAGO 750-362. A resposta está em
`fixtures/autospec/resposta_amp_wago_750_362.txt` como o n8n a mostrou -- com o "Vou indexar..."
antes do JSON e o `\%` dentro dele --, só com o nome do PDF trocado: o original leva o número do
pedido de compra, e o repositório é público.

Na rodada, cinco campos certos ficaram vazios (normas, aplicação, certificado, corrente nominal e
função), e o console listou quatro campos vazios como "preenchidos por dedução". Este teste passa
a resposta inteira pelo mesmo caminho do SIG-FT (`_limpar_e_parsear_json`, `_normalizar_resposta_ia`,
`_conferir_e_filtrar`) e trava o resultado: os cinco voltam, e os catorze que já passavam continuam
iguais.

O documento é montado com os trechos que o agente citou, um por parágrafo: na rodada, todos foram
achados no texto extraído (o console não acusou trecho inexistente).
"""
from __future__ import annotations

from pathlib import Path

from sigft.core.llm import client as llm_client
from sigft.services.autospec import AutoSpecCore

RESPOSTA = (Path(__file__).parent / "fixtures" / "autospec" / "resposta_amp_wago_750_362.txt").read_text(
    encoding="utf-8")

PERGUNTAS = {
    "var_row_79": "1 - FAIXA DE TEMPERATURA DE USO (Indicar a faixa de temperatura de uso do item em grau Celsius (°C).)",
    "var_row_80": "2 - SINAL DE ENTRADA (Indicar o sinal de entrada do item em (mV, V, A, mA) ex.: 4-20mA, 0-5 V, outros)",
    "var_row_81": "3 - SINAL DE SAIDA (Indicar o sinal de saída do item em (mV, V, A, mA) ex.: 4-20mA, 0-5 V, outros)",
    "var_row_82": "4 - TENSAO DE ALIMENTACAO (Indicar a tensão de alimentação do item em (V))",
    "var_row_83": "5 - PORTAS DE COMUNICACAO (Indicar as portas de comunicação do item ex: RS485, fibra otica, outros)",
    "var_row_84": "6 - NORMAS TECNICAS APLICAVEIS (Indicar quais as normas técnicas aplicáveis ao item.)",
    "var_row_85": "7 - TEMPO DE RESPOSTA (Indicar o tempo de resposta do item.)",
    "var_row_86": "8 - TIPO (Indicar o tipo do item ex: circuito impresso, outros)",
    "var_row_87": ("9 - TIPO CONSTRUTIVO (Indicar o tipo construtivo do item. Nota: Material especifico de "
                   "compra com (Número de desenho, referência, nome usual, outros))"),
    "var_row_88": ("10 - PROTECAO (Indicar as proteções existentes no modulo ex.: curto circuito, sobretensão, "
                   "aquecimento e outros)"),
    "var_row_89": "11 - TENSAO AUXILIAR (Indicar a tensão auxiliar do item em Volt (VCC ou VCA))",
    "var_row_90": ("12 - APLICACAO (Indicar a aplicação do item. Nota: mencionar o equipamento (tipo, modelo) "
                   "(ex.: Red EIA, 2 fios, diferencial RS485, red EIA 4 fios direferencial RS 485, fibra "
                   "optica, outros).)"),
    "var_row_91": ("13 - CARACTERISTICAS ADICIONAIS (Indicar dados técnicos que não contém nas características "
                   "anteriores. quando disponivel.)"),
    "var_row_92": ("14 - CERTIFICADO (Indicar o tipo de certificado necessário: Selo de Certificação "
                   "Ambiental, Eficiência Energética, Calibração, outros)"),
    "var_row_93": "15 - TENSAO DE OPERACAO (Indicar tensão de operação do item em (V))",
    "var_row_94": "16 - CORRENTE NOMINAL (Indicar a corrente nominal do item em (A))",
    "var_row_95": "17 - DIMENSOES (Indicar as dimensões do item (in, mm) ex.: comp. x larg. x alt.)",
    "var_row_96": "18 - INTERFACE (Indicar a interface do item)",
    "var_row_97": "19 - GRAU DE PROTECAO (Indicar o grau de proteção do item ex: IP40, IP54 e outros.)",
    "var_row_98": "20 - FUNCAO (Indicar a função básica do item ex.: Distribuição de fonte de alimentação de dados.)",
    "var_row_99": "21 - FIXACAO (Indicar a fixação do item ex.: encaixe, parafusos)",
    "var_row_100": "22 - FREQUENCIA (Indicar a frequencia do item ex: 50/60 Hz.)",
    "var_row_101": ("23 - CONEXAO ELETRICA (Indique o tipo de conexão elétrica (entrada do cabo) ex.: "
                    "conector M12, P2, P3, outros)"),
}

# O que a ficha recebe. Os catorze primeiros já passavam na rc.5; os cinco marcados voltaram.
ESPERADO = {
    "var_row_79": "0 … +55 °C",
    "var_row_80": "Ethernet 10/100 Mbit/s (Modbus TCP/UDP)",
    "var_row_82": "24 VDC (-25 … +30 %)",
    "var_row_83": "2 x RJ-45 (Modbus TCP/UDP)",
    "var_row_86": "Acoplador de barramento de campo (Fieldbus Coupler) Modbus TCP",
    "var_row_87": "Módulo para trilho DIN-35, carcaça de policarbonato e poliamida 6.6",
    "var_row_88": "Isolação 500 V sistema/campo",
    "var_row_91": ("Máx. 250 módulos por nó, 64 sem extensão de barramento; imagem de processo 1020 words "
                   "entrada/saída; 10/100 Mbit/s"),
    "var_row_93": "24 VDC (-25 … +30 %)",
    "var_row_95": "49.5 mm (largura) x 96.8 mm (altura) x 71.9 mm (profundidade)",
    "var_row_96": "Ethernet 10/100 Mbit/s, 2 x RJ-45",
    "var_row_97": "IP20",
    "var_row_99": "Encaixe em trilho DIN-35",
    "var_row_101": "Comunicação: 2 x RJ-45; alimentação: 2 x CAGE CLAMP®",
    # voltaram em 2026-11-06:
    "var_row_84": "EN 61000-6-2; EN 61000-6-3; IEC 60068-2-6; IEC 60068-2-27",
    "var_row_90": ("Acoplador de barramento de campo Modbus TCP para o sistema WAGO I/O 750, ligando os "
                   "módulos de E/S à rede Ethernet"),
    "var_row_92": ("CE; ATEX (TÜV 14 ATEX 148929 X); IECEx (IECEx TUN 14.0035 X); INMETRO "
                   "(BR-Ex_TÜV 12.1297 X); marítimas: ABS, DNV, PRS"),
    "var_row_94": "0.28 A (corrente de entrada típica a 24 V, carga nominal)",
    "var_row_98": "Acoplamento de módulos de E/S do sistema WAGO I/O 750 à rede Modbus TCP/UDP",
}

_OUTRA_SECAO = ("The fieldbus coupler connects the WAGO I/O System to the fieldbus and creates a local "
                "process image, which may include analog, digital and specialty modules.")


def _documento(resposta):
    partes = ["--- LOCAL DOC: Data sheet 750-362.pdf ---"]
    for campo, prova in resposta.items():
        if not campo.startswith("var_row_") or not isinstance(prova, dict):
            continue
        trechos = prova.get("trecho") or []
        for trecho in [trechos] if isinstance(trechos, str) else trechos:
            if trecho:
                partes += [trecho, _OUTRA_SECAO]
    return "\n".join(partes)


def _rodar():
    resposta = llm_client._limpar_e_parsear_json(RESPOSTA)
    core = AutoSpecCore.__new__(AutoSpecCore)
    core._modelo_do_item = "750-362"
    linhas = []

    class _Cb:
        def log(self, msg, nivel="info", contexto=None):
            linhas.append(str(msg))

    missing = {campo: {"desc": desc, "type": "text"} for campo, desc in PERGUNTAS.items()}
    valores = core._normalizar_resposta_ia(resposta, campos_pedidos=list(PERGUNTAS), callbacks=_Cb())
    aprovados = core._conferir_e_filtrar(valores, missing, _documento(resposta), _Cb())
    return aprovados, linhas


def test_os_dezenove_campos_respondidos_entram_na_ficha():
    aprovados, _linhas = _rodar()
    assert {campo: valor for campo, valor in aprovados.items() if str(valor).strip()} == ESPERADO


def test_o_console_conta_a_historia_certa():
    _aprovados, linhas = _rodar()
    texto = "\n".join(linhas)
    assert "ficaram VAZIOS" not in texto
    assert "2 campo(s) preenchidos por DEDUCAO TECNICA" in texto       # aplicação e função
    assert "2 campo(s) gravados SEM os itens" in texto                  # normas e certificado
    assert "ficou de fora: IEC 61131-2; EN 50173" in texto
    assert "0.28 A = 280 mA" in texto                                   # a conta conferida
