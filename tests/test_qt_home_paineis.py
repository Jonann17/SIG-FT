"""A Home em Qt, completa (E5.1): barra de botões, "Versões de teste" e os quatro
painéis em janela -- chaves de API, modelos de IA, gastos de IA e o mural.

Comportamento igual ao de `sigft/app/views/home.py` (interface antiga): mesmas
chaves de configuração, mesmos serviços (`sigft.config`, `core.llm.catalogo`,
`core.llm.selecao`, `core.llm.usage`, `services.atividades`). A seleção de
modelos é gravada de verdade, no `api_config.json` da pasta de dados isolada
pelo conftest; só a REDE (catálogo do provedor) e o log de uso são dublados.

As medidas dos testes de geometria vêm das capturas da interface antiga (Xvfb,
janela 1280x850, `winfo_*`), em `capturas/e5.1/ctk_*.txt`.
"""
import threading
from datetime import date

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QLineEdit, QMessageBox, QStyle

from sigft import config as sigft_config
from sigft.app_qt import estilo
from sigft.app_qt.views import configuracao as config_mod
from sigft.app_qt.views import home as home_mod
from sigft.app_qt.widgets import mural as mural_qt
from sigft.app_qt.widgets.painel_janela import JanelaPainel
from sigft.core import plataforma
from sigft.core.llm import catalogo, selecao
from sigft.services import atividades as at
from sigft.services import updater

NEUTRO_GLOBAL = "Padrão do sistema (modelos atuais)"
NEUTRO_TAREFA = "Usar o global"
ROTULO_OPENROUTER = "OpenRouter (vários modelos, uma chave)"
ROTULO_GEMINI = "Gemini (chave direta do Google)"

CHAVES = {
    "GEMINI": "AIza-segredo-gemini-123",
    "OPENROUTER": "sk-or-segredo-456",
    "GOOGLE_CSE": "cse-789",
}

CATALOGO = {
    "openrouter": ["anthropic/claude-haiku-4.5", "minimax/minimax-m3", "x-ai/grok-4.5"],
    "gemini": ["gemini-3-flash-preview", "gemini-3.5-flash"],
}

RELATORIO = {
    "total": {"chamadas": 2, "falhas": 0, "custo_usd": 0.5, "tokens_in": 10, "tokens_out": 5},
    "por_dia": {"2026-10-01": {}},
    "por_modulo": {"cria_fichas": {"chamadas": 2, "falhas": 0, "tokens_in": 10, "tokens_out": 5,
                                   "custo_usd": 0.5}},
    "por_modelo": {"openrouter/x-ai/grok-4.5": {"chamadas": 2, "falhas": 0, "tokens_in": 10,
                                                "tokens_out": 5, "custo_usd": 0.5}},
}


class Controller:
    """O que a Home usa da janela principal (`SIG_FT_App`)."""

    def __init__(self, chaves=None):
        self.api_keys = dict(CHAVES if chaves is None else chaves)
        self.salvas = []
        self.visitas = []

    def get_key(self, key_id):
        return self.api_keys.get(key_id) or ""

    def save_keys(self, novas):
        self.salvas.append(dict(novas))
        self.api_keys = {**self.api_keys, **novas}

    def show_frame(self, nome):
        self.visitas.append(nome)


@pytest.fixture
def mensagens(monkeypatch):
    """Toda caixa de mensagem vira um registro; `respostas` responde as perguntas."""
    caixas = _Lista()
    caixas.extras = []  # (botões, padrão...) de cada caixa, na mesma ordem
    respostas = []

    def registrar(tipo):
        def caixa(parent, titulo, texto, *a, **k):
            caixas.append((tipo, titulo, texto, parent))
            caixas.extras.append((a, k))
            if tipo == "question":
                return respostas.pop(0) if respostas else QMessageBox.StandardButton.No
            return QMessageBox.StandardButton.Ok
        return caixa

    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(registrar(tipo)))
    caixas.respostas = respostas
    return caixas


class _Lista(list):
    pass


@pytest.fixture
def rede(monkeypatch):
    """O catálogo do provedor e o log de uso, sem rede nem disco."""
    chamadas = _Lista()
    chamadas.catalogo = {k: list(v) for k, v in CATALOGO.items()}
    chamadas.relatorio = RELATORIO

    chamadas.baixado_em, chamadas.vencido, chamadas.erro = None, False, None

    def consultar(provider, chaves=None, *, forcar=False, somente_cache=False, **_kw):
        chamadas.append({"provider": provider, "forcar": forcar, "somente_cache": somente_cache,
                         "thread": threading.current_thread(), "chaves": chaves})
        modelos = list(chamadas.catalogo.get(provider, []))
        return catalogo.Catalogo(modelos, chamadas.baixado_em if modelos else None,
                                 chamadas.vencido if modelos else False,
                                 chamadas.erro if forcar else None)

    monkeypatch.setattr(catalogo, "consultar", consultar)
    monkeypatch.setattr(catalogo, "listar_modelos", lambda *a, **k: consultar(*a, **k).modelos)
    monkeypatch.setattr(home_mod.llm_usage, "usage_report", lambda *a, **k: chamadas.relatorio)
    monkeypatch.setattr(updater, "canal_testes_ligado", lambda **k: False)
    return chamadas


@pytest.fixture
def home(qt_interface, qtbot, rede, mensagens):
    tela = home_mod.HomeView(controller=Controller())
    qtbot.addWidget(tela)
    return tela


def _texto(rotulo):
    """O texto que a pessoa lê (os rótulos de várias linhas guardam o puro)."""
    return getattr(rotulo, "texto_puro", None) or rotulo.text()


def _itens(menu):
    return [menu.itemText(i) for i in range(menu.count())]


def _escolher(menu, texto):
    """Escolha da pessoa no CTkOptionMenu: muda e dispara o `command` (activated)."""
    indice = _itens(menu).index(texto)
    menu.setCurrentIndex(indice)
    menu.activated.emit(indice)


def _rotulo_fav(fav):
    tier = {"padrao": "Padrão", "economia": "Economia", "poder": "Poder"}.get(fav["tier"], fav["tier"])
    return (f"{fav['rotulo']} ({tier}, ${fav['preco_input']:.2f} / "
            f"${fav['preco_output']:.2f} por 1M tokens)")


def _janelas_abertas(home):
    return [j for j in home.findChildren(JanelaPainel) if j.isVisible()]


# =============================================================================
# Textos iguais aos da Home da interface antiga
# =============================================================================

def test_textos_iguais_aos_da_home_antiga():
    """Os textos que a Home da interface antiga mostrava (eram comparados com
    ela; ela saiu em 2026-10-15, e os valores ficam travados aqui)."""
    # Sem o emoji desde 2026-10-20: o desenho é o ícone (`ICONE_DA_BARRA`).
    # 2026-10-22: o botão e a caixa foram para a janela Configuração, com o texto da spec.
    assert config_mod.ACAO["atualizacoes"].texto == "Procurar atualizações"
    assert config_mod.TEXTO_CANAL_TESTES == "Receber versões de teste"
    assert home_mod.HomeView.ROTULO_PROVIDER_IA == {
        "gemini": "Gemini (chave direta do Google)",
        "openrouter": "OpenRouter (vários modelos, uma chave)",
        "openai_compat": "AMP / IA da empresa",
    }
    assert list(home_mod.CHAVES_API) == [
        ("GEMINI", "Gemini API Key:"), ("GOOGLE_SEARCH", "Google Search API:"),
        ("GOOGLE_CSE", "Google CSE ID:"), ("LLAMA", "LlamaCloud API:"),
        ("OPENROUTER", "OpenRouter API Key:"), ("EMPRESA_LLM_BASE_URL", "IA Empresa (Base URL):"),
        ("EMPRESA_LLM_API_KEY", "IA Empresa (API Key):"),
    ]
    assert home_mod.ROTULOS_TAREFA_IA == {
        "categorizar_pdm": "Categorizar PDM (Cria Fichas):",
        "validar_ficha": "Validar ficha (Analyzer):",
        "condicoes": "Condições (Upload Condições):",
        "tech_specs": "Caract. Técnicas (Upload Specs):",
        "autospec": "AutoSpec (RAG):",
        "interpretar_material": "Interpretar material (Cria Fichas):",
        "traduzir_pdm": "Traduzir PDM (Planilhas PMIB):",
    }


