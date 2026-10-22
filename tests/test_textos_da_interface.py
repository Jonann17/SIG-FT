"""Os catálogos de tradução e a guarda do texto de interface (2026-10-22).

A chave de cada tradução é o texto em português dentro de `t("...")` ou de
`marcar("...")` (`sigft/app/idioma.py`); `tools/textos_da_interface.py` as lê do
código. Este arquivo trava três coisas:

1. a ferramenta acha o que deve (testes com código de exemplo);
2. os catálogos `es` e `en` têm tradução para toda chave, nenhuma sobra, os
   `{valores}` são os mesmos e não há travessão;
3. nos arquivos já convertidos (`CONVERTIDOS`, que cresce a cada tarefa do plano
   `docs/superpowers/plans/2026-10-22-configuracao-e-idioma.md`), nenhum literal
   que parece texto de interface fica fora de `t()`/`marcar()`, exceto o que é
   DADO (`NAO_E_INTERFACE`, com o motivo) ou não se traduz (`idioma.NAO_SE_TRADUZ`).
"""
import importlib.util
import json
import pathlib
import string

import pytest

from sigft.app import idioma

RAIZ = pathlib.Path(__file__).resolve().parent.parent
FERRAMENTA = RAIZ / "tools" / "textos_da_interface.py"


def _carregar():
    spec = importlib.util.spec_from_file_location("textos_da_interface", FERRAMENTA)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


ferramenta = _carregar()


# --- 1. a ferramenta ----------------------------------------------------------------

def test_acha_as_chaves_de_t_e_de_marcar():
    fonte = 't("A {x}", x=1)\nmarcar("B")\nidioma.t("C")\nt(VARIAVEL)\n'
    chaves, fstrings = ferramenta.chaves_do_codigo(fonte, "x.py")
    assert [u.texto for u in chaves] == ["A {x}", "B", "C"]
    assert fstrings == []


def test_acusa_f_string_dentro_de_t():
    _chaves, fstrings = ferramenta.chaves_do_codigo('t(f"Ficha {n}")\nmarcar(f"x{y}")\n', "x.py")
    assert [u.linha for u in fstrings] == [1, 2]


def test_acusa_t_com_texto_montado():
    """Texto montado (`+`, `%`, `.format`, f-string) vira OUTRA chave a cada valor:
    a tradução nunca casa. `t(CONSTANTE)` e `t(self.X)` continuam valendo: são o
    jeito de mostrar uma constante marcada."""
    fonte = ('t("A " + x)\nt("A " + "B")\nt(texto=f"F {n}")\nt("Oi %s" % n)\n'
             't("Oi {}".format(n))\nt(CONSTANTE)\nt(self.TITULO)\nmarcar(VARIAVEL)\n')
    chaves, ruins = ferramenta.chaves_do_codigo(fonte, "x.py")
    assert chaves == []
    assert [u.linha for u in ruins] == [1, 2, 3, 4, 5, 8]


def test_metodo_de_outro_objeto_com_o_mesmo_nome_nao_conta():
    """`self.barra.marcar(filtro)` (o console) não é o `marcar` do idioma."""
    chaves, ruins = ferramenta.chaves_do_codigo('self.barra.marcar(filtro)\nobj.t("X")\n', "x.py")
    assert chaves == [] and ruins == []


def test_t_com_texto_por_palavra_chave_e_chave():
    chaves, ruins = ferramenta.chaves_do_codigo('t(texto="Salvar")\nt(texto="Ficha {n}", n=1)\n', "x.py")
    assert [u.texto for u in chaves] == ["Salvar", "Ficha {n}"]
    assert ruins == []


@pytest.mark.parametrize("fonte, achados", [
    ('X = "Texto solto"', ["Texto solto"]),
    ('QLabel(f"Arquivo: {n}")', ["f'Arquivo: {n}'"]),
    ('b = botao("Salvar")', ["Salvar"]),
    ('x = "Atenção"', ["Atenção"]),
    ('Y = marcar("Traduzido depois")', []),
    ('QLabel(t("Traduzido"))', []),
    ('self.log("Vai para o console")', []),
    ('print("Saída de diagnóstico")', []),
    ('_log.warning("nao consegui ler %s", x)', []),
    ('b.setObjectName("Nome Qualquer")', []),
    ('d["Chave Solta"]', []),
    ('raise ValueError("Erro para o programador")', []),
    ('Z = "primario"', []),
    ('W = ("Roboto", 12)', []),
    ('K = "GEMINI"', []),
    ('C = "CriaFichas"', []),
    ('f = "font-size: 13px; color: red;"', []),
    ('g = "QPushButton { min-height: 3px; }"', []),
    ('m = "começou e parou; precisa de alguém"', ["começou e parou; precisa de alguém"]),
    ('e = "Não abriu.\\n\\n{erro}"', ["Não abriu.\n\n{erro}"]),
    ('def f():\n    """Docstring Não Conta."""\n', []),
    ('rotulo(texto, papel="Legenda Grande")', []),
    # Frase toda em minúsculas é texto, não identificador (revisão da Task 2).
    ('v = "nenhum arquivo selecionado"', ["nenhum arquivo selecionado"]),
    # Padrão de arquivo do diálogo não é texto (o nome do filtro, sim).
    ('f = "*.xlsx *.xlsm"', []),
    # Chave de dicionário e termo de comparação são dado, não interface.
    ('d = {"Chave Solta": 1}', []),
    ('if x == "Valor Do Portal": pass', []),
    ('if "Texto Qualquer" in x: pass', []),
    # O valor do dicionário continua sendo visto.
    ('d = {"k": "Texto do valor"}', ["Texto do valor"]),
    # A marca por linha isenta a linha inteira (e só ela).
    ('A = "Dado da planilha"  # nao-e-interface\nB = "Texto de tela"', ["Texto de tela"]),
    ('A = ("Dado em duas "  # nao-e-interface\n     "linhas")', []),
])
def test_a_varredura_pega_o_que_deve(fonte, achados):
    assert [u.texto for u in ferramenta.literais_soltos(fonte, "x.py")] == achados


