r"""A tela de correção de PDM (E5) — e o guard de que ela é ALCANÇÁVEL.

As telas não podem ser importadas neste ambiente (abrem janela de verdade),
então tudo aqui é lido por AST. É a mesma técnica de
`tests/test_frontend_nomes_indefinidos.py`.

⚠️ O TESTE MAIS ÚTIL DESTE ARQUIVO NÃO É SOBRE A TELA NOVA. É o guard de
fiação: **toda tela registrada em `main.py` tem de ter botão na barra lateral
e card na home.** Uma tela que existe, compila, passa nos testes e não aparece
em lugar nenhum é um defeito que nenhuma das três partes da verificação do
`CLAUDE.md` pega -- nem o `compileall`, nem o `pyflakes`, nem abrir o app (ela
simplesmente não está lá, e quem abre não sabe que deveria estar).

O resto confere a separação que o princípio 2 exige: a tela não pode conter
regra de negócio.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
VIEWS = RAIZ / "sigft" / "app" / "views"
TELA = VIEWS / "correcao_pdm.py"


def _arvore(caminho):
    return ast.parse(caminho.read_text(encoding="utf-8"))


def _caminho_pontilhado(no):
    """`self.automacao.solicitar_parada` a partir do `ast.Attribute`.

    Atravessa os níveis todos: a primeira versão parava no primeiro
    `Attribute` e devolvia só `automacao.solicitar_parada`, o que fazia um
    teste reprovar por defeito DELE, não do código.
    """
    partes = []
    while isinstance(no, ast.Attribute):
        partes.append(no.attr)
        no = no.value
    if isinstance(no, ast.Name):
        partes.append(no.id)
        return ".".join(reversed(partes))
    return ""


def _fontes_de_chamada(arvore):
    """`{"planilha_svc.previa", "self.automacao.solicitar_parada", ...}`."""
    nomes = set()
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        caminho = _caminho_pontilhado(no.func)
        if caminho:
            nomes.add(caminho)
    return nomes


def _metodo(arvore, nome_da_classe, nome_do_metodo):
    for no in ast.walk(arvore):
        if isinstance(no, ast.ClassDef) and no.name == nome_da_classe:
            for filho in no.body:
                if isinstance(filho, ast.FunctionDef) and filho.name == nome_do_metodo:
                    return filho
    raise AssertionError(f"{nome_da_classe}.{nome_do_metodo} nao existe")


# =============================================================================
# A. A fiação -- o guard que vale para TODAS as telas
# =============================================================================
def _frames_de_main():
    """`{"Home", "CriaFichas", ...}` -- as chaves de `self.frames[...]`."""
    arvore = _arvore(RAIZ / "sigft" / "app" / "main.py")
    chaves = set()
    for no in ast.walk(arvore):
        if (isinstance(no, ast.Assign) and len(no.targets) == 1
                and isinstance(no.targets[0], ast.Subscript)):
            alvo = no.targets[0]
            if (isinstance(alvo.value, ast.Attribute)
                    and alvo.value.attr == "frames"
                    and isinstance(alvo.slice, ast.Constant)):
                chaves.add(alvo.slice.value)
    return chaves


def _frames_da_barra_lateral():
    """O 3º argumento de cada `_criar_botao_menu(...)`."""
    arvore = _arvore(RAIZ / "sigft" / "app" / "main.py")
    nomes = set()
    for no in ast.walk(arvore):
        if (isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
                and no.func.attr == "_criar_botao_menu" and len(no.args) >= 3
                and isinstance(no.args[2], ast.Constant)):
            nomes.add(no.args[2].value)
    return nomes


def _frames_dos_cards():
    """O 1º item de cada tupla de `home.MODULOS`."""
    arvore = _arvore(VIEWS / "home.py")
    for no in ast.walk(arvore):
        if (isinstance(no, ast.Assign) and len(no.targets) == 1
                and isinstance(no.targets[0], ast.Name)
                and no.targets[0].id == "MODULOS"):
            return {x.elts[0].value for x in no.value.elts
                    if isinstance(x, ast.Tuple) and x.elts}
    raise AssertionError("home.MODULOS nao encontrado")


def test_toda_tela_registrada_tem_botao_na_barra_lateral():
    """Uma tela sem botão existe, compila, passa nos testes -- e o usuário não
    tem como chegar nela. Nenhuma das três partes da verificação do CLAUDE.md
    pega isso: o app abre normalmente, só que sem a tela."""
    faltando = _frames_de_main() - _frames_da_barra_lateral() - {"Home"}

    assert not faltando, f"sem botao na barra lateral: {sorted(faltando)}"


def test_toda_tela_registrada_tem_card_na_home():
    faltando = _frames_de_main() - _frames_dos_cards() - {"Home"}

    assert not faltando, f"sem card na home: {sorted(faltando)}"


def test_nenhum_botao_ou_card_aponta_para_tela_que_nao_existe():
    """O lado oposto, e o mais barulhento dos dois: clicar num card que aponta
    para um frame inexistente levanta `KeyError` na cara do usuário."""
    registrados = _frames_de_main()

    assert not (_frames_da_barra_lateral() - registrados)
    assert not (_frames_dos_cards() - registrados)


def test_a_correcao_de_pdm_esta_nos_tres_lugares():
    assert "CorrecaoPDM" in _frames_de_main()
    assert "CorrecaoPDM" in _frames_da_barra_lateral()
    assert "CorrecaoPDM" in _frames_dos_cards()


def _secoes_da_barra_lateral():
    """`{"Dados Técnicos & Upload": ["UploadConditions", ...], ...}`.

    A seção de um botão é dada pela `row`, e NÃO pela ordem das linhas de
    código -- que é exatamente onde o erro de 2026-09-23 se escondeu: o botão
    da Correção de PDM foi escrito no bloco dos uploads, com `row=15`, e
    nasceu lá embaixo na Gestão.
    """
    arvore = _arvore(RAIZ / "sigft" / "app" / "main.py")
    rotulos, botoes = [], []
    for no in ast.walk(arvore):
        if not (isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)):
            continue
        linha = next((p.value.value for p in no.keywords
                      if p.arg == "row" and isinstance(p.value, ast.Constant)), None)
        if linha is None or len(no.args) < 2:
            continue
        if no.func.attr == "_criar_label_secao":
            rotulos.append((linha, no.args[1].value))
        elif no.func.attr == "_criar_botao_menu" and len(no.args) >= 3:
            botoes.append((linha, no.args[2].value))

    rotulos.sort()
    secoes = {nome: [] for _, nome in rotulos}
    for linha, frame in sorted(botoes):
        acima = [nome for r, nome in rotulos if r < linha]
        if acima:
            secoes[acima[-1]].append(frame)
    return secoes


def test_a_correcao_de_pdm_fica_com_os_UPLOADS_e_nao_na_gestao():
    """Ela conserta o que o "Upload Specs" preenche. Estava na Gestão por causa
    de uma `row` errada."""
    secoes = _secoes_da_barra_lateral()

    assert "CorrecaoPDM" in secoes["Dados Técnicos & Upload"]


def test_a_aplicacao_LMR_e_dado_tecnico_e_nao_gestao():
    """Pedido do usuário em 2026-09-23: *"aplicação LMR é parte técnica e de
    upload, e não gestão"*. Ela cadastra e apaga TAGs no portal."""
    secoes = _secoes_da_barra_lateral()

    assert "LMR" in secoes["Dados Técnicos & Upload"]
    assert "LMR" not in secoes.get("Gestão", [])


