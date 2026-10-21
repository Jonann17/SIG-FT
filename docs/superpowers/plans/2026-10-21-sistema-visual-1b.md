# Sistema visual 1b (ferramentas de uso): plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** entregar as seis ferramentas de uso da etapa 1b da spec
`docs/superpowers/specs/2026-10-20-sistema-visual-design.md` (§ "Etapa 1b"): filtro
do console, janela de resumo do lote, arrastar arquivo e "Últimos arquivos", Ctrl+K,
letra grande e aviso do Windows, sem tocar em serviço nem em robô.

**Architecture:** a regra fica em módulos sem Qt em `sigft/app/` (`busca.py`,
`niveis_log.py`, `resumo_lote.py`) e em `sigft/core/prefs.py` (os recentes); as peças
Qt ficam em `sigft/app_qt/` (`widgets/console.py`, `widgets/resumo_lote.py`,
`widgets/arrastar.py`, `widgets/paleta.py`, `letra.py`, `aviso_windows.py`). O gancho
único nas telas é o `ModuleFrame` (fim da tarefa, `ARRASTAVEIS`) e o
`DialogosDeEspera` (esperas). As cores novas entram só em `estilo.py`, numa função
nova `_folha_ferramentas(tema)`.

**Tech Stack:** Python 3.10+, PySide6 (QtWidgets, QtGui: `QSystemTrayIcon`,
`QShortcut`, arrastar e soltar), pytest-qt (offscreen).

## Global Constraints

- Código, comentários e commits em **português**; mensagem de commit sem acento;
  pé do commit com `Co-Authored-By` e `Claude-Session` (o lembrete de atribuição da sessão).
- Texto que o usuário lê: **sem travessão** (`tests/test_texto_da_ui.py`). Vale para
  rótulos, dicas, mensagens de log novas e as linhas novas do `CHANGELOG.md`.
- **Cor só em `sigft/app_qt/estilo.py`** (`tests/test_qt_sem_cor_crua.py`): nada de
  hexadecimal, `tokens.ESCURO`/`CLARO`, `color:`/`background:` em folha local fora
  dele. Cor calculada em código vem de `estilo.cor_do_papel(...)`.
- **Serviço e robô intocados:** nenhum arquivo em `sigft/services/`, `sigft/core/rpa/`,
  `sigft/core/web/` muda. O nível das linhas é lido do texto que já se loga. O único
  arquivo de `sigft/core/` que muda é `prefs.py`.
- Módulos novos de `sigft/app/` **não importam PySide6** (serviço e regra nunca
  conhecem Qt).
- Nenhuma dependência nova no `requirements.txt`.
- **Nenhum teste de medida existente quebra.** O estado padrão (letra normal, sem
  arquivo recente, sem aviso) tem as medidas de hoje. Cada tarefa lista os testes de
  medida que corre antes do commit.
- **Nada abre sozinho nos testes:** a janela de resumo e o aviso do Windows ficam
  desligados por variável de ambiente posta no `tests/conftest.py`; quem testa o
  recurso tira a variável com `monkeypatch.delenv`.
- Sinal de widget filho **não** recebe `lambda` que capture a tela ou o pai (aviso do
  mural de 2026-10-14: vaza a tela e derruba o processo na saída). Use método ligado
  (`self._algo`) ou `weakref`.
- Testes rodam com `.venv/bin/python -m pytest -q <arquivos>`; antes de cada commit,
  `bash scripts/check.sh` verde (o `tests/test_qt_saida.py` falha só neste contêiner:
  preexistente, ver o plano 1a). Mexeu em `main.py`, `module_frame.py` ou numa tela:
  `QT_QPA_PLATFORM=offscreen .venv/bin/python frontend.py --smoke`.

---

## Mapa de arquivos

| Arquivo | Responsabilidade | Tarefa |
|---|---|---|
| `sigft/app/busca.py` (novo) | comparar texto sem acento e sem caixa | 1 |
| `sigft/app/niveis_log.py` (novo) | as marcas de nível, num lugar só; `classificar(msg, nivel)` | 1 |
| `sigft/app_qt/widgets/console.py` | guarda cada linha com nível; barra Tudo/Avisos/Erros, busca, Copiar | 1 |
| `sigft/app_qt/estilo.py` | `_folha_ferramentas` (console, arrasto, Ctrl+K); aumento da letra | 1, 3, 5, 6 |
| `sigft/app/resumo_lote.py` (novo) | agrupar por PMIB, contar, frases, gravar o log do lote | 2 |
| `sigft/app_qt/widgets/resumo_lote.py` (novo) | a janela "Resumo" (Copiar lista, Abrir log) | 2 |
| `sigft/app_qt/widgets/module_frame.py` | marca do console no começo, resumo e aviso no fim, `ARRASTAVEIS` | 2, 3, 7 |
| `tests/conftest.py` | desliga resumo e aviso do Windows nos testes | 2, 7 |
| `sigft/core/prefs.py` | seção `recentes`: `lembrar_recente`, `recentes` | 3 |
| `sigft/app/file_dialogs.py` | `entregar`/`descartar`/`pendente`; extensões; recentes ao escolher | 3 |
| `sigft/app_qt/file_dialogs.py` | os mesmos nomes para as telas | 3 |
| `sigft/app_qt/widgets/arrastar.py` (novo) | `aceitar_arquivo`, `Arrastavel`, menu "Últimos arquivos" | 3 |
| `sigft/app_qt/widgets/pickers.py` | `FilePickerRow`/`MultiFilePickerRow`/`FileQueueList` aceitam arrasto | 3 |
| 8 telas com botão de arquivo | declaram `ARRASTAVEIS` | 4 |
| `sigft/app_qt/catalogo.py` | `Comando`, `ACOES`, `comandos()`, `filtrar()` | 5, 6 |
| `sigft/app_qt/widgets/paleta.py` (novo) | a caixa do Ctrl+K | 5 |
| `sigft/app_qt/main.py` | atalho Ctrl+K, `executar_comando`, letra na abertura, `--letra` | 5, 6 |
| `sigft/app/tokens.py` | `AUMENTO_DA_LETRA` | 6 |
| `sigft/app_qt/letra.py` (novo) | Normal/Grande, aplicado na hora e lembrado | 6 |
| `sigft/app_qt/widgets/blocos.py` | `pintar` lê a folha de antes do aumento | 6 |
| `sigft/app_qt/views/home.py` | seletor de letra; caixa "Avisar no Windows" | 6, 7 |
| `sigft/app_qt/aviso_windows.py` (novo) | `QSystemTrayIcon.showMessage` fora de foco | 7 |
| `sigft/app_qt/widgets/espera.py` | aviso nas esperas | 7 |
| `CHANGELOG.md`, `docs/base-conhecimento/00-frontend.md`, `CLAUDE.md` | fechamento | 8 |

Ordem (prioridade do Jonathan): 1 filtro do console (item 5 da spec), 2 resumo (item 2),
3 e 4 arrastar e recentes (item 3, dividido: mecanismo e telas), 5 Ctrl+K (item 4),
6 letra (item 6), 7 aviso do Windows (item 1), 8 fechamento.

---

### Task 1: Filtro do console (Tudo / Avisos / Erros, busca, Copiar)

**Files:**
- Create: `sigft/app/busca.py`
- Create: `sigft/app/niveis_log.py`
- Modify: `sigft/app_qt/widgets/console.py` (reescrito inteiro, abaixo)
- Modify: `sigft/app_qt/estilo.py` (fim de `folha_de_estilo`; nova `_folha_ferramentas`)
- Test: `tests/test_niveis_log.py` (novo), `tests/test_qt_console.py` (acrescentar)

**Interfaces:**
- Produces: `busca.normalizar(texto: object) -> str`; `busca.contem(texto: object, consulta: object) -> bool`.
- Produces: `niveis_log.ERRO = "erro"`, `AVISO = "aviso"`, `INFO = "info"`;
  `niveis_log.NIVEL_DO_PROTOCOLO: dict[str, str]`; `MARCAS_DE_ERRO`, `MARCAS_DE_AVISO: tuple[str, ...]`;
  `niveis_log.nivel_da_marca(msg: object) -> str`; `niveis_log.classificar(msg: object, nivel: object = "info") -> str`.
- Produces: `console.Linha(seq: int, msg: str, nivel: str)` (NamedTuple);
  `ConsoleFrame.marca() -> int`; `ConsoleFrame.linhas(desde: int = 0) -> list[Linha]`;
  `ConsoleFrame.filtrar(filtro: str)` (`"tudo"`, `"avisos"`, `"erros"`);
  `ConsoleFrame.buscar(texto: str)`; `ConsoleFrame.copiar()`; `ConsoleFrame.barra: BarraDoConsole`
  (atributos `botoes: dict[str, QPushButton]`, `campo: QLineEdit`, `copiar: QPushButton`);
  constantes `ALTURA_BARRA = 28`, `TEXTO_COPIADO = "Copiado"`.
- Produces: `estilo._folha_ferramentas(tema: str | None = None) -> str` (as tarefas 3 e 5 acrescentam regras).

Decisões desta tarefa (spec ambígua):
- A marca só vale **no começo** da linha (depois de espaço, `>`, `-`, `→`, `•`): o
  resumo do `RelatorioLote` ("✅ 3 sucesso(s) · ❌ 0 falha(s)") tem ❌ no meio e não é erro.
- O `nivel` do protocolo vence quando é `error`/`warn` (os valores reais dos serviços)
  ou sinônimo; `info` é o padrão e não se distingue de "não mandou", então cai na marca.
- Além das marcas da spec, entram as que os serviços usam de fato (varredura AST de
  2026-10-21): `[AVISO]` (25 usos), `[Atenção]`, `[Erro Estrutural]`, `[ERRO FATAL AO SALVAR]`
  (prefixo `[erro`), `Aviso:` (o "Aviso: Falha nas Dimensões" do Upload Condições é aviso)
  e `⚠` (a marca de aviso do `RelatorioLote`).
- "Avisos" mostra avisos **e** erros (tudo o que pede atenção); "Erros", só erros.
- A barra fica na **margem de baixo** da vista do console: a altura do console e o
  começo do texto (testes de medida das telas e `test_texto_comeca_onde_comeca_no_ctktextbox`)
  ficam iguais. Perde-se 28 px de área de texto.

- [ ] **Step 1: testes das marcas (`tests/test_niveis_log.py`)**

```python
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
```

- [ ] **Step 2:** `.venv/bin/python -m pytest -q tests/test_niveis_log.py` → falha
  (`ImportError: cannot import name 'busca'`).

- [ ] **Step 3: `sigft/app/busca.py`**

```python
"""Comparar texto como a pessoa digita: sem acento e sem caixa (2026-10-21, etapa 1b).

Usado pela busca do console (`app_qt/widgets/console.py`) e pela caixa do Ctrl+K
(`app_qt/catalogo.filtrar`). Sem Qt.
"""
from __future__ import annotations

import unicodedata


def normalizar(texto: object) -> str:
    """"Tensão AÇÃO" -> "tensao acao"."""
    decomposto = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in decomposto if not unicodedata.combining(c)).casefold()


def contem(texto: object, consulta: object) -> bool:
    """`consulta` aparece em `texto`, sem olhar acento nem caixa. Consulta vazia: sim."""
    return normalizar(consulta).strip() in normalizar(texto)
```

- [ ] **Step 4: `sigft/app/niveis_log.py`**

```python
"""O nível de cada linha do console: erro, aviso ou informação (2026-10-21, etapa 1b).

UM lugar só para as marcas. O filtro do console (Tudo / Avisos / Erros) e a
janela de resumo do fim do lote leem daqui.

De onde vem o nível, nesta ordem:
1. o `nivel` do protocolo de log (`core/callbacks.py`) quando o serviço o manda:
   "error" e "warn" (os que os serviços usam) e os sinônimos. "info" é o padrão
   do protocolo, e não se distingue de "não mandou": cai na regra 2;
2. a MARCA que abre a linha ("[Erro] ...", "❌ ...", "Falha ao ..."). Só no
   começo: o resumo do `RelatorioLote` ("✅ 3 sucesso(s) · ❌ 0 falha(s)") tem um
   ❌ no meio e não é erro.

Sem Qt. `tests/test_niveis_log.py` trava as marcas com linhas reais dos serviços
e reprova tag nova de serviço sem nível decidido.
"""
from __future__ import annotations

import re

ERRO = "erro"
AVISO = "aviso"
INFO = "info"

NIVEL_DO_PROTOCOLO = {
    "error": ERRO, "erro": ERRO, "critical": ERRO,
    "warn": AVISO, "warning": AVISO, "aviso": AVISO,
}

# Comparadas sem caixa, no começo da linha. Marca que termina em letra só vale
# como palavra inteira: "Falha ao salvar" é erro; "Falhas:" (título do resumo do
# lote) não. "[erro" sem o colchete de fechar pega "[Erro Estrutural]" e
# "[ERRO FATAL AO SALVAR]".
MARCAS_DE_ERRO = ("[erro", "❌", "falha")
MARCAS_DE_AVISO = ("[aviso]", "[!]", "[autoconferência]", "[atenção]", "aviso:", "⚠")

# O que pode vir antes da marca: recuo, o "->" das telas, seta e marcador.
_ABERTURA = re.compile(r"^[\s>\-→•]+")


def _abre_com(texto: str, marca: str) -> bool:
    if not texto.startswith(marca):
        return False
    if marca[-1].isalpha():
        return not texto[len(marca):len(marca) + 1].isalpha()
    return True


def nivel_da_marca(msg: object) -> str:
    """O nível pela marca que abre a PRIMEIRA linha de `msg`."""
    texto = str(msg if msg is not None else "").strip()
    primeira = texto.splitlines()[0] if texto else ""
    primeira = _ABERTURA.sub("", primeira).casefold()
    if any(_abre_com(primeira, marca) for marca in MARCAS_DE_ERRO):
        return ERRO
    if any(_abre_com(primeira, marca) for marca in MARCAS_DE_AVISO):
        return AVISO
    return INFO


def classificar(msg: object, nivel: object = "info") -> str:
    """O nível da linha: o do protocolo quando ele diz erro ou aviso, senão o da marca."""
    do_protocolo = NIVEL_DO_PROTOCOLO.get(str(nivel).casefold())
    return do_protocolo or nivel_da_marca(msg)
```

  Nota: `classificar(None)` devolve `INFO` (o `str(None)` seria "None"; o teste pede INFO,
  e "None" também não abre com marca, então os dois caminhos concordam).

- [ ] **Step 5:** `.venv/bin/python -m pytest -q tests/test_niveis_log.py` → PASS. Se
  `test_toda_tag_de_log_dos_servicos_tem_nivel_decidido` listar uma tag que não está
  aqui, decida o nível dela olhando a linha indicada: aviso/erro entra em
  `MARCAS_*`, informação entra em `TAGS_INFORMATIVAS`. Não apague o teste.

- [ ] **Step 6: testes do console (acrescentar ao fim de `tests/test_qt_console.py`)**

```python
# --- filtro, busca e Copiar (2026-10-21, etapa 1b) ---------------------------------

MISTURA = [
    ("tudo certo", "info"),
    ("[Erro] Ficha 4500063671.0001 não encontrada", "info"),
    ("[Aviso] tabela vazia", "info"),
    ("Tensão nominal gravada", "info"),
    ("❌ 4500063671.0002: TimeoutError", "error"),
]


def _console_com(qtbot, linhas):
    c = qconsole.ConsoleFrame()
    qtbot.addWidget(c)
    for msg, nivel in linhas:
        c.log(msg, nivel)
    qtbot.waitUntil(lambda: c.blockCount() >= len(linhas), timeout=2000)
    return c


def test_filtro_erros_e_avisos(qt_interface, qtbot):
    c = _console_com(qtbot, MISTURA)
    c.filtrar("erros")
    assert c.toPlainText().splitlines() == ["> [Erro] Ficha 4500063671.0001 não encontrada",
                                            "> ❌ 4500063671.0002: TimeoutError"]
    assert c.barra.botoes["erros"].isChecked()
    c.filtrar("avisos")   # avisos E erros: tudo o que pede atenção
    assert len(c.toPlainText().splitlines()) == 3
    c.barra.botoes["tudo"].click()
    assert len(c.toPlainText().splitlines()) == 5


def test_busca_sem_acento_e_sem_caixa(qt_interface, qtbot):
    c = _console_com(qtbot, MISTURA)
    c.barra.campo.setText("TENSAO")
    assert c.toPlainText().splitlines() == ["> Tensão nominal gravada"]
    c.barra.campo.clear()
    assert len(c.toPlainText().splitlines()) == 5


def test_linha_nova_respeita_o_filtro(qt_interface, qtbot):
    c = qconsole.ConsoleFrame()
    qtbot.addWidget(c)
    c.filtrar("erros")
    c.log("comum")
    c.log("[ERRO] ruim")
    qtbot.waitUntil(lambda: "ruim" in c.toPlainText(), timeout=2000)
    assert c.toPlainText().splitlines() == ["> [ERRO] ruim"]
    assert [linha.msg for linha in c.linhas()] == ["comum", "[ERRO] ruim"]   # guardou as duas


def test_copiar_leva_o_que_esta_a_vista(qt_interface, qtbot):
    from PySide6.QtWidgets import QApplication

    c = _console_com(qtbot, MISTURA)
    c.filtrar("erros")
    c.barra.copiar.click()
    assert QApplication.clipboard().text() == c.toPlainText()
    assert c.barra.copiar.text() == qconsole.TEXTO_COPIADO


def test_marca_e_linhas_desde(qt_interface, qtbot):
    c = qconsole.ConsoleFrame()
    qtbot.addWidget(c)
    c.log("antes")
    marca = c.marca()
    c.log("[Erro] depois", "info")
    assert [(linha.msg, linha.nivel) for linha in c.linhas(desde=marca)] == [("[Erro] depois", "erro")]


def test_limpar_esquece_as_linhas_mas_nao_a_contagem(qt_interface, qtbot):
    c = qconsole.ConsoleFrame()
    qtbot.addWidget(c)
    c.log("a")
    marca = c.marca()
    c.clear()
    assert c.linhas() == [] and c.toPlainText() == ""
    c.log("b")
    assert [linha.msg for linha in c.linhas(desde=marca)] == ["b"]


def test_barra_fica_embaixo_sem_mudar_a_altura(qt_interface, qtbot):
    c = qconsole.ConsoleFrame(altura=150)
    qtbot.addWidget(c)
    c.resize(400, 150)
    c.show()
    qtbot.waitExposed(c)
    vista = c.viewport().geometry()
    assert c.height() == 150
    assert c.barra.geometry().top() == vista.bottom() + 1
    assert c.barra.height() == qconsole.ALTURA_BARRA
    assert c.barra.geometry().right() == vista.right()   # não cobre a barra de rolagem


def test_barra_e_escura_nos_dois_temas():
    from sigft.app import tokens
    from sigft.app_qt import estilo

    for tema in ("escuro", "claro"):
        assert f"#barra_console {{ background: {tokens.ESCURO['console_fundo']}; }}" in \
            estilo.folha_de_estilo(tema)
```

  E, no mesmo arquivo, a docstring de `test_log_aceita_o_protocolo_e_o_nivel_nao_muda_a_renderizacao`
  troca a primeira frase "`core/callbacks.py`: a UI ignora o nível." por
  "`core/callbacks.py`: o nível não muda a RENDERIZAÇÃO (só o filtro o usa, 2026-10-21)."

- [ ] **Step 7:** `.venv/bin/python -m pytest -q tests/test_qt_console.py` → os novos
  falham (`AttributeError: 'ConsoleFrame' object has no attribute 'filtrar'`).

- [ ] **Step 8: `sigft/app_qt/widgets/console.py` (o arquivo inteiro)**

