r"""
Testes de `sigft/core/relatorio_lote.py` (Checkpoint 4.4 — padrão único de
log de lote).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 4 -> CP 4.4. Cada bloco
abaixo cobre uma das 5 exigências que o checkpoint enumera, mais os
invariantes que evitam justamente o "log pobre" que o diagnóstico do plano
(seção 1.5) aponta: sem resumo final, sem contexto do item, sem duração.

Nenhum teste usa tempo real (`time_fn` injetado) nem escreve fora de
`tmp_path`.
"""
from __future__ import annotations

import os
from datetime import datetime

import pytest

from sigft.core.callbacks import UICallbacks
from sigft.core.relatorio_lote import (
    MARCA_AVISO,
    MARCA_FALHA,
    MARCA_PULADO,
    MARCA_SUCESSO,
    RelatorioLote,
    caminho_log_do_dia,
    espelhar_em_arquivo,
    formatar_duracao,
)


def _capturador():
    """`UICallbacks` que guarda `(msg, nivel)` de cada chamada."""
    registro = []
    callbacks = UICallbacks(
        log=lambda msg, nivel="info", contexto=None: registro.append((str(msg), nivel))
    )
    return callbacks, registro


def _relogio(passo=1.0):
    estado = [0.0]

    def agora():
        estado[0] += passo
        return estado[0]

    return agora


def _texto(registro):
    return "\n".join(m for m, _n in registro)


# =============================================================================
# formatar_duracao
# =============================================================================

@pytest.mark.parametrize(
    "segundos,esperado",
    [
        (None, ""),
        (0.0, "0,0s"),
        (1.24, "1,2s"),
        (59.9, "59,9s"),
        (60, "1min 00s"),
        (184, "3min 04s"),
        (3600, "1h 00min"),
        (3725, "1h 02min"),
    ],
)
def test_formatar_duracao(segundos, esperado):
    assert formatar_duracao(segundos) == esperado


# =============================================================================
# Exigência 1 — início de lote (o quê, quantos, com qual config)
# =============================================================================

def test_inicio_diz_o_que_vai_fazer_e_quantos_itens():
    callbacks, registro = _capturador()

    RelatorioLote(callbacks, titulo="Traduzindo fichas", total=7).iniciar()

    assert "Traduzindo fichas" in registro[0][0]
    assert "7 item(ns)" in registro[0][0]


def test_inicio_lista_o_contexto_de_arquivos_e_config():
    callbacks, registro = _capturador()

    RelatorioLote(
        callbacks, titulo="X", total=1, contexto={"template": "T.xlsx", "idioma": "ES"}
    ).iniciar()

    texto = _texto(registro)
    assert "template: T.xlsx" in texto
    assert "idioma: ES" in texto


def test_total_desconhecido_nao_inventa_numero():
    callbacks, registro = _capturador()

    RelatorioLote(callbacks, titulo="X").iniciar()

    assert "item(ns)" not in registro[0][0]  # não finge saber a quantidade


# =============================================================================
# Exigência 2 — por item: identificador, resultado, duração
# =============================================================================

def test_item_sem_excecao_conta_como_sucesso_com_duracao():
    callbacks, registro = _capturador()
    lote = RelatorioLote(callbacks, titulo="X", total=1, time_fn=_relogio())

    with lote.item("PMIB-1"):
        pass

    linha = registro[-1][0]
    assert linha.startswith(MARCA_SUCESSO)
    assert "PMIB-1" in linha
    assert "s)" in linha  # duração presente
    assert lote.sucessos == ["PMIB-1"]


def test_item_com_excecao_vira_falha_com_tipo_e_mensagem():
    callbacks, registro = _capturador()
    lote = RelatorioLote(callbacks, titulo="X", total=1, time_fn=_relogio())

    with lote.item("PMIB-2"):
        raise ValueError("coluna ausente")

    linha = registro[-1][0]
    assert linha.startswith(MARCA_FALHA)
    assert "ValueError: coluna ausente" in linha
    assert lote.falhas == ["PMIB-2"]


def test_excecao_de_um_item_nao_derruba_o_lote():
    # É o contrato do padrão de lote do SIG-FT: um item ruim não pode
    # interromper os outros 199.
    callbacks, _registro = _capturador()
    lote = RelatorioLote(callbacks, titulo="X", total=3, time_fn=_relogio())

    for i in range(3):
        with lote.item(f"P{i}"):
            if i == 1:
                raise RuntimeError("falhou")

    assert lote.sucessos == ["P0", "P2"]
    assert lote.falhas == ["P1"]