def test_desenho_do_mural_igual_ao_da_home_antiga():
    # 2026-10-20: a faixa diz o seu nome (a propriedade `faixa`); a cor é da folha,
    # uma por tema (`estilo.COR_DA_FAIXA`), com o roxo da travada mantido no escuro.
    assert mural_qt.COR_FAIXA == {f: f for f in (
        "atrasada", "travada", "deveria_ter_comecado", "em_andamento", "comeca_hoje", "proximos_dias")}
    assert estilo.COR_DA_FAIXA["escuro"]["travada"] == "#B07CE8"
    assert mural_qt.ROTULO_FAIXA == {
        "atrasada": "ATRASADO", "travada": "TRAVADA", "deveria_ter_comecado": "DEVERIA TER COMEÇADO",
        "em_andamento": "EM ANDAMENTO", "comeca_hoje": "COMEÇA HOJE", "proximos_dias": "PRÓXIMOS 7 DIAS"}
    assert mural_qt.EXPLICACAO_FAIXA == {
        "atrasada": "a previsão de término já passou",
        "travada": "começou e parou; precisa de alguém para destravar",
        "deveria_ter_comecado": "a data de início passou e ninguém começou",
        "em_andamento": "alguém está tocando agora",
        "comeca_hoje": "entra na fila de hoje",
        "proximos_dias": "para se preparar"}
    # A escala de 2 a 5 é a mesma nos dois temas; a 1 e a sem criticidade seguem o
    # tema (`texto_suave` e `borda`; eram os cinzas #5A5A5A e #3A3A3A).
    assert mural_qt.COR_CRITICIDADE == {5: "#D32F2F", 4: "#FF6F3C", 3: "#FFA726", 2: "#4DA3A9",
                                        1: "texto_suave"}
    assert mural_qt.COR_CRITICIDADE_PADRAO == "borda"


# =============================================================================
# Barra de botões
# =============================================================================

def test_barra_na_ordem_e_com_as_cores_da_tela_antiga(home):
    # 2026-10-20: cada botão da barra é uma variante (a cor é da folha do tema).
    # 2026-10-20: o emoji da frente do texto virou o ícone Lucide do botão.
    # 2026-10-22: modelos, chaves e atualizações foram para a janela Configuração.
    esperado = [
        ("atividades", "Atividades do dia", "primario", "clipboard-check"),
        ("gastos", "Gastos de IA", "primario", "circle-dollar-sign"),
    ]
    assert list(home.botoes_barra) == [chave for chave, _t, _c, _i in esperado]
    for chave, texto, cor, icone in esperado:
        botao = home.botoes_barra[chave]
        assert botao.text() == texto
        assert botao.property("icone") == icone and not botao.icon().isNull(), chave
        assert botao.property("variante") == cor, chave
        assert "background" not in botao.styleSheet(), chave


@pytest.mark.parametrize("abrir, titulo, tamanho", [
    ("abrir_janela_chaves_api", "Chaves de API", (760, 520)),
    ("abrir_janela_modelos_ia", "Modelos de IA", (900, 680)),
    ("abrir_janela_gastos_ia", "Gastos de IA", (860, 600)),
    ("abrir_mural_atividades", "Atividades do dia", (820, 640)),
])
def test_cada_painel_abre_em_janela(home, monkeypatch, abrir, titulo, tamanho):
    # Desde 2026-10-22 chaves e modelos abrem pela janela Configuração; o método é o mesmo.
    monkeypatch.setattr(home_mod.HomeView, "_ler_mural", lambda self: ({f: [] for f in at.FAIXAS}, None))
    getattr(home, abrir)()
    [janela] = _janelas_abertas(home)
    assert janela.windowTitle() == titulo
    assert (janela.width(), janela.height()) == tamanho
    assert janela.windowModality() == Qt.WindowModality.NonModal


def test_os_botoes_da_barra_abrem_atividades_e_gastos(home, monkeypatch):
    monkeypatch.setattr(home_mod.HomeView, "_ler_mural", lambda self: ({f: [] for f in at.FAIXAS}, None))
    for chave, titulo in (("atividades", "Atividades do dia"), ("gastos", "Gastos de IA")):
        home.botoes_barra[chave].click()
        assert titulo in [j.windowTitle() for j in _janelas_abertas(home)]


@pytest.mark.parametrize("abrir", ["abrir_janela_chaves_api", "abrir_janela_modelos_ia",
                                   "abrir_janela_gastos_ia", "abrir_mural_atividades"])
def test_segundo_clique_traz_a_mesma_janela(home, monkeypatch, abrir):
    # Os painéis guardam os campos na Home (`entries`, os menus de modelo): uma
    # segunda janela do mesmo painel faria a primeira salvar pelos campos da outra.
    monkeypatch.setattr(home_mod.HomeView, "_ler_mural", lambda self: ({f: [] for f in at.FAIXAS}, None))
    primeira = getattr(home, abrir)()
    assert getattr(home, abrir)() is primeira
    assert _janelas_abertas(home) == [primeira]


def test_segundo_clique_restaura_a_janela_minimizada(home, qtbot):
    janela = home.abrir_janela_gastos_ia()
    janela.showMinimized()
    assert janela.isMinimized()
    assert home.abrir_janela_gastos_ia() is janela
    assert not janela.isMinimized() and janela.isVisible()


def test_restaurar_nao_desmaximiza(home, qtbot):
    # Maximizada e depois minimizada: volta MAXIMIZADA (o `showNormal()` a
    # desmaximizava).
    janela = home.abrir_janela_modelos_ia()
    janela.showMaximized()
    janela.showMinimized()
    assert janela.isMinimized() and janela.windowState() & Qt.WindowState.WindowMaximized
    assert home.abrir_janela_modelos_ia() is janela
    assert not janela.isMinimized()
    assert janela.isMaximized()


def test_fechado_reabre_com_o_conteudo_de_agora(home, qtbot, rede):
    primeira = home.abrir_janela_gastos_ia()
    primeira.close()
    rede.relatorio = {}
    segunda = home.abrir_janela_gastos_ia()
    assert segunda is not primeira and segunda.isVisible()
    assert _texto(home.lbl_gastos_ia) == "Nenhuma chamada de IA registrada ainda."


# =============================================================================
# Chaves de API
# =============================================================================

def test_area_de_chaves_com_os_campos_e_os_valores_atuais(home):
    home.abrir_janela_chaves_api()
    assert list(home.entries) == [k for k, _r in home_mod.CHAVES_API]
    assert [r.text() for r in home.rotulos_chaves_api.values()] == [r for _k, r in home_mod.CHAVES_API]
    assert home.entries["GEMINI"].text() == CHAVES["GEMINI"]
    assert home.entries["LLAMA"].text() == ""
    # O emoji do título saiu em 2026-10-20 (o ícone fica no botão da barra).
    assert home.lbl_titulo_chaves_api.text() == "Configuração de Chaves API (Global)"
    assert home.btn_salvar_chaves.text() == "Salvar Chaves"


def test_chaves_ficam_mascaradas_com_asterisco_e_sem_mono(home):
    # `CTkEntry(show="*")`: mascarado, e o caractere é o asterisco do Tk.
    home.abrir_janela_chaves_api()
    for campo in home.entries.values():
        assert campo.echoMode() == QLineEdit.EchoMode.Password
        estilo_campo = campo.style()
        assert estilo_campo.styleHint(QStyle.StyleHint.SH_LineEdit_PasswordCharacter, None, campo) == ord("*")
    assert "︎" not in home.entries["GEMINI"].text()  # dado nunca passa pelo mono


