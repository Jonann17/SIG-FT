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
    # f-string cuja parte fixa tem uma palavra minúscula de 3+ letras é texto,
    # mesmo curta (revisão da Task 4: "com {pessoa}" no cartão do mural).
    ('r = f"com {pessoa}"', ["f'com {pessoa}'"]),
    ('r = f"criticidade {nivel}"', ["f'criticidade {nivel}'"]),
    # Extensão, caminho e separador não são palavra.
    ('r = f"{nome}.xlsx"', []),
    ('r = f"{a}/{b}"', []),
    ('r = f"{a} ({b})"', []),
    ('r = f"tarefa:{nome}"', []),
    ('r = f"font-size: {n}px; background: transparent;"', []),
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
CONVERTIDOS: tuple[str, ...] = (
    # Task 4: textos compartilhados I
    "sigft/app/textos_dialogos.py",
    "sigft/app/textos_dicas.py",
    "sigft/app/resumo_lote.py",
    "sigft/app_qt/widgets/__init__.py",
    "sigft/app_qt/widgets/abas.py",
    "sigft/app_qt/widgets/arrastar.py",
    "sigft/app_qt/widgets/atividade.py",
    "sigft/app_qt/widgets/blocos.py",
    "sigft/app_qt/widgets/console.py",
    "sigft/app_qt/widgets/controles.py",
    "sigft/app_qt/widgets/dialogos_selecao.py",
    "sigft/app_qt/widgets/dialogs.py",
    "sigft/app_qt/widgets/espera.py",
    "sigft/app_qt/widgets/marca.py",
    "sigft/app_qt/widgets/module_frame.py",
    "sigft/app_qt/widgets/mural.py",
    "sigft/app_qt/widgets/painel_janela.py",
    "sigft/app_qt/widgets/paleta.py",
    "sigft/app_qt/widgets/pickers.py",
    "sigft/app_qt/widgets/puxador_console.py",
    "sigft/app_qt/widgets/resumo_lote.py",
    "sigft/app_qt/widgets/revisao_portal.py",
    "sigft/app_qt/widgets/trava_robo.py",
    # Task 5: textos compartilhados II
    "sigft/app/atualizacao_textos.py",
    "sigft/app_qt/__init__.py",
    "sigft/app_qt/atualizacao.py",
    "sigft/app_qt/aviso_windows.py",
    "sigft/app_qt/catalogo.py",
    "sigft/app_qt/cursor.py",
    "sigft/app_qt/escolha_de_idioma.py",
    "sigft/app_qt/estilo.py",
    "sigft/app_qt/file_dialogs.py",
    "sigft/app_qt/icones.py",
    "sigft/app_qt/interface.py",
    "sigft/app_qt/letra.py",
    "sigft/app_qt/main.py",
    "sigft/app_qt/nome.py",
    "sigft/app_qt/novidades.py",
    "sigft/app_qt/pasta_de_logs.py",
    "sigft/app_qt/reinicio.py",
    "sigft/app_qt/propriedades.py",
    "sigft/app_qt/tema.py",
    "sigft/app_qt/views/__init__.py",
    "sigft/app_qt/views/configuracao.py",
    "sigft/app_qt/views/home.py",
    "sigft/app_qt/views/nao_migrada.py",
    # Task 6: Cria Fichas, Planilhas PMIB, Analyzer e as janelas auxiliares
    "sigft/app_qt/views/analyzer.py",
    "sigft/app_qt/views/cria_fichas.py",
    "sigft/app_qt/views/janelas.py",
    "sigft/app_qt/views/pdm.py",
    # Task 7: Upload Condições, Tradutor, Upload Specs
    "sigft/app_qt/views/_upload_comum.py",
    "sigft/app_qt/views/translator.py",
    "sigft/app_qt/views/upload_conditions.py",
    "sigft/app_qt/views/upload_tech_specs.py",
    # Task 8: Correção de PDM, Upload duplicadas, AutoSpec
    "sigft/app_qt/views/autospec.py",
    "sigft/app_qt/views/copia_fichas.py",
    "sigft/app_qt/views/correcao_pdm.py",
    # Task 9: Aplicação LMR, PMIB Manager, Busca PMIB
    "sigft/app_qt/views/apagar_lmr.py",
    "sigft/app_qt/views/aplicacao_lmr.py",
    "sigft/app_qt/views/busca_pmib.py",
    "sigft/app_qt/views/lmr.py",
    "sigft/app_qt/views/pmib_manager.py",
)