def test_etapa_registra_progresso_dentro_do_item():
    callbacks, registro = _capturador()
    lote = RelatorioLote(callbacks, titulo="X", total=1, time_fn=_relogio())

    with lote.item("PMIB-1") as r:
        r.etapa("abrindo ficha no portal")

    assert any("abrindo ficha no portal" in m and "PMIB-1" in m for m, _ in registro)


def test_pular_suprime_o_sucesso_automatico():
    callbacks, _registro = _capturador()
    lote = RelatorioLote(callbacks, titulo="X", total=1, time_fn=_relogio())

    with lote.item("PMIB-1") as r:
        r.pular("já COMPLETO")

    assert lote.pulados == ["PMIB-1"]
    assert lote.sucessos == []


def test_falhar_explicito_suprime_o_sucesso_automatico():
    callbacks, _registro = _capturador()
    lote = RelatorioLote(callbacks, titulo="X", total=1, time_fn=_relogio())

    with lote.item("PMIB-1") as r:
        r.falhar("PDM de origem não encontrado")

    assert lote.falhas == ["PMIB-1"]
    assert lote.sucessos == []


def test_progresso_e_avisado_quando_ha_provedor():
    chamadas = []
    callbacks = UICallbacks(
        log=lambda msg, nivel="info", contexto=None: None,
        progress=lambda atual, total, item=None: chamadas.append((atual, total)),
    )
    lote = RelatorioLote(callbacks, titulo="X", total=2, time_fn=_relogio())

    lote.sucesso("A")
    lote.falha("B", "erro")

    assert chamadas == [(1, 2), (2, 2)]


# =============================================================================
# Exigência 3 — aviso SEMPRE com causa e consequência
# =============================================================================

def test_aviso_junta_causa_e_consequencia_com_seta():
    callbacks, registro = _capturador()
    lote = RelatorioLote(callbacks, titulo="X", total=1)

    lote.aviso("PMIB-1", "campo X rejeitado pelo site", "preencher manualmente")

    msg, nivel = registro[-1]
    assert msg.startswith(MARCA_AVISO)
    assert "campo X rejeitado pelo site → preencher manualmente" in msg
    assert nivel == "warn"


def test_assinatura_de_aviso_obriga_consequencia():
    # A API impede registrar um aviso solto ("erro no campo X") sem dizer o
    # que aquilo significa para quem lê — é a exigência nº 3 virando código.
    callbacks, _registro = _capturador()
    lote = RelatorioLote(callbacks, titulo="X")

    with pytest.raises(TypeError):
        lote.aviso("PMIB-1", "só a causa")


def test_aviso_nao_conta_como_sucesso_nem_falha():
    callbacks, _registro = _capturador()
    lote = RelatorioLote(callbacks, titulo="X", total=1, time_fn=_relogio())

    with lote.item("PMIB-1") as r:
        r.aviso("campo X rejeitado", "preencher manualmente")

    assert lote.sucessos == ["PMIB-1"]  # o item ainda concluiu
    assert lote.falhas == []


# =============================================================================
# Exigência 4 — resumo final obrigatório
# =============================================================================

def test_resumo_traz_contagens_e_tempo_total():
    callbacks, registro = _capturador()

    with RelatorioLote(callbacks, titulo="Lote X", total=2, time_fn=_relogio()) as lote:
        lote.sucesso("A")
        lote.falha("B", "erro Y")

    texto = _texto(registro)
    assert "── Resumo: Lote X ──" in texto
    assert f"{MARCA_SUCESSO} 1 sucesso(s)" in texto
    assert f"{MARCA_FALHA} 1 falha(s)" in texto
    assert "Tempo total:" in texto


def test_resumo_LISTA_as_falhas_com_motivo():
    # Um resumo que só diz "3 falhas" obriga o usuário a rolar o console
    # atrás de quais foram — o checkpoint exige que sejam listadas.
    callbacks, registro = _capturador()

    with RelatorioLote(callbacks, titulo="X", total=2, time_fn=_relogio()) as lote:
        lote.falha("PMIB-9", "timeout no portal")

    texto = _texto(registro)
    assert "Falhas:" in texto
    assert "PMIB-9 — timeout no portal" in texto


def test_resumo_lista_pulados_com_motivo():
    callbacks, registro = _capturador()

    with RelatorioLote(callbacks, titulo="X", total=1, time_fn=_relogio()) as lote:
        lote.pulado("PMIB-3", "sem código PMIB no nome do arquivo")

    texto = _texto(registro)
    assert "Pulados:" in texto
    assert "PMIB-3 — sem código PMIB no nome do arquivo" in texto