def test_salvar_chaves_limpa_espacos_grava_todas_e_avisa(home, mensagens, capsys):
    home.abrir_janela_chaves_api()
    home.entries["OPENROUTER"].setText("  sk-or-nova\n ")
    home.btn_salvar_chaves.click()

    [salvas] = home.controller.salvas
    assert list(salvas) == [k for k, _r in home_mod.CHAVES_API]
    assert salvas["OPENROUTER"] == "sk-or-nova"
    assert salvas["GEMINI"] == CHAVES["GEMINI"]
    [(tipo, titulo, texto, pai)] = mensagens
    assert (tipo, titulo) == ("information", "Sucesso")
    assert texto == "Chaves API salvas com sucesso!\nTodos os módulos usarão as novas chaves."
    assert pai is home.entries["GEMINI"].window(), "a mensagem nasce da janela do painel"
    saida = capsys.readouterr()
    assert "sk-or-nova" not in saida.out + saida.err, "chave é segredo: nunca no log"


def test_esc_e_enter_nao_fecham_nem_salvam_as_chaves(home, qtbot, mensagens):
    janela = home.abrir_janela_chaves_api()
    campo = home.entries["GEMINI"]
    campo.setText("digitada")
    qtbot.keyClick(campo, Qt.Key.Key_Return)
    qtbot.keyClick(campo, Qt.Key.Key_Escape)
    qtbot.keyClick(janela, Qt.Key.Key_Escape)
    assert janela.isVisible()
    assert campo.text() == "digitada"
    assert home.controller.salvas == [] and mensagens == []


def test_salvar_chaves_remonta_o_painel_de_modelos_aberto(qt_interface, qtbot, rede, mensagens):
    # Quem colava a chave do OpenRouter e salvava continuava vendo só o Gemini.
    tela = home_mod.HomeView(controller=Controller({"GEMINI": "g"}))
    qtbot.addWidget(tela)
    tela.abrir_janela_modelos_ia()
    assert _itens(tela.opt_provider_ia) == [ROTULO_GEMINI]
    tela.abrir_janela_chaves_api()
    tela.entries["OPENROUTER"].setText("sk-or")
    tela.salvar_chaves_api()
    assert _itens(tela.opt_provider_ia) == [ROTULO_GEMINI, ROTULO_OPENROUTER]


def test_salvar_chaves_com_o_painel_de_modelos_fechado(qt_interface, qtbot, rede, mensagens):
    tela = home_mod.HomeView(controller=Controller({"GEMINI": "g"}))
    qtbot.addWidget(tela)
    tela.abrir_janela_modelos_ia().close()
    tela.abrir_janela_chaves_api()
    tela.salvar_chaves_api()
    assert [m[1] for m in mensagens] == ["Sucesso"]


# =============================================================================
# Modelos de IA
# =============================================================================

def test_sem_chave_nenhuma_o_painel_explica(qt_interface, qtbot, rede, mensagens):
    tela = home_mod.HomeView(controller=Controller({}))
    qtbot.addWidget(tela)
    tela.abrir_janela_modelos_ia()
    assert _texto(tela.lbl_sem_provedor_ia) == (
        "Nenhum provedor de IA tem chave configurada acima. Configure ao menos uma "
        "chave (ex.: Gemini ou OpenRouter) para escolher o modelo aqui.")
    assert tela.opt_provider_ia is None and tela.lbl_resumo_modelo_ia is None


def test_provedores_com_chave_e_o_primeiro_quando_nada_salvo(home, rede):
    home.abrir_janela_modelos_ia()
    assert home.lbl_titulo_modelos_ia.text() == "Modelos de IA"   # sem o emoji (2026-10-20)
    assert _itens(home.opt_provider_ia) == [ROTULO_GEMINI, ROTULO_OPENROUTER]
    assert home.opt_provider_ia.currentText() == ROTULO_GEMINI
    favs = catalogo.modelos_recomendados("gemini")
    extras = [m for m in CATALOGO["gemini"] if m not in {f["model"] for f in favs}]
    esperado = [NEUTRO_GLOBAL] + [_rotulo_fav(f) for f in favs] + extras
    assert _itens(home.opt_modelo_ia_global) == esperado
    assert home.opt_modelo_ia_global.currentText() == NEUTRO_GLOBAL
    # a montagem lê SÓ o cache: a Home não pode ficar pendurada em rede
    assert rede and all(c["somente_cache"] and not c["forcar"] for c in rede)


def test_reabre_no_provedor_e_no_modelo_salvos(home):
    selecao.definir_global("openrouter", "x-ai/grok-4.5", config_path=sigft_config.CONFIG_FILE)
    home.abrir_janela_modelos_ia()
    assert home.opt_provider_ia.currentText() == ROTULO_OPENROUTER
    [grok] = [f for f in catalogo.modelos_recomendados("openrouter") if f["model"] == "x-ai/grok-4.5"]
    assert home.opt_modelo_ia_global.currentText() == _rotulo_fav(grok)
    assert "︎" not in home.opt_modelo_ia_global.currentText()  # nome de modelo é dado


def test_provedor_da_maioria_das_tarefas_quando_o_global_esta_vazio(home):
    for tarefa, provider, modelo in (("condicoes", "openrouter", "x-ai/grok-4.5"),
                                     ("tech_specs", "openrouter", "x-ai/grok-4.5"),
                                     ("autospec", "gemini", "gemini-3.5-flash")):
        selecao.definir_por_tarefa(tarefa, provider, modelo, config_path=sigft_config.CONFIG_FILE)
    home.abrir_janela_modelos_ia()
    assert home.opt_provider_ia.currentText() == ROTULO_OPENROUTER
    assert home.caixa_modo_avancado_ia.isChecked()
    assert home.frame_modelos_ia_avancado.isVisibleTo(home.frame_modelos_ia)


def test_selecao_salva_fora_da_lista_aparece_como_salvo(home):
    selecao.definir_global("openrouter", "vendor/modelo-antigo", config_path=sigft_config.CONFIG_FILE)
    home.abrir_janela_modelos_ia()
    rotulo = "(salvo) openrouter / vendor/modelo-antigo"
    assert rotulo in _itens(home.opt_modelo_ia_global)
    assert home.opt_modelo_ia_global.currentText() == rotulo


NAO_BAIXADO = ("Catálogo ainda não baixado para este provedor. Clique em \"Atualizar lista de "
               "modelos\". Enquanto isso valem os recomendados e o campo manual.")


def test_rotulo_do_catalogo(home, rede):
    # Conta só o que VEIO do catálogo (rótulo == id). No Gemini os dois ids do
    # catálogo dublado são favoritos (rótulo com preço): lá também diz "não baixado".
    home.abrir_janela_modelos_ia()
    assert _texto(home.lbl_catalogo_ia) == NAO_BAIXADO
    _escolher(home.opt_provider_ia, ROTULO_OPENROUTER)
    favs = catalogo.modelos_recomendados("openrouter")
    do_catalogo = [m for m in CATALOGO["openrouter"] if m not in {f["model"] for f in favs}]
    assert _texto(home.lbl_catalogo_ia) == (
        f"{len(favs) + len(do_catalogo)} modelos disponíveis ({len(do_catalogo)} do catálogo do provedor).")
    rede.catalogo = {}
    _escolher(home.opt_provider_ia, ROTULO_OPENROUTER)
    assert _texto(home.lbl_catalogo_ia) == NAO_BAIXADO


def _epoch(dia, mes):
    from datetime import datetime
    return datetime(2026, mes, dia, 9, 30).timestamp()


