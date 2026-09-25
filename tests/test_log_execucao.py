r"""
O log de execução em arquivo — a trilha de auditoria.

Pedido do usuário (2026-08-18): *"trabalhar com os logs de saída do que está
acontecendo pra eventual auditoria do processo"*.

O que já existia (`core/relatorio_lote.py`) padroniza o TEXTO do console, e o
console some quando a janela fecha. Para responder "por que esta ficha saiu
INCOMPLETO na terça?", a informação já foi embora quando a pergunta aparece.

Os testes aqui defendem as três decisões que fazem esse arquivo servir de
prova, e cada uma tem um jeito específico de falhar em silêncio.
"""
import io as _io

import pytest

from sigft.core import log_execucao
from sigft.core.log_execucao import LogDeExecucao, nome_de_arquivo, recortar


class _ArquivoFalso(_io.StringIO):
    """`StringIO` que conta os `flush` e não fecha de verdade -- para o teste
    conseguir ler o conteúdo depois do `fechar()`."""

    def __init__(self):
        super().__init__()
        self.flushes = 0
        self.fechado = 0

    def flush(self):
        self.flushes += 1

    def close(self):
        self.fechado += 1


def _log(**kwargs):
    arquivo = _ArquivoFalso()
    registro = LogDeExecucao("duplicadas", pasta="", abrir_fn=lambda *_a, **_k: arquivo,
                             **kwargs)
    return registro, arquivo


# =============================================================================
# 1. Grava linha a linha, com flush
# =============================================================================
def test_cada_linha_e_descarregada_no_disco_na_hora():
    """Um lote de RPA morre no meio por motivos que não controlamos. Se o
    arquivo só fosse escrito no fim, justamente a execução que mais interessa
    auditar seria a que não deixa registro."""
    registro, arquivo = _log()
    antes = arquivo.flushes

    registro.envolver()("processando 4500063671.1418")

    assert arquivo.flushes > antes


def test_o_conteudo_ja_esta_no_arquivo_antes_de_fechar():
    registro, arquivo = _log()

    registro.envolver()("linha viva")

    assert "linha viva" in arquivo.getvalue()


# =============================================================================
# 2. Nunca levanta
# =============================================================================
def test_falha_ao_ABRIR_o_arquivo_nao_derruba_nada():
    """Trocar um problema pequeno (sem log) por um grande (lote morto) seria o
    pior negócio possível."""
    def _explode(*_a, **_k):
        raise PermissionError("pasta somente leitura")

    registro = LogDeExecucao("duplicadas", pasta="", abrir_fn=_explode)
    registro.envolver()("segue o baile")  # não levanta
    registro.bloco("html", "<div/>")
    registro.fechar()


def test_falha_ao_ESCREVER_desliga_a_gravacao_e_avisa_UMA_vez():
    class _QuebraNaEscrita(_ArquivoFalso):
        def write(self, _texto):
            raise OSError("disco cheio")

    arquivo = _QuebraNaEscrita()
    registro = LogDeExecucao("duplicadas", pasta="", abrir_fn=lambda *_a, **_k: arquivo)
    console = []

    registrar = registro.envolver(console.append)
    registrar("primeira")
    registrar("segunda")
    registrar("terceira")

    avisos = [l for l in console if "Parei de gravar o log" in l]
    assert len(avisos) == 1, "o aviso repetido a cada linha viraria ruído"
    assert console.count("primeira") == 1, "a tela continua recebendo tudo"
    assert "terceira" in console


# =============================================================================
# 3. Blocos grandes vão só para o arquivo
# =============================================================================
def test_o_bloco_de_html_NAO_polui_o_console():
    """É o que permite despejar a estrutura da tela sem tornar ilegível o
    console que o usuário está acompanhando."""
    registro, arquivo = _log()
    console = []
    registro.envolver(console.append)

    registro.bloco("Seção «Condições»", "<div class='osui-tabs'>…</div>")

    assert "<div class='osui-tabs'>…</div>" in arquivo.getvalue()
    assert not any("osui-tabs" in l for l in console)


def test_o_recorte_avisa_quanto_faltou():
    """Corte silencioso faria quem lê concluir que o elemento acaba ali e
    procurar, do lado do código, o resto de um markup que estava truncado --
    o mesmo erro da armadilha do contador de anexos (§8.2 dos seletores)."""
    saida = recortar("x" * 500, 100)

    assert saida.startswith("x" * 100)
    assert "RECORTADO" in saida
    assert "faltam 400" in saida


@pytest.mark.parametrize("desligado", [0, None, -1])
def test_limite_desligado_devolve_tudo(desligado):
    assert recortar("x" * 500, desligado) == "x" * 500


def test_texto_vazio_ou_None_nao_levanta():
    assert recortar(None) == ""
    assert recortar("") == ""


# =============================================================================
# O resto do contrato
# =============================================================================
def test_a_tela_recebe_exatamente_o_que_recebia_antes():
    """`envolver` não pode mudar o texto: a mesma mensagem que o usuário já
    conhece continua aparecendo, sem carimbo nem prefixo."""
    registro, _arquivo = _log()
    console = []

    registro.envolver(console.append)("Processando 4500063671.1418...")

    assert console == ["Processando 4500063671.1418..."]