def test_a_gestao_ficou_com_o_que_e_gestao():
    """E não vazia: uma seção sem botão nenhum é um rótulo solto na tela."""
    assert _secoes_da_barra_lateral()["Gestão"] == ["PMIBManager", "SearchPMIB"]


def test_nenhuma_secao_da_barra_lateral_fica_vazia():
    for nome, frames in _secoes_da_barra_lateral().items():
        assert frames, f"a secao {nome!r} nao tem botao nenhum"


def test_as_linhas_da_barra_lateral_sao_CONTIGUAS():
    """Um buraco na `row` vira um vão na tela, e foi o rastro do botão que
    estava fora de lugar (14, depois 15, e o 15 era o da Gestão)."""
    arvore = _arvore(RAIZ / "sigft" / "app" / "main.py")
    linhas = []
    for no in ast.walk(arvore):
        if (isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
                and no.func.attr in ("_criar_label_secao", "_criar_botao_menu")):
            for palavra in no.keywords:
                if palavra.arg == "row" and isinstance(palavra.value, ast.Constant):
                    linhas.append(palavra.value.value)

    assert sorted(linhas) == list(range(min(linhas), max(linhas) + 1))


def test_dois_botoes_da_barra_lateral_nao_dividem_a_mesma_linha():
    """`grid(row=...)` repetido faz um botão cobrir o outro, e o de baixo some
    sem erro nenhum."""
    arvore = _arvore(RAIZ / "sigft" / "app" / "main.py")
    linhas = []
    for no in ast.walk(arvore):
        if (isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
                and no.func.attr == "_criar_botao_menu"):
            for palavra in no.keywords:
                if palavra.arg == "row" and isinstance(palavra.value, ast.Constant):
                    linhas.append(palavra.value.value)

    assert len(linhas) == len(set(linhas)), f"linhas repetidas: {sorted(linhas)}"


