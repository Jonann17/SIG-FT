r"""Invariantes da seção de conferência da tela do AutoSpec (2026-08-17).

[2026-10-15] A tela é a Qt (`sigft/app_qt/views/autospec.py`): a interface
antiga saiu do SIG-FT, e cada invariante abaixo passou a ser provada na porta
Qt. O comportamento rodando está em `tests/test_qt_tela_autospec.py`; aqui fica
a prova ESTRUTURAL, que pega a fiação errada mesmo quando ninguém roda o caso.

**Por que testar a tela por AST.** Nasceu assim porque a tela não podia ser
importada no teste (abria janela real). O motivo que continua valendo: a
fiação de salvar/importar tem dois modos de falha que quebram o recurso **em
silêncio**:

1. **Salvar antes de mostrar.** `_conferencia_salvar` lê `self.marcados_conf`.
   Se o fim do lote salvar antes de `_conferencia_mostrar` recriar a grade, o
   `.txt` sai com as marcações do lote ANTERIOR — arquivo plausível e errado,
   que é a pior categoria de bug deste módulo.
2. **Esconder a seção.** O botão IMPORTAR precisa existir na tela de quem
   acabou de reabrir o aplicativo e ainda não processou nada. Esconder o
   quadro (`hide`, `setVisible(False)`...) devolveria o recurso ao problema
   que ele veio resolver.

Nenhum destes é sobre estética; são sobre o dado do usuário. Por isso viram
teste, mesmo que estrutural.
"""
import ast
import pathlib

import pytest


# [CP 7.3] A tela saiu do `frontend.py` para o seu proprio arquivo; [2026-10-15]
# a tela e a da interface Qt.
FRONTEND = pathlib.Path(__file__).resolve().parents[1] / "sigft" / "app_qt" / "views" / "autospec.py"


@pytest.fixture(scope="module")
def classe_autospec():
    arvore = ast.parse(FRONTEND.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.ClassDef) and no.name == "ModuloAutoSpec":
            return no
    pytest.fail("class ModuloAutoSpec sumiu de sigft/app_qt/views/autospec.py")


def _metodo(classe, nome):
    for no in classe.body:
        if isinstance(no, ast.FunctionDef) and no.name == nome:
            return no
    pytest.fail(f"metodo {nome} nao existe em ModuloAutoSpec")


def _chamadas_de_self(no):
    """Nomes dos métodos `self.X(...)` chamados dentro do nó, **na ordem do
    código-fonte**.

    O `sorted` por `(lineno, col_offset)` não é enfeite: `ast.walk` percorre
    em largura, então a ordem que ele devolve não é a ordem em que as coisas
    acontecem. A primeira versão deste helper não ordenava, e o teste de
    ordem abaixo passava mesmo com as duas chamadas trocadas — provava nada.
    """
    chamadas = [(c.lineno, c.col_offset, c.func.attr) for c in ast.walk(no)
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                and isinstance(c.func.value, ast.Name) and c.func.value.id == "self"]
    return [nome for _, _, nome in sorted(chamadas)]


def test_os_seis_metodos_da_secao_existem(classe_autospec):
    esperados = {"_build_conferencia", "_conferencia_mostrar", "_conferencia_salvar",
                 "_conferencia_importar", "_conferencia_processar", "_conferencia_worker"}
    presentes = {no.name for no in classe_autospec.body if isinstance(no, ast.FunctionDef)}
    assert esperados <= presentes


def test_o_worker_MOSTRA_antes_de_SALVAR(classe_autospec):
    """O `.txt` automático tem de refletir a lista nova. `_conferencia_mostrar`
    é quem zera `marcados_conf`; salvar antes grava as marcas do lote
    anterior.

    Na Qt o worker não toca widget: ele entrega o fim do lote à thread da
    interface (`_fila_processada`), e é lá que a ordem vale."""
    worker = ast.unparse(_metodo(classe_autospec, "_worker"))
    assert "interface.na_interface(self._fila_processada" in worker
    assert "_conferencia_salvar" not in worker, "o worker salvaria fora da ordem"
    chamadas = _chamadas_de_self(_metodo(classe_autospec, "_fila_processada"))
    assert "_conferencia_mostrar" in chamadas
    assert "_conferencia_salvar" in chamadas
    assert chamadas.index("_conferencia_mostrar") < chamadas.index("_conferencia_salvar")