def test_catalogo_vencido_continua_no_painel_e_diz_de_quando_e(home, rede):
    # Pendência de 2026-09-25: um dia depois de baixado, o catálogo sumia.
    rede.baixado_em, rede.vencido = _epoch(15, 10), True
    home.abrir_janela_modelos_ia()
    _escolher(home.opt_provider_ia, ROTULO_OPENROUTER)
    favs = catalogo.modelos_recomendados("openrouter")
    do_catalogo = [m for m in CATALOGO["openrouter"] if m not in {f["model"] for f in favs}]
    assert do_catalogo[0] in _itens(home.opt_modelo_ia_global)
    assert _texto(home.lbl_catalogo_ia) == (
        f"{len(favs) + len(do_catalogo)} modelos disponíveis "
        f"({len(do_catalogo)} do catálogo do provedor, lista de 15/10).")
    assert not any(c["forcar"] for c in rede), "abrir o painel não vai à rede"


def test_falha_ao_atualizar_vira_aviso_e_a_lista_que_havia_fica(home, qtbot, rede):
    # Pendência de 2026-09-25: a falha era muda ("ainda não baixado", sem motivo).
    rede.baixado_em, rede.vencido = _epoch(15, 10), True
    home.abrir_janela_modelos_ia()
    _escolher(home.opt_provider_ia, ROTULO_OPENROUTER)
    itens_antes = _itens(home.opt_modelo_ia_global)
    cor_normal = home.lbl_catalogo_ia.styleSheet()
    rede.erro = "ProxyError: 407 Proxy Authentication Required"
    home.btn_atualizar_catalogo_ia.click()
    qtbot.waitUntil(lambda: "407" in _texto(home.lbl_catalogo_ia), timeout=3000)
    assert _texto(home.lbl_catalogo_ia) == (
        "Não foi possível atualizar a lista de modelos (ProxyError: 407 Proxy Authentication "
        "Required). Continua valendo a lista de 15/10.")
    assert _itens(home.opt_modelo_ia_global) == itens_antes
    # 2026-10-20: a cor de alerta é o papel `erro` da folha (a folha local não muda).
    assert home.lbl_catalogo_ia.property("papel") == "erro", "o aviso tem a cor de alerta"
    assert home.lbl_catalogo_ia.styleSheet() == cor_normal
    # Trocar de provedor (ou atualizar de novo com sucesso) tira o aviso.
    _escolher(home.opt_provider_ia, ROTULO_GEMINI)
    assert "Não foi possível" not in _texto(home.lbl_catalogo_ia)
    assert home.lbl_catalogo_ia.property("papel") == "legenda"


def test_falha_ao_atualizar_sem_lista_nenhuma_diz_o_motivo(home, qtbot, rede):
    rede.catalogo = {}
    rede.erro = "HTTPError: 401 Client Error: Unauthorized"
    home.abrir_janela_modelos_ia()
    _escolher(home.opt_provider_ia, ROTULO_OPENROUTER)
    home.btn_atualizar_catalogo_ia.click()
    qtbot.waitUntil(lambda: "401" in _texto(home.lbl_catalogo_ia), timeout=3000)
    assert _texto(home.lbl_catalogo_ia) == (
        "Não foi possível baixar a lista de modelos (HTTPError: 401 Client Error: Unauthorized). "
        "Enquanto isso valem os recomendados e o campo manual.")


def test_filtro_estreita_a_lista_sem_perder_a_escolha(home, qtbot):
    home.abrir_janela_modelos_ia()
    _escolher(home.opt_provider_ia, ROTULO_OPENROUTER)
    [grok] = [f for f in catalogo.modelos_recomendados("openrouter") if f["model"] == "x-ai/grok-4.5"]
    _escolher(home.opt_modelo_ia_global, _rotulo_fav(grok))
    qtbot.keyClicks(home.entry_filtro_modelo_ia, "HAIKU")
    assert _itens(home.opt_modelo_ia_global) == [NEUTRO_GLOBAL, "anthropic/claude-haiku-4.5",
                                                 _rotulo_fav(grok)]
    assert home.opt_modelo_ia_global.currentText() == _rotulo_fav(grok)
    home.entry_filtro_modelo_ia.clear()
    assert len(_itens(home.opt_modelo_ia_global)) > 3


def test_resumo_segue_a_precedencia_manual_lista_padrao(home, qtbot):
    home.abrir_janela_modelos_ia()
    _escolher(home.opt_provider_ia, ROTULO_OPENROUTER)
    assert _texto(home.lbl_resumo_modelo_ia) == (
        "Ao salvar: todas as tarefas voltam ao padrão do sistema (modelos atuais).")
    _escolher(home.opt_modelo_ia_global, "anthropic/claude-haiku-4.5")
    assert _texto(home.lbl_resumo_modelo_ia) == (
        "Ao salvar: openrouter / anthropic/claude-haiku-4.5  (veio do lista de modelos)")
    qtbot.keyClicks(home.entry_modelo_ia_livre, "meta-llama/llama-4")
    assert _texto(home.lbl_resumo_modelo_ia) == (
        "Ao salvar: openrouter / meta-llama/llama-4  (veio do campo manual)")
    # Escolher na lista desiste do manual: vale o último controle mexido.
    _escolher(home.opt_modelo_ia_global, "minimax/minimax-m3" if "minimax/minimax-m3"
              in _itens(home.opt_modelo_ia_global) else _itens(home.opt_modelo_ia_global)[1])
    assert home.entry_modelo_ia_livre.text() == ""
    assert "(veio do lista de modelos)" in _texto(home.lbl_resumo_modelo_ia)
    qtbot.keyClicks(home.entry_modelo_ia_livre, "x/y")
    home.btn_limpar_modelo_ia.click()
    assert home.entry_modelo_ia_livre.text() == ""
    assert "(veio do lista de modelos)" in _texto(home.lbl_resumo_modelo_ia)


def test_modo_avancado_mostra_as_tarefas_e_conta_os_overrides(home):
    home.abrir_janela_modelos_ia()
    _escolher(home.opt_provider_ia, ROTULO_OPENROUTER)
    assert not home.caixa_modo_avancado_ia.isChecked()
    assert not home.frame_modelos_ia_avancado.isVisibleTo(home.frame_modelos_ia)
    home.caixa_modo_avancado_ia.click()
    assert home.frame_modelos_ia_avancado.isVisibleTo(home.frame_modelos_ia)
    assert list(home.menus_modelo_ia_por_tarefa) == list(sigft_config.TAREFAS_DO_PAINEL)
    assert [r.text() for r in home.rotulos_modelo_ia_por_tarefa.values()] == [
        home_mod.ROTULOS_TAREFA_IA[t] for t in sigft_config.TAREFAS_DO_PAINEL]
    menu = home.menus_modelo_ia_por_tarefa["categorizar_pdm"]
    assert menu.currentText() == NEUTRO_TAREFA
    _escolher(menu, "x-ai/grok-4.5" if "x-ai/grok-4.5" in _itens(menu) else _itens(menu)[1])
    assert _texto(home.lbl_resumo_modelo_ia).endswith(
        "  |  1 tarefa(s) com modelo próprio (categorizar_pdm), que vence o padrão acima.")
    home.caixa_modo_avancado_ia.click()
    assert not home.frame_modelos_ia_avancado.isVisibleTo(home.frame_modelos_ia)
    assert "tarefa(s)" not in _texto(home.lbl_resumo_modelo_ia)


def test_trocar_de_provedor_troca_a_lista_e_esquece_o_manual(home, qtbot):
    selecao.definir_global("openrouter", "x-ai/grok-4.5", config_path=sigft_config.CONFIG_FILE)
    home.abrir_janela_modelos_ia()
    qtbot.keyClicks(home.entry_modelo_ia_livre, "algum/id")
    _escolher(home.opt_provider_ia, ROTULO_GEMINI)
    assert home.entry_modelo_ia_livre.text() == ""
    itens = _itens(home.opt_modelo_ia_global)
    [flash] = [f for f in catalogo.modelos_recomendados("gemini") if f["model"] == "gemini-3.5-flash"]
    assert _rotulo_fav(flash) in itens
    # o que está valendo no disco não some da lista (e não é apagado no Salvar)
    assert "(salvo) openrouter / x-ai/grok-4.5" in itens