# =============================================================================
# B. A tela não contém regra de negócio (princípio 2)
# =============================================================================
def test_a_tela_nao_importa_pandas_nem_openpyxl():
    """Ler planilha é da camada de serviço. Uma tela que lê Excel é uma tela
    que não dá para testar."""
    fonte = TELA.read_text(encoding="utf-8")

    assert "import pandas" not in fonte
    assert "import openpyxl" not in fonte


def test_a_tela_nao_importa_playwright_nem_selenium():
    """Princípio 3: só `PMIBPortal` conhece o motor."""
    fonte = TELA.read_text(encoding="utf-8")

    assert "playwright" not in fonte.lower()
    assert "selenium" not in fonte.lower()


def test_a_previa_vem_do_servico_e_nao_e_calculada_na_tela():
    assert "planilha_svc.previa" in _fontes_de_chamada(_arvore(TELA))


def test_a_acao_so_atualizar_a_revisao_usa_a_regra_do_servico():
    """Se a tela extraísse o código do PDM sozinha, passariam a existir duas
    regras de "o que é o código de um PDM"."""
    metodo = _metodo(_arvore(TELA), "ModuloCorrecaoPDM", "_acao_so_revisao")

    assert "planilha_svc.so_a_revisao" in _fontes_de_chamada(metodo)


def test_o_lote_que_vai_para_o_portal_vem_do_servico():
    metodo = _metodo(_arvore(TELA), "ModuloCorrecaoPDM", "_rodar")

    assert "planilha_svc.lote" in _fontes_de_chamada(metodo)


# =============================================================================
# C. As proteções que a tela deve ao usuário
# =============================================================================
def test_a_rodada_pede_confirmacao_antes_de_mexer_no_portal():
    """A operação apaga características no portal. Começar direto no clique
    faria um engano virar 25 fichas alteradas."""
    metodo = _metodo(_arvore(TELA), "ModuloCorrecaoPDM", "_rodar")

    assert "messagebox.askyesno" in _fontes_de_chamada(metodo)


def test_apagar_as_vazias_e_uma_ESCOLHA_e_chega_ao_servico():
    """O interruptor existe e é lido na hora de chamar o serviço. Um switch que
    a tela mostra e não repassa é pior que não ter switch."""
    fonte = TELA.read_text(encoding="utf-8")

    assert "var_apagar_vazias" in fonte
    assert "apagar_vazias=self.var_apagar_vazias.get()" in fonte


def test_a_pausa_de_conferencia_so_existe_se_o_usuario_pedir():
    """`tech_specs` pausa sempre; aqui são 25 fichas numa rodada, e pausar em
    todas devolveria o trabalho manual que o módulo veio eliminar. A política é
    da tela, e o serviço só oferece o gancho."""
    fonte = TELA.read_text(encoding="utf-8")

    assert "if self.var_conferir.get() else None" in fonte