```python
"""Console de log das telas, rápido e seguro para chamar de qualquer thread.

O `CTkTextbox` reescrevia e rolava a cada linha; num lote de milhares de linhas
isso pesava. Aqui as linhas que chegam são juntadas e escritas em LOTE a cada
`INTERVALO_MS` (medido no protótipo: 10.000 linhas em ~0,1 s), e o console
guarda no máximo `MAX_LINHAS` -- as mais antigas saem.

Filtro (2026-10-21, etapa 1b): cada linha guarda o nível (`sigft/app/niveis_log`),
e a barra de BAIXO mostra "Tudo / Avisos / Erros", uma busca sem acento e sem
caixa e "Copiar" (o que está à vista). A barra mora na margem de baixo da vista:
a altura do console e o começo do texto são os de antes (testes de medida das
telas). As linhas ficam guardadas com um número de ordem: `marca()` e
`linhas(desde=...)` são o que a janela de resumo do lote lê.
"""
from __future__ import annotations

import threading
from collections import deque
from typing import NamedTuple

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QHBoxLayout, QLineEdit, QPlainTextEdit, QPushButton, QWidget,
)

from sigft.app import busca, niveis_log, theme
from sigft.app_qt import interface
from sigft.app_qt.widgets import blocos

PREFIXO_LINHA = "> "
INTERVALO_MS = 50
MAX_LINHAS = 20_000
# Onde o texto começa no CTkTextbox, a mais do que no QPlainTextEdit cru (que já
# tem a margem de 4 do documento): 4 px à direita e 5 px abaixo, medidos nas
# capturas do polimento (Tradutor, PDM e Upload: o ">" e a base da 1a linha).
RECUO_TEXTO_CTK = (4, 5)
# A barra do filtro, na margem de baixo da vista (2026-10-21).
ALTURA_BARRA = 28
FILTROS = (("tudo", "Tudo"), ("avisos", "Avisos"), ("erros", "Erros"))
# "Avisos" mostra avisos E erros: tudo o que pede atenção.
NIVEIS_DO_FILTRO = {
    "tudo": None,
    "avisos": frozenset({niveis_log.AVISO, niveis_log.ERRO}),
    "erros": frozenset({niveis_log.ERRO}),
}
TEXTO_BUSCA = "Buscar no console"
TEXTO_COPIAR = "Copiar"
TEXTO_COPIADO = "Copiado"
DICA_COPIAR = "Copia as linhas que estão à vista, com o filtro e a busca de agora."
MS_DO_COPIADO = 1500


class Linha(NamedTuple):
    """Uma linha do console: número de ordem, a mensagem (sem o "> ") e o nível."""
    seq: int
    msg: str
    nivel: str


def formatar_linha(msg: object) -> str:
    """A linha como as telas escrevem: ``"> {msg}"``. Aceita qualquer objeto."""
    return f"{PREFIXO_LINHA}{msg}"


class BarraDoConsole(QWidget):
    """Tudo / Avisos / Erros, a busca e o Copiar. Filha do console; os sinais vão
    a métodos DESTA barra (nada de lambda com o console: mural de 2026-10-14)."""

    def __init__(self, console: "ConsoleFrame") -> None:
        super().__init__(console)
        self.setObjectName("barra_console")
        # Sem isto um QWidget comum não pinta o `background` da folha.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(4)
        self.grupo = QButtonGroup(self)
        self.grupo.setExclusive(True)
        self.botoes: dict[str, QPushButton] = {}
        for indice, (chave, texto) in enumerate(FILTROS):
            botao = QPushButton(texto)
            blocos.sem_tecla(botao)
            botao.setCheckable(True)
            self.grupo.addButton(botao, indice)
            self.botoes[chave] = botao
            lay.addWidget(botao)
        self.botoes["tudo"].setChecked(True)
        self.grupo.idClicked.connect(self._escolheu_filtro)
        lay.addSpacing(8)
        self.campo = QLineEdit()
        self.campo.setPlaceholderText(TEXTO_BUSCA)
        self.campo.setClearButtonEnabled(True)
        self.campo.textChanged.connect(self._buscou)
        lay.addWidget(self.campo, 1)
        self.copiar = QPushButton(TEXTO_COPIAR)
        blocos.sem_tecla(self.copiar)
        self.copiar.setToolTip(DICA_COPIAR)
        self.copiar.clicked.connect(self._copiar)
        lay.addWidget(self.copiar)
        self._volta = QTimer(self)
        self._volta.setSingleShot(True)
        self._volta.timeout.connect(self._texto_do_copiar)

    def marcar(self, filtro: str) -> None:
        botao = self.botoes[filtro]
        if not botao.isChecked():
            botao.setChecked(True)

    def _escolheu_filtro(self, indice: int) -> None:
        self.parentWidget().filtrar(FILTROS[indice][0])

    def _buscou(self, texto: str) -> None:
        self.parentWidget().buscar(texto)

    def _copiar(self) -> None:
        self.parentWidget().copiar()
        self.copiar.setText(TEXTO_COPIADO)
        self._volta.start(MS_DO_COPIADO)

    def _texto_do_copiar(self) -> None:
        self.copiar.setText(TEXTO_COPIAR)


class ConsoleFrame(QPlainTextEdit):
    def __init__(self, parent=None, *, altura: int | None = theme.ALTURA_CONSOLE) -> None:
        super().__init__(parent)
        self.setObjectName("console")
        self.setReadOnly(True)
        self.setMaximumBlockCount(MAX_LINHAS)
        if altura is not None:
            self.setFixedHeight(altura)
        # Só a vista recua (a barra de rolagem continua com a altura toda); a
        # faixa que sobra é o fundo do próprio console, da mesma cor. Embaixo, a
        # margem é a da barra do filtro (`_posicionar_barra`).
        esquerda, cima = RECUO_TEXTO_CTK
        self.setViewportMargins(esquerda, cima, 0, ALTURA_BARRA)
        self._pendentes: deque[Linha] = deque()
        self._linhas: deque[Linha] = deque(maxlen=MAX_LINHAS)
        self._seq = 0
        self._trava = threading.Lock()
        self._agendado = False
        self._filtro = "tudo"
        self._busca = ""
        self.barra = BarraDoConsole(self)
        self._posicionar_barra()

    # -- protocolo `core/callbacks.py` -----------------------------------------
    def log(self, msg: object, nivel: str = "info", contexto: object | None = None) -> None:
        """Assinatura do protocolo `core/callbacks.py`. Qualquer thread."""
        texto = f"{msg}"
        nivel_da_linha = niveis_log.classificar(texto, nivel)
        with self._trava:
            self._seq += 1
            linha = Linha(self._seq, texto, nivel_da_linha)
            self._linhas.append(linha)
            self._pendentes.append(linha)
            if self._agendado:
                return
            self._agendado = True
        try:
            interface.na_interface(self._agendar)
        except RuntimeError:
            # Canal fechado (app fechando) ou ainda não instalado: a linha fica
            # na fila e a PRÓXIMA chamada tenta agendar de novo -- sem isto o
            # `_agendado` ficaria preso em True e o console, mudo para sempre.
            with self._trava:
                self._agendado = False

    def _agendar(self) -> None:
        try:
            QTimer.singleShot(INTERVALO_MS, self._descarregar)
        except RuntimeError:
            pass  # widget destruído

    def _descarregar(self) -> None:
        with self._trava:
            linhas = list(self._pendentes)
            self._pendentes.clear()
            self._agendado = False
        visiveis = [linha for linha in linhas if self._passa(linha)]
        if not visiveis:
            return
        try:
            self.appendPlainText("\n".join(formatar_linha(linha.msg) for linha in visiveis))
            self._rolar_para_o_fim()
        except RuntimeError:
            pass  # widget destruído entre o agendamento e a escrita

    # -- o que a janela de resumo lê -----------------------------------------
    def marca(self) -> int:
        """O número da última linha recebida (0 = nenhuma)."""
        with self._trava:
            return self._seq

    def linhas(self, desde: int = 0) -> list[Linha]:
        """As linhas guardadas depois da `marca` `desde`, na ordem."""
        with self._trava:
            return [linha for linha in self._linhas if linha.seq > desde]

    # -- filtro, busca, copiar -------------------------------------------------
    def _passa(self, linha: Linha) -> bool:
        niveis = NIVEIS_DO_FILTRO[self._filtro]
        if niveis is not None and linha.nivel not in niveis:
            return False
        return not self._busca or busca.contem(linha.msg, self._busca)

    def filtrar(self, filtro: str) -> None:
        if filtro not in NIVEIS_DO_FILTRO:
            raise ValueError(f"filtro desconhecido: {filtro!r}")
        self._filtro = filtro
        self.barra.marcar(filtro)
        self._redesenhar()

    def buscar(self, texto: str) -> None:
        self._busca = str(texto or "").strip()
        self._redesenhar()

    def copiar(self) -> None:
        QApplication.clipboard().setText(self.toPlainText())

    def _redesenhar(self) -> None:
        with self._trava:
            todas = list(self._linhas)
            self._pendentes.clear()   # já entram no redesenho
        self.setPlainText("\n".join(formatar_linha(linha.msg) for linha in todas if self._passa(linha)))
        self._rolar_para_o_fim()

    def clear(self) -> None:  # noqa: D401 -- o `clear` do Qt, que as telas chamam
        """Limpa a tela E as linhas guardadas. A contagem (`marca`) continua."""
        with self._trava:
            self._linhas.clear()
            self._pendentes.clear()
        super().clear()

    # -- desenho -----------------------------------------------------------------
    def _rolar_para_o_fim(self) -> None:
        rolagem = self.verticalScrollBar()
        rolagem.setValue(rolagem.maximum())

    def _posicionar_barra(self) -> None:
        vista = self.viewport().geometry()
        self.barra.setGeometry(0, vista.bottom() + 1, vista.right() + 1, ALTURA_BARRA)

    def viewportEvent(self, evento) -> bool:  # noqa: N802 -- nome do Qt
        # A vista muda de tamanho com a janela e quando a barra de rolagem
        # aparece: a barra do filtro acompanha, sem cobrir a de rolagem.
        if evento.type() == QEvent.Type.Resize:
            self._posicionar_barra()
        return super().viewportEvent(evento)
```

- [ ] **Step 9: folha (`sigft/app_qt/estilo.py`)**. Na última linha de `folha_de_estilo`,
  troque

```python
""" + _folha_e31(tema) + _folha_telas(tema)
```

  por

```python
""" + _folha_e31(tema) + _folha_telas(tema) + _folha_ferramentas(tema)
```

  e acrescente, logo antes de `def folha_da_splash`:

```python
def _folha_ferramentas(tema: str | None = None) -> str:
    """As ferramentas da etapa 1b (2026-10-21).

    * barra do console (`widgets/console.py`): a paleta ESCURA nos dois temas,
      porque ela fica dentro do console, que é escuro sempre.
    """
    e = tokens.ESCURO
    f = tokens.FONTE
    regras = [
        f"#barra_console {{ background: {e['console_fundo']}; }}",
        f"#barra_console QPushButton {{ background: transparent; color: {e['texto_suave']};"
        f" border: 1px solid transparent; border-radius: 4px; padding: 0 8px;"
        f" min-height: 18px; max-height: 18px; font-size: {f['legenda']}px; }}",
        f"#barra_console QPushButton:hover {{ color: {e['texto']}; }}",
        f"#barra_console QPushButton:checked {{ color: {e['texto']}; background: {e['superficie_alta']};"
        f" border-color: {e['borda']}; }}",
        f"#barra_console QLineEdit {{ background: {e['superficie_alta']}; color: {e['texto']};"
        f" border: 1px solid {e['borda']}; border-radius: 4px; padding: 0 6px;"
        f" min-height: 18px; max-height: 18px; font-size: {f['legenda']}px;"
        f" placeholder-text-color: {e['texto_suave']}; }}",
        f"#barra_console QLineEdit:focus {{ border-color: {e['primaria']}; }}",
    ]
    return "\n" + "\n".join(regras) + "\n"
```

- [ ] **Step 10:** `.venv/bin/python -m pytest -q tests/test_qt_console.py tests/test_niveis_log.py tests/test_qt_sem_cor_crua.py tests/test_texto_da_ui.py tests/test_qt_estilo.py` → PASS.
  Testes de medida (a altura do console não pode mudar):
  `.venv/bin/python -m pytest -q tests/test_qt_tela_*.py tests/test_pdm_tela_layout.py tests/test_qt_module_frame.py` → PASS.

- [ ] **Step 11:** `bash scripts/check.sh`; smoke. Commit:

```bash
git add sigft/app/busca.py sigft/app/niveis_log.py sigft/app_qt/widgets/console.py \
        sigft/app_qt/estilo.py tests/test_niveis_log.py tests/test_qt_console.py
git commit -m "Console: filtro Tudo/Avisos/Erros, busca e Copiar; marcas de nivel num lugar so"
```

---

### Task 2: Janela de resumo no fim do lote

**Files:**
- Create: `sigft/app/resumo_lote.py`
- Create: `sigft/app_qt/widgets/resumo_lote.py`
- Modify: `sigft/app_qt/widgets/module_frame.py` (`__init__`, `iniciar_tarefa`, `_tarefa_acabou`, dois métodos novos)
- Modify: `tests/conftest.py` (fixture autouse nova)
- Test: `tests/test_resumo_lote.py` (novo), `tests/test_qt_resumo_lote.py` (novo)

**Interfaces:**
- Consumes: `ConsoleFrame.marca()`, `ConsoleFrame.linhas(desde)`, `Linha.msg`, `Linha.nivel`,
  `niveis_log.ERRO/AVISO/INFO` (Task 1).
- Produces (sem Qt, `sigft/app/resumo_lote.py`): `ENV_DESLIGAR = "SIGFT_SEM_RESUMO_DO_LOTE"`;
  `SEM_CODIGO = "Sem código PMIB"`; `Grupo(codigo: str, linhas: tuple[tuple[str, str], ...])`
  com `.rotulo`; `ligado() -> bool`; `contagem(n, singular, plural) -> str`;
  `frase_da_contagem(erros: int, avisos: int) -> str`;
  `frase_do_fim(titulo: str, erros: int, avisos: int, *, falhou: bool = False) -> str`;
  `agrupar(pares: Iterable[tuple[str, str]]) -> list[Grupo]`; `contar(grupos) -> tuple[int, int]`;
  `texto_para_copiar(titulo: str, grupos) -> str`;
  `gravar_log(titulo: str, pares, pasta, agora: datetime) -> Path`.
- Produces (Qt): `widgets.resumo_lote.JanelaResumoDoLote(parent, titulo: str, pares)` com
  `rotulo`, `arvore`, `botao_copiar`, `botao_log`, `botao_fechar`, `copiar() -> str`,
  `abrir_log() -> Path | None`; `widgets.resumo_lote.abrir_resumo(tela, titulo, pares) -> JanelaResumoDoLote`.
- Produces (`ModuleFrame`): `titulo_da_tela: str`; `pares_do_lote() -> list[tuple[str, str]]`;
  `_fim_do_lote()` (a Task 7 acrescenta o aviso do Windows nele).

Decisões: agrupar pelo código PMIB completo da linha (`pmib_codes.find_pmib_code_in_text`);
linha repetida no mesmo grupo entra uma vez (o resumo do `RelatorioLote` repete as falhas);
linhas sem código vão para o grupo "Sem código PMIB", no fim. "Abrir log" grava TUDO o que
o lote escreveu no console (não só os problemas) em `Documentos\SIG-FT\logs\resumos\` e
abre o arquivo: a maioria dos módulos não tem log em arquivo próprio. O resumo só aparece
para tarefa que roda por `ModuleFrame.iniciar_tarefa`.

- [ ] **Step 1: testes sem Qt (`tests/test_resumo_lote.py`)**

```python
"""O resumo do fim do lote, sem Qt (2026-10-21, etapa 1b)."""
import os
from datetime import datetime

from sigft.app import niveis_log as n
from sigft.app import resumo_lote as r

PARES = [
    ("❌ 4500063671.0002: TimeoutError: sem resposta (1,2s)", n.ERRO),
    ("   [Aviso] 4500063671.0001: nao consegui ler o PDM atual.", n.AVISO),
    ("tudo certo", n.INFO),
    ("[ERRO] A lista de fichas do portal não respondeu.", n.ERRO),
    ("   [Erro] Ficha 4500063671.0002 não encontrada.", n.ERRO),
    ("   [Aviso] 4500063671.0001: nao consegui ler o PDM atual.", n.AVISO),   # repetida
]


def test_agrupa_por_codigo_na_ordem_e_sem_codigo_no_fim():
    grupos = r.agrupar(PARES)
    assert [g.rotulo for g in grupos] == ["4500063671.0002", "4500063671.0001", r.SEM_CODIGO]
    assert [t for t, _ in grupos[0].linhas] == [
        "❌ 4500063671.0002: TimeoutError: sem resposta (1,2s)",
        "[Erro] Ficha 4500063671.0002 não encontrada.",
    ]
    assert len(grupos[1].linhas) == 1            # a repetida entra uma vez
    assert grupos[2].linhas == (("[ERRO] A lista de fichas do portal não respondeu.", n.ERRO),)


def test_sem_problema_nao_ha_grupo():
    assert r.agrupar([("tudo certo", n.INFO)]) == []


def test_contagem_e_frases():
    assert r.contar(r.agrupar(PARES)) == (3, 1)
    assert r.frase_da_contagem(1, 0) == "1 erro"
    assert r.frase_da_contagem(0, 2) == "2 avisos"
    assert r.frase_da_contagem(2, 1) == "2 erros e 1 aviso"
    assert r.frase_do_fim("Upload duplicadas", 0, 0) == "Upload duplicadas terminou sem erro nem aviso."
    assert r.frase_do_fim("Upload duplicadas", 2, 1) == "Upload duplicadas terminou com 2 erros e 1 aviso."
    assert r.frase_do_fim("Upload duplicadas", 1, 0, falhou=True) == \
        "Upload duplicadas parou com erro. Veja o console."


def test_texto_para_copiar():
    texto = r.texto_para_copiar("Upload duplicadas", r.agrupar(PARES))
    linhas = texto.splitlines()
    assert linhas[0] == "Upload duplicadas: 3 erros e 1 aviso"
    assert linhas[2] == "4500063671.0002"
    assert linhas[3] == "  ❌ 4500063671.0002: TimeoutError: sem resposta (1,2s)"
    assert linhas[-1] == "  [ERRO] A lista de fichas do portal não respondeu."
    assert texto.endswith("\n")


def test_gravar_log_leva_tudo(tmp_path):
    caminho = r.gravar_log("Upload duplicadas", PARES, tmp_path / "resumos",
                           datetime(2026, 10, 21, 14, 5, 9))
    assert caminho.name == "Upload_duplicadas_2026-10-21_14-05-09.log"
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    assert linhas[0] == "Upload duplicadas: 21/10/2026 14:05:09"
    assert "> tudo certo" in linhas          # o log leva TUDO, não só os problemas


def test_desligado_pelo_ambiente(monkeypatch):
    monkeypatch.setenv(r.ENV_DESLIGAR, "1")
    assert not r.ligado()
    monkeypatch.delenv(r.ENV_DESLIGAR)
    assert r.ligado()


def test_os_testes_rodam_com_o_resumo_desligado():
    assert os.environ.get(r.ENV_DESLIGAR) == "1"   # tests/conftest.py
```

- [ ] **Step 2:** `.venv/bin/python -m pytest -q tests/test_resumo_lote.py` → falha (`ImportError`).

- [ ] **Step 3: `sigft/app/resumo_lote.py`**

```python
"""O resumo do fim do lote, sem Qt (2026-10-21, etapa 1b).

A janela de resumo (`app_qt/widgets/resumo_lote.py`) e o aviso do Windows leem
daqui: agrupar as linhas de erro e aviso pela ficha (o código PMIB da linha), o
texto do "Copiar lista", as frases e o arquivo do "Abrir log". Não depende de
cada serviço devolver um resultado (a maioria não devolve): lê o que já se loga,
com o nível de `niveis_log`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from sigft.app import niveis_log
from sigft.core.excel import pmib_codes
from sigft.core.log_execucao import nome_de_arquivo

# Os testes desligam a janela (tests/conftest.py): dezenas de testes de tela rodam
# tarefa com erro DE PROPÓSITO, e cada um deixaria uma janela por cima do seguinte.
ENV_DESLIGAR = "SIGFT_SEM_RESUMO_DO_LOTE"
SEM_CODIGO = "Sem código PMIB"


@dataclass(frozen=True)
class Grupo:
    codigo: str                              # "" = as linhas sem código PMIB
    linhas: tuple[tuple[str, str], ...]      # (texto, nível)

    @property
    def rotulo(self) -> str:
        return self.codigo or SEM_CODIGO


def ligado() -> bool:
    return not os.environ.get(ENV_DESLIGAR)


def contagem(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def frase_da_contagem(erros: int, avisos: int) -> str:
    partes = []
    if erros:
        partes.append(contagem(erros, "erro", "erros"))
    if avisos:
        partes.append(contagem(avisos, "aviso", "avisos"))
    return " e ".join(partes) if partes else "nenhum erro nem aviso"


def frase_do_fim(titulo: str, erros: int, avisos: int, *, falhou: bool = False) -> str:
    """A frase do aviso do Windows no fim da tarefa."""
    if falhou:
        return f"{titulo} parou com erro. Veja o console."
    if erros or avisos:
        return f"{titulo} terminou com {frase_da_contagem(erros, avisos)}."
    return f"{titulo} terminou sem erro nem aviso."


def agrupar(pares: Iterable[tuple[str, str]]) -> list[Grupo]:
    """As linhas de erro e aviso de `pares` (texto, nível), por código PMIB, na
    ordem em que cada código apareceu; as sem código no fim. Linha repetida no
    mesmo grupo entra uma vez."""
    por_codigo: dict[str, list[tuple[str, str]]] = {}
    vistos: set[tuple[str, str]] = set()
    for texto, nivel in pares:
        if nivel == niveis_log.INFO:
            continue
        texto = str(texto).strip()
        codigo = pmib_codes.find_pmib_code_in_text(texto) or ""
        if (codigo, texto) in vistos:
            continue
        vistos.add((codigo, texto))
        por_codigo.setdefault(codigo, []).append((texto, nivel))
    grupos = [Grupo(codigo, tuple(linhas)) for codigo, linhas in por_codigo.items() if codigo]
    if "" in por_codigo:
        grupos.append(Grupo("", tuple(por_codigo[""])))
    return grupos


def contar(grupos: Iterable[Grupo]) -> tuple[int, int]:
    """(erros, avisos) dos grupos."""
    niveis = [nivel for grupo in grupos for _texto, nivel in grupo.linhas]
    return niveis.count(niveis_log.ERRO), niveis.count(niveis_log.AVISO)


def texto_para_copiar(titulo: str, grupos: list[Grupo]) -> str:
    erros, avisos = contar(grupos)
    linhas = [f"{titulo}: {frase_da_contagem(erros, avisos)}", ""]
    for grupo in grupos:
        linhas.append(grupo.rotulo)
        linhas += [f"  {texto}" for texto, _nivel in grupo.linhas]
        linhas.append("")
    return "\n".join(linhas).rstrip("\n") + "\n"


def gravar_log(titulo: str, pares, pasta, agora: datetime) -> Path:
    """Tudo o que o lote escreveu no console, num arquivo em `pasta` (criada se
    faltar), com o nome de `log_execucao.nome_de_arquivo`."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / nome_de_arquivo(titulo, agora)
    corpo = [f"{titulo}: {agora:%d/%m/%Y %H:%M:%S}", ""] + [f"> {texto}" for texto, _nivel in pares]
    caminho.write_text("\n".join(corpo) + "\n", encoding="utf-8")
    return caminho
```

- [ ] **Step 4: conftest.** Em `tests/conftest.py`, logo depois da fixture
  `_revisao_antes_do_portal_nao_trava`, acrescente:

```python
# 6. [2026-10-21] A janela de resumo do fim do lote (`app_qt/widgets/resumo_lote`)
#    abre sozinha quando uma tarefa escreve erro ou aviso no console. Dezenas de
#    testes de tela rodam tarefa com erro DE PROPÓSITO; sem esta guarda, cada um
#    deixaria uma janela aberta por cima do seguinte. Quem testa a janela tira a
#    variável (`monkeypatch.delenv`). O nome é `sigft.app.resumo_lote.ENV_DESLIGAR`
#    (teste em tests/test_resumo_lote.py).
@pytest.fixture(autouse=True)
def _sem_janelas_do_fim_da_tarefa(monkeypatch):
    monkeypatch.setenv("SIGFT_SEM_RESUMO_DO_LOTE", "1")
```

- [ ] **Step 5:** `.venv/bin/python -m pytest -q tests/test_resumo_lote.py` → PASS.

- [ ] **Step 6: testes Qt (`tests/test_qt_resumo_lote.py`)**

```python
"""A janela de resumo do fim do lote e o gancho no ModuleFrame (2026-10-21, etapa 1b)."""
import pytest
from PySide6.QtWidgets import QApplication

from sigft.app import resumo_lote as r
from sigft.app_qt.widgets import resumo_lote as janela_mod
from sigft.app_qt.widgets.module_frame import ModuleFrame


class Tela(ModuleFrame):
    def _build_ui(self):
        pass


@pytest.fixture
def abertos(monkeypatch):
    lista = []
    monkeypatch.setattr(janela_mod, "abrir_resumo",
                        lambda tela, titulo, pares: lista.append((titulo, pares)))
    return lista


def _rodar(qtbot, tela, linhas):
    def alvo():
        for msg, nivel in linhas:
            tela.log(msg, nivel)
    tela.iniciar_tarefa(alvo).join(3)
    qtbot.waitUntil(lambda: tela._tarefas_rodando == 0, timeout=2000)


def test_tarefa_com_erro_abre_o_resumo_so_com_as_linhas_dela(qt_interface, qtbot, monkeypatch, abertos):
    monkeypatch.delenv(r.ENV_DESLIGAR)
    tela = Tela(titulo="Upload duplicadas")
    qtbot.addWidget(tela)
    tela.log("[Erro] de uma tarefa anterior")
    _rodar(qtbot, tela, [("começou", "info"), ("[Erro] Ficha 4500063671.0001 não encontrada", "info")])
    assert abertos == [("Upload duplicadas", [("começou", "info"),
                                              ("[Erro] Ficha 4500063671.0001 não encontrada", "erro")])]


def test_tarefa_limpa_nao_abre(qt_interface, qtbot, monkeypatch, abertos):
    monkeypatch.delenv(r.ENV_DESLIGAR)
    tela = Tela(titulo="x")
    qtbot.addWidget(tela)
    _rodar(qtbot, tela, [("tudo certo", "info")])
    assert abertos == []


def test_nos_testes_nao_abre_sem_pedir(qt_interface, qtbot, abertos):
    tela = Tela(titulo="x")
    qtbot.addWidget(tela)
    _rodar(qtbot, tela, [("[ERRO] ruim", "info")])
    assert abertos == []


def test_janela_agrupa_copia_e_abre_o_log(qt_interface, qtbot, monkeypatch, tmp_path):
    abertos_no_sistema = []
    monkeypatch.setattr(janela_mod.plataforma, "abrir_no_sistema", abertos_no_sistema.append)
    monkeypatch.setattr(janela_mod, "pasta_logs", lambda: tmp_path)
    pares = [("tudo certo", "info"), ("[Erro] Ficha 4500063671.0001 não encontrada", "erro"),
             ("[Aviso] sem código", "aviso")]
    j = janela_mod.JanelaResumoDoLote(None, "Upload duplicadas", pares)
    qtbot.addWidget(j)
    assert j.windowTitle() == "Resumo: Upload duplicadas"
    assert j.rotulo.text() == "Terminou com 1 erro e 1 aviso."
    topo = [j.arvore.topLevelItem(i).text(0) for i in range(j.arvore.topLevelItemCount())]
    assert topo == ["4500063671.0001 (1)", "Sem código PMIB (1)"]
    j.botao_copiar.click()
    assert QApplication.clipboard().text() == r.texto_para_copiar("Upload duplicadas", r.agrupar(pares))
    j.botao_log.click()
    assert len(abertos_no_sistema) == 1
    assert abertos_no_sistema[0].parent == tmp_path / janela_mod.PASTA_DOS_RESUMOS
    assert "> tudo certo" in abertos_no_sistema[0].read_text(encoding="utf-8")


