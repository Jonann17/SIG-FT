"""As marcas de nível do console, com linhas REAIS dos serviços (2026-10-21, etapa 1b)."""
import ast
import pathlib
import re

import pytest

from sigft.app import busca
from sigft.app import niveis_log as n

RAIZ = pathlib.Path(__file__).resolve().parent.parent

# Cada linha copiada do arquivo indicado (o f-string preenchido com um valor de exemplo).
LINHAS_REAIS = [
    # services/duplicadas_extrator.py:218
    ("   [Erro] Ficha 4500063671.1234 não encontrada. Abas tentadas: Geral", n.ERRO),
    # services/autorizacao_portal.py:187
    ("[ERRO] A lista de fichas do portal não respondeu. Confira se o login foi feito e se a "
     "página de fichas está aberta.", n.ERRO),
    # app_qt/views/cria_fichas.py:753
    (" -> ❌ ERRO no Selenium: TimeoutException", n.ERRO),
    # services/tech_specs.py:874
    ("Falha IA: 4500063671.1234 (Verifique console para detalhes)", n.ERRO),
    # services/upload_conditions.py:356
    ("Falha definitiva no PMIB 4500063671.1234: timeout", n.ERRO),
    # services/duplicadas_extrator.py:536
    ("      [Aviso] Nenhum bloco com campos nesta seção. Se a ficha tem campos, confira.", n.AVISO),
    # services/autorizados.py:113
    ("[AVISO] export.xls: formato antigo (.xls), não é lido nem gravado.", n.AVISO),
    # services/tech_specs.py:1377
    ("   [!] O site rejeitou 'Tensão nominal'. Tentando injeção forçada...", n.AVISO),
    # services/duplicadas_documentos.py:279
    ("      [Autoconferência] Documentos: a tabela não tem a forma esperada", n.AVISO),
    # services/upload_conditions.py:593: o "Aviso:" abre a linha, o "Falha" vem depois
    ("Aviso: Falha nas Dimensões. KeyError('A')", n.AVISO),
    # core/relatorio_lote.py: o resumo tem ❌ NO MEIO e não é erro
    ("✅ 3 sucesso(s) · ❌ 1 falha(s) · ⏭️ 0 pulado(s)", n.INFO),
    ("   Falhas:", n.INFO),
    ("▶️ Gerando fichas PMIB: 8 item(ns).", n.INFO),
]


@pytest.mark.parametrize("linha, esperado", LINHAS_REAIS)
def test_marca_das_linhas_reais(linha, esperado):
    assert n.classificar(linha) == esperado


def test_o_nivel_do_protocolo_ganha_da_marca():
    # core/relatorio_lote.py: `falha()` manda "error", `aviso()` manda "warn"
    assert n.classificar("⚠️ 4500063671.1234: campo X rejeitado → preencher", "warn") == n.AVISO
    assert n.classificar("qualquer coisa", "error") == n.ERRO
    assert n.classificar("[Erro] mas o serviço disse", "warn") == n.AVISO


def test_info_e_nivel_desconhecido_caem_na_marca():
    assert n.classificar("[Erro] x", "info") == n.ERRO
    assert n.classificar("[Erro] x", "debug") == n.ERRO
    assert n.classificar("linha comum", "debug") == n.INFO


def test_so_vale_a_primeira_linha_e_qualquer_objeto():
    assert n.classificar("tudo certo\n[Erro] na segunda linha") == n.INFO
    assert n.classificar(ValueError("Falha no arquivo")) == n.ERRO
    assert n.classificar(None) == n.INFO
    assert n.classificar("") == n.INFO


def test_busca_sem_acento_e_sem_caixa():
    assert busca.normalizar("Tensão AÇÃO") == "tensao acao"
    assert busca.contem("Tensão nominal gravada", "TENSAO")
    assert busca.contem("qualquer", "")
    assert not busca.contem("Tensão", "corrente")


# As tags entre colchetes que abrem log de serviço e NÃO são aviso nem erro.
# Tag nova num serviço reprova o teste abaixo: decida o nível dela aqui ou em
# `niveis_log.MARCAS_*`, em vez de ela cair calada em "info".
TAGS_INFORMATIVAS = {
    "[i]", "[INFO]", "[Lista]", "[Formato]", "[Injetor]", "[ATUALIZADO]", "[REPROVADA]",
    "[Revisão]", "[Contexto]", "[Tipo]", "[PARADO]", "[CONFERIR]", "[Diagnóstico]",
    "[Parado pelo usuário]", "[SIG-FT]",
}
_TAG = re.compile(r"^\s*(?:->\s*)?(\[(?:[A-ZÀ-Ý!][^\]{}\\]{0,28}|i)\])")
# Primeiro argumento destas é expressão regular, não log: "[A-Z0-9]" não é tag.
_FUNCOES_DE_REGEX = {"compile", "sub", "match", "search", "findall", "split", "fullmatch", "finditer"}


def _tags_que_abrem_log():
    tags = {}
    pastas = [RAIZ / "sigft" / "services", RAIZ / "sigft" / "core"]
    for arquivo in sorted(p for pasta in pastas for p in pasta.rglob("*.py")):
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            alvos = []
            if isinstance(no, ast.Call) and no.args:
                nome = getattr(no.func, "attr", getattr(no.func, "id", ""))
                if nome not in _FUNCOES_DE_REGEX:
                    alvos.append(no.args[0])
            if isinstance(no, ast.Yield) and no.value is not None:
                alvos.append(no.value)
            for alvo in alvos:
                if isinstance(alvo, ast.Constant) and isinstance(alvo.value, str):
                    texto = alvo.value
                elif (isinstance(alvo, ast.JoinedStr) and alvo.values
                      and isinstance(alvo.values[0], ast.Constant)):
                    texto = alvo.values[0].value
                else:
                    continue
                achado = _TAG.match(texto)
                if achado:
                    tags.setdefault(achado.group(1), f"{arquivo.relative_to(RAIZ)}:{no.lineno}")
    return tags


def test_toda_tag_de_log_dos_servicos_tem_nivel_decidido():
    tags = _tags_que_abrem_log()
    assert len(tags) > 10, "a varredura não achou os logs"
    sem_decisao = {tag: onde for tag, onde in tags.items()
                   if tag not in TAGS_INFORMATIVAS and n.nivel_da_marca(tag + " x") == n.INFO}
    assert sem_decisao == {}