def test_o_botao_parar_chega_na_automacao():
    metodo = _metodo(_arvore(TELA), "ModuloCorrecaoPDM", "_parar")

    assert "self.automacao.solicitar_parada" in _fontes_de_chamada(metodo)


def test_o_navegador_e_fechado_mesmo_quando_da_erro():
    """Sem o `finally`, um erro no meio do lote deixa um Chrome órfão aberto a
    cada tentativa."""
    metodo = _metodo(_arvore(TELA), "ModuloCorrecaoPDM", "_worker")
    tentativas = [n for n in ast.walk(metodo) if isinstance(n, ast.Try)]

    assert tentativas and tentativas[0].finalbody


def test_o_relatorio_pode_ser_salvo_em_arquivo():
    """No console ele rola e some, e a lista do que NÃO voltou é justamente o
    que a pessoa vai usar para preencher à mão."""
    arvore = _arvore(TELA)

    assert "file_dialogs.ask_save_file" in _fontes_de_chamada(arvore)


@pytest.mark.parametrize("metodo", ["_acao_so_revisao", "_acao_escolher_pdm",
                                    "_acao_limpar"])
def test_toda_acao_em_massa_redesenha_a_tabela(metodo):
    """Ação que muda o dado e não redesenha deixa a tela mentindo sobre o que
    vai ser enviado ao portal."""
    corpo = _metodo(_arvore(TELA), "ModuloCorrecaoPDM", metodo)

    assert "self._redesenhar" in _fontes_de_chamada(corpo)


# =============================================================================
# D. As chamadas de diálogo batem com a assinatura real
# =============================================================================
# ⚠️ ESTE GUARD NASCEU DE UM ERRO MEU, em 2026-09-23. A primeira versão desta
# tela chamava `ask_open_file("correcao_pdm_status", title="...")`: sem o
# argumento `categoria` e com `title` em vez de `titulo`. Compila, passa no
# `pyflakes`, passa em todos os testes -- e levanta `TypeError` no primeiro
# clique do usuário.
#
# Quem pegaria isso é o `--smoke` (monta a janela de verdade), e ele não roda
# em ambiente sem tkinter/customtkinter. Conferir a assinatura pega a mesma
# classe de defeito sem precisar de janela: `file_dialogs` é importável porque
# não é uma tela.
def _chamadas_de(modulo_alvo, caminho):
    """`[(funcao, n_posicionais, {nomes das keywords}), ...]`."""
    achadas = []
    for no in ast.walk(_arvore(caminho)):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        if not (isinstance(alvo, ast.Attribute) and isinstance(alvo.value, ast.Name)
                and alvo.value.id == modulo_alvo):
            continue
        if any(isinstance(a, ast.Starred) for a in no.args):
            continue   # `*args`: nao da para conferir estaticamente
        if any(p.arg is None for p in no.keywords):
            continue   # `**kwargs`: idem
        achadas.append((alvo.attr, len(no.args),
                        {p.arg for p in no.keywords}))
    return achadas


def _arquivos_da_ui():
    return sorted((RAIZ / "sigft" / "app").rglob("*.py"))


def test_toda_chamada_a_file_dialogs_bate_com_a_assinatura():
    import inspect

    from sigft.app import file_dialogs

    class _Qualquer:
        pass

    problemas = []
    for caminho in _arquivos_da_ui():
        if caminho.name == "file_dialogs.py":
            continue
        for funcao, posicionais, palavras in _chamadas_de("file_dialogs", caminho):
            alvo = getattr(file_dialogs, funcao, None)
            if alvo is None or not callable(alvo):
                problemas.append(f"{caminho.name}: file_dialogs.{funcao} nao existe")
                continue
            try:
                inspect.signature(alvo).bind(
                    *([_Qualquer()] * posicionais),
                    **{nome: _Qualquer() for nome in palavras})
            except TypeError as erro:
                problemas.append(f"{caminho.name}: file_dialogs.{funcao}(...) -> {erro}")

    assert not problemas, "\n".join(problemas)