def test_a_secao_nunca_se_esconde(classe_autospec):
    """Esconder o quadro em qualquer lugar tira o botão IMPORTAR da tela de
    quem reabriu o aplicativo — exatamente quem mais precisa dele. (Na tela
    antiga o nome era `pack_forget`; na Qt, `hide`/`setVisible`/`setHidden`.)"""
    fonte = ast.dump(classe_autospec)
    for esconder in ("pack_forget", "'hide'", "'setVisible'", "'setHidden'"):
        assert esconder not in fonte, esconder


def test_o_build_cria_os_botoes_ANTES_de_montar_o_estado_vazio(classe_autospec):
    """`_conferencia_mostrar(None)` desabilita `btn_conf` e `btn_conf_salvar`.
    Chamado antes de eles existirem, é `AttributeError` na abertura da tela —
    e a tela não é importável para um teste pegar isso rodando."""
    build = _metodo(classe_autospec, "_build_conferencia")
    atribuidos = []
    for no in ast.walk(build):
        if isinstance(no, ast.Attribute) and isinstance(no.ctx, ast.Store):
            atribuidos.append((no.lineno, no.attr))
    chamada_mostrar = [c.lineno for c in ast.walk(build)
                       if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                       and c.func.attr == "_conferencia_mostrar"]
    assert chamada_mostrar, "_build_conferencia nao monta o estado vazio"
    for nome in ("btn_conf", "btn_conf_salvar", "btn_conf_importar", "lista_conf"):
        linhas = [l for l, attr in atribuidos if attr == nome]
        assert linhas, f"self.{nome} nao e criado no _build_conferencia"
        assert min(linhas) < chamada_mostrar[0], f"self.{nome} criado depois do mostrar"


def test_processar_exige_o_STATUS_PMIB(classe_autospec):
    """Vale para a conferência importada: a lista de links volta do `.txt`,
    mas a 2ª passada lê a planilha de status ficha a ficha."""
    fonte = ast.dump(_metodo(classe_autospec, "_conferencia_processar"))
    assert "status_pmib_path" in fonte


def test_mostrar_aceita_a_marcacao_vinda_do_txt(classe_autospec):
    """Sem o parâmetro, importar traria os links de volta com tudo
    desmarcado — a metade conferida ontem se perderia do mesmo jeito."""
    mostrar = _metodo(classe_autospec, "_conferencia_mostrar")
    assert [a.arg for a in mostrar.args.args] == ["self", "conferencia", "marcados"]


def test_salvar_distingue_o_automatico_do_clique(classe_autospec):
    """O automático não pode abrir caixa de diálogo: ele roda no fim do lote,
    sem ninguém para dar OK, e travaria o processamento esperando um."""
    salvar = _metodo(classe_autospec, "_conferencia_salvar")
    assert "automatico" in [a.arg for a in salvar.args.args]
    caixas = [no for no in ast.walk(salvar)
              if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
              and isinstance(no.func.value, ast.Name)
              and no.func.value.id in ("messagebox", "QMessageBox")]
    assert caixas, "o clique tem de avisar (a caixa sumiu?)"
    for no in caixas:
        pais = [p for p in ast.walk(salvar)
                if isinstance(p, ast.If) and "automatico" in ast.unparse(p.test)
                and no in list(ast.walk(p))]
        assert pais, "caixa fora de um if do automatico — abriria no automatico"


def test_a_tela_usa_o_servico_e_nao_reimplementa_o_formato():
    """Se a tela montasse o `.txt` por conta própria, o formato teria duas
    implementações — e uma delas ficaria para trás. Princípio nº 1."""
    fonte = FRONTEND.read_text(encoding="utf-8")
    assert "conferencia_txt.salvar_txt" in fonte
    assert "conferencia_txt.carregar_txt" in fonte
    assert "conferencia_txt.fichas_ausentes" in fonte