def test_resumo_sai_mesmo_quando_o_lote_estoura_no_meio():
    # O caso em que o resumo mais importa: morreu na ficha 2 de 200, o
    # usuário precisa saber o que já tinha sido feito.
    callbacks, registro = _capturador()

    with pytest.raises(RuntimeError):
        with RelatorioLote(callbacks, titulo="X", total=200, time_fn=_relogio()) as lote:
            lote.sucesso("A")
            raise RuntimeError("conexão caiu")

    texto = _texto(registro)
    assert "Lote interrompido por erro inesperado: conexão caiu" in texto
    assert "── Resumo: X ──" in texto
    assert f"{MARCA_SUCESSO} 1 sucesso(s)" in texto


def test_resumo_sinaliza_itens_nao_processados():
    callbacks, registro = _capturador()

    with RelatorioLote(callbacks, titulo="X", total=10, time_fn=_relogio()) as lote:
        lote.sucesso("A")

    assert "de 10 previsto(s); 9 não processado(s)" in _texto(registro)


def test_resumo_nao_duplica_se_finalizar_for_chamado_duas_vezes():
    callbacks, registro = _capturador()

    with RelatorioLote(callbacks, titulo="X", total=1, time_fn=_relogio()) as lote:
        lote.sucesso("A")
        lote.finalizar()  # explícito, e o `with` chama de novo na saída

    assert _texto(registro).count("── Resumo: X ──") == 1


def test_linhas_resumo_pode_ser_lido_sem_emitir():
    callbacks, registro = _capturador()
    lote = RelatorioLote(callbacks, titulo="X", total=1, time_fn=_relogio())
    lote.iniciar()
    lote.sucesso("A")
    antes = len(registro)

    linhas = lote.linhas_resumo()

    assert len(registro) == antes  # nada foi logado
    assert any("Resumo" in linha for linha in linhas)


# =============================================================================
# Exigência 5 — espelho opcional em arquivo
# =============================================================================

def test_espelho_grava_no_arquivo_e_preserva_o_log_original(tmp_path):
    callbacks, registro = _capturador()
    destino = tmp_path / "sigft.log"

    espelhado = espelhar_em_arquivo(callbacks, caminho=str(destino))
    espelhado.log("mensagem de teste", "warn")

    assert registro == [("mensagem de teste", "warn")]  # original intacto
    conteudo = destino.read_text(encoding="utf-8")
    assert "mensagem de teste" in conteudo
    assert "[WARN]" in conteudo


def test_espelho_cria_a_pasta_se_faltar(tmp_path):
    callbacks, _registro = _capturador()
    destino = tmp_path / "logs" / "sub" / "sigft.log"

    espelhar_em_arquivo(callbacks, caminho=str(destino)).log("oi")

    assert destino.is_file()


def test_espelho_preserva_os_demais_callbacks():
    perguntas = []
    callbacks = UICallbacks(
        log=lambda msg, nivel="info", contexto=None: None,
        ask=lambda pergunta, titulo=None: perguntas.append(pergunta) or True,
    )

    espelhado = espelhar_em_arquivo(callbacks, caminho=os.devnull)

    assert espelhado.ask("continuar?") is True
    assert perguntas == ["continuar?"]


def test_falha_ao_gravar_o_espelho_nao_derruba_o_log(tmp_path):
    # Mesma disciplina de core/llm/usage.py (CP 3.4): auditoria nunca pode
    # derrubar um lote de 200 fichas por disco cheio ou permissão.
    callbacks, registro = _capturador()
    obstaculo = tmp_path / "obstaculo"
    obstaculo.write_text("sou um arquivo, não uma pasta", encoding="utf-8")

    espelhado = espelhar_em_arquivo(callbacks, caminho=str(obstaculo / "impossivel.log"))
    espelhado.log("tem que passar mesmo assim")

    assert registro == [("tem que passar mesmo assim", "info")]


def test_caminho_do_log_do_dia_usa_o_formato_pedido_pelo_plano():
    fixo = datetime(2026, 8, 2, 15, 30)

    caminho = caminho_log_do_dia(pasta="logs", agora_fn=lambda: fixo)

    assert caminho == os.path.join("logs", "sigft_20260802.log")


def test_espelho_e_opcional_quem_nao_chamar_nao_ganha_arquivo(tmp_path):
    # Exigência nº 5 diz "espelho OPCIONAL" — o comportamento padrão continua
    # sendo não escrever nada em disco.
    callbacks, _registro = _capturador()
    os.chdir(tmp_path)

    with RelatorioLote(callbacks, titulo="X", total=1, time_fn=_relogio()) as lote:
        lote.sucesso("A")

    assert list(tmp_path.iterdir()) == []