def test_o_guard_de_assinatura_realmente_reprova_uma_chamada_errada():
    """Um guard que nunca reprova não protege nada. `title=` em vez de
    `titulo=` é exatamente o erro que ele nasceu para pegar."""
    import inspect

    from sigft.app import file_dialogs

    with pytest.raises(TypeError):
        inspect.signature(file_dialogs.ask_open_file).bind("chave", title="x")


def test_a_tela_chama_os_servicos_com_a_assinatura_certa():
    """O mesmo cuidado para os serviços: eles são importáveis (não abrem
    janela), então nada impede conferir. Um `callback_log=` que virasse
    `callback=` no serviço quebraria só no clique."""
    import inspect

    from sigft.core import pdm_catalogo
    from sigft.services import correcao_pdm as correcao_svc
    from sigft.services import correcao_pdm_planilha as planilha_svc

    class _Qualquer:
        pass

    modulos = {"planilha_svc": planilha_svc, "correcao_svc": correcao_svc,
               "pdm_catalogo": pdm_catalogo}
    problemas = []
    for apelido, modulo in modulos.items():
        for funcao, posicionais, palavras in _chamadas_de(apelido, TELA):
            alvo = getattr(modulo, funcao, None)
            if alvo is None:
                problemas.append(f"{apelido}.{funcao} nao existe")
                continue
            if isinstance(alvo, type):
                alvo = alvo.__init__
                posicionais += 1   # o `self`
            try:
                inspect.signature(alvo).bind(
                    *([_Qualquer()] * posicionais),
                    **{nome: _Qualquer() for nome in palavras})
            except TypeError as erro:
                problemas.append(f"{apelido}.{funcao}(...) -> {erro}")

    assert not problemas, "\n".join(problemas)


# =============================================================================
# E. A tela desligada -- decisão do usuário em 2026-09-23
# =============================================================================
def test_a_correcao_de_pdm_esta_na_lista_de_telas_bloqueadas():
    """Ela está inteira e verde, mas NUNCA rodou com sucesso contra o portal
    (a E6 não foi feita). Trocar o PDM APAGA as características da ficha:
    liberar uma operação destrutiva não validada é o único jeito de ela
    estragar uma ficha de verdade."""
    fonte = (RAIZ / "sigft" / "app" / "main.py").read_text(encoding="utf-8")

    assert 'TELAS_BLOQUEADAS = {"CorrecaoPDM"}' in fonte


def test_o_bloqueio_vale_no_FUNIL_e_nao_so_no_botao():
    """O card da Home também navega por `show_frame`. Desabilitar só o botão
    da barra lateral deixaria a tela acessível pelo card -- e o usuário pediu
    que ela não fosse clicável, não que ficasse escondida num lugar só."""
    metodo = _metodo(_arvore(RAIZ / "sigft" / "app" / "main.py"),
                     "SIG_FT_App", "show_frame")
    fonte = ast.unparse(metodo)

    assert "TELAS_BLOQUEADAS" in fonte
    assert "return" in fonte


def test_a_tela_bloqueada_CONTINUA_registrada_e_com_botao_e_card():
    """Desligar não é apagar. O frame segue registrado, com botão e card, para
    que os guards de fiação continuem valendo e a volta seja uma linha."""
    assert "CorrecaoPDM" in _frames_de_main()
    assert "CorrecaoPDM" in _frames_da_barra_lateral()
    assert "CorrecaoPDM" in _frames_dos_cards()


def test_o_botao_de_uma_tela_bloqueada_nasce_DESABILITADO():
    metodo = _metodo(_arvore(RAIZ / "sigft" / "app" / "main.py"),
                     "SIG_FT_App", "_criar_botao_menu")
    fonte = ast.unparse(metodo)

    assert "TELAS_BLOQUEADAS" in fonte
    assert "disabled" in fonte


def test_a_tela_bloqueada_aparece_na_barra_sem_o_em_obras():
    """Pedido do usuário em 2026-09-24: o "(em obras)" deixava o texto grande
    demais na barra lateral, e o botão cinza e desabilitado já diz que a tela
    não abre."""
    metodo = _metodo(_arvore(RAIZ / "sigft" / "app" / "main.py"),
                     "SIG_FT_App", "_criar_botao_menu")

    assert "em obras" not in ast.unparse(metodo)