def test_abrir_resumo_mostra_a_janela(qt_interface, qtbot):
    tela = Tela(titulo="x")
    qtbot.addWidget(tela)
    j = janela_mod.abrir_resumo(tela, "x", [("[Erro] a", "erro")])
    assert j.isVisible()
    j.close()
```

- [ ] **Step 7:** `.venv/bin/python -m pytest -q tests/test_qt_resumo_lote.py` → falha (`ImportError`).

- [ ] **Step 8: `sigft/app_qt/widgets/resumo_lote.py`**

```python
"""A janela "Resumo" do fim do lote (2026-10-21, etapa 1b).

Abre sozinha quando a ÚLTIMA tarefa da tela acaba e ela escreveu erro ou aviso no
console (`ModuleFrame._fim_do_lote`); tarefa limpa fica só com a faixa
"Terminou". As linhas vêm agrupadas pela ficha (o código PMIB da linha); a regra
mora em `sigft/app/resumo_lote.py`.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QMessageBox, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from sigft.app import niveis_log, resumo_lote
from sigft.app_qt import estilo
from sigft.app_qt.widgets import blocos
from sigft.core import plataforma
from sigft.core.dados_usuario import pasta_logs

TEXTO_COPIAR = "Copiar lista"
TEXTO_COPIADO = "Copiado"
TEXTO_LOG = "Abrir log"
TEXTO_FECHAR = "Fechar"
DICA_COPIAR = "Copia a lista agrupada por ficha, para colar num e-mail ou numa planilha."
DICA_LOG = "Grava num arquivo tudo o que esta tarefa escreveu no console e abre o arquivo."
PASTA_DOS_RESUMOS = "resumos"
MS_DO_COPIADO = 1500


class JanelaResumoDoLote(QDialog):
    def __init__(self, parent, titulo: str, pares) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(f"Resumo: {titulo}")
        self.resize(760, 480)
        self._titulo = titulo
        self._pares = [(str(texto), nivel) for texto, nivel in pares]
        self.grupos = resumo_lote.agrupar(self._pares)
        erros, avisos = resumo_lote.contar(self.grupos)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        self.rotulo = blocos.rotulo(f"Terminou com {resumo_lote.frase_da_contagem(erros, avisos)}.",
                                    tamanho=15, negrito=True, alinhar="esquerda")
        lay.addWidget(self.rotulo)

        self.arvore = QTreeWidget()
        self.arvore.setHeaderHidden(True)
        for grupo in self.grupos:
            pai = QTreeWidgetItem([f"{grupo.rotulo} ({len(grupo.linhas)})"])
            for texto, nivel in grupo.linhas:
                filho = QTreeWidgetItem([texto])
                papel = "perigo" if nivel == niveis_log.ERRO else "aviso"
                filho.setForeground(0, QBrush(QColor(estilo.cor_do_papel(papel))))
                filho.setToolTip(0, texto)
                pai.addChild(filho)
            self.arvore.addTopLevelItem(pai)
            pai.setExpanded(True)
        lay.addWidget(self.arvore, 1)

        linha = QHBoxLayout()
        linha.setSpacing(8)
        self.botao_copiar = blocos.botao(TEXTO_COPIAR, variante="secundario")
        self.botao_copiar.setToolTip(DICA_COPIAR)
        self.botao_copiar.clicked.connect(self.copiar)
        self.botao_log = blocos.botao(TEXTO_LOG, variante="secundario")
        self.botao_log.setToolTip(DICA_LOG)
        self.botao_log.clicked.connect(self.abrir_log)
        self.botao_fechar = blocos.botao(TEXTO_FECHAR, variante="primario")
        self.botao_fechar.clicked.connect(self.close)
        linha.addWidget(self.botao_copiar)
        linha.addWidget(self.botao_log)
        linha.addStretch()
        linha.addWidget(self.botao_fechar)
        lay.addLayout(linha)

        self._volta = QTimer(self)
        self._volta.setSingleShot(True)
        self._volta.timeout.connect(self._texto_do_copiar)

    def copiar(self) -> str:
        texto = resumo_lote.texto_para_copiar(self._titulo, self.grupos)
        QApplication.clipboard().setText(texto)
        self.botao_copiar.setText(TEXTO_COPIADO)
        self._volta.start(MS_DO_COPIADO)
        return texto

    def _texto_do_copiar(self) -> None:
        self.botao_copiar.setText(TEXTO_COPIAR)

    def abrir_log(self):
        try:
            caminho = resumo_lote.gravar_log(self._titulo, self._pares,
                                             pasta_logs() / PASTA_DOS_RESUMOS, datetime.now())
            plataforma.abrir_no_sistema(caminho)
        except Exception as erro:  # noqa: BLE001 -- vira aviso, a janela segue
            QMessageBox.warning(self, TEXTO_LOG, f"Não consegui abrir o log: {erro}")
            return None
        return caminho


def abrir_resumo(tela, titulo: str, pares) -> JanelaResumoDoLote:
    """Abre (sem prender ninguém: a tarefa já acabou) e devolve a janela."""
    janela = JanelaResumoDoLote(tela, titulo, pares)
    janela.show()
    janela.raise_()
    return janela
```

- [ ] **Step 9: `ModuleFrame` (`sigft/app_qt/widgets/module_frame.py`)**

  Imports: troque `from sigft.app import backends, textos_dicas, theme` por

```python
from sigft.app import backends, textos_dicas, theme
from sigft.app import resumo_lote as resumo_regras
```

  e acrescente, depois de `from sigft.app_qt.widgets.espera import DialogosDeEspera`:

```python
from sigft.app_qt.widgets import resumo_lote as janela_de_resumo
```

  Em `__init__`, depois de `self.embutida = embutida`:

```python
        # O nome que o resumo e o aviso do Windows dão à tela (2026-10-21).
        self.titulo_da_tela = titulo
```

  e troque

```python
        self._tarefas_rodando = 0
        self._tarefa_falhou = False
```

  por

```python
        self._tarefas_rodando = 0
        self._tarefa_falhou = False
        # A linha do console em que o lote atual começou (`console.marca`).
        self._marca_console = 0
```

  Em `iniciar_tarefa`, troque

```python
        if self._tarefas_rodando == 0:
            self._tarefa_falhou = False
            self.atividade.comecar()
```

  por

```python
        if self._tarefas_rodando == 0:
            self._tarefa_falhou = False
            self._marca_console = self.console.marca() if self.console is not None else 0
            self.atividade.comecar()
```

  Em `_tarefa_acabou`, troque

```python
            if self._tarefas_rodando == 0:
                self.atividade.terminar(ok=not self._tarefa_falhou)
```

  por

```python
            if self._tarefas_rodando == 0:
                self.atividade.terminar(ok=not self._tarefa_falhou)
                self._fim_do_lote()
```

  e acrescente, depois de `_tarefa_acabou`:

```python
    def pares_do_lote(self) -> list[tuple[str, str]]:
        """(mensagem, nível) do que o lote que acabou escreveu no console."""
        if self.console is None:
            return []
        return [(linha.msg, linha.nivel) for linha in self.console.linhas(desde=self._marca_console)]

    def _fim_do_lote(self) -> None:
        """Na thread da interface, quando a ÚLTIMA tarefa da tela acaba: com erro
        ou aviso no console, a janela de resumo (2026-10-21). Nunca levanta: o fim
        da tarefa já aconteceu, e um defeito aqui não pode prender o botão."""
        try:
            pares = self.pares_do_lote()
            grupos = resumo_regras.agrupar(pares)
            if grupos and resumo_regras.ligado():
                janela_de_resumo.abrir_resumo(self, self.titulo_da_tela, pares)
        except Exception:  # noqa: BLE001 -- vira traceback no log
            traceback.print_exc()
```

- [ ] **Step 10:** `.venv/bin/python -m pytest -q tests/test_qt_resumo_lote.py tests/test_resumo_lote.py tests/test_qt_module_frame.py tests/test_qt_atividade.py tests/test_qt_sem_cor_crua.py tests/test_texto_da_ui.py tests/test_qt_icones.py` → PASS.

- [ ] **Step 11:** `bash scripts/check.sh`; smoke. Commit:

```bash
git add sigft/app/resumo_lote.py sigft/app_qt/widgets/resumo_lote.py \
        sigft/app_qt/widgets/module_frame.py tests/conftest.py \
        tests/test_resumo_lote.py tests/test_qt_resumo_lote.py
git commit -m "Resumo do lote: janela com erros e avisos por ficha, Copiar lista e Abrir log"
```

---

### Task 3: Arrastar arquivo e "Últimos arquivos" (mecanismo e linhas de seleção)

**Files:**
- Modify: `sigft/core/prefs.py` (`_SECOES_ESTADO`; seção nova no fim do bloco "Preferências de texto")
- Modify: `sigft/app/file_dialogs.py` (entrega; extensões; recentes em `ask_open_file`/`ask_open_files`)
- Modify: `sigft/app_qt/file_dialogs.py` (expõe os nomes)
- Create: `sigft/app_qt/widgets/arrastar.py`
- Modify: `sigft/app_qt/widgets/pickers.py` (`FilePickerRow`, `MultiFilePickerRow`, `FileQueueList`)
- Modify: `sigft/app_qt/widgets/module_frame.py` (`ARRASTAVEIS`, `receptores_de_arquivo`)
- Modify: `sigft/app_qt/estilo.py` (`_folha_ferramentas`)
- Test: `tests/test_prefs_recentes.py` (novo), `tests/test_file_dialogs_entrega.py` (novo),
  `tests/test_qt_arrastar.py` (novo), `tests/test_prefs.py` (o teste da estrutura do JSON)

**Interfaces:**
- Produces (`prefs`): `CHAVE_RECENTES = "recentes"`, `LIMITE_RECENTES = 5`,
  `lembrar_recente(chave: str, caminho, *, config_path=None) -> None`,
  `recentes(chave: str, *, config_path=None) -> list[str]` (o mais novo primeiro; só os que existem).
- Produces (`sigft.app.file_dialogs` e os mesmos nomes em `sigft.app_qt.file_dialogs`):
  `entregar(chave: str, caminhos) -> None`, `descartar(chave: str) -> None`,
  `pendente(chave: str) -> tuple[str, ...] | None`,
  `extensoes_de(filetypes) -> tuple[str, ...] | None`, `extensao_aceita(caminho, extensoes) -> bool`.
- Produces (`arrastar`): `ACEITO = "aceito"`, `RECUSADO = "recusado"`, `TEXTO_SEM_RECENTES`,
  `DICA_ARRASTAR`; `Arrastavel(atributo: str, chave: str, extensoes: tuple[str, ...] | None, varios: bool = False)`;
  `Receptor` com `aceita(caminhos) -> bool`, `receber(caminhos) -> None`,
  `preencher_menu(menu) -> None`, `tem_recentes() -> bool`, `ligar_menu_de_contexto() -> None`;
  `MenuDeRecentes(receptor, pai=None)`; `botao_de_recentes(receptor) -> QToolButton`;
  `aceitar_arquivo(widget, chave, extensoes, ao_receber=None, *, varios=False, destaque=None, menu_de_contexto=False) -> Receptor`;
  `ligar_arrastaveis(tela, arrastaveis) -> dict[str, Receptor]`.
- Produces (`pickers`): `FilePickerRow.receptor`, `FilePickerRow.seta_recentes`
  (idem `MultiFilePickerRow`), `FileQueueList.receptor`.
- Produces (`ModuleFrame`): atributo de classe `ARRASTAVEIS: tuple = ()`; atributo
  `receptores_de_arquivo: dict[str, Receptor]`.

Como funciona (é o que deixa as telas sem mudança): soltar um arquivo (ou escolher um
recente) ENTREGA o arquivo para a chave do diálogo e clica o botão. O `selecionar_...`
da tela chama `ask_open_file(chave)` como sempre; a entrega é achada, o diálogo não abre,
e pasta e recentes são lembrados como numa escolha pelo diálogo. A entrega vale uma vez e
some depois do clique, usada ou não.

Decisões: a seta "▾" dos últimos arquivos fica ao lado do botão só na linha de seleção
(`FilePickerRow`), e **escondida quando não há recente** (nos testes os dados do usuário
são isolados: as medidas não mudam). Nos botões soltos das telas (Task 4) os últimos
arquivos ficam no **botão direito**, para não mexer em layout medido. A fila de fichas
(`FileQueueList`) aceita vários arquivos arrastados; sem menu de recentes.

- [ ] **Step 1: testes de `prefs` (`tests/test_prefs_recentes.py`)**

```python
"""Os últimos arquivos de cada diálogo (2026-10-21, etapa 1b)."""
import pytest

from sigft.core import prefs


@pytest.fixture
def config_path(tmp_path):
    return tmp_path / "user_prefs.json"


def _arquivo(tmp_path, nome):
    caminho = tmp_path / nome
    caminho.write_text("x", encoding="utf-8")
    return str(caminho)


def test_guarda_cinco_o_mais_novo_primeiro(tmp_path, config_path):
    arquivos = [_arquivo(tmp_path, f"f{i}.xlsx") for i in range(7)]
    for caminho in arquivos:
        prefs.lembrar_recente("k", caminho, config_path=config_path)
    assert prefs.recentes("k", config_path=config_path) == list(reversed(arquivos))[:prefs.LIMITE_RECENTES]


def test_repetido_sobe_e_nao_duplica(tmp_path, config_path):
    a, b = _arquivo(tmp_path, "a.xlsx"), _arquivo(tmp_path, "b.xlsx")
    for caminho in (a, b, a):
        prefs.lembrar_recente("k", caminho, config_path=config_path)
    assert prefs.recentes("k", config_path=config_path) == [a, b]


def test_o_que_sumiu_nao_aparece_e_as_chaves_sao_separadas(tmp_path, config_path):
    a = _arquivo(tmp_path, "a.xlsx")
    prefs.lembrar_recente("k", a, config_path=config_path)
    prefs.lembrar_recente("k", str(tmp_path / "sumiu.xlsx"), config_path=config_path)
    assert prefs.recentes("k", config_path=config_path) == [a]
    assert prefs.recentes("outra", config_path=config_path) == []


def test_nao_apaga_as_outras_secoes(tmp_path, config_path):
    prefs.gravar_preferencia("tema", "claro", config_path=config_path)
    prefs.lembrar_recente("k", _arquivo(tmp_path, "a.xlsx"), config_path=config_path)
    assert prefs.ler_preferencia("tema", "escuro", config_path=config_path) == "claro"


@pytest.mark.parametrize("bruto", ['{"recentes": {"k": "a.xlsx"}}', '{"recentes": []}',
                                   '{"recentes": {"k": [1, null]}}', "nao e json"])
def test_ilegivel_e_vazio(config_path, bruto):
    config_path.write_text(bruto, encoding="utf-8")
    assert prefs.recentes("k", config_path=config_path) == []
```

- [ ] **Step 2:** `.venv/bin/python -m pytest -q tests/test_prefs_recentes.py` → falha
  (`AttributeError: module 'sigft.core.prefs' has no attribute 'lembrar_recente'`).

- [ ] **Step 3: `sigft/core/prefs.py`.** Troque

```python
_SECOES_ESTADO = ("ultimos", "categorias", "pastas_padrao", "arquivos", "opcoes", "novidades",
                  "preferencias")
```

  por

```python
_SECOES_ESTADO = ("ultimos", "categorias", "pastas_padrao", "arquivos", "opcoes", "novidades",
                  "preferencias", "recentes")
```

  e acrescente, logo depois de `gravar_preferencia` (antes do bloco "Última versão do app"):

```python
# =============================================================================
# Últimos arquivos de cada diálogo  [2026-10-21]
# =============================================================================
# O menu "Últimos arquivos" ao lado do botão que abre o diálogo (etapa 1b do
# sistema visual): até `LIMITE_RECENTES` caminhos COMPLETOS por chave de
# diálogo, o mais novo primeiro. Mesma lição do "arquivos" de 2026-09-03: a seção
# está em `_SECOES_ESTADO`, senão some ao carregar. Arquivo que sumiu do disco
# não aparece (o caminho fica gravado: pode ser um Box que ainda não sincronizou).
CHAVE_RECENTES = "recentes"
LIMITE_RECENTES = 5


def lembrar_recente(
    chave: str,
    caminho: str | os.PathLike[str],
    *,
    config_path: str | os.PathLike[str] | None = None,
) -> None:
    """Põe `caminho` no topo dos recentes de `chave` (sem repetir)."""
    if not caminho:
        return
    caminho = str(caminho)
    estado = _carregar_estado(config_path)
    secao = estado.setdefault(CHAVE_RECENTES, {})
    anteriores = secao.get(chave)
    lista = [c for c in anteriores if isinstance(c, str) and c] if isinstance(anteriores, list) else []
    lista = [caminho] + [c for c in lista if os.path.normcase(c) != os.path.normcase(caminho)]
    secao[chave] = lista[:LIMITE_RECENTES]
    _salvar_estado(estado, config_path)


def recentes(
    chave: str,
    *,
    config_path: str | os.PathLike[str] | None = None,
) -> list[str]:
    """Os recentes de `chave` que ainda existem, o mais novo primeiro."""
    valor = _carregar_estado(config_path).get(CHAVE_RECENTES, {}).get(chave)
    if not isinstance(valor, list):
        return []
    return [c for c in valor if isinstance(c, str) and c and os.path.isfile(c)]
```

  E em `tests/test_prefs.py`, no `test_persistencia_estrutura_completa_do_json_apos_uso_combinado`:
  acrescente ao comentário a linha `# [2026-10-21] "recentes" entrou com `lembrar_recente` -- os últimos arquivos de cada diálogo.`,
  troque o `assert set(bruto.keys()) == {...}` por

```python
    assert set(bruto.keys()) == {"ultimos", "categorias", "pastas_padrao", "arquivos", "opcoes",
                                 "novidades", "preferencias", "recentes"}
```

  e, no dict do `assert bruto == {`, acrescente `"recentes": {},` depois de `"preferencias": {},`.

- [ ] **Step 4:** `.venv/bin/python -m pytest -q tests/test_prefs_recentes.py tests/test_prefs.py` → PASS.

- [ ] **Step 5: testes da entrega (`tests/test_file_dialogs_entrega.py`)**

```python
"""Arquivo entregue sem diálogo: o caminho do arrastar e dos recentes (2026-10-21)."""
import pytest

from sigft.app import file_dialogs
from sigft.core import prefs


def _nao_abre(**_):
    raise AssertionError("o diálogo não devia abrir")


@pytest.fixture
def config_path(tmp_path):
    return tmp_path / "user_prefs.json"


def test_entregue_volta_sem_dialogo_e_vira_recente(tmp_path, config_path):
    arquivo = tmp_path / "STATUS.xlsx"
    arquivo.write_text("x", encoding="utf-8")
    file_dialogs.entregar("k", [str(arquivo)])
    assert file_dialogs.ask_open_file("k", "excel", dialog_fn=_nao_abre, config_path=config_path) == str(arquivo)
    assert prefs.recentes("k", config_path=config_path) == [str(arquivo)]
    assert prefs.get_initial_dir("k", "excel", config_path=config_path) == str(tmp_path)
    # a entrega vale UMA vez
    assert file_dialogs.pendente("k") is None
    assert file_dialogs.ask_open_file("k", "excel", dialog_fn=lambda **_: "", config_path=config_path) == ""


def test_entrega_de_uma_chave_nao_vale_para_outra(config_path):
    file_dialogs.entregar("a", ["/x.xlsx"])
    try:
        assert file_dialogs.ask_open_file("b", "excel", dialog_fn=lambda **_: "", config_path=config_path) == ""
        assert file_dialogs.pendente("a") == ("/x.xlsx",)
    finally:
        file_dialogs.descartar("a")
    assert file_dialogs.pendente("a") is None


def test_varios_entregues_e_recentes_na_ordem(tmp_path, config_path):
    a, b = tmp_path / "a.xlsx", tmp_path / "b.xlsx"
    for p in (a, b):
        p.write_text("x", encoding="utf-8")
    file_dialogs.entregar("k", [str(a), str(b)])
    assert file_dialogs.ask_open_files("k", "excel", dialog_fn=_nao_abre, config_path=config_path) == (str(a), str(b))
    assert prefs.recentes("k", config_path=config_path) == [str(a), str(b)]


def test_escolha_pelo_dialogo_tambem_vira_recente(tmp_path, config_path):
    arquivo = tmp_path / "a.xlsx"
    arquivo.write_text("x", encoding="utf-8")
    file_dialogs.ask_open_file("k", "excel", dialog_fn=lambda **_: str(arquivo), config_path=config_path)
    assert prefs.recentes("k", config_path=config_path) == [str(arquivo)]


@pytest.mark.parametrize("filetypes, esperado", [
    ([("Excel", "*.xlsx;*.xlsm")], (".xlsx", ".xlsm")),
    ([("Excel", "*.xlsx *.xls")], (".xlsx", ".xls")),
    ([("Docs", "*.pdf *.txt")], (".pdf", ".txt")),
    ([("Texto", "*.txt"), ("Todos", "*.*")], None),
    (None, None),
])
def test_extensoes_de(filetypes, esperado):
    assert file_dialogs.extensoes_de(filetypes) == esperado


def test_extensao_aceita():
    assert file_dialogs.extensao_aceita("C:/pasta/STATUS.XLSX", (".xlsx",))
    assert not file_dialogs.extensao_aceita("manual.pdf", (".xlsx", ".xlsm"))
    assert file_dialogs.extensao_aceita("qualquer.bin", None)
```

- [ ] **Step 6:** `.venv/bin/python -m pytest -q tests/test_file_dialogs_entrega.py` → falha (`AttributeError: ... 'entregar'`).

- [ ] **Step 7: `sigft/app/file_dialogs.py`.** Acrescente depois de `_eh_vazio`:

```python
# --- arquivo entregue sem diálogo  [2026-10-21] -------------------------------
# Arrastar um arquivo para o botão, ou escolher um dos "Últimos arquivos", faz a
# tela receber o arquivo SEM abrir o diálogo, pelo mesmo caminho do clique: quem
# recebeu entrega (`entregar`) e clica o botão; o `ask_open_file(chave)` do clique
# acha a entrega e devolve o arquivo como se a pessoa o tivesse escolhido
# (lembrando pasta e recentes). Assim nenhuma tela muda o seu `selecionar_...`.
# Quem entrega descarta depois do clique (`descartar`): a entrega vale uma vez.
_entregues: dict[str, tuple[str, ...]] = {}


def entregar(chave: str, caminhos) -> None:
    _entregues[chave] = tuple(str(c) for c in caminhos)


def descartar(chave: str) -> None:
    _entregues.pop(chave, None)


def pendente(chave: str) -> tuple[str, ...] | None:
    """A entrega que espera o `ask_open_file(chave)`, se houver."""
    return _entregues.get(chave)


def extensoes_de(filetypes) -> tuple[str, ...] | None:
    """`[("Excel", "*.xlsx;*.xlsm")]` -> `(".xlsx", ".xlsm")`. `"*.*"` ou nada:
    `None`, que aceita qualquer extensão."""
    if not filetypes:
        return None
    achadas: list[str] = []
    for _nome, padrao in filetypes:
        for parte in str(padrao).replace(";", " ").split():
            if parte in ("*", "*.*"):
                return None
            if parte.startswith("*."):
                achadas.append(parte[1:].lower())
    return tuple(dict.fromkeys(achadas)) or None


def extensao_aceita(caminho, extensoes) -> bool:
    """`extensoes=None` aceita qualquer uma; senão, sem olhar a caixa."""
    if extensoes is None:
        return True
    return os.path.splitext(str(caminho))[1].lower() in {e.lower() for e in extensoes}
```

  Em `ask_open_file`, troque

```python
    fn = _resolver_dialog_fn("ask_open_file", dialog_fn)
    initial = _resolver_initialdir(chave, categoria, initialdir, config_path=config_path)

    resultado = fn(initialdir=initial, title=titulo, filetypes=filetypes)
    if _eh_vazio(resultado):
        return ""

    caminho = str(resultado)
    prefs.remember_dir(chave, categoria, os.path.dirname(caminho), config_path=config_path)
    return caminho
```

  por

```python
    fn = _resolver_dialog_fn("ask_open_file", dialog_fn)
    entregue = _entregues.pop(chave, None)
    if entregue:
        resultado = entregue[0]
    else:
        initial = _resolver_initialdir(chave, categoria, initialdir, config_path=config_path)
        resultado = fn(initialdir=initial, title=titulo, filetypes=filetypes)
    if _eh_vazio(resultado):
        return ""

    caminho = str(resultado)
    prefs.remember_dir(chave, categoria, os.path.dirname(caminho), config_path=config_path)
    prefs.lembrar_recente(chave, caminho, config_path=config_path)
    return caminho
```

  Em `ask_open_files`, troque

```python
    fn = _resolver_dialog_fn("ask_open_files", dialog_fn)
    initial = _resolver_initialdir(chave, categoria, initialdir, config_path=config_path)

    resultado = fn(initialdir=initial, title=titulo, filetypes=filetypes)
    if _eh_vazio(resultado):
        return ()
```

  por

```python
    fn = _resolver_dialog_fn("ask_open_files", dialog_fn)
    entregue = _entregues.pop(chave, None)
    if entregue:
        resultado = entregue
    else:
        initial = _resolver_initialdir(chave, categoria, initialdir, config_path=config_path)
        resultado = fn(initialdir=initial, title=titulo, filetypes=filetypes)
    if _eh_vazio(resultado):
        return ()
```

  e troque

```python
    prefs.remember_dir(chave, categoria, os.path.dirname(caminhos[0]), config_path=config_path)
    return caminhos
```

  por

```python
    prefs.remember_dir(chave, categoria, os.path.dirname(caminhos[0]), config_path=config_path)
    # De trás para frente: o primeiro escolhido fica no topo dos recentes.
    for caminho in reversed(caminhos[:prefs.LIMITE_RECENTES]):
        prefs.lembrar_recente(chave, caminho, config_path=config_path)
    return caminhos
```

  Em `sigft/app_qt/file_dialogs.py`, depois de `from sigft.app import file_dialogs as _base`:

```python
# A entrega sem diálogo e as extensões (2026-10-21): os mesmos nomes para as telas.
entregar = _base.entregar
descartar = _base.descartar
pendente = _base.pendente
extensoes_de = _base.extensoes_de
extensao_aceita = _base.extensao_aceita
```

- [ ] **Step 8:** `.venv/bin/python -m pytest -q tests/test_file_dialogs_entrega.py tests/test_file_dialogs.py tests/test_qt_file_dialogs.py` → PASS.

- [ ] **Step 9: testes Qt (`tests/test_qt_arrastar.py`)**

```python
"""Arrastar o arquivo para o botão e os "Últimos arquivos" (2026-10-21, etapa 1b)."""
import os

import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QPushButton

from sigft.app import tokens
from sigft.app_qt import estilo, file_dialogs
from sigft.app_qt.widgets import arrastar, pickers
from sigft.app_qt.widgets.module_frame import ModuleFrame
from sigft.core import prefs

COPIAR = Qt.DropAction.CopyAction
ESQUERDO = Qt.MouseButton.LeftButton
NADA = Qt.KeyboardModifier.NoModifier


def _mesmo(a, b):
    return os.path.normcase(os.path.normpath(str(a))) == os.path.normcase(os.path.normpath(str(b)))


def _nao_abre(**_):
    raise AssertionError("o diálogo não devia abrir")


def _arrastar(widget, *caminhos, soltar=True):
    """Entra, move e (se `soltar`) solta `caminhos` em `widget`. Devolve (mover, soltar)."""
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(c)) for c in caminhos])
    QApplication.sendEvent(widget, QDragEnterEvent(QPoint(5, 5), COPIAR, mime, ESQUERDO, NADA))
    mover = QDragMoveEvent(QPoint(6, 6), COPIAR, mime, ESQUERDO, NADA)
    QApplication.sendEvent(widget, mover)
    solta = None
    if soltar:
        solta = QDropEvent(QPointF(6, 6), COPIAR, mime, ESQUERDO, NADA)
        QApplication.sendEvent(widget, solta)
    return mover, solta


@pytest.fixture
def planilha(tmp_path):
    caminho = tmp_path / "STATUS.xlsx"
    caminho.write_text("x", encoding="utf-8")
    return caminho


class _Selecionar:
    """O `selecionar_...` de uma tela, sem mudança nenhuma: só chama o diálogo."""

    def __init__(self, chave, varios=False):
        self.chave, self.varios, self.recebidos = chave, varios, []

    def __call__(self):
        funcao = file_dialogs.ask_open_files if self.varios else file_dialogs.ask_open_file
        self.recebidos.append(funcao(self.chave, "excel", dialog_fn=lambda **_: ""))


def test_soltar_no_botao_entrega_sem_dialogo(qt_interface, qtbot, planilha):
    botao = QPushButton("Selecionar")
    qtbot.addWidget(botao)
    selecionar = _Selecionar("t.status")
    botao.clicked.connect(selecionar)
    arrastar.aceitar_arquivo(botao, "t.status", (".xlsx",))
    mover, solta = _arrastar(botao, planilha)
    assert mover.isAccepted() and solta.isAccepted()
    assert len(selecionar.recebidos) == 1 and _mesmo(selecionar.recebidos[0], planilha)
    assert botao.property("arrasto") == ""
    assert len(prefs.recentes("t.status")) == 1


def test_extensao_errada_fica_vermelho_e_nao_aceita(qt_interface, qtbot, tmp_path):
    pdf = tmp_path / "manual.pdf"
    pdf.write_text("x", encoding="utf-8")
    botao = QPushButton("Selecionar")
    qtbot.addWidget(botao)
    selecionar = _Selecionar("t.status")
    botao.clicked.connect(selecionar)
    arrastar.aceitar_arquivo(botao, "t.status", (".xlsx",))
    mover, _ = _arrastar(botao, pdf, soltar=False)
    assert botao.property("arrasto") == arrastar.RECUSADO
    assert not mover.isAccepted()
    QApplication.sendEvent(botao, QDragLeaveEvent())
    assert botao.property("arrasto") == ""
    _arrastar(botao, pdf)                 # soltar mesmo assim
    assert selecionar.recebidos == []


def test_dois_arquivos_so_onde_aceita_varios(qt_interface, qtbot, tmp_path):
    a, b = tmp_path / "a.xlsx", tmp_path / "b.xlsx"
    for p in (a, b):
        p.write_text("x", encoding="utf-8")
    um = QPushButton("um")
    varios = QPushButton("varios")
    for botao in (um, varios):
        qtbot.addWidget(botao)
    sel_um, sel_varios = _Selecionar("t.um"), _Selecionar("t.varios", varios=True)
    um.clicked.connect(sel_um)
    varios.clicked.connect(sel_varios)
    arrastar.aceitar_arquivo(um, "t.um", (".xlsx",))
    arrastar.aceitar_arquivo(varios, "t.varios", (".xlsx",), varios=True)
    _arrastar(um, a, b)
    _arrastar(varios, a, b)
    assert sel_um.recebidos == []
    assert len(sel_varios.recebidos[0]) == 2


def test_entrega_nao_sobra_se_a_tela_nao_pediu(qt_interface, qtbot, planilha):
    botao = QPushButton("x")                      # nenhum `clicked` ligado
    qtbot.addWidget(botao)
    arrastar.aceitar_arquivo(botao, "t.k", (".xlsx",)).receber([str(planilha)])
    assert file_dialogs.pendente("t.k") is None


def test_menu_de_recentes_entrega_o_escolhido(qt_interface, qtbot, planilha):
    prefs.lembrar_recente("t.k", str(planilha))
    botao = QPushButton("x")
    qtbot.addWidget(botao)
    selecionar = _Selecionar("t.k")
    botao.clicked.connect(selecionar)
    receptor = arrastar.aceitar_arquivo(botao, "t.k", (".xlsx",), menu_de_contexto=True)
    assert botao.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
    menu = arrastar.MenuDeRecentes(receptor)
    menu.aboutToShow.emit()
    assert [acao.text() for acao in menu.actions()] == ["STATUS.xlsx"]
    menu.actions()[0].trigger()
    assert len(selecionar.recebidos) == 1 and _mesmo(selecionar.recebidos[0], planilha)
    menu.deleteLater()


def test_menu_sem_recentes(qt_interface, qtbot):
    botao = QPushButton("x")
    qtbot.addWidget(botao)
    receptor = arrastar.aceitar_arquivo(botao, "t.nada", (".xlsx",))
    menu = arrastar.MenuDeRecentes(receptor)
    menu.aboutToShow.emit()
    assert [(a.text(), a.isEnabled()) for a in menu.actions()] == [(arrastar.TEXTO_SEM_RECENTES, False)]
    menu.deleteLater()


def test_linha_de_selecao_aceita_arrasto_e_mostra_a_seta(qt_interface, qtbot, planilha):
    avisos = []
    linha = pickers.FilePickerRow(chave="t.linha", categoria="excel", texto_botao="Selecionar",
                                  filetypes=[("Excel", "*.xlsx")], ao_escolher=avisos.append,
                                  dialog_fn=_nao_abre)
    qtbot.addWidget(linha)
    assert linha.seta_recentes.isHidden()        # sem recente: nada muda na linha
    _arrastar(linha, planilha)
    assert _mesmo(linha.valor, planilha)
    assert linha.botao.property("variante") == "primario"
    assert len(avisos) == 1
    assert not linha.seta_recentes.isHidden()


def test_linha_de_selecao_recusa_extensao(qt_interface, qtbot, tmp_path):
    pdf = tmp_path / "manual.pdf"
    pdf.write_text("x", encoding="utf-8")
    linha = pickers.FilePickerRow(chave="t.linha", categoria="excel", texto_botao="Selecionar",
                                  filetypes=[("Excel", "*.xlsx")], dialog_fn=_nao_abre)
    qtbot.addWidget(linha)
    _arrastar(linha, pdf, soltar=False)
    assert linha.botao.property("arrasto") == arrastar.RECUSADO
    QApplication.sendEvent(linha, QDragLeaveEvent())
    assert linha.valor is None


def test_fila_de_fichas_aceita_varios(qt_interface, qtbot, tmp_path):
    a, b = tmp_path / "a.xlsx", tmp_path / "b.xlsx"
    for p in (a, b):
        p.write_text("x", encoding="utf-8")
    fila = pickers.FileQueueList(chave="t.fila", filetypes=[("Excel", "*.xlsx")], dialog_fn=_nao_abre)
    qtbot.addWidget(fila)
    _arrastar(fila, a, b)
    assert [os.path.basename(c) for c in fila.arquivos] == ["a.xlsx", "b.xlsx"]


class _TelaComBotao(ModuleFrame):
    ARRASTAVEIS = (arrastar.Arrastavel("btn", "t.tela", (".xlsx",)),)

    def _build_ui(self):
        self.recebidos = []
        self.btn = QPushButton("Selecionar")
        self.content_layout.addWidget(self.btn)
        self.btn.clicked.connect(self._sel)

    def _sel(self):
        self.recebidos.append(file_dialogs.ask_open_file("t.tela", "excel", dialog_fn=lambda **_: ""))


def test_module_frame_liga_os_arrastaveis(qt_interface, qtbot, planilha):
    tela = _TelaComBotao(titulo="x")
    qtbot.addWidget(tela)
    tela.receptores_de_arquivo["btn"].receber([str(planilha)])
    assert tela.recebidos == [str(planilha)]
    assert arrastar.DICA_ARRASTAR in tela.btn.toolTip()


def test_arrastavel_com_nome_errado_falha_alto(qt_interface, qtbot):
    class Errada(_TelaComBotao):
        ARRASTAVEIS = (arrastar.Arrastavel("btn_que_nao_existe", "t.tela", (".xlsx",)),)

    with pytest.raises(AttributeError, match="btn_que_nao_existe"):
        Errada(titulo="x")


def test_folha_pinta_aceito_e_recusado():
    for tema in ("escuro", "claro"):
        p = tokens.paleta(tema)
        folha = estilo.folha_de_estilo(tema)
        assert ('QPushButton[arrasto="recusado"], QListWidget[arrasto="recusado"] '
                f'{{ border: 1px solid {p["perigo"]}; color: {p["perigo"]}; }}') in folha
        assert ('QPushButton[arrasto="aceito"], QListWidget[arrasto="aceito"] '
                f'{{ border: 1px solid {p["primaria"]}; }}') in folha
```

- [ ] **Step 10:** `.venv/bin/python -m pytest -q tests/test_qt_arrastar.py` → falha (`ImportError: cannot import name 'arrastar'`).

- [ ] **Step 11: `sigft/app_qt/widgets/arrastar.py`**

```python
"""Arrastar o arquivo para o botão, e os "Últimos arquivos" (2026-10-21, etapa 1b).