# Literais que a varredura acusa e que ficam em português de propósito, por
# arquivo. Copie o texto como a ferramenta o imprime (sem as aspas do repr). Cada
# bloco diz por quê: dado de planilha, valor do portal, relatório do --smoke...
NAO_E_INTERFACE: dict[str, set[str]] = {
    # O cabeçalho do arquivo de log do "Abrir log" (formato de data do log): o
    # arquivo guarda o console, que não muda de idioma.
    "sigft/app/resumo_lote.py": {"f'%d/%m/%Y %H:%M:%S'"},
    # O nome do produto na marca do menu: não se traduz.
    "sigft/app_qt/widgets/marca.py": {"SIG-FT System"},
    # Só vão ao console (o console não muda de idioma: spec, "O que muda de idioma").
    "sigft/app_qt/widgets/revisao_portal.py": {
        "Cancelado na revisão antes do portal.",
        "Seguindo com todas as fichas, inclusive as com erro.",
    },
    "sigft/app_qt/widgets/trava_robo.py": {"outro robô"},
    # Task 5. Chaves de tela (`TELAS`, `show_frame`, `ICONE_DA_TELA`), não texto.
    "sigft/app_qt/catalogo.py": {"Translator"},
    # Nome do arquivo de fonte e família de fonte (nome de fonte, não texto).
    "sigft/app_qt/estilo.py": {
        "Roboto-Regular.ttf",
        "NotoEmoji-Regular.ttf",
        '"Roboto", "Noto Emoji"',
        '"Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono", monospace',
    },
    # A pergunta da primeira abertura é bilíngue de propósito: vem antes de haver idioma.
    "sigft/app_qt/escolha_de_idioma.py": {"Idioma / Language"},
    "sigft/app_qt/main.py": {
        # Só a CHAVE da tela inicial (`TELAS`, `show_frame`, `telas["Home"]`), não texto:
        # o botão do menu mostra `t('Home')`.
        "Home",
        # O título da janela: nome do produto e a versão.
        "f'SIG-FT v{_build_info.VERSAO} - GE Vernova'",
        # O `onde` do erro no diário de quedas: linha de log, não tela (2026-10-27).
        "abertura da janela",
        # O aviso de quando a Qt não sobe: antes de o idioma valer.
        "f'A Qt não conseguiu iniciar:\\n{texto}'",
        # O relatório do --smoke: quem lê é o Release, não a pessoa.
        "f'[smoke] FALHOU: a interface Qt nao abriu: {texto}'",
        "f'  FALHOU  {chave}: {type(tela.erro).__name__}: {tela.erro}'",
        'f"[smoke] FALHOU: icones que nao desenham ({len(sem_desenho)}): '
        '{\', \'.join(sem_desenho)} (pasta {icones.PASTA})"',
        'f"[smoke] FALHOU: catalogos de idioma que nao se leem: '
        '{\', \'.join(sem_catalogo)} (pasta {idioma.PASTA_CATALOGOS})"',
        'f"[smoke] AVISO: o backend \'{nome}\' nao carregou: {type(erro).__name__}: {erro}"',
        "[smoke] telas visitadas:",
        'f"[smoke] bloqueadas no menu (nao visitadas): {\', \'.join(bloqueadas)}"',
        "f'[smoke] FALHOU: telas que nao abriram ({len(quebradas)}): '",
        "f'[smoke] a janela principal Qt montou, as {len(linhas)} telas abriram e ela fechou sem erro.'",
    },
    # Task 6. Cria Fichas: colunas e aba que o `data_manager` lê e grava na planilha
    # ("DESCRIÇÃO", "CÓDIGO PMIB", "Lista de Materiais"), valores padrão que vão ao
    # portal e à planilha no "Pular IA" (origem, tipo, unidade, fabricação) e o
    # status gravado no resumo/Excel ("VERIFICAR (PULADO)"). A mensagem do robô
    # ocupado só vai ao console (`_robo_ocupado`), que não muda de idioma.
    "sigft/app_qt/views/cria_fichas.py": {
        "DESCRIÇÃO",
        "CÓDIGO PMIB",
        "Lista de Materiais",
        "Nacional",
        "Não Reparável",
        "Unidade",
        "Catálogo",
        "VERIFICAR (PULADO)",
        "O robô já está trabalhando no portal (criação ou edição). Espere ele terminar antes de iniciar outro.",
    },
    # Task 7. A mensagem do robô ocupado das telas de upload só vai ao console
    # (`_robo_ocupado`), que não muda de idioma (como a do Cria Fichas).
    "sigft/app_qt/views/_upload_comum.py": {
        "O robô já está preenchendo uma fila no portal. Espere ele terminar "
        "(ou use PARAR ROBÔ WEB) antes de iniciar outra.",
    },
    # Task 8. Upload duplicadas: as linhas `registrar(...)` do robô vão ao console
    # e ao log de auditoria (`registrar` é o `log_auditoria.envolver(self.log)`),
    # que não mudam de idioma. "Sem Descrição" é o valor que entra na fila
    # (`descricao` do item, que o robô e o log usam): dado.
    "sigft/app_qt/views/copia_fichas.py": {
        "Sem Descrição",
        "f'[Robô novo] {len(fichas)} ficha(s) na fila. Abrindo o navegador...'",
        "[Robô novo] Marcando o _STATUS_PMIB...",
        "f'[Robô novo] {len(concluidas)} de {len(resultados)} sem pendência; "
        "{marcadas} linha(s) marcada(s) na planilha'",
        "f', {len(falhas)} falha(s).'",
        "[Robô novo] Confira no portal o que o log marcou como pendência antes de "
        "mudar o status das fichas.",
        "f'[Robô novo] Falha: {type(erro).__name__}: {erro}'",
    },
    # Task 9. O `NOME_DO_ROBO` de cada aba da Aplicação LMR só aparece no console
    # (`ComTravaDeRobo.robo_ocupado`), que não muda de idioma.
    "sigft/app_qt/views/apagar_lmr.py": {"Exclusão de aplicações"},
    "sigft/app_qt/views/lmr.py": {"Upload de aplicações"},
    # Busca PMIB: os nomes de coluna das planilhas pesquisadas (o menu "Coluna
    # Alvo" os mostra e o serviço procura por eles) são dado. "PMIB: {código}" é
    # o termo do glossário e o código achado: igual em todo idioma.
    "sigft/app_qt/views/busca_pmib.py": {
        "DESCRIÇÃO",
        "CÓDIGO DO MATERIAL",
        "CÓDIGO CMI",
        "CÓDIGO PMIB",
        "f'PMIB: {cod_itaipu}'",
    },
}


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


def test_toda_a_interface_esta_na_guarda():
    """Arquivo novo em `sigft/app_qt` (ou um que ficou de fora) entra na guarda:
    texto de interface sem `t()` não volta escondido."""
    todos = {p.relative_to(RAIZ).as_posix() for p in ferramenta.arquivos(RAIZ)}
    assert todos - set(CONVERTIDOS) == set()


@pytest.mark.parametrize("codigo, esperado", [
    ("""f"a: {', '.join(x)}" """, """f"a: {', '.join(x)}\""""),
    ('f"Arquivo: {n!r:>5}"', "f'Arquivo: {n!r:>5}'"),
    ('f"chave {{x}} e\\n{y}"', "f'chave {{x}} e\\n{y}'"),
])
def test_texto_da_fstring_nao_muda_com_a_versao_do_python(codigo, esperado):
    # No 3.12 (PEP 701) o `ast.unparse` troca as aspas da f-string que tem aspas
    # dentro, e o `NAO_E_INTERFACE` deixava de casar só no CI de 3.12 (2026-10-23).
    import ast

    no = ast.parse(codigo.strip(), mode="eval").body
    assert ferramenta._texto_do_codigo(no) == esperado