def test_salvar_selecao_grava_global_e_tarefas_e_avisa(home, mensagens):
    home.abrir_janela_modelos_ia()
    _escolher(home.opt_provider_ia, ROTULO_OPENROUTER)
    _escolher(home.opt_modelo_ia_global, "anthropic/claude-haiku-4.5")
    home.caixa_modo_avancado_ia.click()
    _escolher(home.menus_modelo_ia_por_tarefa["validar_ficha"], "minimax/minimax-m3"
              if "minimax/minimax-m3" in _itens(home.menus_modelo_ia_por_tarefa["validar_ficha"])
              else _itens(home.menus_modelo_ia_por_tarefa["validar_ficha"])[1])
    antigo = home.frame_modelos_ia
    home.btn_salvar_selecao_ia.click()

    estado = selecao.carregar(config_path=sigft_config.CONFIG_FILE)
    assert estado["global"] == {"provider": "openrouter", "model": "anthropic/claude-haiku-4.5"}
    assert list(estado["por_tarefa"]) == ["validar_ficha"]
    assert estado["por_tarefa"]["validar_ficha"]["provider"] == "openrouter"
    [(tipo, titulo, texto, _pai)] = mensagens
    assert (tipo, titulo) == ("information", "Seleção salva")
    assert texto == ("Seleção de modelos de IA salva. A próxima execução de cada módulo já usa o "
                     "modelo escolhido. Não é preciso reiniciar o SIG-FT.")
    # remontado no mesmo lugar, mostrando o que acabou de ser salvo
    assert home.frame_modelos_ia is not antigo
    assert home.frame_modelos_ia.window() is antigo.window()
    assert home.opt_modelo_ia_global.currentText() == "anthropic/claude-haiku-4.5"
    assert home.opt_provider_ia.currentText() == ROTULO_OPENROUTER


def test_salvar_com_o_padrao_limpa_o_global(home, mensagens):
    selecao.definir_global("gemini", "gemini-3.5-flash", config_path=sigft_config.CONFIG_FILE)
    home.abrir_janela_modelos_ia()
    _escolher(home.opt_modelo_ia_global, NEUTRO_GLOBAL)
    home.btn_salvar_selecao_ia.click()
    assert selecao.carregar(config_path=sigft_config.CONFIG_FILE)["global"] is None


def test_aplicar_recomendados_com_as_chaves(home, mensagens):
    home.abrir_janela_modelos_ia()
    home.btn_aplicar_recomendados_ia.click()
    estado = selecao.carregar(config_path=sigft_config.CONFIG_FILE)
    assert estado["global"]["model"] == sigft_config.LLM_DEFAULT["model"]
    assert set(estado["por_tarefa"]) == set(sigft_config.LLM_TASKS)
    [(tipo, titulo, _texto_msg, _pai)] = mensagens
    assert (tipo, titulo) == ("information", "Recomendados aplicados")


@pytest.mark.parametrize("resposta, aplicou", [
    (QMessageBox.StandardButton.No, False), (QMessageBox.StandardButton.Yes, True)])
def test_aplicar_recomendados_sem_a_chave_pergunta_antes(qt_interface, qtbot, rede, mensagens,
                                                       resposta, aplicou):
    tela = home_mod.HomeView(controller=Controller({"GEMINI": "g"}))
    qtbot.addWidget(tela)
    tela.abrir_janela_modelos_ia()
    mensagens.respostas.append(resposta)
    tela.btn_aplicar_recomendados_ia.click()
    tipo, titulo, texto, _pai = mensagens[0]
    assert (tipo, titulo) == ("question", "Chave de API faltando")
    assert texto.startswith("Os modelos recomendados exigem OPENROUTER, que ainda não está configurada")
    estado = selecao.carregar(config_path=sigft_config.CONFIG_FILE)
    assert bool(estado["por_tarefa"]) is aplicou


def test_aplicar_mesmo_assim_tem_nao_como_padrao(qt_interface, qtbot, rede, mensagens):
    # Desvio deliberado: o askyesno do Tk tinha "Sim" como padrão; aqui um Enter
    # na pergunta NÃO aplica os recomendados sem a chave.
    tela = home_mod.HomeView(controller=Controller({"GEMINI": "g"}))
    qtbot.addWidget(tela)
    tela.abrir_janela_modelos_ia()
    tela.btn_aplicar_recomendados_ia.click()
    assert mensagens[0][:2] == ("question", "Chave de API faltando")
    botoes, padrao = mensagens.extras[0][0]
    assert botoes == QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    assert padrao == QMessageBox.StandardButton.No


def test_esc_e_enter_nao_salvam_a_selecao(home, qtbot, mensagens):
    janela = home.abrir_janela_modelos_ia()
    qtbot.keyClicks(home.entry_modelo_ia_livre, "meu/modelo")
    qtbot.keyClick(home.entry_modelo_ia_livre, Qt.Key.Key_Return)
    qtbot.keyClick(home.entry_filtro_modelo_ia, Qt.Key.Key_Return)
    qtbot.keyClick(janela, Qt.Key.Key_Escape)
    assert janela.isVisible() and mensagens == []
    assert selecao.carregar(config_path=sigft_config.CONFIG_FILE)["global"] is None


def _catalogo_que_espera(monkeypatch, rede, liberar, vistos, novos=None):
    """`consultar` cuja busca de verdade (`forcar=True`) fica presa até `liberar`."""
    antigo = catalogo.consultar

    def lento(provider, chaves=None, *, forcar=False, **kw):
        if forcar:
            vistos.append((threading.current_thread(), dict(chaves or {})))
            liberar.wait(5)
            if novos is not None:
                rede.catalogo = novos
        return antigo(provider, chaves, forcar=forcar, **kw)

    monkeypatch.setattr(catalogo, "consultar", lento)