`aceitar_arquivo(widget, chave, extensoes, ao_receber)` liga um widget (o botão
que abre o diálogo, ou a linha `FilePickerRow`) a uma chave de diálogo. Soltar
um arquivo nele, ou escolher um dos últimos, ENTREGA o arquivo
(`file_dialogs.entregar`) e chama `ao_receber` (padrão: o clique do botão). O
`ask_open_file(chave)` do clique acha a entrega e não abre o diálogo
(`sigft/app/file_dialogs.py`): nenhuma tela muda o seu `selecionar_...`.
Extensão errada: o widget fica vermelho (`arrasto="recusado"`, cor da folha) e
o soltar não é aceito.

As telas que usam botão declaram `ARRASTAVEIS` (o `ModuleFrame` liga na
montagem, com os últimos arquivos no botão direito). Os sinais vão a métodos
ligados, nunca a lambda com a tela (mural de 2026-10-14).
"""
from __future__ import annotations

import os
from typing import NamedTuple

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QMenu, QToolButton

from sigft.app_qt import estilo, file_dialogs
from sigft.core import prefs

ACEITO = "aceito"
RECUSADO = "recusado"
TEXTO_SEM_RECENTES = "Nenhum arquivo recente"
DICA_ARRASTAR = "Dá para arrastar o arquivo até aqui. Botão direito: últimos arquivos."
SETA_RECENTES = "▾"
DICA_RECENTES = "Últimos arquivos usados aqui"


class Arrastavel(NamedTuple):
    """Um botão de tela que recebe arquivo: o atributo, a chave do diálogo que o
    `selecionar_...` dele usa, as extensões (`None`: qualquer) e se aceita vários."""
    atributo: str
    chave: str
    extensoes: tuple[str, ...] | None
    varios: bool = False


def caminhos_do_arrasto(mime) -> list[str]:
    """Os arquivos locais de um arrasto (do Explorer). Outro conteúdo: lista vazia."""
    if mime is None or not mime.hasUrls():
        return []
    return [url.toLocalFile() for url in mime.urls() if url.isLocalFile() and url.toLocalFile()]


class Receptor(QObject):
    """Filtro de eventos no `widget`: aceita o arrasto e entrega o arquivo."""

    def __init__(self, widget, chave: str, extensoes, ao_receber=None, *, varios: bool = False,
                 destaque=None) -> None:
        super().__init__(widget)
        self.widget = widget
        self.chave = chave
        self.extensoes = tuple(extensoes) if extensoes else None
        self.varios = varios
        self._ao_receber = ao_receber
        self.destaque = destaque if destaque is not None else widget
        self._ok = False
        widget.setAcceptDrops(True)
        widget.installEventFilter(self)

    def aceita(self, caminhos) -> bool:
        if not caminhos or (len(caminhos) > 1 and not self.varios):
            return False
        return all(os.path.isfile(c) and file_dialogs.extensao_aceita(c, self.extensoes) for c in caminhos)

    def receber(self, caminhos) -> None:
        """Entrega `caminhos` e chama `ao_receber` (o clique), como se a pessoa
        os tivesse escolhido no diálogo. A entrega não sobra para o próximo clique."""
        file_dialogs.entregar(self.chave, caminhos)
        try:
            (self._ao_receber or self.widget.click)()
        finally:
            file_dialogs.descartar(self.chave)

    def tem_recentes(self) -> bool:
        return bool(prefs.recentes(self.chave))

    def preencher_menu(self, menu: QMenu) -> None:
        menu.clear()
        lista = prefs.recentes(self.chave)
        if not lista:
            menu.addAction(TEXTO_SEM_RECENTES).setEnabled(False)
        for caminho in lista:
            acao = menu.addAction(os.path.basename(caminho))
            acao.setData(caminho)
            acao.setToolTip(caminho)

    def ligar_menu_de_contexto(self) -> None:
        self.widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.widget.customContextMenuRequested.connect(self._abrir_menu_de_contexto)

    def _abrir_menu_de_contexto(self, posicao) -> None:
        menu = MenuDeRecentes(self, self.widget)
        menu.exec(self.widget.mapToGlobal(posicao))
        menu.deleteLater()

    def _marcar(self, estado: str) -> None:
        estilo.definir_propriedade(self.destaque, "arrasto", estado)

    def eventFilter(self, obj, evento) -> bool:  # noqa: N802 -- nome do Qt
        if obj is not self.widget:
            return False
        tipo = evento.type()
        if tipo == QEvent.Type.DragEnter:
            caminhos = caminhos_do_arrasto(evento.mimeData())
            if not caminhos:
                return False
            self._ok = self.aceita(caminhos)
            self._marcar(ACEITO if self._ok else RECUSADO)
            # Aceito mesmo quando recusado: só assim chega o DragLeave que tira o
            # vermelho. Quem recusa de fato é o DragMove (cursor de proibido).
            evento.accept()
            return True
        if tipo == QEvent.Type.DragMove:
            if self._ok:
                evento.acceptProposedAction()
            else:
                evento.ignore()
            return True
        if tipo == QEvent.Type.DragLeave:
            self._marcar("")
            return False
        if tipo == QEvent.Type.Drop:
            self._marcar("")
            caminhos = caminhos_do_arrasto(evento.mimeData())
            if self._ok and self.aceita(caminhos):
                evento.acceptProposedAction()
                self.receber(caminhos)
            else:
                evento.ignore()
            self._ok = False
            return True
        return False


class MenuDeRecentes(QMenu):
    """O menu "Últimos arquivos" de um `Receptor`: refeito a cada abertura."""

    def __init__(self, receptor: Receptor, pai=None) -> None:
        super().__init__(pai)
        self._receptor = receptor
        self.aboutToShow.connect(self._preencher)
        self.triggered.connect(self._escolheu)

    def _preencher(self) -> None:
        self._receptor.preencher_menu(self)

    def _escolheu(self, acao) -> None:
        caminho = acao.data()
        if caminho:
            self._receptor.receber([caminho])


def botao_de_recentes(receptor: Receptor) -> QToolButton:
    """A setinha "▾" ao lado do botão, com o menu dos últimos arquivos."""
    seta = QToolButton()
    seta.setObjectName("seta_recentes")
    seta.setText(estilo.mono(SETA_RECENTES))
    seta.setToolTip(DICA_RECENTES)
    seta.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    seta.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    seta.setMenu(MenuDeRecentes(receptor, seta))
    return seta


def aceitar_arquivo(widget, chave: str, extensoes, ao_receber=None, *, varios: bool = False,
                    destaque=None, menu_de_contexto: bool = False) -> Receptor:
    receptor = Receptor(widget, chave, extensoes, ao_receber, varios=varios, destaque=destaque)
    if menu_de_contexto:
        receptor.ligar_menu_de_contexto()
    return receptor


def ligar_arrastaveis(tela, arrastaveis) -> dict[str, Receptor]:
    """Liga cada `Arrastavel` da tela ao seu botão (atributo que não existe: erro
    com o nome, que o `show_frame` mostra na tela de erro)."""
    receptores: dict[str, Receptor] = {}
    for item in arrastaveis:
        widget = getattr(tela, item.atributo, None)
        if widget is None:
            raise AttributeError(f"{type(tela).__name__}.ARRASTAVEIS: não há '{item.atributo}' na tela")
        receptores[item.atributo] = aceitar_arquivo(widget, item.chave, item.extensoes,
                                                    varios=item.varios, menu_de_contexto=True)
        dica = widget.toolTip()
        if DICA_ARRASTAR not in dica:
            widget.setToolTip(f"{dica}\n\n{DICA_ARRASTAR}" if dica else DICA_ARRASTAR)
    return receptores
```

- [ ] **Step 12: `sigft/app_qt/widgets/pickers.py`.** Troque

```python
from sigft.app_qt import file_dialogs
from sigft.app_qt import estilo
from sigft.app_qt.widgets import blocos
```

  por

```python
from sigft.app_qt import file_dialogs
from sigft.app_qt import estilo
from sigft.app_qt.widgets import arrastar, blocos
```

  Em `_LinhaSeletora`, acrescente depois de `_notificar`:

```python
    def _ligar_arrasto(self, chave: str, filetypes, *, varios: bool) -> None:
        """Arrastar arquivo para a linha e a seta dos últimos arquivos, ao lado do
        botão (2026-10-21). A seta só aparece quando há recente: sem recente a
        linha tem as medidas de sempre."""
        self.receptor = arrastar.aceitar_arquivo(self, chave, file_dialogs.extensoes_de(filetypes),
                                                 self._abrir_dialogo, varios=varios, destaque=self.botao)
        self.seta_recentes = arrastar.botao_de_recentes(self.receptor)
        self.layout().insertWidget(1, self.seta_recentes)
        self._mostrar_seta()

    def _mostrar_seta(self) -> None:
        self.seta_recentes.setVisible(self.receptor.tem_recentes())
```

  Em `FilePickerRow.__init__`, depois da chamada `super().__init__(...)`:

```python
        self._ligar_arrasto(chave, filetypes, varios=False)
```

  e em `FilePickerRow._abrir_dialogo`, troque

```python
        self.definir(caminho, os.path.basename(caminho))
        self._notificar()
```

  por

```python
        self.definir(caminho, os.path.basename(caminho))
        self._mostrar_seta()
        self._notificar()
```

  Em `MultiFilePickerRow.__init__`, depois de `super().__init__(...)`:

```python
        self._ligar_arrasto(chave, filetypes, varios=True)
```

  e em `MultiFilePickerRow._abrir_dialogo`, troque

```python
        self.definir(tuple(caminhos), f"{len(caminhos)} arquivos selecionados")
        self._notificar()
```

  por

```python
        self.definir(tuple(caminhos), f"{len(caminhos)} arquivos selecionados")
        self._mostrar_seta()
        self._notificar()
```

  Em `FileQueueList.__init__`, no fim (depois de `self.botao_limpar.clicked.connect(self.limpar)`):

```python
        # Arrastar várias fichas do Explorer para a fila (2026-10-21).
        self.receptor = arrastar.aceitar_arquivo(self, chave, file_dialogs.extensoes_de(filetypes),
                                                 self.adicionar, varios=True, destaque=self.listbox)
```

- [ ] **Step 13: `ModuleFrame`.** Acrescente `from sigft.app_qt.widgets import arrastar` aos
  imports; logo abaixo de `class ModuleFrame(DialogosDeEspera, QWidget):`:

```python
    # Os botões da tela que recebem arquivo arrastado (2026-10-21): tuplas
    # `arrastar.Arrastavel(atributo, chave, extensoes, varios)`. A tela só declara;
    # a montagem liga (`arrastar.ligar_arrastaveis`).
    ARRASTAVEIS: tuple = ()
```

  e troque

```python
        if construir:
            self._build_ui()
            aplicar_dicas(self)
```

  por

```python
        self.receptores_de_arquivo: dict = {}
        if construir:
            self._build_ui()
            aplicar_dicas(self)
            self.receptores_de_arquivo = arrastar.ligar_arrastaveis(self, self.ARRASTAVEIS)
```

- [ ] **Step 14: folha.** Em `estilo._folha_ferramentas`, troque o começo e a lista para:

```python
def _folha_ferramentas(tema: str | None = None) -> str:
    """As ferramentas da etapa 1b (2026-10-21).

    * barra do console (`widgets/console.py`): a paleta ESCURA nos dois temas,
      porque ela fica dentro do console, que é escuro sempre;
    * arrastar arquivo (`widgets/arrastar.py`): borda `primaria` quando o arquivo
      serve, `perigo` (borda e texto) quando não serve; a seta dos recentes.
    """
    tema = _tema(tema)
    p = tokens.paleta(tema)
    e = tokens.ESCURO
    f = tokens.FONTE
    regras = [
        f"#barra_console {{ background: {e['console_fundo']}; }}",
        f"#barra_console QPushButton {{ background: transparent; color: {e['texto_suave']};"
        f" border: 1px solid transparent; border-radius: 4px; padding: 0 8px;"
        f" min-height: 18px; max-height: 18px; font-size: {f['legenda']}px; }}",
        f"#barra_console QPushButton:hover {{ color: {e['texto']}; }}",
        f"#barra_console QPushButton:checked {{ color: {e['texto']}; background: {e['superficie_alta']};"
        f" border-color: {e['borda']}; }}",
        f"#barra_console QLineEdit {{ background: {e['superficie_alta']}; color: {e['texto']};"
        f" border: 1px solid {e['borda']}; border-radius: 4px; padding: 0 6px;"
        f" min-height: 18px; max-height: 18px; font-size: {f['legenda']}px;"
        f" placeholder-text-color: {e['texto_suave']}; }}",
        f"#barra_console QLineEdit:focus {{ border-color: {e['primaria']}; }}",
        # Arrastar arquivo: depois das variantes (mesma especificidade, esta ganha).
        f'QPushButton[arrasto="aceito"], QListWidget[arrasto="aceito"] {{ border: 1px solid {p["primaria"]}; }}',
        f'QPushButton[arrasto="recusado"], QListWidget[arrasto="recusado"] '
        f'{{ border: 1px solid {p["perigo"]}; color: {p["perigo"]}; }}',
        f'#seta_recentes {{ background: transparent; border: none; color: {p["texto_suave"]};'
        f' padding: 0 4px; font-size: {f["corpo"]}px; }}',
        f'#seta_recentes:hover {{ color: {p["texto"]}; }}',
        "#seta_recentes::menu-indicator { image: none; width: 0; }",
    ]
    return "\n" + "\n".join(regras) + "\n"
```

- [ ] **Step 15:** `.venv/bin/python -m pytest -q tests/test_qt_arrastar.py tests/test_qt_pickers.py tests/test_qt_fila_arquivos.py tests/test_qt_module_frame.py tests/test_qt_sem_cor_crua.py tests/test_texto_da_ui.py tests/test_qt_icones.py tests/test_prefs.py tests/test_file_dialogs.py` → PASS.
  Medidas (a seta escondida não pode mexer em nada):
  `.venv/bin/python -m pytest -q tests/test_qt_tela_*.py tests/test_qt_pickers.py::test_medidas_iguais_as_do_interface_antiga` → PASS.

- [ ] **Step 16:** `bash scripts/check.sh`; smoke. Commit:

```bash
git add sigft/core/prefs.py sigft/app/file_dialogs.py sigft/app_qt/file_dialogs.py \
        sigft/app_qt/widgets/arrastar.py sigft/app_qt/widgets/pickers.py \
        sigft/app_qt/widgets/module_frame.py sigft/app_qt/estilo.py \
        tests/test_prefs_recentes.py tests/test_prefs.py tests/test_file_dialogs_entrega.py \
        tests/test_qt_arrastar.py
git commit -m "Arrastar arquivo para a linha de selecao e ultimos 5 arquivos por dialogo"
```

---

### Task 4: Arrastar nos botões de arquivo das telas

**Files:**
- Modify: `sigft/app_qt/views/autospec.py`, `copia_fichas.py`, `correcao_pdm.py`, `cria_fichas.py`,
  `pdm.py`, `pmib_manager.py`, `upload_conditions.py`, `upload_tech_specs.py` (só um atributo
  de classe e um import em cada)
- Test: `tests/test_qt_arrastar_telas.py` (novo)

**Interfaces:**
- Consumes: `arrastar.Arrastavel`, `ModuleFrame.ARRASTAVEIS`, `ModuleFrame.receptores_de_arquivo`,
  `file_dialogs.pendente` (Task 3).

Fora de propósito: botão que **inicia** algo depois de abrir o diálogo (o "Iniciar" do
Tradutor e da LMR, o `_start_web_from_file` dos uploads, o "anexar" do Upload Condições):
soltar um arquivo ali subiria um robô. As telas com `FilePickerRow`/`FileQueueList`
(Analyzer, LMR, Apagar LMR, a fila dos uploads) já ganharam o arrasto na Task 3.

- [ ] **Step 1: teste (`tests/test_qt_arrastar_telas.py`)**

```python
"""Soltar o arquivo no botão de cada tela chega ao `selecionar_...` dela (2026-10-21)."""
import pytest

from sigft.app_qt import file_dialogs
from sigft.app_qt import main as qmain
from sigft.app_qt.views import (
    autospec, copia_fichas, correcao_pdm, cria_fichas, lmr, pdm, pmib_manager, translator,
    upload_conditions, upload_tech_specs,
)

# (tela em main.TELAS, botão, chave do diálogo, função de diálogo, uma extensão aceita)
CASOS = [
    ("AutoSpec", "btn_status", "autospec.status_pmib", "ask_open_file", ".xlsx"),
    ("AutoSpec", "btn_sheet", "autospec.ficha", "ask_open_file", ".xlsx"),
    ("AutoSpec", "btn_refs", "autospec.manuais", "ask_open_files", ".pdf"),
    ("AutoSpec", "btn_conf_importar", "autospec.conferencia", "ask_open_file", ".txt"),
    ("CopiaFichas", "btn_status", "copia_fichas.status_pmib", "ask_open_file", ".xlsm"),
    ("CorrecaoPDM", "btn_status", "correcao_pdm.status_pmib", "ask_open_file", ".xlsx"),
    ("CorrecaoPDM", "btn_catalogo", "correcao_pdm.sam_gm", "ask_open_file", ".xlsx"),
    ("CriaFichas", "btn_pmib", "cria_fichas.excel_pmib", "ask_open_file", ".xlsx"),
    ("CriaFichas", "btn_pdm", "cria_fichas.excel_pdm", "ask_open_file", ".xls"),
    ("CriaFichas", "btn_excel_edicao", "cria_fichas.excel_edicao", "ask_open_file", ".xlsx"),
    ("PDM", "btn_sam_gm", "pdm.sam_gm", "ask_open_file", ".xlsx"),
    ("PDM", "btn_pmib", "pdm.status_pmib", "ask_open_file", ".xlsx"),
    ("PDM", "btn_template", "pdm.template", "ask_open_file", ".xls"),
    ("PMIBManager", "btn_api", "pmib_manager.api", "ask_open_file", ".xlsx"),
    ("PMIBManager", "btn_master", "pmib_manager.master", "ask_open_file", ".xlsx"),
    ("PMIBManager", "btn_autorizados", "pmib_manager.autorizados", "ask_open_file", ".xlsx"),
    ("UploadConditions", "btn_status", "upload_conditions.status_pmib", "ask_open_file", ".xlsm"),
    ("UploadSpecs", "btn_status", "upload_tech_specs.status_pmib", "ask_open_file", ".xlsx"),
    ("UploadSpecs", "btn_master", "upload_tech_specs.master", "ask_open_file", ".xlsm"),
]

CLASSES = {
    "AutoSpec": autospec.ModuloAutoSpec, "CopiaFichas": copia_fichas.ModuloCopiaFichas,
    "CorrecaoPDM": correcao_pdm.ModuloCorrecaoPDM, "CriaFichas": cria_fichas.ModuloCriaFichas,
    "PDM": pdm.ModuloPDM, "PMIBManager": pmib_manager.ModuloPMIBManager,
    "UploadConditions": upload_conditions.ModuloUploadConditions,
    "UploadSpecs": upload_tech_specs.ModuloUploadTechSpecs,
}


@pytest.mark.parametrize("tela_chave, atributo, chave, funcao, extensao", CASOS)
def test_soltar_no_botao_chega_ao_selecionar_da_tela(qt_interface, qtbot, monkeypatch, tmp_path,
                                                    tela_chave, atributo, chave, funcao, extensao):
    arquivo = tmp_path / f"arquivo{extensao}"
    arquivo.write_text("x", encoding="utf-8")
    pedidos = []

    def falso(chave_pedida, _categoria, **_kwargs):
        pedidos.append((chave_pedida, file_dialogs.pendente(chave_pedida)))
        return () if funcao == "ask_open_files" else ""   # "cancelou": a tela para ali

    monkeypatch.setattr(file_dialogs, funcao, falso)
    tela = qmain.TELAS[tela_chave](None, None)
    qtbot.addWidget(tela)
    monkeypatch.setattr(tela, "backend", lambda _nome: object())
    getattr(tela, atributo).setEnabled(True)
    receptor = tela.receptores_de_arquivo[atributo]
    assert receptor.aceita([str(arquivo)])
    receptor.receber([str(arquivo)])
    assert pedidos == [(chave, (str(arquivo),))]


def test_casos_cobrem_todo_arrastavel_declarado():
    declarados = {(t, a.atributo, a.chave) for t, classe in CLASSES.items() for a in classe.ARRASTAVEIS}
    assert declarados == {(t, atributo, chave) for t, atributo, chave, _f, _e in CASOS}


def test_botao_que_inicia_robo_nao_aceita_arrasto():
    assert translator.ModuloTranslator.ARRASTAVEIS == ()
    assert lmr.ModuloLMR.ARRASTAVEIS == ()
```

- [ ] **Step 2:** `.venv/bin/python -m pytest -q tests/test_qt_arrastar_telas.py` → falha
  (`KeyError: 'btn_status'` em `receptores_de_arquivo`, e o teste de cobertura).

- [ ] **Step 3: declarar nas telas.** Em cada arquivo, acrescente
  `from sigft.app_qt.widgets.arrastar import Arrastavel` aos imports e, logo abaixo da
  linha `class ...:` (depois da docstring da classe, se houver), o atributo:

  `sigft/app_qt/views/autospec.py`, em `class ModuloAutoSpec(ModuleFrame):`

```python
    # Arrastar arquivo do Explorer para os botões (2026-10-21, etapa 1b).
    ARRASTAVEIS = (
        Arrastavel("btn_status", "autospec.status_pmib", (".xlsx",)),
        Arrastavel("btn_sheet", "autospec.ficha", (".xlsx",)),
        Arrastavel("btn_refs", "autospec.manuais", (".pdf", ".txt"), varios=True),
        Arrastavel("btn_conf_importar", "autospec.conferencia", (".txt",)),
    )
```

  `sigft/app_qt/views/copia_fichas.py`, em `class ModuloCopiaFichas(ModuleFrame):`

```python
    # Arrastar arquivo do Explorer para o botão (2026-10-21, etapa 1b).
    ARRASTAVEIS = (Arrastavel("btn_status", "copia_fichas.status_pmib", (".xlsx", ".xlsm")),)
```

  `sigft/app_qt/views/correcao_pdm.py`, em `class ModuloCorrecaoPDM(ModuleFrame):`

```python
    # Arrastar arquivo do Explorer para os botões (2026-10-21, etapa 1b).
    ARRASTAVEIS = (
        Arrastavel("btn_status", "correcao_pdm.status_pmib", (".xlsx", ".xlsm")),
        Arrastavel("btn_catalogo", "correcao_pdm.sam_gm", (".xlsx", ".xlsm")),
    )
```

  `sigft/app_qt/views/cria_fichas.py`, em `class ModuloCriaFichas(ModuleFrame):`

```python
    # Arrastar arquivo do Explorer para os botões (2026-10-21, etapa 1b).
    ARRASTAVEIS = (
        Arrastavel("btn_pmib", "cria_fichas.excel_pmib", (".xlsx",)),
        Arrastavel("btn_pdm", "cria_fichas.excel_pdm", (".xlsx", ".xls")),
        Arrastavel("btn_excel_edicao", "cria_fichas.excel_edicao", (".xlsx",)),
    )
```

  `sigft/app_qt/views/pdm.py`, em `class ModuloPDM(ModuleFrame):`

```python
    # Arrastar arquivo do Explorer para os botões (2026-10-21, etapa 1b).
    ARRASTAVEIS = (
        Arrastavel("btn_sam_gm", "pdm.sam_gm", (".xlsx", ".xls")),
        Arrastavel("btn_pmib", "pdm.status_pmib", (".xlsx", ".xls")),
        Arrastavel("btn_template", "pdm.template", (".xlsx", ".xls")),
    )
```

  `sigft/app_qt/views/pmib_manager.py`, em `class ModuloPMIBManager(ModuleFrame):`

```python
    # Arrastar arquivo do Explorer para os botões (2026-10-21, etapa 1b).
    ARRASTAVEIS = (
        Arrastavel("btn_api", "pmib_manager.api", (".xlsx", ".xls")),
        Arrastavel("btn_master", "pmib_manager.master", (".xlsx", ".xls")),
        Arrastavel("btn_autorizados", "pmib_manager.autorizados", (".xlsx",)),
    )
```

  `sigft/app_qt/views/upload_conditions.py`, em `class ModuloUploadConditions(TelaDeUpload):`

```python
    # Arrastar arquivo do Explorer para o botão (2026-10-21, etapa 1b).
    ARRASTAVEIS = (Arrastavel("btn_status", "upload_conditions.status_pmib", (".xlsx", ".xlsm")),)
```

  `sigft/app_qt/views/upload_tech_specs.py`, em `class ModuloUploadTechSpecs(TelaDeUpload):`

```python
    # Arrastar arquivo do Explorer para os botões (2026-10-21, etapa 1b).
    ARRASTAVEIS = (
        Arrastavel("btn_status", "upload_tech_specs.status_pmib", (".xlsx", ".xlsm")),
        Arrastavel("btn_master", "upload_tech_specs.master", (".xlsx", ".xlsm")),
    )
```

- [ ] **Step 4:** `.venv/bin/python -m pytest -q tests/test_qt_arrastar_telas.py` → PASS.
  Telas e AutoSpec (as invariantes do Rafael seguem):
  `.venv/bin/python -m pytest -q tests/test_qt_tela_*.py tests/test_autospec_conferencia_tela.py tests/test_autospec_auditoria_tela.py tests/test_qt_dicas.py tests/test_tela_*.py` → PASS.
  Se um teste de dica comparar o texto inteiro da dica de um destes botões, ele passa a
  esperar o texto + `"\n\n" + arrastar.DICA_ARRASTAR` (ajuste com o motivo na docstring).

- [ ] **Step 5:** `bash scripts/check.sh`; smoke (as 12 telas abrem: um atributo errado
  aparece como tela de erro). Commit:

```bash
git add sigft/app_qt/views/autospec.py sigft/app_qt/views/copia_fichas.py \
        sigft/app_qt/views/correcao_pdm.py sigft/app_qt/views/cria_fichas.py \
        sigft/app_qt/views/pdm.py sigft/app_qt/views/pmib_manager.py \
        sigft/app_qt/views/upload_conditions.py sigft/app_qt/views/upload_tech_specs.py \
        tests/test_qt_arrastar_telas.py
git commit -m "Telas: botoes de selecao de arquivo aceitam arrasto e ultimos arquivos no botao direito"
```

---

### Task 5: Ctrl+K (busca dos módulos e das ações)

**Files:**
- Modify: `sigft/app_qt/catalogo.py` (`Comando`, `ACOES`, `comandos`, `filtrar`)
- Create: `sigft/app_qt/widgets/paleta.py`
- Modify: `sigft/app_qt/main.py` (imports, `ACAO_NA_HOME`, atalho, `abrir_paleta`, `executar_comando`, `abrir_pasta_de_logs`, `_home_view`)
- Modify: `sigft/app_qt/estilo.py` (`_folha_ferramentas`: regras da paleta)
- Test: `tests/test_qt_paleta.py` (novo)

**Interfaces:**
- Consumes: `busca.normalizar` (Task 1); `catalogo.MENU`, `MODULOS`, `ICONE_DA_TELA`,
  `TELAS_BLOQUEADAS`; `HomeView.abrir_mural_atividades`, `abrir_janela_modelos_ia`,
  `abrir_janela_gastos_ia`, `abrir_janela_chaves_api`, `procurar_atualizacoes`, `escolher_tema(escolha)`.
- Produces: `catalogo.Comando(chave: str, texto: str, icone: str, palavras: str = "")`
  (chave `"tela:<alvo>"` ou `"acao:<chave>"`); `catalogo.ACOES: tuple[tuple[str, str, str, str], ...]`;
  `catalogo.comandos() -> list[Comando]`; `catalogo.filtrar(lista, consulta: str) -> list[Comando]`.
- Produces: `paleta.PaletaDeComandos(parent, comandos)` com sinal `escolheu(str)`, `campo`,
  `lista`, `vazio`, `escolher_atual()`, `abrir_sobre(janela)`.
- Produces: `main.ACAO_NA_HOME: dict[str, str]`; `SIG_FT_App.atalho_paleta: QShortcut`;
  `SIG_FT_App.abrir_paleta() -> PaletaDeComandos`; `SIG_FT_App.executar_comando(chave: str) -> None`;
  `SIG_FT_App.abrir_pasta_de_logs() -> None`; `SIG_FT_App._home_view() -> HomeView | None`.
  A Task 6 acrescenta `letra_normal`/`letra_grande`.

Decisão: a CorrecaoPDM (bloqueada no menu) fica fora da lista: o `show_frame` a recusaria.
São 11 módulos + as ações da Home.

- [ ] **Step 1: testes (`tests/test_qt_paleta.py`)**

```python
"""Ctrl+K: a caixa de busca dos módulos e das ações (2026-10-21, etapa 1b)."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence

from sigft.app_qt import catalogo, icones
from sigft.app_qt import main as qmain
from sigft.app_qt.widgets.paleta import PaletaDeComandos


def test_comandos_tem_os_modulos_liberados_e_as_acoes():
    chaves = [c.chave for c in catalogo.comandos()]
    modulos = [c for c in chaves if c.startswith("tela:")]
    assert len(modulos) == len(catalogo.MODULOS) - len(catalogo.TELAS_BLOQUEADAS)
    assert "tela:CorrecaoPDM" not in chaves
    assert {f"acao:{acao[0]}" for acao in catalogo.ACOES} <= set(chaves)
    assert len(chaves) == len(set(chaves))


def test_todo_icone_existe():
    assert {c.icone for c in catalogo.comandos()} <= icones.NOMES


@pytest.mark.parametrize("consulta, primeiro", [
    ("tradutor", "tela:Translator"),
    ("TRADUTOR", "tela:Translator"),
    ("condicoes", "tela:UploadConditions"),
    ("4.2", "tela:Translator"),
    ("tema claro", "acao:tema_claro"),
    ("chaves", "acao:chaves"),
    ("search", "tela:SearchPMIB"),
])
def test_filtra_sem_acento_e_sem_caixa(consulta, primeiro):
    assert catalogo.filtrar(catalogo.comandos(), consulta)[0].chave == primeiro


def test_vazio_mostra_tudo_e_nada_nao_mostra_nada():
    assert catalogo.filtrar(catalogo.comandos(), "") == catalogo.comandos()
    assert catalogo.filtrar(catalogo.comandos(), "xyzzy") == []


def _paleta(qtbot):
    escolhas = []
    p = PaletaDeComandos(None, catalogo.comandos())
    qtbot.addWidget(p)
    p.escolheu.connect(escolhas.append)
    p.show()
    return p, escolhas


def test_digitar_filtra_e_enter_escolhe(qt_interface, qtbot):
    p, escolhas = _paleta(qtbot)
    qtbot.keyClicks(p.campo, "tradu")
    assert p.lista.count() == 1 and p.lista.currentRow() == 0
    qtbot.keyClick(p.campo, Qt.Key.Key_Return)
    assert escolhas == ["tela:Translator"]
    assert not p.isVisible()


def test_setas_andam_na_lista_sem_sair_do_campo(qt_interface, qtbot):
    p, _ = _paleta(qtbot)
    qtbot.keyClicks(p.campo, "tema")
    assert p.lista.count() == 3
    qtbot.keyClick(p.campo, Qt.Key.Key_Down)
    qtbot.keyClick(p.campo, Qt.Key.Key_Down)
    qtbot.keyClick(p.campo, Qt.Key.Key_Down)      # no fim, fica no fim
    assert p.lista.currentItem().data(Qt.ItemDataRole.UserRole) == "acao:tema_sistema"
    qtbot.keyClick(p.campo, Qt.Key.Key_Up)
    assert p.lista.currentItem().data(Qt.ItemDataRole.UserRole) == "acao:tema_claro"


def test_nada_encontrado_e_enter_nao_faz_nada(qt_interface, qtbot):
    p, escolhas = _paleta(qtbot)
    qtbot.keyClicks(p.campo, "xyzzy")
    assert p.lista.count() == 0 and not p.vazio.isHidden()
    qtbot.keyClick(p.campo, Qt.Key.Key_Return)
    assert escolhas == []


def test_esc_fecha_sem_escolher(qt_interface, qtbot):
    p, escolhas = _paleta(qtbot)
    qtbot.keyClick(p.campo, Qt.Key.Key_Escape)
    assert not p.isVisible() and escolhas == []