def test_a_linha_de_comando_lista_os_literais(tmp_path, capsys):
    arquivo = tmp_path / "tela.py"
    arquivo.write_text('X = "Texto solto"\nY = t("ok")\n', encoding="utf-8")
    assert ferramenta.main(["--literais", str(arquivo)]) == 1
    assert "1: 'Texto solto'" in capsys.readouterr().out


def test_arrumar_ordena_e_nao_escapa_acento(tmp_path):
    pasta = tmp_path / "sigft" / "app" / "idiomas"
    pasta.mkdir(parents=True)
    (pasta / "es.json").write_text('{"b": "B", "a": "Ação"}', encoding="utf-8")
    (pasta / "en.json").write_text("{}", encoding="utf-8")
    ferramenta.arrumar(tmp_path)
    assert (pasta / "es.json").read_text(encoding="utf-8") == '{\n  "a": "Ação",\n  "b": "B"\n}\n'
    assert (pasta / "en.json").read_text(encoding="utf-8") == "{}\n"


# --- 2. os catálogos de verdade -----------------------------------------------------

@pytest.mark.parametrize("codigo", ferramenta.IDIOMAS_COM_CATALOGO)
def test_toda_chave_tem_traducao(codigo):
    assert ferramenta.faltando(codigo) == []


@pytest.mark.parametrize("codigo", ferramenta.IDIOMAS_COM_CATALOGO)
def test_nenhuma_traducao_sobra(codigo):
    assert ferramenta.sobrando(codigo) == []


def test_nenhum_f_string_dentro_de_t():
    _chaves, fstrings = ferramenta.chaves()
    assert [f"{u.arquivo}:{u.linha}" for u in fstrings] == []


# Chave literal no texto (não um valor) se escreve `{{` e `}}`, no código E no
# catálogo: `t()` chama `str.format` quando há valores, e `{x}` solto seria lido
# como um valor que falta.
def _campos(texto):
    return sorted(nome for _lit, nome, _fmt, _conv in string.Formatter().parse(texto) if nome)


@pytest.mark.parametrize("codigo", ferramenta.IDIOMAS_COM_CATALOGO)
def test_os_valores_sao_os_mesmos_na_traducao(codigo):
    diferentes = [chave for chave, valor in ferramenta.catalogo(codigo).items()
                  if _campos(chave) != _campos(valor)]
    assert diferentes == []


@pytest.mark.parametrize("codigo", ferramenta.IDIOMAS_COM_CATALOGO)
def test_traducao_sem_travessao(codigo):
    assert [v for v in ferramenta.catalogo(codigo).values() if "—" in v or "–" in v] == []


@pytest.mark.parametrize("codigo", ferramenta.IDIOMAS_COM_CATALOGO)
def test_catalogo_na_forma_do_arrumar(codigo):
    caminho = RAIZ / "sigft" / "app" / "idiomas" / f"{codigo}.json"
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    esperado = json.dumps(dict(sorted(dados.items())), ensure_ascii=False, indent=2) + "\n"
    assert caminho.read_text(encoding="utf-8") == esperado, "rode tools/textos_da_interface.py --arrumar"


# --- 3. a guarda ----------------------------------------------------------------------

# Os arquivos já convertidos. Cada tarefa do plano acrescenta os seus.
CONVERTIDOS: tuple[str, ...] = ()

# Literais que a varredura acusa e que ficam em português de propósito, por
# arquivo. Copie o texto como a ferramenta o imprime (sem as aspas do repr). Cada
# bloco diz por quê: dado de planilha, valor do portal, relatório do --smoke...
NAO_E_INTERFACE: dict[str, set[str]] = {}


@pytest.mark.parametrize("arquivo", CONVERTIDOS)
def test_texto_de_interface_passa_por_t(arquivo):
    fonte = (RAIZ / arquivo).read_text(encoding="utf-8")
    permitidos = NAO_E_INTERFACE.get(arquivo, set()) | idioma.NAO_SE_TRADUZ
    soltos = [f"{u.linha}: {u.texto!r}" for u in ferramenta.literais_soltos(fonte, arquivo)
              if u.texto not in permitidos]
    assert soltos == []


def test_o_que_fica_em_portugues_ainda_existe():
    """Uma entrada de `NAO_E_INTERFACE` que o código não tem mais é lixo: some."""
    for arquivo, textos in NAO_E_INTERFACE.items():
        assert arquivo in CONVERTIDOS, arquivo
        fonte = (RAIZ / arquivo).read_text(encoding="utf-8")
        achados = {u.texto for u in ferramenta.literais_soltos(fonte, arquivo)}
        assert textos <= achados, (arquivo, textos - achados)