def test_roda_do_mouse_em_cima_do_menu_nao_troca_o_modelo(home, qtbot):
    # O CTkOptionMenu não escuta a roda; o QComboBox, sim -- e o painel rola:
    # rolar a janela com o ponteiro em cima de um menu trocaria a escolha.
    from PySide6.QtCore import QPoint, QPointF
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QApplication

    home.abrir_janela_modelos_ia()
    menu = home.opt_modelo_ia_global
    antes = menu.currentText()
    for passo in (-120, 120, -120):
        evento = QWheelEvent(QPointF(20, 10), QPointF(menu.mapToGlobal(QPoint(20, 10))), QPoint(0, 0),
                             QPoint(0, passo), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                             Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(menu, evento)
        assert not evento.isAccepted(), "a roda segue para a área, que rola"
    assert menu.currentText() == antes


def test_nenhum_controle_dos_paineis_pega_o_foco(home, monkeypatch):
    # CTkButton, CTkCheckBox e CTkOptionMenu nunca pegam o foco: no Qt, um botão
    # com foco é apertado pelo Espaço (e o "Fechar" jogaria fora o digitado).
    from PySide6.QtWidgets import QCheckBox, QComboBox, QPushButton

    monkeypatch.setattr(home_mod.HomeView, "_ler_mural", lambda self: ({f: [] for f in at.FAIXAS}, None))
    janelas = [home.abrir_janela_chaves_api(), home.abrir_janela_modelos_ia(),
               home.abrir_janela_gastos_ia(), home.abrir_mural_atividades(),
               home.abrir_configuracao()]
    controles_ = [home.btn_configuracao, *home.botoes_barra.values()]
    for janela in janelas:
        controles_ += janela.findChildren(QPushButton) + janela.findChildren(QCheckBox)
        controles_ += janela.findChildren(QComboBox)
    assert len(controles_) > 20
    for controle in controles_:
        assert controle.focusPolicy() == Qt.FocusPolicy.NoFocus, controle.text() if hasattr(
            controle, "text") else controle
        if isinstance(controle, QPushButton):
            assert not controle.autoDefault() and not controle.isDefault()


def test_atualizar_catalogo_busca_numa_thread_de_fundo(home, qtbot, rede, monkeypatch):
    home.abrir_janela_modelos_ia()
    rede.catalogo = {"gemini": []}
    _escolher(home.opt_provider_ia, ROTULO_GEMINI)
    assert _texto(home.lbl_catalogo_ia) == NAO_BAIXADO
    liberar, vistos = threading.Event(), []
    _catalogo_que_espera(monkeypatch, rede, liberar, vistos, novos={"gemini": ["gemini-novo"]})
    na_interface = []
    recarregar = home._recarregar_modelos_do_provider

    def espiao(*a, **k):
        na_interface.append(threading.current_thread() is threading.main_thread())
        return recarregar(*a, **k)

    monkeypatch.setattr(home, "_recarregar_modelos_do_provider", espiao)
    home.btn_atualizar_catalogo_ia.click()
    assert _texto(home.lbl_catalogo_ia) == "Buscando a lista de modelos do provedor..."
    liberar.set()
    qtbot.waitUntil(lambda: "gemini-novo" in _itens(home.opt_modelo_ia_global), timeout=3000)
    [(thread, chaves)] = vistos
    assert thread is not threading.main_thread() and thread.daemon
    assert chaves["GEMINI"] == CHAVES["GEMINI"]
    assert na_interface == [True]
    assert _texto(home.lbl_catalogo_ia).endswith("(1 do catálogo do provedor).")


def test_catalogo_que_chega_depois_de_reabrir_vai_para_o_painel_novo(home, qtbot, rede, monkeypatch,
                                                                     capsys):
    primeira = home.abrir_janela_modelos_ia()
    liberar, vistos = threading.Event(), []
    _catalogo_que_espera(monkeypatch, rede, liberar, vistos,
                         novos={**CATALOGO, "gemini": ["gemini-novo"]})
    home.btn_atualizar_catalogo_ia.click()
    primeira.close()
    segunda = home.abrir_janela_modelos_ia()
    assert segunda is not primeira
    liberar.set()
    qtbot.waitUntil(lambda: "gemini-novo" in _itens(home.opt_modelo_ia_global), timeout=3000)
    assert home.opt_modelo_ia_global.window() is segunda
    assert "Traceback" not in capsys.readouterr().err


def test_catalogo_que_chega_depois_do_painel_destruido_e_descartado(home, qtbot, rede, monkeypatch,
                                                                    capsys):
    # A resposta chega (na thread da interface) e a GUARDA a descarta: o painel
    # não é redesenhado sobre widgets destruídos.
    from PySide6.QtCore import QCoreApplication, QEvent

    janela = home.abrir_janela_modelos_ia()
    liberar, vistos = threading.Event(), []
    _catalogo_que_espera(monkeypatch, rede, liberar, vistos)
    chegadas, redesenhos = [], []
    chegou = home._catalogo_chegou
    monkeypatch.setattr(home, "_catalogo_chegou", lambda: (
        chegadas.append(threading.current_thread() is threading.main_thread()), chegou()))
    monkeypatch.setattr(home, "_recarregar_modelos_do_provider", lambda *a, **k: redesenhos.append(a))
    home.btn_atualizar_catalogo_ia.click()
    janela.close()
    janela.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not _vivo(janela)
    liberar.set()
    qtbot.waitUntil(lambda: bool(chegadas), timeout=3000)
    assert chegadas == [True], "a resposta veio pela thread da interface"
    assert redesenhos == [], "a guarda descartou a resposta (painel destruído)"
    assert "Traceback" not in capsys.readouterr().err


def _vivo(widget):
    from shiboken6 import isValid
    return isValid(widget)


# =============================================================================
# Gastos de IA
# =============================================================================

def test_gastos_mostra_o_relatorio_e_atualiza(home, rede):
    from sigft.core.llm import usage

    home.abrir_janela_gastos_ia()
    assert home.lbl_titulo_gastos_ia.text() == "Gastos de IA"   # sem o emoji (2026-10-20)
    assert _texto(home.lbl_gastos_ia) == usage.formatar_relatorio_texto(RELATORIO)
    rede.relatorio = {}
    home.btn_atualizar_gastos_ia.click()
    assert _texto(home.lbl_gastos_ia) == "Nenhuma chamada de IA registrada ainda."


def test_gastos_que_nao_carregam_viram_aviso(home, monkeypatch):
    def quebra(*_a, **_k):
        raise ValueError("arquivo ilegível")

    monkeypatch.setattr(home_mod.llm_usage, "usage_report", quebra)
    home.abrir_janela_gastos_ia()
    assert _texto(home.lbl_gastos_ia) == (
        "Não foi possível carregar os gastos de IA agora (arquivo ilegível).")


def test_abrir_pasta_de_logs_abre_a_pasta_de_dados(home, monkeypatch, mensagens):
    from sigft.core.dados_usuario import pasta_logs

    abertas = []
    monkeypatch.setattr(plataforma, "abrir_pasta_criando_se_preciso", abertas.append)
    home.abrir_janela_gastos_ia()
    home.btn_pasta_logs_ia.click()
    assert abertas == [str(pasta_logs())]
    assert mensagens == []


def test_abrir_pasta_de_logs_que_falha_avisa(home, monkeypatch, mensagens):
    def quebra(_pasta):
        raise OSError("sem explorador")

    monkeypatch.setattr(plataforma, "abrir_pasta_criando_se_preciso", quebra)
    home.abrir_janela_gastos_ia()
    home.btn_pasta_logs_ia.click()
    [(tipo, titulo, texto, _pai)] = mensagens
    assert (tipo, titulo, texto) == ("critical", "Erro",
                                     "Não foi possível abrir a pasta de logs: sem explorador")


# =============================================================================
# Mural de atividades
# =============================================================================

def _item(desc, dias, termino=None, **extra):
    return {"descricao": desc, "_dias": dias, "_termino": termino, **extra}


def _rotulos(widget):
    return [_texto(r) for r in widget.findChildren(QLabel)]


def test_mural_abre_com_a_data_de_hoje(home, monkeypatch):
    gavetas = {f: [] for f in at.FAIXAS}
    gavetas[at.ATRASADA] = [_item("Revisar fichas", -4, "término 04/10/26", com_quem="Luan",
                                  status="Em andamento", criticidade=5, _grupo="Fichas UG07")]
    monkeypatch.setattr(home_mod.HomeView, "_ler_mural", lambda self: (gavetas, None))
    janela = home.abrir_mural_atividades()
    textos = _rotulos(janela.conteudo)
    assert textos[:2] == [date.today().strftime("%d/%m/%Y"), "1 atividade(s) pedindo atenção"]
    assert ["1", "ATRASADO", "a previsão de término já passou", "Fichas UG07", "Revisar fichas",
            at.frase_do_prazo(at.ATRASADA, -4), "término 04/10/26",
            "com Luan   ·   Em andamento   ·   criticidade 5"] == textos[2:]


def test_mural_com_erro_mostra_so_o_erro(qt_interface, qtbot):
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    pai = QWidget()
    QVBoxLayout(pai)
    qtbot.addWidget(pai)
    mural_qt.montar(pai, {f: [] for f in at.FAIXAS}, "09/10/2026", "Nao encontrei o arquivo.")
    [rotulo] = pai.findChildren(QLabel)
    assert _texto(rotulo) == "Nao encontrei o arquivo."
    assert rotulo.property("papel") == "erro"   # o vermelho é da folha (2026-10-20)


def test_mural_vazio_diz_que_nada_esta_pendente(qt_interface, qtbot):
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    pai = QWidget()
    QVBoxLayout(pai)
    qtbot.addWidget(pai)
    mural_qt.montar(pai, {f: [] for f in at.FAIXAS}, "09/10/2026")
    assert _rotulos(pai) == ["09/10/2026", "0 atividade(s) pedindo atenção",
                             "Nada pendente para hoje nem para os próximos dias."]


def test_mural_faixas_na_ordem_de_urgencia_e_sem_as_vazias(qt_interface, qtbot):
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    pai = QWidget()
    QVBoxLayout(pai)
    qtbot.addWidget(pai)
    gavetas = {f: [] for f in at.FAIXAS}
    gavetas[at.PROXIMOS_DIAS] = [_item("Depois", 2)]
    gavetas[at.ATRASADA] = [_item(None, -1, criticidade="x")]
    mural_qt.montar(pai, gavetas, "09/10/2026")
    textos = _rotulos(pai)
    assert textos.index("ATRASADO") < textos.index("PRÓXIMOS 7 DIAS")
    assert "(sem descrição)" in textos
    assert "TRAVADA" not in textos
    assert "criticidade x" in textos  # o texto da planilha, como veio


def test_cor_da_barra_de_criticidade():
    assert mural_qt._cor_da_criticidade(5) == "#D32F2F"
    assert mural_qt._cor_da_criticidade("1") == "texto_suave"   # o tema decide (2026-10-20)
    assert mural_qt._nivel_da_criticidade("muito") == 0
    assert mural_qt._cor_da_criticidade("muito") == mural_qt.COR_CRITICIDADE_PADRAO
    assert mural_qt._cor_da_criticidade(None) == mural_qt.COR_CRITICIDADE_PADRAO


def test_mural_mostra_o_texto_da_planilha_como_veio(qt_interface, qtbot):
    # O CTkLabel mostra o texto cru. O QLabel, em AutoText, tomaria "<a>"/"<b>"
    # por HTML e os engoliria (o rótulo saía com 112 px).
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    from sigft.app_qt import estilo as _estilo

    _estilo.carregar_fontes()
    pai = QWidget()
    QVBoxLayout(pai)
    qtbot.addWidget(pai)
    gavetas = {f: [] for f in at.FAIXAS}
    gavetas[at.ATRASADA] = [_item("Trocar <a> por <b> no PDM", -1, _grupo="<i>Grupo</i>",
                                  com_quem="<b>Luan</b>")]
    mural_qt.montar(pai, gavetas, "09/10/2026")
    for texto in ("Trocar <a> por <b> no PDM", "<i>Grupo</i>", "com <b>Luan</b>"):
        rotulo = _por_texto(pai, texto)
        assert rotulo.textFormat() == Qt.TextFormat.PlainText, texto
        rotulo.ensurePolished()
        assert rotulo.sizeHint().width() >= rotulo.fontMetrics().horizontalAdvance(texto), texto


# =============================================================================
# Geometria contra a interface antiga (janela 1280x850; capturas/e5.1/ctk_*.txt)
# =============================================================================

@pytest.fixture
def com_folha(qt_interface):
    anterior = qt_interface.styleSheet()
    estilo.carregar_fontes()
    qt_interface.setStyleSheet(estilo.folha_de_estilo())
    yield
    qt_interface.setStyleSheet(anterior)


def _geo(widget, origem):
    p = widget.mapTo(origem, widget.rect().topLeft())
    return p.x(), p.y(), widget.width(), widget.height()


def _exposta(qtbot, janela):
    qtbot.waitExposed(janela)
    qtbot.wait(20)
    return janela


def test_medidas_da_home(com_folha, qtbot, rede, mensagens):
    # interface antiga: a Home é um CTkScrollableFrame no grid(padx=20, pady=20), o conteúdo
    # 6 px para dentro (o canto): (26, 26) na origem da tela Qt (x 277 da janela).
    # Título (46, 46) h 38; subtítulo (46, 89) h 28; texto (46, 147) h 28; barra
    # y 185 h 40 a partir de x 46, 10 px entre os botões; a engrenagem à
    # direita do título (2026-10-22: tema, letra e a caixa saíram da Home);
    # cards (52, 247) e (502, 247), 438 de largura.
    tela = home_mod.HomeView(controller=Controller())
    qtbot.addWidget(tela)
    tela.resize(1280 - estilo.LARGURA_BARRA_LATERAL, 850)
    tela.show()
    _exposta(qtbot, tela)
    corpo = tela.widget()
    assert _geo(tela.label_titulo, corpo)[:2] == (46, 46)
    assert _geo(tela.label_titulo, corpo)[3] == 38
    assert _geo(tela.label_subtitulo, corpo)[1::2] == (89, 28)
    assert _geo(tela.label_texto, corpo)[1::2] == (147, 28)
    botoes = list(tela.botoes_barra.values())
    assert _geo(botoes[0], corpo)[:2] == (46, 185)
    for anterior, botao in zip(botoes, botoes[1:]):
        assert _geo(botao, corpo)[0] == _geo(anterior, corpo)[0] + anterior.width() + 10
        assert _geo(botao, corpo)[1::2] == (185, 40)
    engrenagem = _geo(tela.btn_configuracao, corpo)
    assert engrenagem[0] + engrenagem[2] == corpo.width() - 57
    assert 46 <= engrenagem[1] and engrenagem[1] + engrenagem[3] <= 46 + 38
    cards = list(tela.cards.values())
    assert _geo(cards[0], corpo)[:3] == (52, 247, 438)
    assert _geo(cards[1], corpo)[:3] == (502, 247, 438)
    assert tela.horizontalScrollBar().maximum() == 0
    assert tela.verticalScrollBar().maximum() == 0, "os 12 cards cabem sem rolar (decisão de 2026-10-07)"


def test_medidas_do_painel_de_chaves(com_folha, qtbot, rede, mensagens):
    # 2026-10-20: medida do sistema visual (botão/campo 32, título 22, borda 1); a CTk saiu em 2026-10-15.
    tela = home_mod.HomeView(controller=Controller())
    qtbot.addWidget(tela)
    j = _exposta(qtbot, tela.abrir_janela_chaves_api())
    assert _geo(tela.frame_chaves_api, j) == (26, 26, 697, 348)
    assert _geo(tela.lbl_titulo_chaves_api, j)[:2] == (36, 36)
    for i, chave in enumerate(tela.entries):
        y = 76 + 36 * i
        assert _geo(tela.rotulos_chaves_api[chave], j) == (36, y, 140, 32), chave
        assert _geo(tela.entries[chave], j) == (181, y, 527, 32), chave
    x, y, w, h = _geo(tela.btn_salvar_chaves, j)
    assert (y, w, h) == (336, 140, 28) and abs(x - 304) <= 1
    assert _geo(j.botao_fechar, j) == (320, 480, 120, 28)


def test_medidas_do_painel_de_modelos(com_folha, qtbot, rede, mensagens):
    # 2026-10-20: medida do sistema visual (botão/campo 32, título 22, borda 1); a CTk saiu em 2026-10-15.
    selecao.definir_global("openrouter", "x-ai/grok-4.5", config_path=sigft_config.CONFIG_FILE)
    tela = home_mod.HomeView(controller=Controller())
    qtbot.addWidget(tela)
    j = _exposta(qtbot, tela.abrir_janela_modelos_ia())
    assert _geo(tela.frame_modelos_ia, j)[:3] == (26, 26, 837)
    assert _geo(tela.lbl_titulo_modelos_ia, j)[:2] == (36, 36)
    assert _geo(tela.lbl_descricao_modelos_ia, j)[:2] == (36, 74)
    assert _geo(tela.lbl_descricao_modelos_ia, j)[3] == 30  # duas linhas de 15, como o Tk
    assert _geo(tela.opt_provider_ia, j) == (261, 114, 300, 32)
    assert _geo(tela.btn_atualizar_catalogo_ia, j)[:2] == (571, 116)
    assert _geo(tela.lbl_catalogo_ia, j)[1::2] == (151, 28)
    assert _geo(tela.entry_filtro_modelo_ia, j) == (261, 184, 300, 32)
    assert _geo(tela.opt_modelo_ia_global, j) == (261, 221, 420, 32)
    assert _geo(tela.caixa_modo_avancado_ia, j)[:2] == (36, 263)
    assert _geo(tela.caixa_modo_avancado_ia, j)[3] == 24
    x, y, w, h = _geo(tela.entry_modelo_ia_livre, j)
    assert (y, w, h) == (302, 300, 32)
    assert _geo(tela.btn_limpar_modelo_ia, j) == (x + 305, 304, 70, 28)
    assert _geo(tela.lbl_resumo_modelo_ia, j)[:2] == (36, 347)
    assert _geo(tela.btn_aplicar_recomendados_ia, j)[:2] == (36, 385)
    ap = _geo(tela.btn_aplicar_recomendados_ia, j)
    assert _geo(tela.btn_salvar_selecao_ia, j)[:2] == (ap[0] + ap[2] + 10, 385)
    assert _geo(tela.frame_modelos_ia, j)[3] == 402


def test_medidas_do_painel_de_modelos_no_modo_avancado(com_folha, qtbot, rede, mensagens):
    selecao.definir_global("openrouter", "x-ai/grok-4.5", config_path=sigft_config.CONFIG_FILE)
    selecao.definir_por_tarefa("categorizar_pdm", "openrouter", "x-ai/grok-4.5",
                               config_path=sigft_config.CONFIG_FILE)
    tela = home_mod.HomeView(controller=Controller())
    qtbot.addWidget(tela)
    j = _exposta(qtbot, tela.abrir_janela_modelos_ia())
    for i, tarefa in enumerate(sigft_config.TAREFAS_DO_PAINEL):
        y = 294 + 36 * i
        assert _geo(tela.rotulos_modelo_ia_por_tarefa[tarefa], j)[:3] == (36, y, 220), tarefa
        assert _geo(tela.menus_modelo_ia_por_tarefa[tarefa], j) == (261, y, 420, 32), tarefa
    # 7 tarefas desde 2026-10-16 (entraram a passada 1 do Cria Fichas e a
    # tradução de PDM): duas linhas de 36 px (32 desde 2026-10-20 + 4) a mais que as 5 da tela antiga.
    assert _geo(tela.entry_modelo_ia_livre, j)[1] == 492 + 2 * 36
    resumo = _geo(tela.lbl_resumo_modelo_ia, j)
    assert resumo[:2] == (36, 537 + 2 * 36)
    assert _geo(tela.btn_aplicar_recomendados_ia, j)[1] == resumo[1] + resumo[3] + 10


# O relatório e o mural das capturas (`scratchpad/e51/dados_e51.py`): 11 linhas de
# gastos; duas faixas com cartões de alturas diferentes.
RELATORIO_CAPTURA = {
    "total": {"chamadas": 42, "falhas": 1, "custo_usd": 0.3127, "tokens_in": 120000,
              "tokens_out": 30000},
    "por_dia": {"2026-10-01": {}, "2026-10-08": {}},
    "por_modulo": {
        "cria_fichas": {"chamadas": 30, "falhas": 1, "tokens_in": 90000, "tokens_out": 20000,
                        "custo_usd": 0.2},
        "analyzer": {"chamadas": 12, "falhas": 0, "tokens_in": 30000, "tokens_out": 10000,
                     "custo_usd": 0.1127},
    },
    "por_modelo": {
        "openrouter/x-ai/grok-4.5": {"chamadas": 30, "falhas": 1, "tokens_in": 90000,
                                     "tokens_out": 20000, "custo_usd": 0.2},
        "gemini/gemini-3-flash-preview": {"chamadas": 12, "falhas": 0, "tokens_in": 30000,
                                          "tokens_out": 10000, "custo_usd": 0.1127},
    },
}


def _gavetas_da_captura():
    g = {faixa: [] for faixa in at.FAIXAS}
    g[at.ATRASADA] = [
        _item("Revisar fichas do lote UG07 com o fornecedor", -4, "término 04/10/26",
              _grupo="Fichas UG07", com_quem="Luan", status="Em andamento", criticidade=5),
        _item("Enviar relatório de pendências do Analyzer", -1, "término 07/10/26",
              com_quem="Rafael", criticidade=3),
    ]
    g[at.TRAVADA] = [_item("Aguardando datasheet do fabricante", 3, "término 11/10/26",
                           _grupo="AutoSpec", com_quem="Fornecedor", status="Travada", criticidade=4)]
    return g


def test_medidas_do_painel_de_gastos(com_folha, qtbot, rede, mensagens):
    # interface antiga: título (36, 36); texto (36, 74) com 11 linhas de 15 px (165); botões
    # (36, 249) e (186, 249), 140x28; quadro (26, 26, 797, 266).
    rede.relatorio = RELATORIO_CAPTURA
    tela = home_mod.HomeView(controller=Controller())
    qtbot.addWidget(tela)
    j = _exposta(qtbot, tela.abrir_janela_gastos_ia())
    assert _geo(tela.frame_gastos_ia, j) == (26, 26, 797, 266)
    assert _geo(tela.lbl_titulo_gastos_ia, j)[:2] == (36, 36)
    assert _geo(tela.lbl_gastos_ia, j) == (36, 74, 777, 165)
    assert _geo(tela.btn_atualizar_gastos_ia, j) == (36, 249, 140, 28)
    assert _geo(tela.btn_pasta_logs_ia, j) == (186, 249, 140, 28)
    assert _geo(j.botao_fechar, j) == (370, 560, 120, 28)


def _por_texto(widget, texto):
    [achado] = [r for r in widget.findChildren(QLabel) if _texto(r) == texto]
    return achado


def _por_nome(widget, nome):
    from PySide6.QtWidgets import QWidget

    return widget.findChildren(QWidget, nome)


def test_medidas_do_mural(com_folha, qtbot, rede, mensagens, monkeypatch):
    # interface antiga (janela 820x640): cabeçalho (30, 20); faixa (30, 76) com o contador de
    # 48 px e os textos em x 88; régua (30, 138, 749, 2); cartão 1 (30, 149, 749,
    # 132) com a barra de 6 e o corpo em x 44; cartão 2 em y 287 com 102; a
    # segunda faixa em y 408.
    monkeypatch.setattr(home_mod.HomeView, "_ler_mural", lambda self: (_gavetas_da_captura(), None))
    tela = home_mod.HomeView(controller=Controller())
    qtbot.addWidget(tela)
    j = _exposta(qtbot, tela.abrir_mural_atividades())
    hoje = _por_texto(j, date.today().strftime("%d/%m/%Y"))
    assert _geo(hoje, j)[:2] == (30, 20) and _geo(hoje, j)[3] == 28
    contagem = _por_texto(j, "3 atividade(s) pedindo atenção")
    assert _geo(contagem, j)[0] == _geo(hoje, j)[0] + hoje.width() + 12
    x, y, w, _h = _geo(_por_texto(j, "2"), j)
    assert (x, w) == (30, 48) and abs(y - 86) <= 1
    assert _geo(_por_texto(j, "ATRASADO"), j)[:2] == (88, 76)
    assert _geo(_por_texto(j, "a previsão de término já passou"), j)[:2] == (88, 104)
    assert _geo(_por_nome(j, "regua_faixa")[0], j) == (30, 138, 749, 2)
    linhas = _por_nome(j, "linha_cartao")
    assert _geo(linhas[0], j) == (30, 149, 749, 132)
    assert _geo(linhas[1], j)[1::2] == (287, 102)
    assert _geo(_por_nome(j, "barra_criticidade")[0], j) == (30, 149, 6, 132)
    assert _geo(_por_nome(j, "corpo_cartao")[0], j) == (44, 149, 735, 132)
    assert _geo(_por_texto(j, "Fichas UG07"), j)[:2] == (54, 157)
    assert _geo(_por_texto(j, "Revisar fichas do lote UG07 com o fornecedor"), j)[:2] == (54, 201)
    prazo = _geo(_por_texto(j, at.frase_do_prazo(at.ATRASADA, -4)), j)
    assert (prazo[0] + prazo[2], prazo[1]) == (769, 187)
    termino = _geo(_por_texto(j, "término 04/10/26"), j)
    assert (termino[0] + termino[2], termino[1]) == (769, 215)
    assert _geo(_por_texto(j, "com Luan   ·   Em andamento   ·   criticidade 5"), j)[:2] == (54, 245)
    assert _geo(_por_texto(j, "TRAVADA"), j)[:2] == (88, 408)