@pytest.fixture
def janela(qt_interface, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    j = qmain.SIG_FT_App()
    j.fechar_sem_perguntar = True
    qtbot.addWidget(j)
    return j


def test_ctrl_k_esta_ligado(janela):
    assert janela.atalho_paleta.key() == QKeySequence("Ctrl+K")


def test_escolher_um_modulo_abre_a_tela(janela, qtbot):
    p = janela.abrir_paleta()
    assert janela.abrir_paleta() is p               # aberta: não abre outra
    qtbot.keyClicks(p.campo, "tradutor")
    qtbot.keyClick(p.campo, Qt.Key.Key_Return)
    assert janela.pilha.currentWidget() is janela.telas["Translator"]


def test_toda_acao_tem_quem_faca(janela, monkeypatch):
    feitos = []
    home = janela.telas["Home"]
    for metodo in {*qmain.ACAO_NA_HOME.values(), "escolher_tema"}:
        monkeypatch.setattr(home, metodo, lambda *a, m=metodo: feitos.append((m, a)))
    monkeypatch.setattr(janela, "abrir_pasta_de_logs", lambda: feitos.append(("logs", ())))
    janela.show_frame("Translator")
    for chave, *_resto in catalogo.ACOES:
        janela.executar_comando(f"acao:{chave}")
    assert ("escolher_tema", ("claro",)) in feitos
    assert ("abrir_janela_chaves_api", ()) in feitos
    assert len(feitos) == len(catalogo.ACOES) - 1      # "inicio" só navega
    assert janela.pilha.currentWidget() is janela.telas["Home"]


def test_comando_desconhecido_nao_derruba(janela):
    janela.executar_comando("acao:nao_existe")
    janela.executar_comando("qualquer")
```

- [ ] **Step 2:** `.venv/bin/python -m pytest -q tests/test_qt_paleta.py` → falha (`ImportError: ... paleta`).

- [ ] **Step 3: `sigft/app_qt/catalogo.py`.** Acrescente aos imports do topo (depois de
  `from __future__ import annotations`):

```python
from typing import NamedTuple

from sigft.app import busca
```

  e, depois de `dica_do_menu`:

```python
# --- Ctrl+K (etapa 1b, 2026-10-21) ------------------------------------------------

class Comando(NamedTuple):
    """Um item da caixa do Ctrl+K."""
    chave: str          # "tela:CriaFichas" ou "acao:modelos"
    texto: str
    icone: str          # nome de `icones.NOMES`
    palavras: str = ""  # o que mais a busca acha (o texto do menu, sinônimos)


# As ações além dos módulos: chave, texto, ícone e palavras. Quem faz cada uma é
# `main.SIG_FT_App.executar_comando`; `tests/test_qt_paleta.py` cobra que toda
# chave tenha quem a faça.
ACOES = (
    ("inicio", "Início", "house", "home tela inicial"),
    ("atividades", "Atividades do dia", "clipboard-check", "mural"),
    ("modelos", "Modelos de IA", "bot", "ia llm provedor"),
    ("gastos", "Gastos de IA", "circle-dollar-sign", "custo uso"),
    ("chaves", "Chaves de API", "key-round", "api key senha"),
    ("atualizacoes", "Procurar atualizações", "refresh-cw", "versao nova atualizar"),
    ("logs", "Abrir logs", "folder-open", "pasta log"),
    ("tema_escuro", "Tema escuro", "moon", "aparencia cor"),
    ("tema_claro", "Tema claro", "sun", "aparencia cor"),
    ("tema_sistema", "Tema do sistema", "monitor", "aparencia cor windows"),
)


def comandos() -> list[Comando]:
    """Os módulos liberados (na ordem dos cartões da Home) e as ações."""
    no_menu = {item[2]: item[1] for item in MENU if item[0] == "botao"}
    lista = [Comando(f"tela:{alvo}", titulo, ICONE_DA_TELA[alvo], f"{no_menu.get(alvo, '')} {alvo}")
             for alvo, titulo, _descricao in MODULOS if alvo not in TELAS_BLOQUEADAS]
    lista += [Comando(f"acao:{chave}", texto, icone, palavras) for chave, texto, icone, palavras in ACOES]
    return lista


def filtrar(lista, consulta: str) -> list[Comando]:
    """Os comandos que têm TODAS as palavras da `consulta` (sem acento, sem caixa)
    no texto ou nas palavras; os que COMEÇAM pela primeira vêm antes."""
    termos = busca.normalizar(consulta).split()
    if not termos:
        return list(lista)

    def onde(comando: Comando) -> str:
        return busca.normalizar(f"{comando.texto} {comando.palavras}")

    achados = [c for c in lista if all(t in onde(c) for t in termos)]
    return sorted(achados, key=lambda c: not busca.normalizar(c.texto).startswith(termos[0]))
```

- [ ] **Step 4: `sigft/app_qt/widgets/paleta.py`**

```python
"""Ctrl+K: a caixa de busca dos módulos e das ações (2026-10-21, etapa 1b).

Abre no meio da janela; filtra enquanto se digita (sem acento e sem caixa,
`catalogo.filtrar`); as setas andam na lista sem tirar o cursor do campo; Enter
escolhe, Esc fecha. A lista é `catalogo.comandos()`; quem faz cada comando é
`main.SIG_FT_App.executar_comando`.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

from sigft.app_qt import catalogo, estilo, icones

TEXTO_DICA = "Buscar módulo ou ação"
TEXTO_VAZIO = "Nada com esse nome."
LARGURA = 560
ALTURA_LISTA = 320


class PaletaDeComandos(QDialog):
    escolheu = Signal(str)

    def __init__(self, parent, comandos) -> None:
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("paleta")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(LARGURA)
        self._comandos = list(comandos)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        self.campo = QLineEdit()
        self.campo.setPlaceholderText(TEXTO_DICA)
        self.campo.installEventFilter(self)
        self.campo.textChanged.connect(self._filtrar)
        lay.addWidget(self.campo)
        self.lista = QListWidget(objectName="lista_paleta")
        self.lista.setFixedHeight(ALTURA_LISTA)
        self.lista.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lista.itemClicked.connect(self._clicou)
        lay.addWidget(self.lista)
        self.vazio = QLabel(TEXTO_VAZIO)
        self.vazio.setProperty("papel", "legenda")
        lay.addWidget(self.vazio)
        self._filtrar("")

    def _filtrar(self, consulta: str) -> None:
        self.lista.clear()
        cor = estilo.cor_do_papel("texto")
        for comando in catalogo.filtrar(self._comandos, consulta):
            item = QListWidgetItem(icones.icone(comando.icone, cor), comando.texto)
            item.setData(Qt.ItemDataRole.UserRole, comando.chave)
            self.lista.addItem(item)
        if self.lista.count():
            self.lista.setCurrentRow(0)
        self.vazio.setVisible(self.lista.count() == 0)

    def eventFilter(self, obj, evento) -> bool:  # noqa: N802 -- nome do Qt
        if obj is self.campo and evento.type() == QEvent.Type.KeyPress:
            tecla = evento.key()
            if tecla in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                self._mover(1 if tecla == Qt.Key.Key_Down else -1)
                return True
            if tecla in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.escolher_atual()
                return True
        return super().eventFilter(obj, evento)

    def _mover(self, passo: int) -> None:
        if not self.lista.count():
            return
        linha = min(max(self.lista.currentRow() + passo, 0), self.lista.count() - 1)
        self.lista.setCurrentRow(linha)

    def _clicou(self, item) -> None:
        self.lista.setCurrentItem(item)
        self.escolher_atual()

    def escolher_atual(self) -> None:
        item = self.lista.currentItem()
        if item is None:
            return
        chave = item.data(Qt.ItemDataRole.UserRole)
        self.accept()
        self.escolheu.emit(chave)

    def abrir_sobre(self, janela) -> None:
        """No meio da `janela`, a um quinto da altura, com o cursor no campo."""
        self.adjustSize()
        geometria = janela.frameGeometry()
        self.move(geometria.x() + (geometria.width() - self.width()) // 2,
                  geometria.y() + geometria.height() // 5)
        self.show()
        self.campo.setFocus()
```

- [ ] **Step 5: `sigft/app_qt/main.py`.** Imports: troque

```python
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
```

  por

```python
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
```

  troque `from sigft.core import instancia` por `from sigft.core import instancia, plataforma`,
  e acrescente:

```python
from shiboken6 import isValid

from sigft.app_qt.widgets.paleta import PaletaDeComandos
```

  Depois do dicionário `TELAS`:

```python
# Ctrl+K (etapa 1b, 2026-10-21): o método da Home que cada `acao:` chama. As
# outras ações (`inicio`, `logs`, `tema_*`) estão em `executar_comando`.
ACAO_NA_HOME = {
    "atividades": "abrir_mural_atividades",
    "modelos": "abrir_janela_modelos_ia",
    "gastos": "abrir_janela_gastos_ia",
    "chaves": "abrir_janela_chaves_api",
    "atualizacoes": "procurar_atualizacoes",
}
```

  Em `SIG_FT_App.__init__`, depois de `self.show_frame("Home")`:

```python
        # Ctrl+K: a caixa de busca dos módulos e das ações (etapa 1b, 2026-10-21).
        self._paleta = None
        self.atalho_paleta = QShortcut(QKeySequence("Ctrl+K"), self)
        self.atalho_paleta.activated.connect(self.abrir_paleta)
```

  E, depois de `show_home`:

```python
    # -- Ctrl+K ------------------------------------------------------------------
    def abrir_paleta(self) -> PaletaDeComandos:
        if self._paleta is not None and isValid(self._paleta) and self._paleta.isVisible():
            self._paleta.raise_()
            return self._paleta
        paleta = PaletaDeComandos(self, catalogo.comandos())
        paleta.escolheu.connect(self.executar_comando)
        self._paleta = paleta
        paleta.abrir_sobre(self)
        return paleta

    def _home_view(self):
        home = self.telas.get("Home")
        return home if isinstance(home, HomeView) else None

    def executar_comando(self, chave: str) -> None:
        """Faz o comando `chave` do Ctrl+K (`catalogo.comandos`). Desconhecido: nada."""
        tipo, _, alvo = chave.partition(":")
        if tipo == "tela":
            self.show_frame(alvo)
            return
        if tipo != "acao":
            return
        home = self._home_view()
        if alvo == "inicio":
            self.show_home()
        elif alvo in ACAO_NA_HOME:
            if home is not None:
                getattr(home, ACAO_NA_HOME[alvo])()
        elif alvo.startswith("tema_"):
            escolha = alvo.removeprefix("tema_")
            if home is not None:
                home.escolher_tema(escolha)
            else:
                tema.aplicar(QApplication.instance(), escolha)
        elif alvo == "logs":
            self.abrir_pasta_de_logs()

    def abrir_pasta_de_logs(self) -> None:
        """`Documentos\\SIG-FT\\logs\\` no explorador (criada se faltar)."""
        from sigft.core.dados_usuario import pasta_logs

        try:
            plataforma.abrir_pasta_criando_se_preciso(str(pasta_logs()))
        except Exception as erro:  # noqa: BLE001 -- vira aviso
            QMessageBox.critical(self, "Erro", f"Não foi possível abrir a pasta de logs: {erro}")
```

- [ ] **Step 6: folha.** Em `estilo._folha_ferramentas`, acrescente à docstring o item
  `* Ctrl+K (`widgets/paleta.py`): cartão `superficie` com borda; item escolhido como o do menu.`,
  acrescente depois de `f = tokens.FONTE`:

```python
    menu = MENU_ESCOLHIDO["claro" if tema == "claro" else "escuro"]
    raio, raio_cartao = tokens.RAIO["controle"], tokens.RAIO["cartao"]
```

  e, no fim da lista `regras`:

```python
        # Ctrl+K (widgets/paleta.py)
        f'#paleta {{ background: {p["superficie"]}; border: 1px solid {p["borda"]};'
        f' border-radius: {raio_cartao}px; }}',
        f'#lista_paleta {{ background: {p["superficie"]}; border: none; outline: none;'
        f' font-size: {f["corpo"]}px; }}',
        f'#lista_paleta::item {{ padding: 6px 8px; border-radius: {raio}px; }}',
        f'#lista_paleta::item:selected {{ background: {menu["fundo"]}; color: {menu["texto"]}; }}',
```

- [ ] **Step 7:** `.venv/bin/python -m pytest -q tests/test_qt_paleta.py tests/test_qt_catalogo.py tests/test_qt_main.py tests/test_qt_registro_telas.py tests/test_qt_icones.py tests/test_qt_sem_cor_crua.py tests/test_texto_da_ui.py tests/test_frontend_nomes_indefinidos.py` → PASS.

- [ ] **Step 8:** `bash scripts/check.sh`; smoke; e abra o app (`.venv/bin/python frontend.py`
  numa máquina com tela, ou o smoke offscreen) para ver que o Ctrl+K não quebrou a abertura. Commit:

```bash
git add sigft/app_qt/catalogo.py sigft/app_qt/widgets/paleta.py sigft/app_qt/main.py \
        sigft/app_qt/estilo.py tests/test_qt_paleta.py
git commit -m "Ctrl+K: caixa de busca com os modulos e as acoes da Home"
```

---

### Task 6: Tamanho da letra (Normal / Grande)

**Files:**
- Modify: `sigft/app/tokens.py` (`AUMENTO_DA_LETRA`)
- Modify: `sigft/app_qt/estilo.py` (`AUMENTO_LETRA`, `ajustar_tamanhos`, `folha_sem_aumento`,
  `folha_de_estilo` vira o invólucro de `_folha_base`; seletor de letra no `_folha_telas`)
- Create: `sigft/app_qt/letra.py`
- Modify: `sigft/app_qt/widgets/blocos.py` (`pintar`)
- Modify: `sigft/app_qt/views/home.py` (seletor na linha do título)
- Modify: `sigft/app_qt/main.py` (`_preparar_qt`, `--letra`, ações `letra_*`)
- Modify: `sigft/app_qt/catalogo.py` (`ACOES`)
- Test: `tests/test_qt_letra.py` (novo), `tests/test_qt_paleta.py` (ajuste)

**Interfaces:**
- Consumes: `catalogo.ACOES`, `SIG_FT_App.executar_comando` (Task 5); `estilo._folha_ferramentas` (Tasks 1, 3, 5).
- Produces: `tokens.AUMENTO_DA_LETRA = {"normal": 0, "grande": 2}`;
  `estilo.AUMENTO_LETRA: int`; `estilo.ajustar_tamanhos(folha: str, aumento: int) -> str`;
  `estilo.folha_sem_aumento(widget) -> str`; `estilo.PROP_FOLHA_BASE`, `estilo.PROP_FOLHA_POSTA`.
- Produces: `letra.TAMANHOS = ("normal", "grande")`, `letra.PADRAO`, `letra.CHAVE_PREFERENCIA = "letra"`,
  `letra.escolhido() -> str`, `letra.aumento(escolha: str) -> int`,
  `letra.aplicar(app, escolha: str, *, gravar: bool = True) -> str`,
  `letra.ajustar_widget(widget, aumento_px: int) -> None`; `letra._vigia: list`.
- Produces: `HomeView.botoes_letra: dict[str, QPushButton]`, `HomeView.escolher_letra(escolha)`;
  `main._opcao_da_linha_de_comando(argv, nome) -> str | None`; `_preparar_qt(escolha_tema=None, escolha_letra=None)`.

Como: "+2 px em toda a escala" = todo `font-size` da folha do app (que inclui `tokens.FONTE`)
e de cada folha própria de peça (`blocos.botao(tamanho_fonte=...)`, `blocos.rotulo`,
`CaixaDeMarcar`...), que ganham da folha do app. A troca na hora refaz cada peça a partir
da folha de antes do aumento, guardada nela; peça nova ou repintada é ajustada por um vigia
no `Polish`/`StyleChange`, que só existe com a letra grande. **No Normal nada muda**: as
medidas de hoje ficam (o regex com aumento 0 devolve a folha igual e o vigia não existe).
Risco: com a letra grande, texto em peça de altura fixa pode encostar na borda; o smoke
`--letra grande` e as capturas da Task 8 mostram.

- [ ] **Step 1: testes (`tests/test_qt_letra.py`)**

```python
"""Letra Normal / Grande, aplicada na hora como o tema (2026-10-21, etapa 1b)."""
import re

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from sigft.app import tokens
from sigft.app_qt import estilo, letra
from sigft.app_qt.widgets import blocos


class Controller:
    api_keys: dict = {}


@pytest.fixture
def letra_temporaria(qt_interface, tmp_path, monkeypatch):
    monkeypatch.setattr(letra, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    anterior = qt_interface.styleSheet()
    yield qt_interface
    letra.aplicar(qt_interface, "normal", gravar=False)
    qt_interface.setStyleSheet(anterior)


def _tamanhos(folha):
    return [int(t) for t in re.findall(r"font-size:\s*(\d+)px", folha)]


def test_ajustar_tamanhos():
    folha = "a { font-size: 12px; } b { font-size: 9pt; }"
    assert estilo.ajustar_tamanhos(folha, 2) == "a { font-size: 14px; } b { font-size: 11pt; }"
    assert estilo.ajustar_tamanhos(folha, 0) == folha


def test_grande_soma_2_em_toda_a_escala_da_folha(letra_temporaria):
    normal = estilo.folha_de_estilo()
    letra.aplicar(letra_temporaria, "grande")
    assert _tamanhos(letra_temporaria.styleSheet()) == \
        [t + tokens.AUMENTO_DA_LETRA["grande"] for t in _tamanhos(normal)]
    assert letra.escolhido() == "grande"


def test_peca_com_folha_propria_cresce_e_volta(letra_temporaria, qtbot):
    rotulo = blocos.rotulo("Olá", tamanho=13)
    qtbot.addWidget(rotulo)
    letra.aplicar(letra_temporaria, "grande")
    assert "font-size: 15px" in rotulo.styleSheet()
    letra.aplicar(letra_temporaria, "normal")
    assert "font-size: 13px" in rotulo.styleSheet()


def test_peca_criada_depois_nasce_grande(letra_temporaria, qtbot):
    letra.aplicar(letra_temporaria, "grande")
    botao = blocos.botao("Salvar", tamanho_fonte=12)
    qtbot.addWidget(botao)
    botao.show()
    qtbot.waitExposed(botao)
    assert "font-size: 14px" in botao.styleSheet()


def test_pintar_depois_nao_soma_duas_vezes(letra_temporaria, qtbot):
    botao = blocos.botao("Salvar", tamanho_fonte=12)
    qtbot.addWidget(botao)
    botao.show()
    qtbot.waitExposed(botao)
    letra.aplicar(letra_temporaria, "grande")
    blocos.pintar(botao, "QPushButton { font-weight: bold; }")
    QApplication.processEvents()
    assert "font-size: 14px" in botao.styleSheet()
    assert "font-size: 16px" not in botao.styleSheet()


def test_normal_nao_deixa_vigia(letra_temporaria):
    letra.aplicar(letra_temporaria, "grande")
    assert len(letra._vigia) == 1
    letra.aplicar(letra_temporaria, "normal")
    assert letra._vigia == []


def test_escolha_invalida_e_normal(tmp_path, monkeypatch):
    monkeypatch.setattr(letra, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    (tmp_path / "p.json").write_text('{"preferencias": {"letra": "enorme"}}', encoding="utf-8")
    assert letra.escolhido() == "normal"


def test_seletor_na_home_marca_e_aplica(letra_temporaria, qtbot):
    from sigft.app_qt.views import home as home_mod

    tela = home_mod.HomeView(controller=Controller())
    qtbot.addWidget(tela)
    assert set(tela.botoes_letra) == set(letra.TAMANHOS)
    assert tela.botoes_letra["normal"].property("ativo") is True
    tela.botoes_letra["grande"].click()
    assert estilo.AUMENTO_LETRA == tokens.AUMENTO_DA_LETRA["grande"]
    assert tela.botoes_letra["grande"].property("ativo") is True
    assert tela.botoes_letra["normal"].property("ativo") is False


@pytest.mark.parametrize("escolha", ["normal", "grande"])
def test_seletores_cabem_na_linha_do_titulo(letra_temporaria, qtbot, escolha):
    # A barra de botões já ocupa quase toda a Home a 1280 px: tema e letra ficam
    # na linha do título, à direita, sem rolagem horizontal nem mexer no título.
    from sigft.app_qt.views import home as home_mod

    letra.aplicar(letra_temporaria, escolha, gravar=False)
    tela = home_mod.HomeView(controller=Controller())
    qtbot.addWidget(tela)
    tela.resize(1280 - estilo.LARGURA_BARRA_LATERAL, 850)
    tela.show()
    qtbot.waitExposed(tela)
    corpo = tela.widget()
    assert corpo.minimumSizeHint().width() <= tela.viewport().width()
    qtbot.waitUntil(lambda: corpo.width() == tela.viewport().width(), timeout=1000)
    titulo = tela.label_titulo.geometry()
    if escolha == "normal":
        assert (titulo.x(), titulo.y(), titulo.height()) == (46, 46, 38)
    for botao in [*tela.botoes_tema.values(), *tela.botoes_letra.values()]:
        topo = botao.mapTo(corpo, QPoint(0, 0))
        assert topo.y() >= titulo.y() and topo.y() + botao.height() <= titulo.y() + titulo.height()
        assert topo.x() + botao.width() <= corpo.width() - 57


def test_opcao_da_linha_de_comando():
    from sigft.app_qt import main as qmain

    assert qmain._opcao_da_linha_de_comando(["f", "--smoke", "--letra", "grande"], "--letra") == "grande"
    assert qmain._opcao_da_linha_de_comando(["f", "--letra=grande"], "--letra") == "grande"
    assert qmain._opcao_da_linha_de_comando(["f", "--smoke"], "--letra") is None
    assert qmain._tema_da_linha_de_comando(["f", "--tema", "claro"]) == "claro"
```

  E em `tests/test_qt_paleta.py`, `test_toda_acao_tem_quem_faca`: troque
  `{*qmain.ACAO_NA_HOME.values(), "escolher_tema"}` por
  `{*qmain.ACAO_NA_HOME.values(), "escolher_tema", "escolher_letra"}` e acrescente
  `assert ("escolher_letra", ("grande",)) in feitos`.

- [ ] **Step 2:** `.venv/bin/python -m pytest -q tests/test_qt_letra.py tests/test_qt_paleta.py` → falha (`ImportError: cannot import name 'letra'`).

- [ ] **Step 3: tokens.** No fim de `sigft/app/tokens.py`, depois de `RAIO = ...`:

```python
# Tamanho da letra (etapa 1b, 2026-10-21): "grande" soma 2 px a TODA a escala (a
# de cima e cada `font-size` da folha e das peças), aplicado na hora
# (`sigft/app_qt/letra.py`).
AUMENTO_DA_LETRA = {"normal": 0, "grande": 2}
```

- [ ] **Step 4: `estilo.py`.** Logo depois de `TEMA_ATUAL = "escuro"`:

```python
# O aumento da letra que está valendo, em px (`letra.aplicar` muda; 0 = normal).
AUMENTO_LETRA = 0
_TAMANHO_DE_LETRA = re.compile(r"(font-size:\s*)(\d+)(px|pt)")
# Onde `letra` guarda, numa peça com folha própria, a folha de ANTES do aumento e
# a que ela pôs (para refazer a partir da base, nunca somar duas vezes).
PROP_FOLHA_BASE = "_letra_folha_base"
PROP_FOLHA_POSTA = "_letra_folha_posta"


def ajustar_tamanhos(folha: str, aumento: int) -> str:
    """Soma `aumento` a cada `font-size` de `folha` (px e pt). Com 0, a mesma folha."""
    if not aumento or not folha:
        return folha
    return _TAMANHO_DE_LETRA.sub(
        lambda m: f"{m.group(1)}{int(m.group(2)) + aumento}{m.group(3)}", folha)


def folha_sem_aumento(widget) -> str:
    """A folha própria de `widget` como a tela a escreveu, sem o aumento da letra."""
    folha = widget.styleSheet()
    if folha and widget.property(PROP_FOLHA_POSTA) == folha:
        return widget.property(PROP_FOLHA_BASE) or ""
    return folha
```

  Troque a linha `def folha_de_estilo(tema: str | None = None) -> str:` por
  `def _folha_base(tema: str | None = None) -> str:` e acrescente, logo ACIMA dela:

```python
def folha_de_estilo(tema: str | None = None) -> str:
    """A folha QSS do app inteiro no `tema` ("escuro" ou "claro"), dos tokens, com
    o aumento da letra que está valendo (`AUMENTO_LETRA`, 2026-10-21).

    Sem argumento, o tema que está valendo (`TEMA_ATUAL`, que `tema.aplicar`
    define)."""
    return ajustar_tamanhos(_folha_base(tema), AUMENTO_LETRA)
```

  No `_folha_telas`, troque

```python
        f'#seletor_tema QPushButton[ativo="true"] {{ background: {menu["fundo"]}; color: {menu["texto"]};'
        f' border-color: {menu["fundo"]}; }}',
        # Mouse em cima: o texto acompanha o ícone, que já vai para a cor do menu.
        f'#seletor_tema QPushButton:hover {{ color: {menu["texto"]}; }}',
```

  por

```python
        f'#seletor_tema QPushButton[ativo="true"], #seletor_letra QPushButton[ativo="true"] '
        f'{{ background: {menu["fundo"]}; color: {menu["texto"]}; border-color: {menu["fundo"]}; }}',
        # Mouse em cima: o texto acompanha o ícone, que já vai para a cor do menu.
        f'#seletor_tema QPushButton:hover, #seletor_letra QPushButton:hover {{ color: {menu["texto"]}; }}',
```

- [ ] **Step 5: `blocos.pintar`.** Troque

```python
    base = widget.property(_FOLHA_BASE)
    if base is None:
        base = widget.styleSheet()
        widget.setProperty(_FOLHA_BASE, base)
```

  por

```python
    base = widget.property(_FOLHA_BASE)
    if base is None:
        # A folha de antes do aumento da letra (2026-10-21): o aumento é refeito
        # depois, pelo vigia de `letra.py`; somado aqui, ele contaria duas vezes.
        base = estilo.folha_sem_aumento(widget)
        widget.setProperty(_FOLHA_BASE, base)
```

- [ ] **Step 6: `sigft/app_qt/letra.py`**

```python
"""Tamanho da letra: Normal ou Grande, trocado com o app aberto (2026-10-21, etapa 1b).

Como o tema (`tema.py`): a escolha fica nas preferências (`prefs`, chave `letra`)
e `aplicar` faz a troca inteira na hora:

1. `estilo.AUMENTO_LETRA` (de `tokens.AUMENTO_DA_LETRA`) e a folha do app
   regerada: `folha_de_estilo` soma o aumento a cada `font-size`;
2. as peças com folha PRÓPRIA (`blocos.botao(tamanho_fonte=...)`, rótulos,
   caixas) e com `setFont` em pixel: a folha própria ganha da do app, então cada
   uma é refeita a partir da folha de antes do aumento, guardada nela;
3. peça criada depois (tela aberta pela primeira vez) ou que trocou de folha
   (`blocos.pintar`): um vigia no app ajusta no `Polish`/`StyleChange`. O vigia
   só existe com a letra grande: no normal nada muda, nem as medidas.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QWidget

from sigft.app import tokens
from sigft.app_qt import estilo

_log = logging.getLogger(__name__)

TAMANHOS = ("normal", "grande")
PADRAO = "normal"
CHAVE_PREFERENCIA = "letra"
_PROP_FONTE_BASE = "_letra_fonte_base"
_TIPOS_VIGIADOS = (QEvent.Type.Polish, QEvent.Type.StyleChange)


def _arquivo_de_prefs():
    """O `config_path` das preferências: `None` é o `user_prefs.json` da pasta de
    dados. Função para os testes apontarem outro arquivo."""
    return None


def _valida(escolha) -> str:
    return escolha if escolha in TAMANHOS else PADRAO


def escolhido() -> str:
    """A escolha guardada; nenhuma, ou uma que não é tamanho: o normal."""
    from sigft.core import prefs

    try:
        valor = prefs.ler_preferencia(CHAVE_PREFERENCIA, PADRAO, config_path=_arquivo_de_prefs())
    except Exception:  # noqa: BLE001 -- preferência é conveniência
        return PADRAO
    return _valida(valor)


def aumento(escolha: str) -> int:
    return tokens.AUMENTO_DA_LETRA[_valida(escolha)]


def ajustar_widget(widget: QWidget, aumento_px: int) -> None:
    """Refaz a folha própria (e a fonte em pixel) de `widget` com `aumento_px`."""
    folha = widget.styleSheet()
    if folha:
        base = estilo.folha_sem_aumento(widget)
        nova = estilo.ajustar_tamanhos(base, aumento_px)
        widget.setProperty(estilo.PROP_FOLHA_BASE, base)
        widget.setProperty(estilo.PROP_FOLHA_POSTA, nova)
        if nova != folha:
            widget.setStyleSheet(nova)
        if "font-size" in base:
            return   # a folha decide o tamanho: mexer no QFont não muda nada
    if not widget.testAttribute(Qt.WidgetAttribute.WA_SetFont):
        return
    fonte = widget.font()
    base_px = widget.property(_PROP_FONTE_BASE)
    if base_px is None:
        if fonte.pixelSize() <= 0:
            return   # fonte em pontos (widget cru do Tk): a folha dele cuida
        base_px = fonte.pixelSize()
        widget.setProperty(_PROP_FONTE_BASE, base_px)
    if fonte.pixelSize() != base_px + aumento_px:
        fonte.setPixelSize(base_px + aumento_px)
        widget.setFont(fonte)


class _Vigia(QObject):
    """Ajusta a peça que nasce ou troca de folha com a letra grande valendo."""

    def eventFilter(self, obj, evento) -> bool:  # noqa: N802 -- nome do Qt
        if evento.type() in _TIPOS_VIGIADOS and estilo.AUMENTO_LETRA and isinstance(obj, QWidget):
            try:
                ajustar_widget(obj, estilo.AUMENTO_LETRA)
            except RuntimeError:
                pass   # peça já destruída
        return False


_vigia: list = []


def _vigiar(app, ligado: bool) -> None:
    if ligado and not _vigia:
        vigia = _Vigia()
        app.installEventFilter(vigia)
        _vigia.append(vigia)
    elif not ligado and _vigia:
        app.removeEventFilter(_vigia.pop())


def aplicar(app, escolha: str, *, gravar: bool = True) -> str:
    """Troca a letra do app inteiro para `escolha` (inválida: normal) e devolve a
    escolha que valeu. `gravar=False`: a abertura e o `--smoke --letra`."""
    escolha = _valida(escolha)
    if gravar:
        from sigft.core import prefs

        try:
            prefs.gravar_preferencia(CHAVE_PREFERENCIA, escolha, config_path=_arquivo_de_prefs())
        except Exception:  # noqa: BLE001 -- lembrar não pode impedir a troca
            _log.warning("nao consegui gravar o tamanho de letra escolhido", exc_info=True)
    estilo.AUMENTO_LETRA = aumento(escolha)
    _vigiar(app, bool(estilo.AUMENTO_LETRA))
    app.setStyleSheet(estilo.folha_de_estilo())
    for widget in app.allWidgets():
        try:
            ajustar_widget(widget, estilo.AUMENTO_LETRA)
        except RuntimeError:
            pass
    return escolha
```

- [ ] **Step 7: Home (`sigft/app_qt/views/home.py`).** Troque
  `from sigft.app_qt import atualizacao, estilo, icones, interface, nome, tema` por
  `from sigft.app_qt import atualizacao, estilo, icones, interface, letra, nome, tema`.
  Depois de `SELETOR_TEMA = (...)`:

```python
# O seletor de letra (2026-10-21, etapa 1b): escolha, texto e dica. Na linha do
# título, à direita do de tema; sem ícone (o Lucide do pacote não tem um de letra).
SELETOR_LETRA = (
    ("normal", "Normal", "Letra do tamanho de sempre."),
    ("grande", "Grande", "Letra 2 px maior em todo o SIG-FT, para ler com mais folga."),
)
```

  Em `__init__`, troque

```python
        linha_titulo.addWidget(self._criar_seletor_tema(), 0, Qt.AlignmentFlag.AlignVCenter)
```

  por

```python
        linha_titulo.addWidget(self._criar_seletor_tema(), 0, Qt.AlignmentFlag.AlignVCenter)
        linha_titulo.addSpacing(12)
        linha_titulo.addWidget(self._criar_seletor_letra(), 0, Qt.AlignmentFlag.AlignVCenter)
```

  e, depois de `escolher_tema`:

```python
    # =====================================================================
    # SELETOR DE LETRA  [2026-10-21]
    # =====================================================================
    def _criar_seletor_letra(self) -> QFrame:
        """Normal e Grande; o da escolha atual fica `ativo`, como no de tema."""
        quadro = QFrame(objectName="seletor_letra")
        linha = QHBoxLayout(quadro)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(4)
        self.botoes_letra = {}
        for escolha, texto, dica in SELETOR_LETRA:
            botao = blocos.botao(texto, variante="secundario", tamanho_fonte=12)
            botao.setToolTip(dica)
            dialogs.sem_tecla(botao)
            botao.clicked.connect(lambda _=False, e=escolha: self.escolher_letra(e))
            self.botoes_letra[escolha] = botao
            linha.addWidget(botao)
        self._marcar_letra(letra.escolhido())
        return quadro

    def _marcar_letra(self, escolha: str) -> None:
        for chave, botao in self.botoes_letra.items():
            estilo.definir_propriedade(botao, "ativo", chave == escolha)

    def escolher_letra(self, escolha: str) -> None:
        """Troca a letra do app inteiro e lembra a escolha (`letra.aplicar`)."""
        self._marcar_letra(letra.aplicar(QApplication.instance(), escolha))
```

  (O `lambda` é o mesmo padrão do seletor de tema logo acima: a Home vive o app inteiro.)

- [ ] **Step 8: `main.py`.** Troque `from sigft.app_qt import atualizacao, catalogo, cursor, estilo, icones, interface, novidades, tema`
  por `from sigft.app_qt import atualizacao, catalogo, cursor, estilo, icones, interface, letra, novidades, tema`.
  Troque

```python
def _preparar_qt(escolha_tema: str | None = None) -> QApplication:
    """A QApplication pronta: tradução, fontes, cursor e o tema.

    O tema é o guardado nas preferências (`tema.escolhido`), ou `escolha_tema`
    (o `--smoke --tema claro`), sem gravar: a abertura só lê."""
    app = QApplication.instance() or _criar_qapplication()
    _instalar_traducao(app)
    interface.instalar()
    estilo.carregar_fontes()
    tema.aplicar(app, escolha_tema or tema.escolhido(), gravar=False)
```

  por

```python
def _preparar_qt(escolha_tema: str | None = None, escolha_letra: str | None = None) -> QApplication:
    """A QApplication pronta: tradução, fontes, cursor, a letra e o tema.

    Letra e tema são os guardados nas preferências, ou os da linha de comando
    (`--smoke --tema claro --letra grande`), sem gravar: a abertura só lê. A
    letra vem antes: a folha que o tema aplica já sai com o aumento."""
    app = QApplication.instance() or _criar_qapplication()
    _instalar_traducao(app)
    interface.instalar()
    estilo.carregar_fontes()
    letra.aplicar(app, escolha_letra or letra.escolhido(), gravar=False)
    tema.aplicar(app, escolha_tema or tema.escolhido(), gravar=False)
```

  Troque a função `_tema_da_linha_de_comando` inteira por:

```python
def _opcao_da_linha_de_comando(argv: list[str], nome: str) -> str | None:
    """O valor de `nome X` (ou `nome=X`) da linha de comando, se houver."""
    for i, arg in enumerate(argv):
        if arg == nome and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith(nome + "="):
            return arg.split("=", 1)[1]
    return None


def _tema_da_linha_de_comando(argv: list[str]) -> str | None:
    """O `--tema X` (ou `--tema=X`) da linha de comando, se houver."""
    return _opcao_da_linha_de_comando(argv, "--tema")
```

  No `_smoke`, troque

```python
        # `--smoke --tema claro`: o smoke também no claro, sem gravar a escolha.
        _preparar_qt(_tema_da_linha_de_comando(sys.argv))
```

  por

```python
        # `--smoke --tema claro --letra grande`: o smoke também no claro e com a
        # letra grande, sem gravar a escolha.
        _preparar_qt(_tema_da_linha_de_comando(sys.argv),
                     _opcao_da_linha_de_comando(sys.argv, "--letra"))
```

  Em `executar_comando`, troque

```python
        elif alvo == "logs":
            self.abrir_pasta_de_logs()
```

  por

```python
        elif alvo.startswith("letra_"):
            escolha = alvo.removeprefix("letra_")
            if home is not None:
                home.escolher_letra(escolha)
            else:
                letra.aplicar(QApplication.instance(), escolha)
        elif alvo == "logs":
            self.abrir_pasta_de_logs()
```

  Em `catalogo.ACOES`, acrescente no fim:

```python
    ("letra_normal", "Letra normal", "settings", "tamanho fonte"),
    ("letra_grande", "Letra grande", "settings", "tamanho fonte maior"),
```

- [ ] **Step 9:** `.venv/bin/python -m pytest -q tests/test_qt_letra.py tests/test_qt_paleta.py tests/test_qt_tema.py tests/test_qt_estilo.py tests/test_qt_blocos.py tests/test_tokens.py tests/test_qt_sem_cor_crua.py tests/test_texto_da_ui.py` → PASS.
  Medidas da linha do título e da Home:
  `.venv/bin/python -m pytest -q tests/test_qt_tema.py::test_o_seletor_cabe_na_linha_do_titulo_sem_alargar_a_home tests/test_qt_nome.py tests/test_qt_home.py tests/test_qt_home_paineis.py` → PASS.

- [ ] **Step 10:** `bash scripts/check.sh`; smoke nos quatro jeitos:
  `QT_QPA_PLATFORM=offscreen .venv/bin/python frontend.py --smoke`,
  `... --smoke --letra grande`, `... --smoke --tema claro`, `... --smoke --tema claro --letra grande`
  (todos com "as N telas abriram"). Commit:

```bash
git add sigft/app/tokens.py sigft/app_qt/estilo.py sigft/app_qt/letra.py \
        sigft/app_qt/widgets/blocos.py sigft/app_qt/views/home.py sigft/app_qt/main.py \
        sigft/app_qt/catalogo.py tests/test_qt_letra.py tests/test_qt_paleta.py
git commit -m "Letra Normal/Grande na Home, aplicada na hora e lembrada"
```

---

### Task 7: Aviso do Windows (fim da tarefa e esperas)

**Files:**
- Create: `sigft/app_qt/aviso_windows.py`
- Modify: `sigft/app_qt/widgets/module_frame.py` (`_fim_do_lote`)
- Modify: `sigft/app_qt/widgets/espera.py` (as esperas avisam)
- Modify: `sigft/app_qt/views/home.py` (caixa "Avisar no Windows" na linha do subtítulo)
- Modify: `tests/conftest.py` (a fixture da Task 2 ganha a segunda variável)
- Test: `tests/test_qt_aviso_windows.py` (novo)

**Interfaces:**
- Consumes: `ModuleFrame._fim_do_lote`, `titulo_da_tela`, `pares_do_lote` (Task 2);
  `resumo_lote.agrupar`, `contar`, `frase_do_fim` (Task 2).
- Produces: `aviso_windows.ENV_DESLIGAR = "SIGFT_SEM_AVISO_DO_WINDOWS"`, `CHAVE_OPCAO = "avisos_do_windows"`,
  `TITULO_FIM = "SIG-FT"`, `TITULO_ESPERA = "O SIG-FT está esperando você"`, `LIMITE_DO_TEXTO = 180`;
  `ligado() -> bool` (padrão `True`); `ligar(valor: bool) -> None`; `primeira_linha(texto) -> str`;
  `avisar(janela, texto, *, titulo=TITULO_FIM) -> bool`; `trazer_para_frente(janela) -> None`;
  `bandeja_da(janela) -> QSystemTrayIcon`; `_mostrar(janela, titulo, texto) -> bool`; `_em_foco(janela) -> bool`.
- Produces: `espera.TEXTO_ESPERA_EXCEL`, `espera.TEXTO_ESPERA_TRAVADOS`;
  `DialogosDeEspera._avisar_que_espera(texto: str) -> None`;
  `HomeView.caixa_avisos_windows`, `home.TEXTO_AVISOS_WINDOWS`.

Decisões: a frase do fim é a contagem de problemas ("Upload duplicadas terminou com 2 erros
e 1 aviso."), e não o "6 de 8 sem pendência" do exemplo da spec: nenhum serviço entrega
esse número de forma uniforme, e o resumo da Task 2 já conta erros e avisos. "Em foco" =
o SIG-FT é o aplicativo ativo e a janela não está minimizada (um painel da Home na frente
também conta como SIG-FT em foco). A caixa liga/desliga fica na linha do **subtítulo**
da Home (à direita): a barra de botões não tem mais largura (sobram 20 px a 1280) e a
linha do título já tem tema e letra; a caixa tem 24 px de altura, menos que os 28 da
linha, então a altura da linha não muda (`test_medidas_da_home`: subtítulo y 89 h 28).

- [ ] **Step 1: testes (`tests/test_qt_aviso_windows.py`)**

```python
"""Aviso do Windows fora de foco: fim da tarefa e esperas (2026-10-21, etapa 1b)."""
import os
import threading

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

from sigft.app_qt import aviso_windows as aviso


@pytest.fixture
def mostrados(monkeypatch, tmp_path):
    """O aviso ligado, o SIG-FT fora de foco e o `_mostrar` trocado por uma lista:
    nem com isto o Windows mostra nada num teste."""
    monkeypatch.delenv(aviso.ENV_DESLIGAR, raising=False)
    monkeypatch.setattr(aviso, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    monkeypatch.setattr(aviso, "_em_foco", lambda janela: False)
    lista = []
    monkeypatch.setattr(aviso, "_mostrar", lambda janela, titulo, texto: lista.append((titulo, texto)) or True)
    return lista


def test_os_testes_rodam_com_o_aviso_desligado():
    assert os.environ.get(aviso.ENV_DESLIGAR) == "1"   # tests/conftest.py


def test_desligado_pelo_ambiente_nunca_mostra(qt_interface, qtbot, monkeypatch):
    chamados = []
    monkeypatch.setattr(aviso, "_mostrar", lambda *a: chamados.append(a) or True)
    monkeypatch.setattr(aviso, "_em_foco", lambda janela: False)
    janela = QWidget()
    qtbot.addWidget(janela)
    assert aviso.avisar(janela, "terminou") is False
    assert chamados == []


def test_fora_de_foco_mostra(qt_interface, qtbot, mostrados):
    janela = QWidget()
    qtbot.addWidget(janela)
    assert aviso.avisar(janela, "Upload duplicadas terminou sem erro nem aviso.")
    assert mostrados == [(aviso.TITULO_FIM, "Upload duplicadas terminou sem erro nem aviso.")]


def test_em_foco_nao_mostra(qt_interface, qtbot, mostrados, monkeypatch):
    monkeypatch.setattr(aviso, "_em_foco", lambda janela: True)
    janela = QWidget()
    qtbot.addWidget(janela)
    assert not aviso.avisar(janela, "x")
    assert mostrados == []


def test_ligado_por_padrao_e_desligar_cala(qt_interface, qtbot, mostrados):
    assert aviso.ligado() is True
    aviso.ligar(False)
    assert aviso.ligado() is False
    janela = QWidget()
    qtbot.addWidget(janela)
    assert not aviso.avisar(janela, "x")


def test_primeira_linha():
    assert aviso.primeira_linha("\n  Faça o login no portal\ne aperte Continuar") == "Faça o login no portal"
    assert len(aviso.primeira_linha("x" * 500)) == aviso.LIMITE_DO_TEXTO
    assert aviso.primeira_linha(None) == ""


def test_clicar_no_aviso_traz_a_janela(qt_interface, qtbot, monkeypatch):
    trazidas = []
    monkeypatch.setattr(aviso, "trazer_para_frente", trazidas.append)
    janela = QWidget()
    qtbot.addWidget(janela)
    bandeja = aviso.bandeja_da(janela)
    assert aviso.bandeja_da(janela) is bandeja          # uma por janela
    bandeja.messageClicked.emit()
    assert trazidas == [janela]


def test_trazer_para_frente_tira_o_minimizado(qt_interface, qtbot):
    janela = QWidget()
    qtbot.addWidget(janela)
    janela.show()
    janela.setWindowState(Qt.WindowState.WindowMinimized)
    aviso.trazer_para_frente(janela)
    assert not janela.isMinimized()


def test_fim_da_tarefa_avisa_com_a_contagem(qt_interface, qtbot, mostrados):
    from sigft.app_qt.widgets.module_frame import ModuleFrame

    class Tela(ModuleFrame):
        def _build_ui(self):
            pass

    tela = Tela(titulo="Upload duplicadas")
    qtbot.addWidget(tela)
    tela.iniciar_tarefa(tela.log, "[Erro] Ficha 4500063671.0001 não encontrada").join(3)
    qtbot.waitUntil(lambda: bool(mostrados), timeout=2000)
    assert mostrados == [(aviso.TITULO_FIM, "Upload duplicadas terminou com 1 erro.")]


def _tela_de_espera(qtbot):
    from sigft.app_qt.widgets.espera import DialogosDeEspera

    class Tela(DialogosDeEspera, QWidget):
        pass

    tela = Tela()
    qtbot.addWidget(tela)
    return tela


def _aberto(tipo):
    return next(w for w in QApplication.topLevelWidgets() if isinstance(w, tipo) and w.isVisible())


def test_pausa_avisa_com_a_primeira_linha(qt_interface, qtbot, mostrados):
    from sigft.app_qt.widgets import dialogs as qd

    tela = _tela_de_espera(qtbot)
    t = threading.Thread(target=tela.pausar_e_esperar,
                         args=("Faça o login no portal e aperte Continuar.\nDetalhe",), daemon=True)
    t.start()
    qtbot.waitUntil(lambda: bool(mostrados), timeout=2000)
    assert mostrados == [(aviso.TITULO_ESPERA, "Faça o login no portal e aperte Continuar.")]
    _aberto(qd.PausaLoginDialog).botao.click()
    t.join(3)


def test_excel_travado_avisa(qt_interface, qtbot, mostrados):
    from sigft.app_qt.widgets import dialogs as qd
    from sigft.app_qt.widgets import espera

    tela = _tela_de_espera(qtbot)
    t = threading.Thread(target=tela.perguntar_retry_excel, daemon=True)
    t.start()
    qtbot.waitUntil(lambda: bool(mostrados), timeout=2000)
    assert mostrados == [(aviso.TITULO_ESPERA, espera.TEXTO_ESPERA_EXCEL)]
    _aberto(qd.RetryLockDialog).close()
    t.join(3)


def test_caixa_da_home_liga_e_desliga(qt_interface, qtbot, tmp_path, monkeypatch):
    from sigft.app_qt.views import home as home_mod

    class Controller:
        api_keys: dict = {}

    monkeypatch.setattr(aviso, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    tela = home_mod.HomeView(controller=Controller())
    qtbot.addWidget(tela)
    assert tela.caixa_avisos_windows.text() == home_mod.TEXTO_AVISOS_WINDOWS
    assert tela.caixa_avisos_windows.isChecked()
    tela.caixa_avisos_windows.setChecked(False)
    assert aviso.ligado() is False
```

- [ ] **Step 2:** `.venv/bin/python -m pytest -q tests/test_qt_aviso_windows.py` → falha (`ImportError`).

- [ ] **Step 3: conftest.** Na fixture `_sem_janelas_do_fim_da_tarefa` (Task 2), acrescente
  a segunda linha e o comentário:

```python
@pytest.fixture(autouse=True)
def _sem_janelas_do_fim_da_tarefa(monkeypatch):
    monkeypatch.setenv("SIGFT_SEM_RESUMO_DO_LOTE", "1")
    # [2026-10-21] O aviso do Windows (`app_qt/aviso_windows.py`) NUNCA nos
    # testes: a notificação sairia na máquina de quem roda a suíte.
    monkeypatch.setenv("SIGFT_SEM_AVISO_DO_WINDOWS", "1")
```

- [ ] **Step 4: `sigft/app_qt/aviso_windows.py`**

```python
"""Aviso do Windows quando uma tarefa termina ou pede algo (2026-10-21, etapa 1b).

Só quando o SIG-FT não está em foco (outro programa na frente, ou minimizado):
quem está olhando para a tela já vê a faixa "Terminou" e a caixa da espera.
`QSystemTrayIcon.showMessage` vira a notificação nativa do Windows, sem
dependência nova; clicar nela (ou no ícone da bandeja) traz a janela para a frente.

Liga e desliga na Home ("Avisar no Windows"), ligado por padrão (`prefs.get_opcao`).
NUNCA nos testes: `tests/conftest.py` põe `ENV_DESLIGAR`, e quem testa o aviso
tira a variável E troca `_mostrar`.
"""
from __future__ import annotations

import os
import weakref

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from sigft.app_qt import estilo, icones

ENV_DESLIGAR = "SIGFT_SEM_AVISO_DO_WINDOWS"
CHAVE_OPCAO = "avisos_do_windows"
TITULO_FIM = "SIG-FT"
TITULO_ESPERA = "O SIG-FT está esperando você"
MS_NA_TELA = 10_000
LIMITE_DO_TEXTO = 180


def _arquivo_de_prefs():
    """O `config_path` das preferências: `None` é o `user_prefs.json` da pasta de
    dados. Função para os testes apontarem outro arquivo."""
    return None


def ligado() -> bool:
    from sigft.core import prefs

    try:
        return prefs.get_opcao(CHAVE_OPCAO, True, config_path=_arquivo_de_prefs())
    except Exception:  # noqa: BLE001 -- preferência é conveniência
        return True


def ligar(valor: bool) -> None:
    from sigft.core import prefs

    try:
        prefs.set_opcao(CHAVE_OPCAO, bool(valor), config_path=_arquivo_de_prefs())
    except Exception:  # noqa: BLE001 -- lembrar não pode atrapalhar o clique
        pass


def primeira_linha(texto) -> str:
    """A primeira linha com texto, cortada em `LIMITE_DO_TEXTO`."""
    linhas = [linha.strip() for linha in str(texto or "").splitlines() if linha.strip()]
    linha = linhas[0] if linhas else ""
    if len(linha) <= LIMITE_DO_TEXTO:
        return linha
    return linha[:LIMITE_DO_TEXTO - 3].rstrip() + "..."


def _em_foco(janela) -> bool:
    if janela.isMinimized() or not janela.isVisible():
        return False
    return QGuiApplication.applicationState() == Qt.ApplicationState.ApplicationActive


def avisar(janela, texto, *, titulo: str = TITULO_FIM) -> bool:
    """Na thread da interface. Mostra o aviso se ligado e fora de foco; devolve se saiu."""
    if os.environ.get(ENV_DESLIGAR) or janela is None or not texto:
        return False
    if not ligado() or _em_foco(janela):
        return False
    return _mostrar(janela, titulo, primeira_linha(texto))


def trazer_para_frente(janela) -> None:
    if janela.isMinimized():
        janela.setWindowState(janela.windowState() & ~Qt.WindowState.WindowMinimized)
    janela.show()
    janela.raise_()
    janela.activateWindow()


def _icone(janela):
    for icone in (janela.windowIcon(), QApplication.windowIcon()):
        if not icone.isNull():
            return icone
    return icones.icone("house", estilo.cor_do_papel("primaria"))


def bandeja_da(janela) -> QSystemTrayIcon:
    """O ícone de bandeja da `janela` (um só, criado na primeira vez). Guarda só
    uma referência FRACA à janela: o sinal do filho não segura a tela viva."""
    bandeja = getattr(janela, "_bandeja_do_aviso", None)
    if bandeja is None:
        bandeja = QSystemTrayIcon(_icone(janela), janela)
        bandeja.setToolTip("SIG-FT")
        referencia = weakref.ref(janela)

        def _clicou(*_args) -> None:
            alvo = referencia()
            if alvo is not None:
                trazer_para_frente(alvo)

        bandeja.messageClicked.connect(_clicou)
        bandeja.activated.connect(_clicou)
        janela._bandeja_do_aviso = bandeja
    return bandeja


def _mostrar(janela, titulo: str, texto: str) -> bool:
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return False
    bandeja = bandeja_da(janela)
    bandeja.show()
    bandeja.showMessage(titulo, texto, _icone(janela), MS_NA_TELA)
    return True
```

- [ ] **Step 5: fim da tarefa (`module_frame.py`).** Acrescente
  `from sigft.app_qt import aviso_windows, interface` no lugar de `from sigft.app_qt import interface`,
  e troque o corpo do `try` de `_fim_do_lote` por:

```python
        try:
            pares = self.pares_do_lote()
            grupos = resumo_regras.agrupar(pares)
            if grupos and resumo_regras.ligado():
                janela_de_resumo.abrir_resumo(self, self.titulo_da_tela, pares)
            # O aviso do Windows, só com o SIG-FT fora de foco (2026-10-21).
            erros, avisos = resumo_regras.contar(grupos)
            aviso_windows.avisar(self.window(), resumo_regras.frase_do_fim(
                self.titulo_da_tela, erros, avisos, falhou=self._tarefa_falhou))
        except Exception:  # noqa: BLE001 -- vira traceback no log
            traceback.print_exc()
```

  e a docstring de `_fim_do_lote` ganha: "E o aviso do Windows, se o SIG-FT está fora de foco."

- [ ] **Step 6: esperas (`sigft/app_qt/widgets/espera.py`).** Troque
  `from sigft.app_qt import interface` por `from sigft.app_qt import aviso_windows, interface` e,
  depois dos imports:

```python
# O que o aviso do Windows diz em cada espera (2026-10-21). A pausa do login usa a
# primeira linha da própria mensagem.
TEXTO_ESPERA_EXCEL = "Um arquivo do Excel está aberto e trava a gravação. Feche o arquivo e escolha Repetir."
TEXTO_ESPERA_TRAVADOS = "Alguns arquivos não puderam ser gravados. Escolha Repetir ou Seguir."
```

  Em `class DialogosDeEspera:`, acrescente como primeiro método:

```python
    def _avisar_que_espera(self, texto: str) -> None:
        """O aviso do Windows de que o SIG-FT espera a pessoa (só fora de foco).
        Na thread da interface; nunca impede a caixa de abrir."""
        if not texto:
            return
        try:
            aviso_windows.avisar(self.window(), texto, titulo=aviso_windows.TITULO_ESPERA)
        except Exception:  # noqa: BLE001 -- o aviso é conveniência
            traceback.print_exc()
```

  Troque `def _abrir_e_esperar(self, construir_dialogo) -> dict:` por
  `def _abrir_e_esperar(self, construir_dialogo, aviso: str = "") -> dict:`; nele, troque

```python
            dialogo = construir_dialogo(evento, resultado)
            dialogo.exec()
            return resultado
```

  por

```python
            dialogo = construir_dialogo(evento, resultado)
            self._avisar_que_espera(aviso)
            dialogo.exec()
            return resultado
```

  e troque

```python
                self._dialogo_aberto = dialogo  # segura a referência enquanto está aberto
                dialogo.show()
```

  por

```python
                self._dialogo_aberto = dialogo  # segura a referência enquanto está aberto
                dialogo.show()
                self._avisar_que_espera(aviso)
```

  Os três que esperam a caixa:

```python
    def pausar_e_esperar(self, mensagem: str, texto_botao: str = TEXTO_CONTINUAR) -> None:
        self._abrir_e_esperar(lambda evento, _res: dialogs.PausaLoginDialog(
            self, mensagem=mensagem, evento_espera=evento, texto_botao=texto_botao),
            aviso=aviso_windows.primeira_linha(mensagem))

    def perguntar_retry_excel(self, caminho: object = None) -> bool:
        mensagem = msg_excel_bloqueado(caminho) if caminho is not None else MSG_EXCEL_BLOQUEADO
        resultado = self._abrir_e_esperar(lambda evento, res: dialogs.RetryLockDialog(
            self, mensagem=mensagem, evento_espera=evento, resultado=res), aviso=TEXTO_ESPERA_EXCEL)
        return bool(resultado.get("retry", False))
```

  e, em `perguntar_arquivos_travados`, a chamada vira
  `self._abrir_e_esperar(lambda evento, res: dialogos_selecao.ArquivosTravadosDialog(self, itens=itens, momento=momento, evento_espera=evento, resultado=res), aviso=TEXTO_ESPERA_TRAVADOS)`.

  Troque `def _na_interface_e_esperar(self, func):` por `def _na_interface_e_esperar(self, func, aviso: str = ""):`; nele, troque

```python
        if interface.na_thread_da_interface():
            return func()
```

  por

```python
        if interface.na_thread_da_interface():
            self._avisar_que_espera(aviso)
            return func()
```

  e troque

```python
        def rodar() -> None:
            try:
                caixa["valor"] = func()
```

  por

```python
        def rodar() -> None:
            try:
                self._avisar_que_espera(aviso)
                caixa["valor"] = func()
```

  Nas chamadas: em `perguntar_sim_nao`, `self._na_interface_e_esperar(perguntar, aviso=f"{titulo}: responda Sim ou Não.")`;
  em `pedir_texto`, `self._na_interface_e_esperar(pedir, aviso=f"{titulo}: o SIG-FT espera a sua resposta.")`;
  em `avisar` com `esperar=True`, `self._na_interface_e_esperar(lambda: funcao(self, titulo, mensagem), aviso=f"{titulo}: aperte OK para seguir.")`.

- [ ] **Step 7: Home.** Troque
  `from sigft.app_qt import atualizacao, estilo, icones, interface, letra, nome, tema` por
  `from sigft.app_qt import atualizacao, aviso_windows, estilo, icones, interface, letra, nome, tema`.
  Depois de `TEXTO_CANAL_TESTES = "Versões de teste"`:

```python
# [2026-10-21] O aviso do Windows (`app_qt/aviso_windows.py`): na linha do
# subtítulo, à direita (a barra de botões não tem mais largura a 1280 px).
TEXTO_AVISOS_WINDOWS = "Avisar no Windows"
DICA_AVISOS_WINDOWS = ("Com o SIG-FT atrás de outra janela, um aviso do Windows diz quando uma "
                       "tarefa termina ou quando o robô espera você (o login no portal, por exemplo).")
```

  Em `__init__`, troque

```python
        self.label_subtitulo.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.label_subtitulo)
```

  por

```python
        self.label_subtitulo.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        # [2026-10-21] A caixa do aviso do Windows divide a linha do subtítulo: 24 px
        # de altura, menos que os 28 da linha, que fica com a altura de antes.
        linha_subtitulo = QHBoxLayout()
        linha_subtitulo.setContentsMargins(0, 0, 0, 0)
        linha_subtitulo.setSpacing(0)
        linha_subtitulo.addWidget(self.label_subtitulo, 1)
        linha_subtitulo.addWidget(self._criar_caixa_avisos(), 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(linha_subtitulo)
```

  e, depois de `_lembrar_canal_testes`:

```python
    def _criar_caixa_avisos(self):
        """"Avisar no Windows", marcada por padrão (`aviso_windows.ligado`)."""
        caixa = controles.CaixaDeMarcar(TEXTO_AVISOS_WINDOWS, tamanho_fonte=12)
        caixa.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        caixa.setChecked(aviso_windows.ligado())
        caixa.setToolTip(DICA_AVISOS_WINDOWS)
        caixa.toggled.connect(aviso_windows.ligar)
        self.caixa_avisos_windows = caixa
        return caixa
```

- [ ] **Step 8:** `.venv/bin/python -m pytest -q tests/test_qt_aviso_windows.py tests/test_qt_espera.py tests/test_qt_perguntas.py tests/test_qt_module_frame.py tests/test_qt_resumo_lote.py tests/test_qt_sem_cor_crua.py tests/test_texto_da_ui.py tests/test_qt_dicas.py` → PASS.
  Medidas da Home: `.venv/bin/python -m pytest -q tests/test_qt_home_paineis.py::test_medidas_da_home tests/test_qt_home.py tests/test_qt_tema.py tests/test_qt_nome.py tests/test_qt_letra.py` → PASS.

- [ ] **Step 9:** `bash scripts/check.sh`; smoke. Commit:

```bash
git add sigft/app_qt/aviso_windows.py sigft/app_qt/widgets/module_frame.py \
        sigft/app_qt/widgets/espera.py sigft/app_qt/views/home.py tests/conftest.py \
        tests/test_qt_aviso_windows.py
git commit -m "Aviso do Windows fora de foco no fim da tarefa e nas esperas; liga e desliga na Home"
```

---

### Task 8: Fechamento

**Files:**
- Modify: `CHANGELOG.md` (bloco em aberto `## 1.2.1`)
- Modify: `docs/base-conhecimento/00-frontend.md` (seção "Sistema visual")
- Modify: `CLAUDE.md` (mural) e `docs/refatoracao/PENDENCIAS.md` (o aviso mais antigo do mural)
- Create (scratchpad, não vai para o repositório): `capturas_1b.py`

**Interfaces:**
- Consumes: tudo das Tasks 1 a 7.

- [ ] **Step 1:** `bash scripts/check.sh` inteiro → verde (exceto o `test_qt_saida` deste contêiner).

- [ ] **Step 2: smoke nos quatro jeitos**

```bash
for args in "" "--tema claro" "--letra grande" "--tema claro --letra grande"; do
  QT_QPA_PLATFORM=offscreen .venv/bin/python frontend.py --smoke $args | tail -1
done
```

  Esperado em cada um: `[smoke] a janela principal Qt montou, as 11 telas abriram e ela fechou sem erro.`
  (o número é o das telas não bloqueadas).

- [ ] **Step 3: capturas.** Salve no scratchpad como `capturas_1b.py` e rode com a pasta de
  saída como argumento (os dados do usuário vão para dentro dela, nunca os reais):

```python
"""Capturas da etapa 1b nos dois temas e nas duas letras (offscreen)."""
import os
import sys
from pathlib import Path

SAIDA = Path(sys.argv[1]).resolve()
SAIDA.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["SIGFT_DADOS_DIR"] = str(SAIDA / "dados")
sys.path.insert(0, str(Path(__file__).resolve().parent) if False else "/home/user/sig-ft")

from PySide6.QtTest import QTest  # noqa: E402

from sigft.app import backends  # noqa: E402
from sigft.app_qt import letra, tema  # noqa: E402
from sigft.app_qt import main as qmain  # noqa: E402
from sigft.app_qt.widgets import resumo_lote  # noqa: E402

app = qmain._preparar_qt("escuro", "normal")
backends.carregar_todos(ao_falhar=lambda *_: None)
LINHAS = ["Lendo a planilha...", "   [Erro] Ficha 4500063671.0001 não encontrada.",
          "   [Aviso] A tabela de 'Documentos' está vazia nesta ficha.", "✅ 4500063671.0002",
          "[ERRO] A lista de fichas do portal não respondeu."]
for nome_tema in ("escuro", "claro"):
    for nome_letra in ("normal", "grande"):
        letra.aplicar(app, nome_letra, gravar=False)
        tema.aplicar(app, nome_tema, gravar=False)
        sufixo = f"{nome_tema}_{nome_letra}"
        janela = qmain.SIG_FT_App()
        janela.fechar_sem_perguntar = True
        janela.resize(1280, 850)
        janela.show()
        QTest.qWait(300)
        janela.grab().save(str(SAIDA / f"home_{sufixo}.png"))
        janela.show_frame("CopiaFichas")
        tela = janela.telas["CopiaFichas"]
        for linha in LINHAS:
            tela.log(linha)
        QTest.qWait(300)
        janela.grab().save(str(SAIDA / f"console_tudo_{sufixo}.png"))
        tela.console.filtrar("avisos")
        QTest.qWait(100)
        janela.grab().save(str(SAIDA / f"console_avisos_{sufixo}.png"))
        resumo = resumo_lote.abrir_resumo(tela, "Upload duplicadas", tela.pares_do_lote())
        QTest.qWait(200)
        resumo.grab().save(str(SAIDA / f"resumo_{sufixo}.png"))
        resumo.close()
        paleta = janela.abrir_paleta()
        QTest.keyClicks(paleta.campo, "tema")
        QTest.qWait(200)
        paleta.grab().save(str(SAIDA / f"ctrl_k_{sufixo}.png"))
        paleta.close()
        janela.close()
print(f"capturas em {SAIDA}")
```

  Rode: `.venv/bin/python <scratchpad>/capturas_1b.py <scratchpad>/capturas_1b`. Olhe cada
  PNG (o `Read` mostra imagem): barra do console legível nos dois temas, linha do título
  sem sobrepor na letra grande, resumo agrupado, Ctrl+K centrado. Mande ao Jonathan (e ao
  Luan) antes do PR, como pede a spec ("prints das telas principais nos dois temas").

- [ ] **Step 4: CHANGELOG.** No bloco `## 1.2.1 - 2026-10-16` (o único em aberto; confira
  com a skill `sigft-lancar-versao`: um bloco só, sem número novo), logo depois da linha
  "- Interface: a tela de carregamento abre no tema escolhido, com o número da versão.":

```markdown
- Interface: o console de cada tela ganha um **filtro** (Tudo, Avisos, Erros), uma busca que não liga para acento nem maiúscula e o botão **Copiar**, que leva só o que está à vista.
- Interface: quando um lote termina com erro ou aviso, abre a janela **Resumo**, com as linhas agrupadas por ficha (código PMIB) e os botões "Copiar lista" e "Abrir log". Lote sem problema continua só com a faixa "Terminou".
- Interface: dá para **arrastar o arquivo** do Windows até o botão que o escolhe (planilhas, manuais, a conferência do AutoSpec, a fila de fichas). Arquivo do tipo errado deixa o botão vermelho e não entra. Os **últimos 5 arquivos** de cada botão ficam num menu: a setinha ao lado da linha de seleção, ou o botão direito do mouse.
- Interface: **Ctrl+K** abre uma caixa de busca com os módulos e as ações da Home (Modelos de IA, Chaves de API, Abrir logs, Tema claro...). Digite parte do nome, ande com as setas e aperte Enter.
- Interface: **letra grande**. Na Home, ao lado do tema, escolha Normal ou Grande (2 px a mais em todo o SIG-FT). A troca é na hora e fica lembrada.
- Interface: com o SIG-FT atrás de outra janela, um **aviso do Windows** diz quando a tarefa terminou ("Upload duplicadas terminou com 2 erros") ou quando o robô espera você ("Faça o login no portal..."). Clicar no aviso traz o SIG-FT para a frente. Liga e desliga na Home, em "Avisar no Windows"; vem ligado.
```

  `.venv/bin/python -m pytest -q tests/test_novidades.py tests/test_texto_da_ui.py` → PASS.

- [ ] **Step 5: base de conhecimento.** Em `docs/base-conhecimento/00-frontend.md`, logo
  antes de `## Pontos de Atenção`:

```markdown
### Ferramentas de uso (etapa 1b, 2026-10-21)

- **Nível das linhas** (`sigft/app/niveis_log.py`, sem Qt): `classificar(msg, nivel)`;
  o `nivel` do protocolo vence quando é `error`/`warn`, senão a marca que ABRE a linha
  (`[Erro`, `[ERRO`, `❌`, `Falha` → erro; `[Aviso]`, `[AVISO]`, `[!]`,
  `[Autoconferência]`, `[Atenção]`, `Aviso:`, `⚠` → aviso). Tag nova de serviço sem
  nível decidido reprova `tests/test_niveis_log.py`.
- **Console** (`widgets/console.py`): guarda cada linha com nível e número (`marca()`,
  `linhas(desde=)`); barra na margem de BAIXO (Tudo / Avisos / Erros, busca sem acento,
  Copiar). A altura do console e o começo do texto não mudaram.
- **Resumo do lote** (`sigft/app/resumo_lote.py` + `widgets/resumo_lote.py`): no fim
  da última tarefa da tela (`ModuleFrame._fim_do_lote`), se houve erro ou aviso, a
  janela agrupada por código PMIB, com "Copiar lista" e "Abrir log" (grava em
  `logs\resumos\`). Desligada nos testes (`SIGFT_SEM_RESUMO_DO_LOTE`, conftest).
- **Arrastar e recentes** (`widgets/arrastar.py`): soltar o arquivo ENTREGA-o à chave
  do diálogo (`file_dialogs.entregar`) e clica o botão; o `ask_open_file(chave)` acha a
  entrega e não abre o diálogo. Tela com botão declara `ARRASTAVEIS`; `FilePickerRow` e
  `FileQueueList` já aceitam. Últimos 5 por chave em `user_prefs.json` (seção `recentes`).
- **Ctrl+K** (`widgets/paleta.py`): itens de `catalogo.comandos()` (módulos liberados +
  `catalogo.ACOES`), filtro `catalogo.filtrar`; quem faz é `SIG_FT_App.executar_comando`.
- **Letra** (`sigft/app_qt/letra.py`): Normal / Grande (`tokens.AUMENTO_DA_LETRA`),
  aplicada na hora como o tema: a folha do app e cada folha própria ganham +2 px; um
  vigia ajusta peça nova só com a letra grande. Smoke: `--letra grande`.
- **Aviso do Windows** (`sigft/app_qt/aviso_windows.py`): `QSystemTrayIcon.showMessage`
  fora de foco, no fim da tarefa e nas esperas (`DialogosDeEspera`); "Avisar no Windows"
  na Home. Nunca nos testes (`SIGFT_SEM_AVISO_DO_WINDOWS`, conftest).
```

- [ ] **Step 6: mural do `CLAUDE.md`.** O mural tem 5 avisos (o máximo): mova o mais antigo
  (2026-10-14, Luan) para `docs/refatoracao/PENDENCIAS.md` como uma linha datada (regra 2
  do mural), e acrescente no fim da tabela:

```markdown
| 2026-10-21 | Jonathan | 🔴 **Etapa 1b do sistema visual:** o console guarda cada linha com nível (`sigft/app/niveis_log.py`, marcas num lugar só) e tem barra de filtro embaixo; no fim da tarefa o `ModuleFrame` abre o Resumo e o aviso do Windows, **desligados nos testes** pelo `conftest` (quem testa tira a variável).<br>Botão de arquivo novo: declare em `ARRASTAVEIS` da tela (`widgets/arrastar.py`); tag nova de log (`[Algo]`) precisa de nível em `niveis_log` ou reprova `test_niveis_log`. |
```

- [ ] **Step 7:** `bash scripts/check.sh` → verde. Commit:

```bash
git add CHANGELOG.md docs/base-conhecimento/00-frontend.md CLAUDE.md docs/refatoracao/PENDENCIAS.md
git commit -m "Sistema visual 1b: CHANGELOG, doc da interface e mural"
```

- [ ] **Step 8: PR** para a base `jonathan/sistema-visual` (onde está a 1a), depois da
  aprovação das capturas:

```bash
git push -u origin jonathan/sistema-visual-1b
gh pr create --base jonathan/sistema-visual --head jonathan/sistema-visual-1b \
  --title "Sistema visual 1b: ferramentas de uso" --body "$(cat <<'EOF'
Etapa 1b da spec docs/superpowers/specs/2026-10-20-sistema-visual-design.md.

- Console: filtro Tudo/Avisos/Erros, busca sem acento, Copiar; marcas de nivel num lugar so (sigft/app/niveis_log.py).
- Resumo do lote: janela com erros e avisos agrupados por PMIB, Copiar lista e Abrir log.
- Arrastar arquivo para os botoes e linhas de selecao; ultimos 5 arquivos por dialogo.
- Ctrl+K: busca dos 11 modulos liberados e das acoes da Home.
- Letra Normal/Grande, aplicada na hora.
- Aviso do Windows fora de foco no fim da tarefa e nas esperas.

Nenhum servico nem robo mudou. Resumo e aviso desligados nos testes pelo conftest.
Verificacao: scripts/check.sh verde; --smoke nos dois temas e nas duas letras; capturas aprovadas.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Autoconferência do plano

**Cobertura da spec (§ Etapa 1b):**
1. Aviso do Windows (fim da tarefa em `_tarefa_acabou`, esperas em `pausar_e_esperar` e
   irmãs, clique traz a janela, liga/desliga na Home ligado por padrão, sem dependência): Task 7.
2. Resumo do lote (mesmo critério do item 5, agrupado por ficha com PMIB, "Copiar lista",
   "Abrir log", só com erro ou aviso, lê o que já se loga): Task 2.
3. Arrastar para `FilePickerRow` e para botão (`aceitar_arquivo(widget, chave, extensões,
   ao_receber)`), extensão errada vermelha, últimos 5 por chave em `user_prefs.json` com a
   seção registrada: Tasks 3 e 4.
4. Ctrl+K com os módulos e as ações da Home, sem acento e sem caixa, setas e Enter, lista
   em `catalogo.py`: Task 5 (letras: Task 6).
5. Filtro do console com `nivel` do protocolo e marcas num lugar só, teste com linhas reais: Task 1.
6. Letra Normal/Grande, +2 px em toda a escala, na Home, aplicada na hora, dos tokens: Task 6.
Fechamento (check, smoke nos dois temas, capturas, CHANGELOG "Interface:", doc, PR): Task 8.

**Nomes conferidos entre tarefas:** `Linha.msg/nivel`, `ConsoleFrame.marca/linhas(desde=)`
(1 → 2); `pares_do_lote`, `_fim_do_lote`, `titulo_da_tela`, `resumo_lote.agrupar/contar/frase_do_fim`
(2 → 7); `file_dialogs.entregar/descartar/pendente`, `Arrastavel`, `receptores_de_arquivo`
(3 → 4); `catalogo.ACOES`, `executar_comando`, `ACAO_NA_HOME` (5 → 6); `_folha_ferramentas`
(1 → 3 → 5, a versão inteira repetida em cada uma); `letra.aplicar`, `HomeView.escolher_letra` (6).