def test_o_arquivo_carimba_a_hora_de_cada_linha():
    """No console o carimbo seria ruído; no arquivo é o que permite cruzar com
    o horário de uma falha no portal."""
    registro, arquivo = _log()

    registro.envolver()("uma linha")

    assert "] uma linha" in arquivo.getvalue()


def test_o_nome_do_arquivo_ordena_por_data():
    """Data ISO na frente: a ordem alfabética da pasta vira ordem cronológica,
    que é como se procura "o log daquele dia"."""
    import datetime

    nome = nome_de_arquivo("duplicadas", datetime.datetime(2026, 8, 18, 14, 32, 5))

    assert nome == "duplicadas_2026-08-18_14-32-05.log"


def test_nome_de_modulo_com_caractere_estranho_nao_vira_caminho():
    nome = nome_de_arquivo("../../etc/passwd", __import__("datetime").datetime(2026, 1, 1))

    assert "/" not in nome and "\\" not in nome


def test_abre_e_fecha_com_marcas_de_inicio_e_fim():
    registro, arquivo = _log(contexto={"fichas": 3})
    registro.fechar()
    conteudo = arquivo.getvalue()

    assert "início" in conteudo and "fim" in conteudo
    assert "fichas: 3" in conteudo, "o contexto do lote entra no cabeçalho"
    assert arquivo.fechado == 1


def test_serve_de_context_manager():
    arquivo = _ArquivoFalso()
    with LogDeExecucao("x", pasta="", abrir_fn=lambda *_a, **_k: arquivo) as registro:
        registro.envolver()("dentro")

    assert arquivo.fechado == 1


def test_a_pasta_padrao_e_a_de_dados_do_usuario():
    """Era `config.PASTA_LOGS` ("logs") relativo -- a pasta do programa, que no
    app instalado é `Program Files` e não grava (2026-09-25)."""
    from sigft.core import dados_usuario

    assert log_execucao.LogDeExecucao("m", abrir_fn=lambda *_a, **_k: _ArquivoFalso()) \
        .caminho.startswith(str(dados_usuario.pasta_logs()))


def test_falha_na_ABERTURA_tambem_avisa_na_primeira_linha():
    """O caso pior, e o que a primeira versão perdia: a primeira escrita
    acontece no cabeçalho, ANTES de `envolver()` conhecer o console. Avisar ali
    não chegava a ninguém, e o usuário auditava um arquivo inexistente
    achando que a gravação estava ligada."""
    def _explode(*_a, **_k):
        raise PermissionError("pasta somente leitura")

    registro = LogDeExecucao("duplicadas", pasta="", abrir_fn=_explode)
    console = []

    registro.envolver(console.append)("primeira linha do lote")

    assert any("Parei de gravar o log" in l for l in console)


# =============================================================================
# A fiação da tela — por AST, porque `frontend.py` abre janela
# =============================================================================
# Mesma disciplina de `test_forcar_processamento_completo.py`: o defeito
# clássico aqui é o interruptor existir e o valor nunca ser lido, e um teste
# só de backend passaria feliz o tempo todo.
import ast  # noqa: E402
import pathlib  # noqa: E402

# [CP 7.3] A tela saiu do `frontend.py` para o seu proprio arquivo.
FRONTEND = pathlib.Path(__file__).resolve().parents[1] / "sigft" / "app" / "views" / "copia_fichas.py"


@pytest.fixture(scope="module")
def copia_fichas():
    arvore = ast.parse(FRONTEND.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.ClassDef) and no.name == "ModuloCopiaFichas":
            return no
    pytest.fail("class ModuloCopiaFichas sumiu de sigft/app/views/copia_fichas.py")


def _metodo(classe, nome):
    for no in classe.body:
        if isinstance(no, ast.FunctionDef) and no.name == nome:
            return no
    pytest.fail(f"método {nome} não existe em {classe.name}")


def test_a_tela_LE_o_interruptor_de_auditoria(copia_fichas):
    worker = _metodo(copia_fichas, "_worker_robo_novo")
    leituras = [
        c for c in ast.walk(worker)
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
        and c.func.attr == "get" and isinstance(c.func.value, ast.Attribute)
        and c.func.value.attr == "var_log_auditoria"
    ]

    assert leituras, "o interruptor de auditoria voltou a ser decorativo"


def test_o_log_e_repassado_ao_servico(copia_fichas):
    worker = _metodo(copia_fichas, "_worker_robo_novo")
    passou = any(kw.arg == "log_auditoria"
                 for c in ast.walk(worker) if isinstance(c, ast.Call)
                 for kw in c.keywords)

    assert passou, "o log é criado e não chega no `processar_lote`"


def test_o_log_e_FECHADO_no_finally(copia_fichas):
    """Sem isto, o arquivo fica com a última linha presa no buffer justamente
    quando o lote morre no meio -- que é a execução que mais interessa."""
    worker = _metodo(copia_fichas, "_worker_robo_novo")
    tries = [n for n in ast.walk(worker) if isinstance(n, ast.Try) and n.finalbody]
    fechamentos = [
        c for t in tries for no in t.finalbody for c in ast.walk(no)
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
        and c.func.attr == "fechar"
        and isinstance(c.func.value, ast.Name) and c.func.value.id == "log_auditoria"
    ]

    assert fechamentos, "log_auditoria.fechar() não está no finally"
