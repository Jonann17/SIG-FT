# Diário de quedas, colunas lembradas e menu recolhível: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** três peças independentes da Tanda A (spec
`docs/superpowers/specs/2026-10-26-diario-colunas-menu-design.md`), num PR só: o diário de
quedas (`logs/diario.log`, `queda.log` e o aviso no topo da Home), as colunas lembradas nas
duas tabelas (seleção de fichas e Resumo do lote) e o menu lateral recolhível (com o Ctrl+K).

**Architecture:** o diário é um módulo sem Qt (`sigft/core/diario.py`, só biblioteca padrão)
com estado de processo: `abrir()` lê como a sessão anterior acabou ANTES de gravar a nova
`ABERTURA`, instala `sys.excepthook`, `threading.excepthook` e o `faulthandler`; a janela
(`main.py`) chama `abrir` na abertura e `registrar_fechamento` no `closeEvent` aceito, e a Home
lê `diario.aviso_pendente()`. As colunas são `sigft/app_qt/widgets/colunas.py`: uma função
pura (`juntar`) casa a preferência guardada com as colunas de agora, e `instalar_colunas` liga o
cabeçalho (mover, largura, menu do botão direito) às preferências (`core/prefs`, seção nova
`colunas`). O menu recolhível é `SIG_FT_App.recolher_menu`, que troca a largura da barra, o
texto e a dica dos botões, a marca e as seções; fica em `prefs.get_opcao("menu_recolhido")`.

**Tech Stack:** Python 3.10+, PySide6 6.11/6.12 (QtWidgets), pytest + pytest-qt (offscreen),
biblioteca padrão (`faulthandler`, `threading`, `platform`). Nenhuma dependência nova.

## Global Constraints

- Código, comentários, docs e commits em **português**; mensagem de commit **sem acento**; pé
  do commit com as linhas de atribuicao da sessao (vem no lembrete da sessao); o
  autor `git -c user.name=Jonathan -c user.email=jas.espinola.2022@aluno.unila.edu.br commit`.
  Nada de `git add -A`; nada de `git push`; não trocar de branch
  (`jonathan/diario-colunas-menu`).
- **Nenhum identificador de modelo de IA** escrito em arquivo do repositório (fora o pé do commit).
- **Serviço e `sigft/core/` nunca importam Qt.** `sigft/core/diario.py` só usa biblioteca
  padrão (`tests/test_diario.py` trava, como `tests/test_saida_log.py`). Nada em
  `sigft/services/`, `sigft/core/rpa/`, `sigft/core/web/` muda. Robôs, portal, serviços e o
  `sigft.log` (`core/saida_log.py`) ficam como estão (spec, "Fora do escopo").
- **Cor só em `sigft/app_qt/estilo.py`**, por papel ou variante: hexadecimal, `color:` ou
  `background:` em outro arquivo de `sigft/app_qt` reprova (`tests/test_qt_sem_cor_crua.py`).
- **Texto de interface por `t("texto em português")`**; constante de módulo em
  `marcar("...")` e `t(CONSTANTE)` onde aparece. Toda chave nova com tradução em
  `sigft/app/idiomas/es.json` e `en.json`, na forma do `--arrumar` (chaves em ordem, `indent=2`,
  acento como acento). Arquivo novo em `sigft/app_qt/` entra em `CONVERTIDOS` de
  `tests/test_textos_da_interface.py`. Texto que o usuário lê (código, catálogos e CHANGELOG):
  **sem travessão** (`—` nem `–`). Log, linha do diário e console: em português, fora do `t()`.
- Propriedade dinâmica do Qt se lê com `propriedades.ler(objeto, nome)`, **nunca** `.property(`
  direto em `sigft/` (`tests/test_propriedades.py`).
- Sinal de widget filho **não** recebe `lambda` que capture a tela ou a janela: método ligado
  (com `self.sender()` quando precisar saber quem chamou).
- Preferência é conveniência: ler ou gravar `prefs` **nunca** levanta para a interface
  (`try/except Exception` com `# noqa: BLE001`, como `tema.py`/`aviso_windows.py`).
- O diário **nunca impede a abertura** e nada dele levanta (spec, "Nunca impede a abertura").
- Os testes rodam em português (`tests/conftest.py`); teste de idioma usa
  `tests/_idioma.em_idioma(...)`. A pasta de dados de cada teste é isolada
  (`SIGFT_DADOS_DIR`), então `user_prefs.json` e `logs/` de um teste não vazam.
- Comandos de verificação (da raiz do repositório):
  `.venv/bin/python -m pytest -q <arquivos>`;
  `SIGFT_PY=.venv/bin/python bash scripts/check.sh` (a única falha conhecida neste contêiner é
  `tests/test_qt_saida.py::test_sessao_que_vaza_uma_tela_sai_com_zero`, preexistente);
  `.venv/bin/python -m ruff check .`;
  `QT_QPA_PLATFORM=offscreen timeout 180 .venv/bin/python frontend.py --smoke --idioma es`
  (e `pt`, `en`) sempre que `main.py`, uma tela ou a barra lateral mudar.
- Nada de reformatação em massa; cada tarefa termina num commit pequeno.

---

## Mapa de arquivos

| Arquivo | Responsabilidade | Tarefa |
|---|---|---|
| `sigft/core/diario.py` (novo) | linhas do diário, rotação, leitura da sessão anterior, ganchos de erro, `faulthandler` | 1 |
| `tests/test_diario.py` (novo) | o diário sem Qt | 1 |
| `sigft/app_qt/main.py` | `diario.abrir` no `main()`, `registrar_fechamento` no `closeEvent`; barra lateral recolhível, Ctrl+K `acao:menu` | 2, 4 |
| `sigft/app_qt/views/home.py` | aviso da sessão anterior no topo (`aviso_sessao`) | 2 |
| `tests/conftest.py` | `SIGFT_SEM_DIARIO=1` em toda a suíte | 2 |
| `tests/test_qt_diario.py` (novo) | abertura, fechamento e aviso da Home | 2 |
| `sigft/core/prefs.py` | seção `colunas`: `ler_colunas`, `gravar_colunas` | 3 |
| `sigft/app_qt/widgets/colunas.py` (novo) | `Coluna`, `juntar`, `descrever`, `ColunasLembradas`, `instalar_colunas` | 3 |
| `sigft/app_qt/widgets/dialogos_selecao.py` | `EsticaColunas` com `ligado`/`ajustando`; `TabelaSelecaoDialog(chave_colunas=, colunas_internas=)` | 3 |
| `sigft/app_qt/views/janelas.py` | as duas seleções passam a chave da tabela | 3 |
| `sigft/app_qt/widgets/resumo_lote.py` | cabeçalho com Mensagem e Tipo, colunas lembradas | 3 |
| `tests/test_colunas_juntar.py`, `tests/test_qt_colunas.py` (novos) | a função pura e o Qt | 3 |
| `sigft/app_qt/estilo.py` | `LARGURA_BARRA_RECOLHIDA`, regras `#traco_secao` e `[recolhido="true"]` | 4 |
| `sigft/app_qt/icones.py`, `assets/icons/chevrons-left.svg`, `chevrons-right.svg` (novos) | a seta do pé do menu | 4 |
| `sigft/app_qt/widgets/marca.py` | `Marca.recolher` (só o símbolo da GE) | 4 |
| `sigft/app_qt/catalogo.py` | ação `menu` do Ctrl+K, `comandos(menu_recolhido=)` | 4 |
| `tests/test_qt_menu_recolhivel.py` (novo), `tests/test_qt_paleta.py` | menu e Ctrl+K | 4 |
| `sigft/app/idiomas/es.json`, `en.json` | traduções novas | 2, 3, 4 |
| `tests/test_textos_da_interface.py` | `colunas.py` em `CONVERTIDOS` | 3 |
| `CHANGELOG.md`, `docs/base-conhecimento/00-frontend.md` | uma linha por peça no bloco 1.3.1; seção curta | 5 |

---

### Task 1: O diário de quedas, sem Qt

**Files:**
- Create: `sigft/core/diario.py`
- Test: `tests/test_diario.py`

**Interfaces:**
- Consumes: `sigft.core.dados_usuario.pasta_logs() -> Path` (cria `Documentos\SIG-FT\logs\`).
- Produces (usado pela Task 2):
  - constantes `ENV_DESLIGAR = "SIGFT_SEM_DIARIO"`, `ARQUIVO = "diario.log"`,
    `ARQUIVO_VELHO = "diario.log.1"`, `ARQUIVO_QUEDA = "queda.log"`,
    `ARQUIVO_QUEDA_ANTERIOR = "queda.log.anterior"`, `LIMITE_BYTES = 1024 * 1024`,
    `NORMAL = "normal"`, `CAIU = "caiu"`, `ENCERRADO = "encerrado"`;
  - `classificar(linhas: list[str], houve_queda: bool = False) -> str | None`;
  - `abrir(*, versao: str, idioma: str, pasta=None, ganchos: bool = True) -> str | None`
    (a situação da sessão anterior; `None` = não havia sessão ou o diário ficou desligado);
  - `registrar_fechamento() -> None`;
  - `registrar_erro(tipo, valor, rastro, *, onde: str = "") -> None`;
  - `ligado() -> bool`, `sessao_anterior() -> str | None`,
    `aviso_pendente() -> str | None` (`CAIU`/`ENCERRADO` ainda não dispensado),
    `dispensar_aviso() -> None`, `esquecer() -> None` (zera o estado; testes).
  - Formato da linha: `AAAA-MM-DD HH:MM:SS EVENTO detalhe`; os eventos são
    `ABERTURA versao=... idioma=... sistema=... python=...`, `FECHAMENTO pela janela` e
    `ERRO NAO TRATADO (thread <nome>)` seguido do traceback com 4 espaços na frente de cada linha.

- [ ] **Step 1: Write the failing tests**

Crie `tests/test_diario.py`:

```python
"""O diário de quedas (`sigft/core/diario.py`, 2026-10-26).

Sem Qt: a sessão anterior é lida do disco, a nova é marcada, e os ganchos de
erro (Python, threads, `faulthandler`) gravam no mesmo arquivo. O
`faulthandler` de verdade é o do pytest: aqui ele é trocado por um dublê.
"""
from __future__ import annotations

import ast
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from sigft.core import diario


def _linha(evento: str, quando: str = "2026-10-25 09:00:00") -> str:
    return f"{quando} {evento}\n"


class _FaultFalso:
    """O `faulthandler` de mentira: guarda o NOME do arquivo em que foi ligado."""

    def __init__(self) -> None:
        self.arquivo = None

    def enable(self, arquivo, all_threads=True) -> None:
        self.arquivo = Path(arquivo.name).name

    def disable(self) -> None:
        self.arquivo = None


@pytest.fixture
def ambiente(monkeypatch, tmp_path):
    monkeypatch.delenv(diario.ENV_DESLIGAR, raising=False)
    falso = _FaultFalso()
    monkeypatch.setattr(diario, "faulthandler", falso)
    # Os ganchos que o `abrir` troca voltam ao que eram no fim do teste.
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    diario.esquecer()
    yield SimpleNamespace(pasta=tmp_path, faulthandler=falso)
    diario.esquecer()


def _abrir(pasta, **kw):
    return diario.abrir(versao="1.3.1", idioma="es", pasta=pasta, **kw)


def _texto(pasta) -> str:
    return (pasta / diario.ARQUIVO).read_text(encoding="utf-8")


def _escrever(pasta, *eventos: str) -> None:
    (pasta / diario.ARQUIVO).write_text("".join(_linha(e) for e in eventos), encoding="utf-8")


# --- classificar: a regra, sem disco ------------------------------------------------

def test_sem_abertura_nao_ha_sessao_anterior():
    assert diario.classificar([]) is None
    assert diario.classificar(["lixo", _linha("FECHAMENTO pela janela")]) is None


def test_abertura_com_fechamento_e_normal():
    linhas = [_linha("ABERTURA versao=1.3.0"), _linha("FECHAMENTO pela janela")]
    assert diario.classificar(linhas) == diario.NORMAL


def test_erro_sem_fechamento_e_queda():
    linhas = [_linha("ABERTURA versao=1.3.0"), _linha("ERRO NAO TRATADO (thread principal)"),
              "    Traceback (most recent call last):\n"]
    assert diario.classificar(linhas) == diario.CAIU


def test_rastro_do_faulthandler_sem_fechamento_e_queda():
    assert diario.classificar([_linha("ABERTURA versao=1.3.0")], houve_queda=True) == diario.CAIU


def test_nada_depois_da_abertura_e_encerrado_de_fora():
    assert diario.classificar([_linha("ABERTURA versao=1.3.0")]) == diario.ENCERRADO


def test_erro_e_depois_fechamento_e_normal():
    # Erro num clique (o Qt segue) e a pessoa fechou a janela depois: fechou normal.
    linhas = [_linha("ABERTURA versao=1.3.0"), _linha("ERRO NAO TRATADO (thread principal)"),
              _linha("FECHAMENTO pela janela")]
    assert diario.classificar(linhas) == diario.NORMAL


def test_vale_so_a_ultima_sessao():
    caiu_e_depois_normal = [_linha("ABERTURA a"), _linha("ERRO NAO TRATADO (thread x)"),
                            _linha("ABERTURA b"), _linha("FECHAMENTO pela janela")]
    normal_e_depois_caiu = [_linha("ABERTURA a"), _linha("FECHAMENTO pela janela"),
                            _linha("ABERTURA b"), _linha("ERRO NAO TRATADO (thread x)")]
    assert diario.classificar(caiu_e_depois_normal) == diario.NORMAL
    assert diario.classificar(normal_e_depois_caiu) == diario.CAIU


def test_linha_do_traceback_nao_conta_como_evento():
    linhas = [_linha("ABERTURA a"), "    " + _linha("FECHAMENTO pela janela")]
    assert diario.classificar(linhas) == diario.ENCERRADO


# --- abrir: a sessão anterior e a nova ------------------------------------------------

def test_abrir_le_a_sessao_anterior_antes_de_marcar_a_nova(ambiente):
    _escrever(ambiente.pasta, "ABERTURA versao=1.3.0", "FECHAMENTO pela janela")
    assert _abrir(ambiente.pasta) == diario.NORMAL
    assert diario.sessao_anterior() == diario.NORMAL
    assert diario.aviso_pendente() is None
    ultima = _texto(ambiente.pasta).splitlines()[-1]
    assert " ABERTURA " in ultima
    assert "versao=1.3.1" in ultima and "idioma=es" in ultima and "sistema=" in ultima


def test_primeira_abertura_nao_tem_aviso(ambiente):
    assert _abrir(ambiente.pasta) is None
    assert diario.ligado()
    assert diario.aviso_pendente() is None


def test_queda_vira_aviso_ate_ser_dispensado(ambiente):
    _escrever(ambiente.pasta, "ABERTURA versao=1.3.0", "ERRO NAO TRATADO (thread principal)")
    assert _abrir(ambiente.pasta) == diario.CAIU
    assert diario.aviso_pendente() == diario.CAIU
    diario.dispensar_aviso()
    assert diario.aviso_pendente() is None
    assert diario.sessao_anterior() == diario.CAIU


def test_encerrado_de_fora_vira_aviso(ambiente):
    _escrever(ambiente.pasta, "ABERTURA versao=1.3.0")
    assert _abrir(ambiente.pasta) == diario.ENCERRADO
    assert diario.aviso_pendente() == diario.ENCERRADO


def test_queda_log_com_rastro_e_queda_e_vira_o_anterior(ambiente):
    _escrever(ambiente.pasta, "ABERTURA versao=1.3.0")
    (ambiente.pasta / diario.ARQUIVO_QUEDA).write_text("Fatal Python error: Segmentation fault\n",
                                                       encoding="utf-8")
    assert _abrir(ambiente.pasta) == diario.CAIU
    anterior = (ambiente.pasta / diario.ARQUIVO_QUEDA_ANTERIOR).read_text(encoding="utf-8")
    assert anterior.startswith("Fatal Python error")
    assert (ambiente.pasta / diario.ARQUIVO_QUEDA).read_text(encoding="utf-8") == ""
    assert ambiente.faulthandler.arquivo == diario.ARQUIVO_QUEDA


def test_queda_log_vazio_nao_e_queda(ambiente):
    _escrever(ambiente.pasta, "ABERTURA versao=1.3.0", "FECHAMENTO pela janela")
    (ambiente.pasta / diario.ARQUIVO_QUEDA).write_text("", encoding="utf-8")
    assert _abrir(ambiente.pasta) == diario.NORMAL
    assert not (ambiente.pasta / diario.ARQUIVO_QUEDA_ANTERIOR).exists()


def test_fechamento_gravado_a_proxima_abertura_ve_normal(ambiente):
    _abrir(ambiente.pasta)
    diario.registrar_fechamento()
    assert _texto(ambiente.pasta).splitlines()[-1].endswith("FECHAMENTO pela janela")
    diario.esquecer()
    assert _abrir(ambiente.pasta) == diario.NORMAL


def test_sem_fechamento_a_proxima_abertura_ve_encerrado(ambiente):
    _abrir(ambiente.pasta)
    diario.esquecer()
    assert _abrir(ambiente.pasta) == diario.ENCERRADO


def test_pasta_que_nao_grava_desliga_o_diario_e_nao_levanta(ambiente):
    gancho_antes = sys.excepthook
    bloqueio = ambiente.pasta / "nao_e_pasta"
    bloqueio.write_text("um arquivo no lugar da pasta", encoding="utf-8")
    assert _abrir(bloqueio) is None
    assert not diario.ligado()
    assert sys.excepthook is gancho_antes
    diario.registrar_fechamento()
    diario.registrar_erro(ValueError, ValueError("x"), None, onde="thread principal")
    assert diario.aviso_pendente() is None


def test_arquivo_estragado_nao_levanta(ambiente):
    (ambiente.pasta / diario.ARQUIVO).write_bytes(b"\xff\xfe\x00 lixo \x80\x81\n")
    assert _abrir(ambiente.pasta) is None
    assert diario.ligado()


def test_desligado_pela_variavel_nao_grava_nada(ambiente, monkeypatch):
    monkeypatch.setenv(diario.ENV_DESLIGAR, "1")
    assert _abrir(ambiente.pasta) is None
    assert not diario.ligado()
    assert not (ambiente.pasta / diario.ARQUIVO).exists()


# --- tamanho ---------------------------------------------------------------------------

def test_passou_de_1_mb_vira_ponto_1_e_recomeca(ambiente):
    grande = "x" * (diario.LIMITE_BYTES + 1)
    (ambiente.pasta / diario.ARQUIVO).write_text(grande, encoding="utf-8")
    _abrir(ambiente.pasta)
    assert (ambiente.pasta / diario.ARQUIVO_VELHO).read_text(encoding="utf-8") == grande
    linhas = _texto(ambiente.pasta).splitlines()
    assert len(linhas) == 1 and " ABERTURA " in linhas[0]


def test_sessao_que_ficou_metade_no_ponto_1_tambem_conta(ambiente):
    (ambiente.pasta / diario.ARQUIVO_VELHO).write_text(_linha("ABERTURA versao=1.3.0"), encoding="utf-8")
    (ambiente.pasta / diario.ARQUIVO).write_text(_linha("FECHAMENTO pela janela"), encoding="utf-8")
    assert _abrir(ambiente.pasta) == diario.NORMAL


# --- ganchos ----------------------------------------------------------------------------

def test_thread_que_quebra_fica_no_diario(ambiente, monkeypatch):
    vistos = []
    # No corpo do teste (e não na fixture): o pytest pode pôr o gancho dele ao
    # começar a fase do teste, e é o que estiver aqui que o diário embrulha.
    monkeypatch.setattr(threading, "excepthook", lambda args: vistos.append(args.exc_type))
    _abrir(ambiente.pasta)

    def quebrar():
        raise RuntimeError("robo caiu de proposito")

    linha = threading.Thread(target=quebrar, name="robo-teste")
    linha.start()
    linha.join()
    texto = _texto(ambiente.pasta)
    assert "ERRO NAO TRATADO (thread robo-teste)" in texto
    assert "    Traceback (most recent call last):" in texto
    assert "RuntimeError: robo caiu de proposito" in texto
    assert vistos == [RuntimeError]   # o gancho de antes continua sendo chamado


def test_erro_da_thread_principal_fica_no_diario(ambiente, monkeypatch):
    vistos = []
    monkeypatch.setattr(sys, "excepthook", lambda tipo, valor, rastro: vistos.append(tipo))
    _abrir(ambiente.pasta)
    try:
        raise ValueError("de proposito")
    except ValueError:
        sys.excepthook(*sys.exc_info())
    assert vistos == [ValueError]
    assert "ERRO NAO TRATADO (thread principal)" in _texto(ambiente.pasta)
    assert diario.classificar(_texto(ambiente.pasta).splitlines()) == diario.CAIU


def test_sem_ganchos_nao_troca_nada(ambiente):
    antes = (sys.excepthook, threading.excepthook)
    _abrir(ambiente.pasta, ganchos=False)
    assert (sys.excepthook, threading.excepthook) == antes
    assert ambiente.faulthandler.arquivo is None


def test_modulo_nao_importa_interface():
    from test_sem_interface_antiga import MODULOS_PROIBIDOS

    arvore = ast.parse(Path(diario.__file__).read_text(encoding="utf-8"))
    nomes = {n.module if isinstance(n, ast.ImportFrom) else a.name
             for n in ast.walk(arvore) if isinstance(n, (ast.Import, ast.ImportFrom))
             for a in (n.names if isinstance(n, ast.Import) else [n])}
    assert not any(n and n.split(".")[0] in MODULOS_PROIBIDOS | {"PySide6"} for n in nomes)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest -q tests/test_diario.py`
Expected: FAIL na coleta, `ImportError: cannot import name 'diario' from 'sigft.core'`.

- [ ] **Step 3: Write the implementation**

Crie `sigft/core/diario.py`:

```python
"""O diário de quedas: como cada sessão do SIG-FT terminou (2026-10-26).

Quando alguém diz "o SIG-FT fechou sozinho", o `sigft.log` (`core/saida_log.py`)
não diz se a pessoa fechou a janela, se o app caiu ou se foi encerrado de fora.
Este diário diz: uma linha por evento, com data e hora, em
`Documentos\\SIG-FT\\logs\\diario.log`:

* `ABERTURA` na abertura, com a versão, o idioma e o sistema;
* `FECHAMENTO pela janela` quando a janela principal fecha (o `closeEvent` aceito);
* `ERRO NAO TRATADO (thread ...)` com o traceback, pelo `sys.excepthook` e pelo
  `threading.excepthook` (os robôs rodam em threads). As linhas do traceback vêm
  com 4 espaços na frente: só a linha que começa pela data é evento.

Queda dura (o processo morre sem passar pelo Python): o `faulthandler` grava o
rastro em `logs\\queda.log`, aberto na abertura e mantido aberto.

A sessão ANTERIOR é lida em `abrir`, antes de a nova `ABERTURA` ser gravada
(`classificar`): com `FECHAMENTO` depois da última `ABERTURA`, fechou normal; sem
ele, e com `ERRO NAO TRATADO` ou `queda.log` não vazio, caiu; sem nada, foi
encerrado de fora (Gerenciador de Tarefas, desligamento, falta de luz). O
`queda.log` com rastro vira `queda.log.anterior` antes de o novo ser aberto.

Passou de `LIMITE_BYTES`, o arquivo vira `diario.log.1` (uma cópia só) e
recomeça; a leitura da sessão anterior junta os dois.

**Nunca impede a abertura**: pasta sem permissão, disco cheio ou arquivo
estragado deixam o diário desligado nesta sessão, e nada daqui levanta. Nos
testes vem desligado (`ENV_DESLIGAR`, posta pelo `tests/conftest.py`).

Só biblioteca padrão: nenhum import de interface aqui.
"""
from __future__ import annotations

import faulthandler
import os
import platform
import re
import sys
import threading
import time
import traceback
from pathlib import Path

ENV_DESLIGAR = "SIGFT_SEM_DIARIO"
ARQUIVO = "diario.log"
ARQUIVO_VELHO = "diario.log.1"
ARQUIVO_QUEDA = "queda.log"
ARQUIVO_QUEDA_ANTERIOR = "queda.log.anterior"
LIMITE_BYTES = 1024 * 1024

ABERTURA = "ABERTURA"
FECHAMENTO = "FECHAMENTO pela janela"
ERRO = "ERRO NAO TRATADO"

# Como a sessão anterior acabou (`classificar`).
NORMAL = "normal"
CAIU = "caiu"
ENCERRADO = "encerrado"

# Só a linha que COMEÇA pela data é evento (o traceback vem recuado).
_EVENTO = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} (ABERTURA|FECHAMENTO|ERRO NAO TRATADO)\b")

_pasta: Path | None = None        # None: diário desligado nesta sessão
_anterior: str | None = None
_dispensado = False
_arquivo_queda = None             # o queda.log aberto, onde o faulthandler escreve


def classificar(linhas: list[str], houve_queda: bool = False) -> str | None:
    """Como a última sessão de `linhas` acabou: `NORMAL`, `CAIU` ou `ENCERRADO`.
    `None` quando não há `ABERTURA` (primeira vez, ou diário apagado)."""
    eventos = [m.group(1) for linha in linhas if (m := _EVENTO.match(linha))]
    if ABERTURA not in eventos:
        return None
    ultima = len(eventos) - 1 - eventos[::-1].index(ABERTURA)
    depois = eventos[ultima + 1:]
    if "FECHAMENTO" in depois:
        return NORMAL
    if ERRO in depois or houve_queda:
        return CAIU
    return ENCERRADO


def _ler_linhas(pasta: Path) -> list[str]:
    """`diario.log.1` e depois `diario.log`: a sessão anterior pode ter começado
    antes de uma rotação."""
    linhas: list[str] = []
    for nome in (ARQUIVO_VELHO, ARQUIVO):
        try:
            linhas += (pasta / nome).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            pass
    return linhas


def _houve_queda(pasta: Path) -> bool:
    try:
        return (pasta / ARQUIVO_QUEDA).stat().st_size > 0
    except OSError:
        return False


def _guardar_queda_anterior(pasta: Path) -> None:
    """O `queda.log` com rastro vira `queda.log.anterior` (o vazio é só reaberto)."""
    try:
        if _houve_queda(pasta):
            os.replace(pasta / ARQUIVO_QUEDA, pasta / ARQUIVO_QUEDA_ANTERIOR)
    except OSError:
        pass


def _gravar(evento: str) -> bool:
    """Uma linha no diário (abre, escreve e fecha: o que foi escrito fica no disco
    mesmo que o processo morra logo depois). `False` se não deu."""
    if _pasta is None:
        return False
    try:
        arquivo = _pasta / ARQUIVO
        try:
            if arquivo.stat().st_size > LIMITE_BYTES:
                os.replace(arquivo, _pasta / ARQUIVO_VELHO)
        except FileNotFoundError:
            pass
        with open(arquivo, "a", encoding="utf-8") as saida:
            saida.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {evento}\n")
        return True
    except Exception:  # noqa: BLE001 -- o diário nunca derruba o app
        return False


def registrar_erro(tipo, valor, rastro, *, onde: str = "") -> None:
    """`ERRO NAO TRATADO (onde)` e o traceback recuado. Nunca levanta."""
    try:
        texto = "".join(traceback.format_exception(tipo, valor, rastro)).rstrip("\n")
        recuado = "\n".join("    " + linha for linha in texto.splitlines())
        _gravar(f"{ERRO} ({onde or 'desconhecido'})\n{recuado}")
    except Exception:  # noqa: BLE001 -- o diário nunca derruba o app
        pass


def registrar_fechamento() -> None:
    """A janela principal fechou (o `closeEvent` aceito)."""
    _gravar(FECHAMENTO)


def _instalar_ganchos(pasta: Path) -> None:
    """Erro não tratado (thread principal e threads) e queda dura vão para o diário.
    Cada gancho chama o que havia antes: o traceback continua saindo onde saía."""
    global _arquivo_queda
    anterior_python = sys.excepthook
    anterior_thread = threading.excepthook

    def _no_python(tipo, valor, rastro):
        registrar_erro(tipo, valor, rastro, onde="thread principal")
        anterior_python(tipo, valor, rastro)

    def _na_thread(args):
        if args.exc_type is not SystemExit:
            nome = args.thread.name if args.thread is not None else "?"
            registrar_erro(args.exc_type, args.exc_value, args.exc_traceback, onde=f"thread {nome}")
        anterior_thread(args)

    sys.excepthook = _no_python
    threading.excepthook = _na_thread
    try:
        _arquivo_queda = open(pasta / ARQUIVO_QUEDA, "w", encoding="utf-8")
        faulthandler.enable(_arquivo_queda, all_threads=True)
    except Exception:  # noqa: BLE001 -- sem o rastro da queda dura, o resto segue
        _arquivo_queda = None


def abrir(*, versao: str, idioma: str, pasta: str | os.PathLike[str] | None = None,
          ganchos: bool = True) -> str | None:
    """Lê como a sessão anterior acabou, marca a `ABERTURA` desta e (com `ganchos`)
    liga os ganchos de erro e o `faulthandler`. Devolve a situação da anterior
    (`NORMAL`, `CAIU`, `ENCERRADO`) ou `None`. Nunca levanta: qualquer falha deixa
    o diário desligado nesta sessão."""
    global _pasta, _anterior
    esquecer()
    if os.environ.get(ENV_DESLIGAR):
        return None
    try:
        if pasta is None:
            from sigft.core.dados_usuario import pasta_logs

            pasta = pasta_logs()
        pasta = Path(pasta)
        anterior = classificar(_ler_linhas(pasta), _houve_queda(pasta))
        _guardar_queda_anterior(pasta)
        _pasta = pasta
        detalhe = (f"versao={versao} idioma={idioma} sistema={platform.platform()} "
                   f"python={platform.python_version()}")
        if not _gravar(f"{ABERTURA} {detalhe}"):
            _pasta = None
            return None
        _anterior = anterior
        if ganchos:
            _instalar_ganchos(pasta)
        return anterior
    except Exception:  # noqa: BLE001 -- o diário nunca impede a abertura
        _pasta = None
        return None


def ligado() -> bool:
    return _pasta is not None


def sessao_anterior() -> str | None:
    return _anterior


def aviso_pendente() -> str | None:
    """`CAIU` ou `ENCERRADO` enquanto o aviso da Home não foi dispensado."""
    if _dispensado or _anterior not in (CAIU, ENCERRADO):
        return None
    return _anterior


def dispensar_aviso() -> None:
    """O "Entendido" da Home: o aviso some até a próxima queda."""
    global _dispensado
    _dispensado = True


def esquecer() -> None:
    """Zera o estado (desliga o `faulthandler` e fecha o `queda.log`, se abertos).
    Os ganchos de `sys`/`threading` ficam: quem testa os devolve (`monkeypatch`)."""
    global _pasta, _anterior, _dispensado, _arquivo_queda
    if _arquivo_queda is not None:
        try:
            faulthandler.disable()
        except Exception:  # noqa: BLE001
            pass
        try:
            _arquivo_queda.close()
        except Exception:  # noqa: BLE001
            pass
    _pasta, _anterior, _dispensado, _arquivo_queda = None, None, False, None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q tests/test_diario.py`
Expected: PASS (todos).

Run: `.venv/bin/python -m ruff check sigft/core/diario.py tests/test_diario.py`
Expected: `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add sigft/core/diario.py tests/test_diario.py
git -c user.name=Jonathan -c user.email=jas.espinola.2022@aluno.unila.edu.br commit -F - <<'EOF'
Diario de quedas: abertura, fechamento, erro nao tratado e queda dura

<linhas de atribuicao da sessao>
EOF
```

---

### Task 2: O diário ligado ao app (abertura, fechamento e o aviso da Home)

**Files:**
- Modify: `sigft/app_qt/main.py` (imports perto da linha 54; `closeEvent` perto da linha 401;
  `main()` perto da linha 662)
- Modify: `sigft/app_qt/views/home.py` (imports perto da linha 40; constantes depois de
  `TEXTO_PROCURANDO`; `HomeView.__init__` antes do cabeçalho; dois métodos novos)
- Modify: `tests/conftest.py` (fixture `_sem_janelas_do_fim_da_tarefa`)
- Modify: `sigft/app/idiomas/es.json`, `sigft/app/idiomas/en.json`
- Test: `tests/test_qt_diario.py`

**Interfaces:**
- Consumes (Task 1): `diario.abrir(*, versao, idioma, pasta=None, ganchos=True)`,
  `diario.registrar_fechamento()`, `diario.aviso_pendente()`, `diario.dispensar_aviso()`,
  `diario.ligado()`, `diario.esquecer()`, `diario.CAIU`, `diario.ENCERRADO`,
  `diario.ENV_DESLIGAR`, `diario.ARQUIVO`.
- Produces:
  - `home.AVISO_DA_SESSAO: dict[str, str]` (`diario.CAIU`/`diario.ENCERRADO` -> texto marcado),
    `home.TEXTO_ABRIR_REGISTRO`, `home.TEXTO_ENTENDIDO`, `home.DICA_ABRIR_REGISTRO`;
  - `HomeView.aviso_sessao: QFrame | None`, `HomeView.lbl_aviso_sessao`,
    `HomeView.btn_abrir_registro`, `HomeView.btn_entendido`,
    `HomeView.abrir_registro() -> None`, `HomeView.dispensar_aviso_da_sessao() -> None`.

- [ ] **Step 1: Write the failing tests**

Crie `tests/test_qt_diario.py`:

```python
"""O diário de quedas na interface (2026-10-26): a abertura no `main()`, o
fechamento pela janela e o aviso no topo da Home."""
from __future__ import annotations

import os
import sys
import threading

import pytest
from PySide6.QtWidgets import QMessageBox

from _idioma import ainda_em_portugues, em_idioma
from sigft import _build_info
from sigft.app import idioma
from sigft.app_qt import escolha_de_idioma
from sigft.app_qt import main as qmain
from sigft.app_qt.views import home as home_mod
from sigft.app_qt.views.home import HomeView
from sigft.core import diario, instancia


class _FaultFalso:
    def enable(self, arquivo, all_threads=True) -> None:
        pass

    def disable(self) -> None:
        pass


@pytest.fixture
def diario_em(monkeypatch, tmp_path):
    """Liga o diário numa pasta temporária, com a sessão anterior escrita pelos
    eventos dados (sem os ganchos: o teste é da interface)."""
    monkeypatch.delenv(diario.ENV_DESLIGAR, raising=False)
    monkeypatch.setattr(diario, "faulthandler", _FaultFalso())
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    diario.esquecer()

    def _ligar(*eventos: str):
        texto = "".join(f"2026-10-25 09:00:00 {e}\n" for e in eventos)
        (tmp_path / diario.ARQUIVO).write_text(texto, encoding="utf-8")
        diario.abrir(versao="1.3.1", idioma="pt", pasta=tmp_path, ganchos=False)
        return tmp_path

    yield _ligar
    diario.esquecer()


@pytest.fixture
def janela(qt_interface, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    j = qmain.SIG_FT_App()
    qtbot.addWidget(j)
    return j


def test_nos_testes_o_diario_vem_desligado():
    assert os.environ.get(diario.ENV_DESLIGAR) == "1"
    assert not diario.ligado()


# --- a Home ---------------------------------------------------------------------------

def test_home_sem_aviso_quando_a_ultima_sessao_fechou_normal(qt_interface, qtbot, diario_em):
    diario_em("ABERTURA versao=1.3.0", "FECHAMENTO pela janela")
    home = HomeView()
    qtbot.addWidget(home)
    assert home.aviso_sessao is None


def test_home_avisa_a_queda_e_o_entendido_some_com_ele(qt_interface, qtbot, diario_em):
    diario_em("ABERTURA versao=1.3.0", "ERRO NAO TRATADO (thread principal)")
    home = HomeView()
    qtbot.addWidget(home)
    home.show()
    assert home.aviso_sessao.isVisible()
    assert home.lbl_aviso_sessao.text() == "Da última vez, o SIG-FT fechou de forma inesperada."
    home.btn_entendido.click()
    assert not home.aviso_sessao.isVisible()
    assert diario.aviso_pendente() is None
    outra = HomeView()
    qtbot.addWidget(outra)
    assert outra.aviso_sessao is None


def test_home_avisa_o_encerramento_de_fora(qt_interface, qtbot, diario_em):
    diario_em("ABERTURA versao=1.3.0")
    home = HomeView()
    qtbot.addWidget(home)
    assert home.lbl_aviso_sessao.text() == (
        "Da última vez, o SIG-FT foi encerrado sem fechar a janela "
        "(pelo Gerenciador de Tarefas ou ao desligar o computador).")


def test_abrir_o_registro_abre_a_pasta_de_logs(qt_interface, qtbot, diario_em, monkeypatch):
    chamadas = []
    monkeypatch.setattr(home_mod.pasta_de_logs, "abrir", lambda pai=None: chamadas.append(pai))
    diario_em("ABERTURA versao=1.3.0")
    home = HomeView()
    qtbot.addWidget(home)
    assert home.btn_abrir_registro.toolTip()
    home.btn_abrir_registro.click()
    assert chamadas == [home]


@pytest.mark.parametrize("codigo", ["es", "en"])
def test_aviso_traduzido(qt_interface, qtbot, diario_em, codigo):
    diario_em("ABERTURA versao=1.3.0", "ERRO NAO TRATADO (thread principal)")
    with em_idioma(codigo):
        home = HomeView()
        qtbot.addWidget(home)
        assert ainda_em_portugues(home.aviso_sessao, codigo) == set()


# --- a janela -------------------------------------------------------------------------

def test_fechar_a_janela_grava_o_fechamento(janela, diario_em):
    pasta = diario_em()
    janela.fechar_sem_perguntar = True
    janela.close()
    ultima = (pasta / diario.ARQUIVO).read_text(encoding="utf-8").splitlines()[-1]
    assert ultima.endswith("FECHAMENTO pela janela")


def test_fechar_recusado_nao_grava_o_fechamento(janela, diario_em, monkeypatch):
    pasta = diario_em()
    monkeypatch.setattr(instancia, "tarefas_em_andamento", lambda: True)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    janela.close()
    assert "FECHAMENTO" not in (pasta / diario.ARQUIVO).read_text(encoding="utf-8")
    janela.fechar_sem_perguntar = True   # a faxina do qtbot fecha sem perguntar


def test_main_abre_o_diario_depois_do_idioma_e_antes_da_splash(qt_interface, monkeypatch):
    from sigft.core import dados_usuario
    from sigft.core.rpa import navegador

    eventos = []

    class SplashFalsa:
        pronta = type("S", (), {"connect": lambda self, f: None})()

        def __init__(self):
            eventos.append("splash")

        def show(self):
            pass

        def carregar(self):
            pass

    app_falso = type("A", (), {"exec": lambda self: None})()
    monkeypatch.setattr(instancia, "preparar", lambda: None)
    monkeypatch.setattr(instancia, "encerrar", lambda codigo=0: None)
    monkeypatch.setattr(dados_usuario, "migrar_se_preciso", lambda: [])
    monkeypatch.setattr(navegador, "preparar_ambiente_do_rpa", lambda: None)
    monkeypatch.setattr(qmain, "_preparar_qt", lambda: eventos.append("qt") or app_falso)
    monkeypatch.setattr(escolha_de_idioma, "perguntar_na_abertura",
                        lambda: eventos.append("idioma") or None)
    monkeypatch.setattr(diario, "abrir",
                        lambda **k: eventos.append(("diario", k["versao"], k["idioma"])))
    monkeypatch.setattr(qmain, "SplashScreen", SplashFalsa)
    qmain.main()
    assert eventos == ["qt", "idioma", ("diario", _build_info.VERSAO, idioma.atual()), "splash"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest -q tests/test_qt_diario.py`
Expected: FAIL. `test_nos_testes_o_diario_vem_desligado` (a variável não existe ainda),
`AttributeError: 'HomeView' object has no attribute 'aviso_sessao'`, e os da janela e do
`main()` (nada grava `FECHAMENTO`, `abrir` não é chamado).

- [ ] **Step 3: Desligar o diário em toda a suíte**

Em `tests/conftest.py`, dentro de `_sem_janelas_do_fim_da_tarefa`, depois da linha
`monkeypatch.setenv("SIGFT_SEM_AVISO_DO_WINDOWS", "1")`, acrescente:

```python
    # [2026-10-26] O diário de quedas (`sigft/core/diario.py`) NUNCA nos testes: o
    # `main()` dos testes gravaria no `logs/` e trocaria o `faulthandler` do pytest.
    # Quem testa o diário tira a variável e usa uma pasta temporária.
    monkeypatch.setenv("SIGFT_SEM_DIARIO", "1")
```

- [ ] **Step 4: Ligar o diário na janela e no `main()`**

Em `sigft/app_qt/main.py`, troque o import

```python
from sigft.core import instancia
```

por

```python
from sigft.core import diario, instancia
```

No `closeEvent`, troque o fim

```python
            if resposta != QMessageBox.StandardButton.Yes:
                evento.ignore()
                return
        evento.accept()
```

por

```python
            if resposta != QMessageBox.StandardButton.Yes:
                evento.ignore()
                return
        evento.accept()
        # [2026-10-26] O diário de quedas: esta sessão fechou pela janela. O "Não"
        # da pergunta acima não chega aqui. Sem diário aberto, não faz nada.
        diario.registrar_fechamento()
```

No `main()`, troque

```python
    if (escolhido := escolha_de_idioma.perguntar_na_abertura()) is not None:
        _aplicar_idioma(app, escolhido)
    splash = SplashScreen()
```

por

```python
    if (escolhido := escolha_de_idioma.perguntar_na_abertura()) is not None:
        _aplicar_idioma(app, escolhido)
    # [2026-10-26] O diário de quedas (`sigft/core/diario.py`): lê como a sessão
    # anterior acabou (a Home avisa se caiu ou foi encerrada de fora), marca esta
    # abertura e liga os ganchos de erro e o `faulthandler`. Depois do idioma (a
    # linha da abertura o leva) e antes da janela. Nunca levanta.
    diario.abrir(versao=_build_info.VERSAO, idioma=idioma.atual())
    splash = SplashScreen()
```

- [ ] **Step 5: O aviso no topo da Home**

Em `sigft/app_qt/views/home.py`, depois de `from sigft.app_qt.widgets.painel_janela import JanelaPainel`
acrescente:

```python
from sigft.core import diario
```

Depois de `TEXTO_PROCURANDO = marcar("Procurando...")`, acrescente:

```python
# O aviso da sessão anterior no topo da Home (2026-10-26): o diário de quedas
# (`sigft/core/diario.py`) diz se a última sessão caiu ou foi encerrada de fora.
AVISO_DA_SESSAO = {
    diario.CAIU: marcar("Da última vez, o SIG-FT fechou de forma inesperada."),
    diario.ENCERRADO: marcar("Da última vez, o SIG-FT foi encerrado sem fechar a janela "
                             "(pelo Gerenciador de Tarefas ou ao desligar o computador)."),
}
TEXTO_ABRIR_REGISTRO = marcar("Abrir o registro")
TEXTO_ENTENDIDO = marcar("Entendido")
DICA_ABRIR_REGISTRO = marcar("Abre a pasta de logs, onde fica o diário do SIG-FT (diario.log).")
```

No `HomeView.__init__`, troque

```python
        layout.setContentsMargins(46, 46, 57, 20)
        layout.setSpacing(0)

        # --- CABEÇALHO --- (pady (20, 5); (0, 20); 10; os de baixo somam)
```

por

```python
        layout.setContentsMargins(46, 46, 57, 20)
        layout.setSpacing(0)

        # --- AVISO DA SESSÃO ANTERIOR --- [2026-10-26] Só quando a última sessão
        # caiu ou foi encerrada de fora; sem janela modal.
        self.aviso_sessao = self._criar_aviso_da_sessao()
        if self.aviso_sessao is not None:
            layout.addWidget(self.aviso_sessao)
            layout.addSpacing(16)

        # --- CABEÇALHO --- (pady (20, 5); (0, 20); 10; os de baixo somam)
```

E acrescente, logo depois do método `criar_texto_simples`:

```python
    # =====================================================================
    # AVISO DA SESSÃO ANTERIOR  [2026-10-26]
    # =====================================================================
    def _criar_aviso_da_sessao(self):
        """O cartão com borda de aviso, o texto e os botões "Abrir o registro" e
        "Entendido". `None` quando a sessão anterior fechou normal (ou o diário
        está desligado), ou quando o aviso já foi dispensado."""
        texto = AVISO_DA_SESSAO.get(diario.aviso_pendente())
        if texto is None:
            return None
        quadro = QFrame(objectName="cartao")
        quadro.setProperty("borda", "aviso")
        linha = QHBoxLayout(quadro)
        linha.setContentsMargins(14, 10, 14, 10)
        linha.setSpacing(10)
        self.lbl_aviso_sessao = blocos.rotulo(t(texto), alinhar="esquerda")
        linha.addWidget(self.lbl_aviso_sessao, 1)
        self.btn_abrir_registro = blocos.botao(t(TEXTO_ABRIR_REGISTRO), variante="secundario")
        self.btn_abrir_registro.setToolTip(t(DICA_ABRIR_REGISTRO))
        self.btn_abrir_registro.clicked.connect(self.abrir_registro)
        linha.addWidget(self.btn_abrir_registro)
        self.btn_entendido = blocos.botao(t(TEXTO_ENTENDIDO), variante="primario")
        self.btn_entendido.clicked.connect(self.dispensar_aviso_da_sessao)
        linha.addWidget(self.btn_entendido)
        return quadro

    def abrir_registro(self) -> None:
        """A pasta de logs (o `diario.log` e o `queda.log.anterior`), como o "Abrir logs"."""
        pasta_de_logs.abrir(self)

    def dispensar_aviso_da_sessao(self) -> None:
        """"Entendido": o aviso some até a próxima queda."""
        diario.dispensar_aviso()
        if _vivo(self.aviso_sessao):
            self.aviso_sessao.hide()
```

(`QFrame`, `QHBoxLayout`, `blocos`, `pasta_de_logs` e `_vivo` já estão importados/definidos em
`home.py`. As cores vêm da folha: `#cartao` e `#cartao[borda="aviso"]` já existem em
`estilo.py`.)

- [ ] **Step 6: As traduções**

```bash
.venv/bin/python - <<'EOF'
import json
import pathlib

NOVOS = {
    "es": {
        "Da última vez, o SIG-FT fechou de forma inesperada.":
            "La última vez, SIG-FT se cerró de forma inesperada.",
        "Da última vez, o SIG-FT foi encerrado sem fechar a janela (pelo Gerenciador de Tarefas "
        "ou ao desligar o computador).":
            "La última vez, SIG-FT fue finalizado sin cerrar la ventana (desde el Administrador "
            "de tareas o al apagar el equipo).",
        "Abrir o registro": "Abrir el registro",
        "Entendido": "Entendido",
        "Abre a pasta de logs, onde fica o diário do SIG-FT (diario.log).":
            "Abre la carpeta de logs, donde está el diario de SIG-FT (diario.log).",
    },
    "en": {
        "Da última vez, o SIG-FT fechou de forma inesperada.":
            "Last time, SIG-FT closed unexpectedly.",
        "Da última vez, o SIG-FT foi encerrado sem fechar a janela (pelo Gerenciador de Tarefas "
        "ou ao desligar o computador).":
            "Last time, SIG-FT was ended without closing the window (from Task Manager or "
            "when shutting down the computer).",
        "Abrir o registro": "Open the log",
        "Entendido": "Got it",
        "Abre a pasta de logs, onde fica o diário do SIG-FT (diario.log).":
            "Opens the logs folder, where the SIG-FT diary is (diario.log).",
    },
}
for codigo, pares in NOVOS.items():
    caminho = pathlib.Path("sigft/app/idiomas") / f"{codigo}.json"
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    dados.update(pares)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
EOF
.venv/bin/python tools/textos_da_interface.py --arrumar
.venv/bin/python tools/textos_da_interface.py
```

Expected da última linha: `es: 0 faltando, 0 sobrando` e `en: 0 faltando, 0 sobrando`.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q tests/test_qt_diario.py tests/test_diario.py tests/test_textos_da_interface.py tests/test_qt_home.py tests/test_qt_main.py tests/test_qt_idioma_abertura.py tests/test_qt_sem_cor_crua.py`
Expected: PASS.

Run: `QT_QPA_PLATFORM=offscreen timeout 180 .venv/bin/python frontend.py --smoke --idioma es`
Expected: termina com `[smoke] a janela principal Qt montou, as 12 telas abriram e ela fechou sem erro.`

- [ ] **Step 8: Gate completo e commit**

Run: `SIGFT_PY=.venv/bin/python bash scripts/check.sh`
Expected: verde, exceto `tests/test_qt_saida.py::test_sessao_que_vaza_uma_tela_sai_com_zero`.

```bash
git add sigft/app_qt/main.py sigft/app_qt/views/home.py tests/conftest.py tests/test_qt_diario.py \
    sigft/app/idiomas/es.json sigft/app/idiomas/en.json
git -c user.name=Jonathan -c user.email=jas.espinola.2022@aluno.unila.edu.br commit -F - <<'EOF'
Diario de quedas no app: abertura, fechamento e aviso no topo da Home

<linhas de atribuicao da sessao>
EOF
```

---

### Task 3: Colunas lembradas (seleção de fichas e Resumo do lote)

**Files:**
- Modify: `sigft/core/prefs.py` (`_SECOES_ESTADO` e uma seção nova no fim)
- Create: `sigft/app_qt/widgets/colunas.py`
- Modify: `sigft/app_qt/widgets/dialogos_selecao.py` (`EsticaColunas`, `TabelaSelecaoDialog.__init__`)
- Modify: `sigft/app_qt/views/janelas.py` (`JanelaSelecao`, `JanelaSelecaoDuplicadas`)
- Modify: `sigft/app_qt/widgets/resumo_lote.py` (a árvore)
- Modify: `tests/test_textos_da_interface.py` (`CONVERTIDOS`)
- Modify: `sigft/app/idiomas/es.json`, `sigft/app/idiomas/en.json`
- Test: `tests/test_colunas_juntar.py`, `tests/test_qt_colunas.py`

**Interfaces:**
- Consumes: `sigft.core.prefs._carregar_estado/_salvar_estado` (internos do próprio `prefs`);
  `dialogos_selecao.tabela_ttk(colunas) -> QTreeWidget` (com `tree.esticar_colunas`).
- Produces:
  - `prefs.CHAVE_COLUNAS = "colunas"`, `prefs.ler_colunas(chave, *, config_path=None) -> object`,
    `prefs.gravar_colunas(chave, valor: object, *, config_path=None) -> None` (`valor=None` apaga);
  - `colunas.Coluna(chave: str, largura: int | None, visivel: bool)` (NamedTuple);
  - `colunas.juntar(guardado: object, colunas: Sequence[str]) -> list[Coluna] | None`;
  - `colunas.descrever(colunas: Sequence[Coluna]) -> list[dict]`;
  - `colunas.ColunasLembradas` com `chave: str`, `colunas: list[str]`, `aplicar(lista)`,
    `estado() -> list[Coluna]`, `mostrar_coluna(chave, visivel) -> bool`, `gravar()`,
    `restaurar()`, `montar_menu() -> QMenu`;
  - `colunas.instalar_colunas(tabela, chave: str, colunas: Sequence[str]) -> ColunasLembradas`
    (também guardado em `tabela.colunas_lembradas`);
  - `EsticaColunas.ligado: bool`, `.ajustando: bool`, `.esticar()`, `.ligar()`, `.desligar()`;
  - `TabelaSelecaoDialog(..., chave_colunas: str | None = None, colunas_internas=None)` e
    `TabelaSelecaoDialog.colunas: ColunasLembradas | None`;
  - chaves de tabela: `"selecao_de_itens"` (`JanelaSelecao`), `"selecao_duplicadas"`
    (`JanelaSelecaoDuplicadas`, internas `("descricao", "pmib_original", "pmib_alvo")`),
    `"resumo_do_lote"` (`JanelaResumoDoLote`, internas `("mensagem", "tipo")`).

**Decisão registrada (ambiguidade da spec):** o Resumo do lote tinha UMA coluna com o cabeçalho
escondido, e não havia o que reordenar nem esconder. Ele ganha o cabeçalho e a coluna **Tipo**
(Erro ou Aviso, a mesma informação que a cor da linha já dá). O texto copiado e o log gravado
não mudam.

- [ ] **Step 1: Write the failing tests (função pura e prefs)**

Crie `tests/test_colunas_juntar.py`:

```python
"""Colunas lembradas (2026-10-26): a regra de juntar a preferência com as colunas
de agora (função pura, sem tabela nenhuma) e a seção `colunas` do `prefs`."""
from sigft.app_qt.widgets.colunas import Coluna, descrever, juntar
from sigft.core import prefs

COLUNAS = ("descricao", "original", "alvo")


def test_nada_guardado_vale_o_padrao():
    assert juntar(None, COLUNAS) is None


def test_preferencia_estragada_vale_o_padrao():
    assert juntar("lixo", COLUNAS) is None
    assert juntar({"chave": "alvo"}, COLUNAS) is None
    assert juntar([1, "x", {"chave": 3}, {"sem": "chave"}], COLUNAS) is None


def test_ordem_largura_e_visibilidade_voltam():
    guardado = [{"chave": "alvo", "largura": 90, "visivel": True},
                {"chave": "descricao", "largura": 300, "visivel": False},
                {"chave": "original", "largura": 120, "visivel": True}]
    assert juntar(guardado, COLUNAS) == [Coluna("alvo", 90, True), Coluna("descricao", 300, False),
                                         Coluna("original", 120, True)]


def test_coluna_que_sumiu_e_ignorada_e_a_nova_entra_no_fim_visivel():
    guardado = [{"chave": "velha", "largura": 50, "visivel": True},
                {"chave": "alvo", "largura": 90, "visivel": False}]
    assert juntar(guardado, COLUNAS) == [Coluna("alvo", 90, False), Coluna("descricao", None, True),
                                         Coluna("original", None, True)]


def test_repetida_e_largura_invalida():
    guardado = [{"chave": "alvo", "largura": -5}, {"chave": "alvo", "largura": 80},
                {"chave": "descricao", "largura": True, "visivel": "sim"},
                {"chave": "original", "largura": "120"}]
    assert juntar(guardado, COLUNAS) == [Coluna("alvo", None, True), Coluna("descricao", None, True),
                                         Coluna("original", None, True)]


def test_todas_escondidas_a_primeira_volta_a_aparecer():
    guardado = [{"chave": c, "largura": 100, "visivel": False} for c in COLUNAS]
    assert [c.visivel for c in juntar(guardado, COLUNAS)] == [True, False, False]


def test_descrever_e_o_que_juntar_le():
    lista = [Coluna("alvo", 90, True), Coluna("descricao", None, False), Coluna("original", 120, True)]
    assert juntar(descrever(lista), COLUNAS) == lista


def test_prefs_guarda_por_tabela_e_apaga_com_none(tmp_path):
    arquivo = tmp_path / "prefs.json"
    assert prefs.ler_colunas("selecao", config_path=arquivo) is None
    prefs.gravar_colunas("selecao", [{"chave": "a", "largura": 10, "visivel": True}], config_path=arquivo)
    prefs.gravar_colunas("resumo", [{"chave": "b", "largura": None, "visivel": False}], config_path=arquivo)
    prefs.set_opcao("outra", True, config_path=arquivo)   # a seção sobrevive a outra gravação
    assert prefs.ler_colunas("selecao", config_path=arquivo) == [{"chave": "a", "largura": 10, "visivel": True}]
    prefs.gravar_colunas("selecao", None, config_path=arquivo)
    assert prefs.ler_colunas("selecao", config_path=arquivo) is None
    assert prefs.ler_colunas("resumo", config_path=arquivo) == [{"chave": "b", "largura": None, "visivel": False}]
```

- [ ] **Step 2: Write the failing tests (Qt)**

Crie `tests/test_qt_colunas.py`:

```python
"""Colunas lembradas nas tabelas (2026-10-26): arrastar o cabeçalho, a borda e o
menu do botão direito, lembrados pela chave interna de cada coluna."""
from types import SimpleNamespace

from _idioma import em_idioma
from sigft.app.idioma import t
from sigft.app_qt.views import janelas
from sigft.app_qt.widgets import colunas as colunas_mod
from sigft.app_qt.widgets import dialogos_selecao as qd
from sigft.app_qt.widgets import resumo_lote
from sigft.core import prefs

INTERNAS = ("descricao", "original", "alvo")


def _tabela(qtbot, titulos=("Descrição", "PMIB Original", "PMIB Alvo")):
    tabela = qd.tabela_ttk([(titulo, 120, "w") for titulo in titulos])
    qtbot.addWidget(tabela)
    return tabela, colunas_mod.instalar_colunas(tabela, "teste", INTERNAS)


def _ordem(tabela):
    cabecalho = tabela.header()
    return [INTERNAS[cabecalho.logicalIndex(p)] for p in range(cabecalho.count())]


def _acao(menu, chave):
    return next(a for a in menu.actions() if a.data() == chave)


def test_instalar_liga_o_cabecalho(qt_interface, qtbot):
    tabela, colunas = _tabela(qtbot)
    assert tabela.colunas_lembradas is colunas
    assert tabela.header().sectionsMovable()
    assert colunas.colunas == list(INTERNAS)


def test_reordenar_e_alargar_ficam_lembrados(qt_interface, qtbot):
    tabela, colunas = _tabela(qtbot)
    cabecalho = tabela.header()
    cabecalho.moveSection(cabecalho.visualIndex(2), 0)
    cabecalho.resizeSection(0, 333)
    colunas.gravar()
    nova, _ = _tabela(qtbot)
    assert _ordem(nova) == ["alvo", "descricao", "original"]
    assert nova.header().sectionSize(0) == 333
    assert not nova.esticar_colunas.ligado   # vale a largura de quem mexeu
    assert nova.header().stretchLastSection()


def test_esconder_fica_lembrado(qt_interface, qtbot):
    _tabela_velha, colunas = _tabela(qtbot)
    assert colunas.mostrar_coluna("original", False) is True
    nova, _ = _tabela(qtbot)
    assert nova.header().isSectionHidden(1)
    assert not nova.header().isSectionHidden(0)


def test_a_ultima_coluna_visivel_nao_se_esconde(qt_interface, qtbot):
    tabela, colunas = _tabela(qtbot)
    colunas.mostrar_coluna("descricao", False)
    colunas.mostrar_coluna("original", False)
    assert colunas.mostrar_coluna("alvo", False) is False
    assert not tabela.header().isSectionHidden(2)
    menu = colunas.montar_menu()
    assert not _acao(menu, "alvo").isEnabled() and _acao(menu, "alvo").isChecked()
    assert _acao(menu, "descricao").isEnabled() and not _acao(menu, "descricao").isChecked()


def test_menu_tem_cada_coluna_e_restaurar(qt_interface, qtbot):
    _tabela_teste, colunas = _tabela(qtbot)
    textos = [a.text() for a in colunas.montar_menu().actions() if not a.isSeparator()]
    assert textos == ["Descrição", "PMIB Original", "PMIB Alvo", "Restaurar colunas"]


def test_desmarcar_no_menu_esconde(qt_interface, qtbot):
    tabela, colunas = _tabela(qtbot)
    _acao(colunas.montar_menu(), "original").setChecked(False)
    assert tabela.header().isSectionHidden(1)
    assert prefs.ler_colunas("teste")[1]["visivel"] is False


def test_restaurar_volta_ao_padrao(qt_interface, qtbot):
    tabela, colunas = _tabela(qtbot)
    cabecalho = tabela.header()
    cabecalho.moveSection(cabecalho.visualIndex(2), 0)
    colunas.mostrar_coluna("descricao", False)
    menu = colunas.montar_menu()
    next(a for a in menu.actions() if a.text() == "Restaurar colunas").trigger()
    assert _ordem(tabela) == list(INTERNAS)
    assert not any(cabecalho.isSectionHidden(i) for i in range(3))
    assert prefs.ler_colunas("teste") is None
    assert tabela.esticar_colunas.ligado
    assert not cabecalho.stretchLastSection()


def test_coluna_que_sumiu_e_ignorada_e_a_nova_entra_no_fim(qt_interface, qtbot):
    prefs.gravar_colunas("teste", [{"chave": "velha", "largura": 50, "visivel": True},
                                   {"chave": "alvo", "largura": 90, "visivel": True},
                                   {"chave": "descricao", "largura": 200, "visivel": False}])
    tabela, _ = _tabela(qtbot)
    assert _ordem(tabela) == ["alvo", "descricao", "original"]
    assert tabela.header().isSectionHidden(0)
    assert not tabela.header().isSectionHidden(1)


def test_preferencia_estragada_vale_o_padrao(qt_interface, qtbot):
    prefs.gravar_colunas("teste", "lixo")
    tabela, _ = _tabela(qtbot)
    assert _ordem(tabela) == list(INTERNAS)
    assert tabela.esticar_colunas.ligado


def test_trocar_o_idioma_nao_perde_o_que_foi_guardado(qt_interface, qtbot):
    _tabela_velha, colunas = _tabela(qtbot)
    colunas.mostrar_coluna("original", False)
    with em_idioma("es"):
        nova, _ = _tabela(qtbot, titulos=(t("Descrição"), "PMIB Original", "PMIB Alvo"))
        assert nova.headerItem().text(0) != "Descrição"
        assert nova.header().isSectionHidden(1)


def test_fechar_a_janela_grava_a_largura_que_esperava(qt_interface, qtbot):
    dlg = qd.TabelaSelecaoDialog(None, colunas=("A", "B"), linhas=[(1, ("x", "y"))], modal=False,
                                 chave_colunas="teste_dialogo", colunas_internas=("a", "b"))
    qtbot.addWidget(dlg)
    dlg.tree.header().resizeSection(0, 250)
    assert dlg.colunas._gravar_depois.isActive()
    dlg.close()
    assert prefs.ler_colunas("teste_dialogo")[0] == {"chave": "a", "largura": 250, "visivel": True}


def test_tabela_sem_chave_nao_lembra_nada(qt_interface, qtbot):
    dlg = qd.TabelaSelecaoDialog(None, colunas=("A",), linhas=[(1, ("x",))], modal=False)
    qtbot.addWidget(dlg)
    assert dlg.colunas is None


def test_selecao_de_duplicadas_usa_a_chave_interna(qt_interface, qtbot):
    fila = [{"descricao": "Bomba", "pmib_original": "1", "pmib_alvo": "2"}]
    dlg = janelas.JanelaSelecaoDuplicadas(None, fila, lambda escolha: None)
    qtbot.addWidget(dlg)
    assert dlg.colunas.chave == "selecao_duplicadas"
    assert dlg.colunas.colunas == ["descricao", "pmib_original", "pmib_alvo"]


def test_selecao_de_itens_usa_o_nome_da_coluna_da_planilha(qt_interface, qtbot):
    class Linha(list):
        def to_numpy(self):
            return SimpleNamespace(tolist=lambda: list(self))

    df = SimpleNamespace(columns=["DESCRIÇÃO", 7],
                         iterrows=lambda: iter([(3, Linha(["p", 1]))]))
    dlg = janelas.JanelaSelecao(None, df, lambda escolha: None)
    qtbot.addWidget(dlg)
    assert dlg.colunas.chave == "selecao_de_itens"
    assert dlg.colunas.colunas == ["DESCRIÇÃO", "7"]


def test_resumo_do_lote_tem_cabecalho_tipo_e_colunas_lembradas(qt_interface, qtbot):
    j = resumo_lote.JanelaResumoDoLote(None, "x", [("[Erro] a", "erro"), ("[Aviso] b", "aviso")])
    qtbot.addWidget(j)
    assert not j.arvore.isHeaderHidden()
    assert [j.arvore.headerItem().text(i) for i in range(2)] == ["Mensagem", "Tipo"]
    grupo = j.arvore.topLevelItem(0)
    assert [grupo.child(i).text(1) for i in range(grupo.childCount())] == ["Erro", "Aviso"]
    assert j.colunas.chave == "resumo_do_lote"
    assert j.colunas.colunas == ["mensagem", "tipo"]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest -q tests/test_colunas_juntar.py tests/test_qt_colunas.py`
Expected: FAIL na coleta, `ModuleNotFoundError: No module named 'sigft.app_qt.widgets.colunas'`.

- [ ] **Step 4: A seção `colunas` no `prefs`**

Em `sigft/core/prefs.py`, troque

```python
_SECOES_ESTADO = ("ultimos", "categorias", "pastas_padrao", "arquivos", "opcoes", "novidades",
                  "preferencias", "recentes")
```

por

```python
_SECOES_ESTADO = ("ultimos", "categorias", "pastas_padrao", "arquivos", "opcoes", "novidades",
                  "preferencias", "recentes", "colunas")
```

E acrescente no fim do arquivo:

```python
# =============================================================================
# Colunas lembradas de cada tabela  [2026-10-26]
# =============================================================================
# Ordem, largura e visibilidade das colunas de uma tabela da interface
# (`sigft/app_qt/widgets/colunas.py`), pela CHAVE da tabela. O valor é o que
# `colunas.descrever` monta (uma lista de dicts); validar é de quem lê
# (`colunas.juntar`), que trata valor estragado como "nunca gravado".
CHAVE_COLUNAS = "colunas"


def ler_colunas(
    chave: str,
    *,
    config_path: str | os.PathLike[str] | None = None,
) -> object:
    """O que foi guardado para a tabela `chave`, cru; `None` se nada."""
    return _carregar_estado(config_path).get(CHAVE_COLUNAS, {}).get(chave)


def gravar_colunas(
    chave: str,
    valor: object,
    *,
    config_path: str | os.PathLike[str] | None = None,
) -> None:
    """Guarda `valor` para a tabela `chave`; `None` apaga (o "Restaurar colunas")."""
    estado = _carregar_estado(config_path)
    secao = estado.setdefault(CHAVE_COLUNAS, {})
    if valor is None:
        secao.pop(chave, None)
    else:
        secao[chave] = valor
    _salvar_estado(estado, config_path)
```

- [ ] **Step 5: `EsticaColunas` que se desliga**

Em `sigft/app_qt/widgets/dialogos_selecao.py`, troque a classe `EsticaColunas` inteira por:

```python
class EsticaColunas(QObject):
    """O ttk.Treeview estica as colunas (`stretch=True`, o padrão) para ocupar a
    largura: a sobra é repartida IGUALMENTE entre elas. Encolher abaixo das
    larguras pedidas, não -- aí aparece a rolagem horizontal.

    [2026-10-26] As colunas lembradas (`widgets/colunas.py`) o desligam quando a
    pessoa mexe nas colunas (vale a largura dela) e o religam no "Restaurar
    colunas". `ajustando` diz que a mudança de largura é daqui, e não de quem usa."""

    def __init__(self, tree: QTreeWidget, base: list[int]) -> None:
        super().__init__(tree)
        self._tree, self._base = tree, base
        self.ligado = True
        self.ajustando = False
        tree.viewport().installEventFilter(self)

    def eventFilter(self, objeto, evento) -> bool:  # noqa: N802 -- nome do Qt
        if evento.type() == QEvent.Type.Resize:
            self.esticar()
        return False

    def esticar(self) -> None:
        if not self.ligado or not self._base:
            return
        sobra = self._tree.viewport().width() - sum(self._base)
        extra = max(0, sobra) // len(self._base)
        resto = max(0, sobra) - extra * len(self._base)
        self.ajustando = True
        try:
            for i, largura in enumerate(self._base):
                self._tree.setColumnWidth(i, largura + extra + (resto if i == len(self._base) - 1 else 0))
        finally:
            self.ajustando = False

    def desligar(self) -> None:
        self.ligado = False

    def ligar(self) -> None:
        self.ligado = True
        self.esticar()
```

- [ ] **Step 6: `sigft/app_qt/widgets/colunas.py`**

```python
"""Colunas lembradas nas tabelas (2026-10-26).

Arrastar o cabeçalho troca a ordem; arrastar a borda muda a largura; o botão
direito no cabeçalho abre um menu para esconder e mostrar cada coluna, e
"Restaurar colunas". Fica nas preferências (`core/prefs`, seção `colunas`) pela
chave da tabela e pela chave INTERNA de cada coluna: o texto do cabeçalho muda
com o idioma, a chave não.

`juntar` (função pura) casa o que foi guardado com as colunas de agora: coluna
que deixou de existir é ignorada; coluna nova entra no fim, visível; preferência
estragada vale o padrão (`None`). A última coluna visível não se esconde.

Na tabela com `EsticaColunas` (`dialogos_selecao.tabela_ttk`, a sobra repartida
igual), mexer nas colunas o desliga e a última coluna passa a esticar; o
"Restaurar colunas" o religa.

Uso: `instalar_colunas(tabela, "selecao_duplicadas", ("descricao", ...))`.
"""
from __future__ import annotations

from typing import NamedTuple, Sequence

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QMenu, QTreeView

from sigft.app.idioma import marcar, t

TEXTO_RESTAURAR = marcar("Restaurar colunas")
# Arrastar a borda solta dezenas de `sectionResized`: grava uma vez, quando para.
MS_PARA_GRAVAR = 400


class Coluna(NamedTuple):
    chave: str
    largura: int | None
    visivel: bool


def _largura(valor: object) -> int | None:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
        return None
    return valor


def juntar(guardado: object, colunas: Sequence[str]) -> list[Coluna] | None:
    """A ordem, a largura e a visibilidade de `colunas` (as chaves internas de
    agora) segundo `guardado` (o que `descrever` gravou). `None`: nada que sirva,
    vale o padrão da tabela."""
    if not isinstance(guardado, list):
        return None
    existentes = set(colunas)
    vistas: set[str] = set()
    lista: list[Coluna] = []
    for item in guardado:
        if not isinstance(item, dict):
            continue
        chave = item.get("chave")
        if not isinstance(chave, str) or chave not in existentes or chave in vistas:
            continue
        vistas.add(chave)
        visivel = item.get("visivel")
        lista.append(Coluna(chave, _largura(item.get("largura")),
                            visivel if isinstance(visivel, bool) else True))
    if not lista:
        return None
    lista += [Coluna(chave, None, True) for chave in colunas if chave not in vistas]
    if not any(coluna.visivel for coluna in lista):
        lista[0] = lista[0]._replace(visivel=True)
    return lista


def descrever(colunas: Sequence[Coluna]) -> list[dict]:
    """O que vai para as preferências (JSON), na ordem da tela."""
    return [{"chave": c.chave, "largura": c.largura, "visivel": c.visivel} for c in colunas]


def _arquivo_de_prefs():
    """O `config_path` das preferências: `None` é o `user_prefs.json` da pasta de
    dados. Função para os testes apontarem outro arquivo."""
    return None


def _ler(chave: str) -> object:
    from sigft.core import prefs

    try:
        return prefs.ler_colunas(chave, config_path=_arquivo_de_prefs())
    except Exception:  # noqa: BLE001 -- preferência é conveniência
        return None


def _gravar(chave: str, valor: object) -> None:
    from sigft.core import prefs

    try:
        prefs.gravar_colunas(chave, valor, config_path=_arquivo_de_prefs())
    except Exception:  # noqa: BLE001 -- lembrar não pode atrapalhar a tabela
        pass


class ColunasLembradas(QObject):
    """Liga o cabeçalho de `tabela` às preferências. Filho da tabela: morre com ela."""

    def __init__(self, tabela: QTreeView, chave: str, colunas: Sequence[str]) -> None:
        super().__init__(tabela)
        self._tabela = tabela
        self.chave = chave
        self.colunas = [str(c) for c in colunas]
        self._cabecalho = tabela.header()
        self._aplicando = False
        self._estica_ultima = self._cabecalho.stretchLastSection()
        self._padrao = {i: self._cabecalho.sectionSize(i) for i in range(len(self.colunas))}
        self._larguras = dict(self._padrao)
        self._gravar_depois = QTimer(self)
        self._gravar_depois.setSingleShot(True)
        self._gravar_depois.setInterval(MS_PARA_GRAVAR)
        self._gravar_depois.timeout.connect(self.gravar)

        cabecalho = self._cabecalho
        cabecalho.setSectionsMovable(True)
        cabecalho.setFirstSectionMovable(True)
        cabecalho.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        cabecalho.customContextMenuRequested.connect(self._abrir_menu)
        cabecalho.sectionMoved.connect(self._mexeu)
        cabecalho.sectionResized.connect(self._redimensionou)
        # A janela que fecha antes do relógio grava o que esperava (Hide).
        tabela.installEventFilter(self)
        self.aplicar(juntar(_ler(chave), self.colunas))

    # -- estado -----------------------------------------------------------------------
    def _esticador(self):
        return getattr(self._tabela, "esticar_colunas", None)

    def _ocupado(self) -> bool:
        """A mudança é do programa (aplicando, ou o `EsticaColunas`), não de quem usa."""
        return self._aplicando or bool(getattr(self._esticador(), "ajustando", False))

    def estado(self) -> list[Coluna]:
        """As colunas na ordem da tela, com a última largura vista de cada uma."""
        cabecalho = self._cabecalho
        lista = []
        for posicao in range(len(self.colunas)):
            logico = cabecalho.logicalIndex(posicao)
            lista.append(Coluna(self.colunas[logico], self._larguras.get(logico),
                                not cabecalho.isSectionHidden(logico)))
        return lista

    def _soltar_esticador(self) -> None:
        """Daqui em diante vale a largura de quem mexeu: a sobra repartida igual
        (`EsticaColunas`) para, e a última coluna estica."""
        esticador = self._esticador()
        if esticador is not None and esticador.ligado:
            esticador.desligar()
        if not self._cabecalho.stretchLastSection():
            antes, self._aplicando = self._aplicando, True
            try:
                self._cabecalho.setStretchLastSection(True)
            finally:
                self._aplicando = antes

    def aplicar(self, lista: list[Coluna] | None) -> None:
        """Põe a tabela como `lista` diz; `None` é o padrão (a ordem e as larguras
        de nascença, tudo visível, a sobra repartida como antes)."""
        cabecalho = self._cabecalho
        padrao = lista is None
        if lista is None:
            lista = [Coluna(c, self._padrao.get(i), True) for i, c in enumerate(self.colunas)]
        self._aplicando = True
        try:
            for posicao, coluna in enumerate(lista):
                logico = self.colunas.index(coluna.chave)
                if cabecalho.visualIndex(logico) != posicao:
                    cabecalho.moveSection(cabecalho.visualIndex(logico), posicao)
                if coluna.largura:
                    cabecalho.resizeSection(logico, coluna.largura)
                    self._larguras[logico] = coluna.largura
                cabecalho.setSectionHidden(logico, not coluna.visivel)
            if padrao:
                cabecalho.setStretchLastSection(self._estica_ultima)
                esticador = self._esticador()
                if esticador is not None:
                    esticador.ligar()
            else:
                self._soltar_esticador()
        finally:
            self._aplicando = False

    # -- o que quem usa faz --------------------------------------------------------------
    def _redimensionou(self, logico: int, _antes: int, agora: int) -> None:
        if agora > 0 and logico < len(self.colunas):
            self._larguras[logico] = agora
        if self._ocupado() or agora <= 0:
            return
        self._soltar_esticador()
        self._gravar_depois.start()

    def _mexeu(self, *_args) -> None:
        if self._ocupado():
            return
        self._soltar_esticador()
        self._gravar_depois.start()

    def mostrar_coluna(self, chave: str, visivel: bool) -> bool:
        """Mostra ou esconde a coluna `chave` e grava. A última visível não se
        esconde: devolve `False` e nada muda."""
        visiveis = [c.chave for c in self.estado() if c.visivel]
        if not visivel and visiveis == [chave]:
            return False
        self._aplicando = True
        try:
            self._cabecalho.setSectionHidden(self.colunas.index(chave), not visivel)
        finally:
            self._aplicando = False
        self._soltar_esticador()
        self.gravar()
        return True

    def gravar(self) -> None:
        self._gravar_depois.stop()
        _gravar(self.chave, descrever(self.estado()))

    def restaurar(self, *_args) -> None:
        """"Restaurar colunas": esquece o guardado e volta ao padrão."""
        self._gravar_depois.stop()
        _gravar(self.chave, None)
        self.aplicar(None)

    # -- o menu do botão direito -------------------------------------------------------
    def montar_menu(self) -> QMenu:
        """Uma linha marcável por coluna (na ordem da tela) e "Restaurar colunas"."""
        menu = QMenu(self._cabecalho)
        estado = self.estado()
        visiveis = [c.chave for c in estado if c.visivel]
        modelo = self._tabela.model()
        for coluna in estado:
            logico = self.colunas.index(coluna.chave)
            texto = str(modelo.headerData(logico, Qt.Orientation.Horizontal) or coluna.chave)
            acao = menu.addAction(texto)
            acao.setCheckable(True)
            acao.setChecked(coluna.visivel)
            acao.setData(coluna.chave)
            acao.setEnabled(not (coluna.visivel and visiveis == [coluna.chave]))
            acao.toggled.connect(self._marcou)
        menu.addSeparator()
        restaurar = menu.addAction(t(TEXTO_RESTAURAR))
        restaurar.triggered.connect(self.restaurar)
        return menu

    def _marcou(self, marcado: bool) -> None:
        acao = self.sender()
        if acao is not None:
            self.mostrar_coluna(acao.data(), marcado)

    def _abrir_menu(self, posicao) -> None:
        menu = self.montar_menu()
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        menu.popup(self._cabecalho.mapToGlobal(posicao))

    def eventFilter(self, objeto, evento) -> bool:  # noqa: N802 -- nome do Qt
        if evento.type() == QEvent.Type.Hide and self._gravar_depois.isActive():
            self.gravar()
        return False


def instalar_colunas(tabela: QTreeView, chave: str, colunas: Sequence[str]) -> ColunasLembradas:
    """Liga as colunas lembradas em `tabela` numa linha. `colunas`: a chave interna
    de cada coluna, na ordem lógica (a de criação)."""
    lembradas = ColunasLembradas(tabela, chave, colunas)
    tabela.colunas_lembradas = lembradas
    return lembradas
```

- [ ] **Step 7: As duas tabelas usam**

Em `sigft/app_qt/widgets/dialogos_selecao.py`, acrescente aos imports (depois de
`from sigft.app_qt.widgets import blocos`):

```python
from sigft.app_qt.widgets.colunas import instalar_colunas
```

Na assinatura de `TabelaSelecaoDialog.__init__`, troque

```python
                 texto_confirmar: str | None = None, com_cancelar: bool = True,
                 modal: bool = True, ao_confirmar=None) -> None:
```

por

```python
                 texto_confirmar: str | None = None, com_cancelar: bool = True,
                 modal: bool = True, ao_confirmar=None, chave_colunas: str | None = None,
                 colunas_internas=None) -> None:
```

e, logo depois do laço que insere as linhas (`for chave, valores in linhas: ...`), acrescente:

```python
        # [2026-10-26] Colunas lembradas (`widgets/colunas.py`), quando quem abre dá a
        # chave da tabela. A chave de cada coluna é `colunas_internas` (o texto
        # mostrado muda com o idioma) ou, sem ela, o próprio nome da coluna.
        self.colunas = None
        if chave_colunas:
            internas = colunas_internas if colunas_internas is not None else colunas
            self.colunas = instalar_colunas(self.tree, chave_colunas, [str(c) for c in internas])
```

Na docstring de `TabelaSelecaoDialog`, acrescente a frase:
"`chave_colunas` liga as colunas lembradas (`widgets/colunas.py`); `colunas_internas` é a chave
de cada coluna quando o texto mostrado é traduzido."

Em `sigft/app_qt/views/janelas.py`, em `JanelaSelecao`, troque

```python
        com_cancelar=False,
        ao_confirmar=lambda chaves: callback_confirmar([int(i) for i in chaves]),
    )
```

por

```python
        com_cancelar=False,
        ao_confirmar=lambda chaves: callback_confirmar([int(i) for i in chaves]),
        # As colunas são as da planilha: o nome delas é a chave (não se traduz).
        chave_colunas="selecao_de_itens",
    )
```

E em `JanelaSelecaoDuplicadas`, troque

```python
        preselecionar_tudo=True,
        ao_confirmar=_confirmar,
    )
```

por

```python
        preselecionar_tudo=True,
        ao_confirmar=_confirmar,
        chave_colunas="selecao_duplicadas",
        colunas_internas=("descricao", "pmib_original", "pmib_alvo"),
    )
```

Em `sigft/app_qt/widgets/resumo_lote.py`, acrescente ao import de widgets:

```python
from sigft.app_qt.widgets.colunas import instalar_colunas
```

depois de `PASTA_DOS_RESUMOS = "resumos"` acrescente:

```python
# [2026-10-26] O cabeçalho (antes escondido) e as colunas lembradas: chave interna,
# título e largura de nascença da primeira (a última estica).
COLUNAS_DO_RESUMO = ("mensagem", "tipo")
TITULOS_DO_RESUMO = (marcar("Mensagem"), marcar("Tipo"))
TIPO_DO_NIVEL = {niveis_log.ERRO: marcar("Erro")}
TIPO_AVISO = marcar("Aviso")
LARGURA_MENSAGEM = 560
```

e troque o bloco da árvore

```python
        self.arvore = QTreeWidget()
        self.arvore.setHeaderHidden(True)
        # (item, nível) de cada linha: a cor sai do papel e é repintada na troca
        # de tema (`tema.mudou`), porque o `QTreeWidgetItem` guarda a cor dada.
        self._itens: list[tuple[QTreeWidgetItem, str]] = []
        for grupo in self.grupos:
            pai = QTreeWidgetItem([f"{grupo.rotulo} ({len(grupo.linhas)})"])
            for texto, nivel in grupo.linhas:
                filho = QTreeWidgetItem([texto])
                filho.setToolTip(0, texto)
                pai.addChild(filho)
                self._itens.append((filho, nivel))
            self.arvore.addTopLevelItem(pai)
            pai.setExpanded(True)
        lay.addWidget(self.arvore, 1)
```

por

```python
        self.arvore = QTreeWidget()
        self.arvore.setColumnCount(len(COLUNAS_DO_RESUMO))
        self.arvore.setHeaderLabels([t(titulo) for titulo in TITULOS_DO_RESUMO])
        self.arvore.setColumnWidth(0, LARGURA_MENSAGEM)
        # (item, nível) de cada linha: a cor sai do papel e é repintada na troca
        # de tema (`tema.mudou`), porque o `QTreeWidgetItem` guarda a cor dada.
        self._itens: list[tuple[QTreeWidgetItem, str]] = []
        for grupo in self.grupos:
            pai = QTreeWidgetItem([f"{grupo.rotulo} ({len(grupo.linhas)})", ""])
            for texto, nivel in grupo.linhas:
                filho = QTreeWidgetItem([texto, t(TIPO_DO_NIVEL.get(nivel, TIPO_AVISO))])
                filho.setToolTip(0, texto)
                pai.addChild(filho)
                self._itens.append((filho, nivel))
            self.arvore.addTopLevelItem(pai)
            pai.setExpanded(True)
        self.colunas = instalar_colunas(self.arvore, "resumo_do_lote", COLUNAS_DO_RESUMO)
        lay.addWidget(self.arvore, 1)
```

e, em `_pintar_cores`, troque

```python
            item.setForeground(0, QBrush(QColor(estilo.cor_do_papel(papel))))
```

por

```python
            for coluna in range(self.arvore.columnCount()):
                item.setForeground(coluna, QBrush(QColor(estilo.cor_do_papel(papel))))
```

- [ ] **Step 8: A guarda dos textos e as traduções**

Em `tests/test_textos_da_interface.py`, na tupla `CONVERTIDOS`, depois de
`"sigft/app_qt/widgets/blocos.py",` acrescente:

```python
    "sigft/app_qt/widgets/colunas.py",
```

Depois:

```bash
.venv/bin/python - <<'EOF'
import json
import pathlib

NOVOS = {
    "es": {"Restaurar colunas": "Restaurar columnas", "Mensagem": "Mensaje"},
    "en": {"Restaurar colunas": "Reset columns", "Mensagem": "Message"},
}
for codigo, pares in NOVOS.items():
    caminho = pathlib.Path("sigft/app/idiomas") / f"{codigo}.json"
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    dados.update(pares)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
EOF
.venv/bin/python tools/textos_da_interface.py --arrumar
.venv/bin/python tools/textos_da_interface.py
```

Expected: `es: 0 faltando, 0 sobrando` e `en: 0 faltando, 0 sobrando` ("Tipo", "Erro" e "Aviso"
já têm tradução).

- [ ] **Step 9: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q tests/test_colunas_juntar.py tests/test_qt_colunas.py tests/test_qt_dialogos_selecao.py tests/test_qt_resumo_lote.py tests/test_resumo_lote.py tests/test_prefs.py tests/test_textos_da_interface.py tests/test_propriedades.py tests/test_qt_sem_cor_crua.py tests/test_qt_idioma_telas.py`
Expected: PASS.

- [ ] **Step 10: Gate completo e commit**

Run: `SIGFT_PY=.venv/bin/python bash scripts/check.sh` e `.venv/bin/python -m ruff check .`
Expected: verde (a falha conhecida do `test_qt_saida.py` à parte); `All checks passed!`.

```bash
git add sigft/core/prefs.py sigft/app_qt/widgets/colunas.py sigft/app_qt/widgets/dialogos_selecao.py \
    sigft/app_qt/views/janelas.py sigft/app_qt/widgets/resumo_lote.py tests/test_textos_da_interface.py \
    tests/test_colunas_juntar.py tests/test_qt_colunas.py sigft/app/idiomas/es.json sigft/app/idiomas/en.json
git -c user.name=Jonathan -c user.email=jas.espinola.2022@aluno.unila.edu.br commit -F - <<'EOF'
Colunas lembradas na selecao de fichas e no Resumo do lote

<linhas de atribuicao da sessao>
EOF
```

---

### Task 4: Menu lateral recolhível (e o Ctrl+K)

**Files:**
- Create: `assets/icons/chevrons-left.svg`, `assets/icons/chevrons-right.svg`
- Modify: `sigft/app_qt/icones.py` (`NOMES`)
- Modify: `sigft/app_qt/estilo.py` (constante depois de `LARGURA_BARRA_LATERAL`; duas regras em `_folha_base`)
- Modify: `sigft/app_qt/widgets/marca.py` (`LARGURA_LOGO_RECOLHIDO`, `_original`, `recolher`)
- Modify: `sigft/app_qt/catalogo.py` (constantes do menu, ação `menu`, `comandos(menu_recolhido=)`)
- Modify: `sigft/app_qt/main.py` (import `QFrame`; ajudantes de preferência; `_montar_sidebar`;
  `recolher_menu`/`alternar_menu`; `__init__`; `abrir_paleta`; `executar_comando`)
- Modify: `tests/test_qt_paleta.py` (`test_toda_acao_tem_quem_faca`)
- Modify: `sigft/app/idiomas/es.json`, `sigft/app/idiomas/en.json`
- Test: `tests/test_qt_menu_recolhivel.py`

**Interfaces:**
- Consumes: `prefs.get_opcao/set_opcao`, `icones.aplicar`, `estilo.definir_propriedade`,
  `catalogo.dica_do_menu(alvo)`, `tests/_varredura.cortados(raiz) -> set[str]`.
- Produces:
  - `estilo.LARGURA_BARRA_RECOLHIDA = 60`;
  - `icones.NOMES` com `"chevrons-left"` e `"chevrons-right"`;
  - `Marca.recolher(recolhida: bool) -> None`, `marca.LARGURA_LOGO_RECOLHIDO = 36`;
  - `catalogo.TEXTO_RECOLHER_MENU`, `catalogo.TEXTO_EXPANDIR_MENU`,
    `catalogo.ICONE_RECOLHER_MENU = "chevrons-left"`, `catalogo.ICONE_EXPANDIR_MENU = "chevrons-right"`,
    ação `AcaoDoCtrlK("menu", ...)` em `catalogo.ACOES`, `catalogo.comandos(*, menu_recolhido=False)`;
  - `main.CHAVE_MENU_RECOLHIDO = "menu_recolhido"`, `main.MARGENS_DA_BARRA`,
    `main.MARGENS_DA_BARRA_RECOLHIDA`, `main.LADO_BOTAO_MENU = 36`;
  - `SIG_FT_App.barra_lateral: QScrollArea`, `.botao_menu: QPushButton`, `.menu_recolhido: bool`,
    `.recolher_menu(recolhido: bool, *, gravar: bool = True) -> None`, `.alternar_menu(*_args) -> None`;
    Ctrl+K `acao:menu` chama `alternar_menu`.

- [ ] **Step 1: Write the failing tests**

Crie `tests/test_qt_menu_recolhivel.py`:

```python
"""O menu lateral recolhível (2026-10-26): só os ícones, lembrado, pelo botão do
pé ou pelo Ctrl+K; expandido, todos os nomes inteiros."""
import pytest

from _idioma import em_idioma
from _varredura import cortados
from sigft.app.idioma import t
from sigft.app_qt import catalogo, estilo, letra, tema
from sigft.app_qt import main as qmain
from sigft.core import prefs


@pytest.fixture
def montar(qt_interface, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(letra, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    monkeypatch.setattr(tema, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    anterior = qt_interface.styleSheet()
    tema.aplicar(qt_interface, "escuro", gravar=False)

    def _montar():
        janela = qmain.SIG_FT_App()
        janela.fechar_sem_perguntar = True
        qtbot.addWidget(janela)
        janela.resize(1280, 850)
        janela.show()
        qtbot.waitExposed(janela)
        return janela

    yield _montar
    letra.aplicar(qt_interface, "normal", gravar=False)
    tema.aplicar(qt_interface, tema.PADRAO, gravar=False)
    qt_interface.setStyleSheet(anterior)


def _nomes_do_menu():
    return {t(item[1]) for item in catalogo.MENU if item[0] == "botao"}


def test_nasce_expandido(montar):
    janela = montar()
    assert janela.menu_recolhido is False
    assert janela.barra_lateral.width() == estilo.LARGURA_BARRA_LATERAL
    assert {b.text().strip() for b in janela.botoes_menu.values()} == _nomes_do_menu()


def test_recolher_deixa_so_os_icones_com_o_nome_na_dica(montar, qtbot):
    janela = montar()
    janela.recolher_menu(True)
    qtbot.wait(20)
    assert janela.barra_lateral.width() == estilo.LARGURA_BARRA_RECOLHIDA
    assert janela.pilha.mapTo(janela, janela.pilha.rect().topLeft()).x() == estilo.LARGURA_BARRA_RECOLHIDA
    for item in catalogo.MENU:
        if item[0] != "botao":
            continue
        botao = janela.botoes_menu[item[2]]
        assert botao.text() == ""
        assert not botao.icon().isNull()
        assert botao.toolTip().startswith(t(item[1]))
        assert catalogo.dica_do_menu(item[2]) in botao.toolTip()
        assert botao.accessibleName() == t(item[1])
    assert janela.botao_home.text() == "" and janela.botao_home.toolTip().startswith("Home")
    assert not any(r.isVisible() for r in janela._rotulos_secao)
    assert all(traco.isVisible() for traco in janela._tracos_secao)
    assert not janela.marca.nome.isVisible()
    assert janela.botao_menu.property("icone") == catalogo.ICONE_EXPANDIR_MENU
    assert janela.botao_menu.toolTip() == "Expandir menu"


def test_expandir_volta_os_nomes_e_as_dicas(montar):
    janela = montar()
    janela.recolher_menu(True)
    janela.recolher_menu(False)
    assert janela.barra_lateral.width() == estilo.LARGURA_BARRA_LATERAL
    for alvo, botao in janela.botoes_menu.items():
        assert botao.toolTip() == catalogo.dica_do_menu(alvo)
    assert {b.text().strip() for b in janela.botoes_menu.values()} == _nomes_do_menu()
    assert all(r.isVisible() for r in janela._rotulos_secao)
    assert not any(traco.isVisible() for traco in janela._tracos_secao)
    assert janela.marca.nome.isVisible()
    assert janela.botao_menu.toolTip() == "Recolher menu"


def test_fica_lembrado_para_a_proxima_abertura(montar):
    janela = montar()
    janela.botao_menu.click()
    assert janela.menu_recolhido is True
    assert prefs.get_opcao(qmain.CHAVE_MENU_RECOLHIDO, False) is True
    outra = montar()
    assert outra.menu_recolhido is True
    assert outra.barra_lateral.width() == estilo.LARGURA_BARRA_RECOLHIDA
    outra.botao_menu.click()
    assert prefs.get_opcao(qmain.CHAVE_MENU_RECOLHIDO, True) is False


def test_item_da_tela_aberta_destacado_nos_dois_estados(montar):
    janela = montar()
    janela.show_frame("Analyzer")
    janela.recolher_menu(True)
    assert janela.botoes_menu["Analyzer"].property("ativo") is True
    janela.recolher_menu(False)
    assert janela.botoes_menu["Analyzer"].property("ativo") is True
    janela.show_home()
    janela.recolher_menu(True)
    assert janela.botao_home.property("ativo") is True


def test_ctrl_k_alterna_e_o_texto_acompanha(montar):
    janela = montar()
    textos = {c.chave: c.texto for c in catalogo.comandos(menu_recolhido=False)}
    assert textos["acao:menu"] == "Recolher menu"
    janela.executar_comando("acao:menu")
    assert janela.menu_recolhido is True
    expandir = {c.chave: c for c in catalogo.comandos(menu_recolhido=True)}["acao:menu"]
    assert expandir.texto == "Expandir menu" and expandir.icone == catalogo.ICONE_EXPANDIR_MENU
    paleta = janela.abrir_paleta()
    assert "Expandir menu" in [c.texto for c in paleta._comandos]
    paleta.close()
    janela.executar_comando("acao:menu")
    assert janela.menu_recolhido is False


@pytest.mark.parametrize("codigo", ["es", "en"])
def test_ctrl_k_traduzido_acha_tambem_em_portugues(codigo):
    with em_idioma(codigo):
        lista = catalogo.comandos()
        assert {c.chave: c.texto for c in lista}["acao:menu"] != "Recolher menu"
        for consulta in ("recolher", "menu lateral"):
            assert "acao:menu" in [c.chave for c in catalogo.filtrar(lista, consulta)], consulta


@pytest.mark.parametrize("tamanho", ["normal", "grande"])
@pytest.mark.parametrize("codigo", ["pt", "es", "en"])
def test_expandido_mostra_todos_os_nomes_inteiros(montar, qtbot, qt_interface, codigo, tamanho):
    with em_idioma(codigo):
        letra.aplicar(qt_interface, tamanho, gravar=False)
        janela = montar()
        janela.recolher_menu(True)
        qtbot.wait(20)
        janela.recolher_menu(False)
        qtbot.wait(20)
        assert cortados(janela.barra_lateral) == set()
        assert {b.text().strip() for b in janela.botoes_menu.values()} == _nomes_do_menu()
        assert not janela.barra_lateral.horizontalScrollBar().isVisible()
    letra.aplicar(qt_interface, "normal", gravar=False)


def test_folha_tem_as_regras_do_menu_recolhido():
    folha = estilo.folha_de_estilo()
    assert "#traco_secao" in folha
    assert 'QPushButton[menu="true"][recolhido="true"]' in folha
    assert '#home[recolhido="true"]' in folha
```

(`PaletaDeComandos._comandos` é a lista que ela recebeu: `widgets/paleta.py`, linha 37.)

Em `tests/test_qt_paleta.py`, `test_toda_acao_tem_quem_faca`, troque

```python
    monkeypatch.setattr(janela, "abrir_pasta_de_logs", lambda: feitos.append(("logs", ())))
```

por

```python
    monkeypatch.setattr(janela, "abrir_pasta_de_logs", lambda: feitos.append(("logs", ())))
    monkeypatch.setattr(janela, "alternar_menu", lambda: feitos.append(("menu", ())))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest -q tests/test_qt_menu_recolhivel.py tests/test_qt_paleta.py`
Expected: FAIL com `AttributeError: 'SIG_FT_App' object has no attribute 'menu_recolhido'` (e
`LARGURA_BARRA_RECOLHIDA`, `comandos(menu_recolhido=...)` inexistentes).

- [ ] **Step 3: Os ícones da seta**

Crie `assets/icons/chevrons-left.svg`:

```svg
<!-- @license lucide-static v0.460.0 - ISC -->
<svg
  class="lucide lucide-chevrons-left"
  xmlns="http://www.w3.org/2000/svg"
  width="24"
  height="24"
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="2"
  stroke-linecap="round"
  stroke-linejoin="round"
>
  <path d="m11 17-5-5 5-5" />
  <path d="m18 17-5-5 5-5" />
</svg>
```

Crie `assets/icons/chevrons-right.svg`:

```svg
<!-- @license lucide-static v0.460.0 - ISC -->
<svg
  class="lucide lucide-chevrons-right"
  xmlns="http://www.w3.org/2000/svg"
  width="24"
  height="24"
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="2"
  stroke-linecap="round"
  stroke-linejoin="round"
>
  <path d="m6 17 5-5-5-5" />
  <path d="m13 17 5-5-5-5" />
</svg>
```

(Os desenhos são os do `lucide-static@0.460.0`; com rede, confira contra
`https://cdn.jsdelivr.net/npm/lucide-static@0.460.0/icons/chevrons-left.svg` e `...-right.svg`.)

Em `sigft/app_qt/icones.py`, troque o fim de `NOMES`

```python
    "external-link", "sun", "moon", "monitor",
})
```

por

```python
    "external-link", "sun", "moon", "monitor", "chevrons-left", "chevrons-right",
})
```

- [ ] **Step 4: Estilo**

Em `sigft/app_qt/estilo.py`, depois de `LARGURA_BARRA_LATERAL = 277`, acrescente:

```python

# O menu lateral recolhido (2026-10-26): só os ícones. 60 = 8 de margem de cada
# lado e os botões de 44, com o ícone de 16 no meio.
LARGURA_BARRA_RECOLHIDA = 60
```

Em `_folha_base`, logo depois da linha

```python
QPushButton[menu="true"]:disabled {{ color: {p['texto_suave']}; }}
```

acrescente

```python
QPushButton[menu="true"][recolhido="true"] {{ text-align: center; padding: 0; }}
#traco_secao {{ background: {p['borda']}; border: none; }}
```

e logo depois da linha

```python
#home:hover, #home[ativo="true"] {{ background: {menu['fundo']}; color: {menu['texto']}; }}
```

acrescente

```python
#home[recolhido="true"] {{ text-align: center; padding: 0; }}
```

- [ ] **Step 5: A marca recolhida**

Em `sigft/app_qt/widgets/marca.py`, depois de `LARGURA_LOGO = 180`, acrescente:

```python
# Na barra recolhida (2026-10-26) a marca vira só o símbolo da GE: o quadrado da
# esquerda do `logo.png` (o círculo com o "GE"), nesta largura.
LARGURA_LOGO_RECOLHIDO = 36
```

No `__init__`, troque

```python
        self.logo = QLabel()
        caminho = caminho_logo or LOGO_PADRAO
        if os.path.exists(caminho):
            self.logo.setPixmap(QPixmap(caminho).scaledToWidth(
                LARGURA_LOGO, Qt.TransformationMode.SmoothTransformation))
```

por

```python
        self.logo = QLabel()
        caminho = caminho_logo or LOGO_PADRAO
        self._original = QPixmap(caminho) if os.path.exists(caminho) else QPixmap()
        if not self._original.isNull():
            self.logo.setPixmap(self._original.scaledToWidth(
                LARGURA_LOGO, Qt.TransformationMode.SmoothTransformation))
```

E acrescente, depois de `minimumSizeHint`:

```python
    # -- barra recolhida (2026-10-26) ----------------------------------------
    def recolher(self, recolhida: bool) -> None:
        """Recolhida: só o símbolo da GE, sem o nome. Expandida: como nasceu."""
        self.nome.setVisible(not recolhida)
        if not self._original.isNull():
            if recolhida:
                lado = self._original.height()
                desenho = self._original.copy(0, 0, lado, lado).scaledToWidth(
                    LARGURA_LOGO_RECOLHIDO, Qt.TransformationMode.SmoothTransformation)
            else:
                desenho = self._original.scaledToWidth(
                    LARGURA_LOGO, Qt.TransformationMode.SmoothTransformation)
            self.logo.setPixmap(desenho)
        self.updateGeometry()
```

- [ ] **Step 6: O Ctrl+K**

Em `sigft/app_qt/catalogo.py`, antes de `class AcaoDoCtrlK(NamedTuple):`, acrescente:

```python
# O menu lateral recolhível (2026-10-26): o botão do pé do menu e a ação do Ctrl+K
# (`acao:menu`, que alterna). O texto e o ícone dizem o que o clique FAZ.
TEXTO_RECOLHER_MENU = marcar("Recolher menu")
TEXTO_EXPANDIR_MENU = marcar("Expandir menu")
ICONE_RECOLHER_MENU = "chevrons-left"
ICONE_EXPANDIR_MENU = "chevrons-right"
```

Em `ACOES`, troque

```python
    AcaoDoCtrlK("logs", marcar("Abrir logs"), "folder-open", marcar("pasta log")),
```

por

```python
    AcaoDoCtrlK("logs", marcar("Abrir logs"), "folder-open", marcar("pasta log")),
    AcaoDoCtrlK("menu", TEXTO_RECOLHER_MENU, ICONE_RECOLHER_MENU,
                marcar("menu lateral barra esconder mostrar recolher expandir")),
```

E troque a função `comandos` inteira por:

```python
def comandos(*, menu_recolhido: bool = False) -> list[Comando]:
    """Os módulos (na ordem dos cartões da Home) e as ações, no idioma da sessão.
    O módulo bloqueado aparece como no menu: apagado, com a mesma dica, e não se
    escolhe. A busca acha pelas palavras traduzidas E pelas em português (o
    nome do módulo, o texto da ação e as palavras): quem trocou de idioma e
    ainda digita em português acha (revisão da Task 5, 2026-10-22).
    `menu_recolhido`: a ação do menu lateral diz "Expandir menu" (2026-10-26)."""
    menu_pt = {item[2]: item[1] for item in MENU if item[0] == "botao"}
    lista = []
    for alvo, titulo, _descricao in MODULOS:
        bloqueado = alvo in TELAS_BLOQUEADAS
        palavras = _com_o_portugues(
            f"{t(menu_pt.get(alvo, ''))} {alvo}", f"{menu_pt.get(alvo, '')} {titulo}")
        lista.append(Comando(
            f"tela:{alvo}", t(titulo) + (t(SUFIXO_BLOQUEADO) if bloqueado else ""), ICONE_DA_TELA[alvo],
            palavras, bloqueado=bloqueado, dica=dica_do_menu(alvo)))
    for acao in ACOES:
        texto_marcado, icone = acao.texto, acao.icone
        if acao.chave == "menu" and menu_recolhido:
            texto_marcado, icone = TEXTO_EXPANDIR_MENU, ICONE_EXPANDIR_MENU
        if acao.nome:
            texto, texto_pt = t(texto_marcado, nome=t(acao.nome)), texto_marcado.format(nome=acao.nome)
        else:
            texto, texto_pt = t(texto_marcado), texto_marcado
        palavras = _com_o_portugues(t(acao.palavras), f"{acao.palavras} {texto_pt}")
        lista.append(Comando(f"acao:{acao.chave}", texto, icone, palavras))
    return lista
```

- [ ] **Step 7: A barra lateral recolhível na janela**

Em `sigft/app_qt/main.py`:

1. No import de `PySide6.QtWidgets`, acrescente `QFrame`:

```python
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)
```

2. Depois da função `_arquivo_de_chaves`, acrescente:

```python
# O menu lateral recolhível (2026-10-26): a preferência, as margens de cada
# estado e o lado do botão do pé (a seta).
CHAVE_MENU_RECOLHIDO = "menu_recolhido"
MARGENS_DA_BARRA = (12, 26, 19, 12)            # 19 = 12 + os 7 px da faixa vazia
MARGENS_DA_BARRA_RECOLHIDA = (8, 26, 8, 12)
LADO_BOTAO_MENU = 36


def _menu_recolhido_guardado() -> bool:
    from sigft.core import prefs

    try:
        return prefs.get_opcao(CHAVE_MENU_RECOLHIDO, False)
    except Exception:  # noqa: BLE001 -- preferência é conveniência
        return False


def _guardar_menu_recolhido(valor: bool) -> None:
    from sigft.core import prefs

    try:
        prefs.set_opcao(CHAVE_MENU_RECOLHIDO, bool(valor))
    except Exception:  # noqa: BLE001 -- lembrar não pode atrapalhar o clique
        pass
```

3. No `SIG_FT_App.__init__`, troque

```python
        linha.addWidget(self._montar_sidebar())
        self.pilha = QStackedWidget(objectName="conteudo")
```

por

```python
        linha.addWidget(self._montar_sidebar())
        # [2026-10-26] O menu abre como ficou da última vez (recolhido ou não).
        self.recolher_menu(_menu_recolhido_guardado(), gravar=False)
        self.pilha = QStackedWidget(objectName="conteudo")
```

4. Troque o método `_montar_sidebar` inteiro por:

```python
    def _montar_sidebar(self) -> QScrollArea:
        area = QScrollArea(objectName="sidebar")
        # A largura total da barra da interface antiga (277), para os módulos
        # começarem no mesmo x. Lá, 17 desses px são a faixa da barra de rolagem,
        # SEMPRE visível (um traço cinza que não rola nada quando tudo cabe).
        # Aqui a faixa fica vazia -- margem direita maior --, e a barra do Qt só
        # aparece quando há o que rolar: a mesma largura sem o traço inútil, e os
        # botões com a largura que já tinham (246). Recolhida (2026-10-26):
        # `LARGURA_BARRA_RECOLHIDA`, em `recolher_menu`.
        area.setFixedWidth(estilo.LARGURA_BARRA_LATERAL)
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.barra_lateral = area
        interno = QWidget(objectName="sidebar_interno")
        lay = QVBoxLayout(interno)
        lay.setContentsMargins(*MARGENS_DA_BARRA)
        lay.setSpacing(estilo.ESPACO_MENU)
        self._lay_barra = lay
        # [2026-10-26] O que o menu recolhido troca (`recolher_menu`): cada botão com
        # o nome e a dica de quando está aberto; os títulos de seção e o traço fino
        # que fica no lugar deles.
        self._nomes_do_menu: list[tuple[QPushButton, str, str]] = []
        self._rotulos_secao: list[QLabel] = []
        self._tracos_secao: list[QFrame] = []

        # O logo da GE Vernova e o nome do SIG-FT viraram um botão só: brilham
        # sob o mouse e voltam à Home (sistema visual, 2026-10-20). Mesmas
        # medidas dos dois rótulos de antes (`widgets/marca.py`).
        self.marca = Marca(resource_path(os.path.join("assets", "logo.png")))
        blocos.sem_tecla(self.marca)
        self.marca.clicked.connect(self.show_home)
        lay.addWidget(self.marca)
        lay.addSpacing(22)
        # O emoji virou ícone (Lucide, na cor do tema: sistema visual, 2026-10-20).
        nome_home = t("Home")
        home = QPushButton(f" {nome_home}", objectName="home")
        # O ícone acompanha o texto do item escolhido (e sob o mouse): a marca
        # no claro (2026-10-20).
        icones.aplicar(home, catalogo.ICONE_DA_TELA["Home"], tamanho=16,
                       papel_cor_ativo=estilo.PAPEL_MENU_ESCOLHIDO)
        self.botao_home = home
        blocos.sem_tecla(home)   # os botões da barra (CTkButton) nunca pegam o foco
        home.clicked.connect(self.show_home)
        dica_home = t("Volta à tela inicial: os módulos, a engrenagem da configuração e os gastos de IA.")
        home.setToolTip(dica_home)
        home.setAccessibleName(nome_home)
        self._nomes_do_menu.append((home, nome_home, dica_home))
        lay.addWidget(home)
        lay.addSpacing(6)

        self.botoes_menu: dict[str, QPushButton] = {}
        for item in catalogo.MENU:
            if item[0] == "secao":
                lay.addSpacing(20)
                rotulo = QLabel(t(item[1]).upper(), objectName="secao")
                traco = QFrame(objectName="traco_secao")
                traco.setFixedHeight(1)
                traco.hide()
                lay.addWidget(rotulo)
                lay.addWidget(traco)
                self._rotulos_secao.append(rotulo)
                self._tracos_secao.append(traco)
                lay.addSpacing(5)
                continue
            _tipo, texto, alvo = item
            nome = t(texto)
            botao = QPushButton(f" {nome}")
            blocos.sem_tecla(botao)
            botao.setProperty("menu", True)
            icones.aplicar(botao, catalogo.ICONE_DA_TELA[alvo], tamanho=16,
                           papel_cor_ativo=estilo.PAPEL_MENU_ESCOLHIDO)
            botao.setEnabled(alvo not in catalogo.TELAS_BLOQUEADAS)
            dica = catalogo.dica_do_menu(alvo)
            botao.setToolTip(dica)
            botao.setAccessibleName(nome)
            botao.clicked.connect(lambda _=False, a=alvo: self.show_frame(a))
            self.botoes_menu[alvo] = botao
            self._nomes_do_menu.append((botao, nome, dica))
            lay.addWidget(botao)
        lay.addStretch()
        # [2026-10-26] A seta do pé recolhe e expande o menu (o ícone e a dica
        # dizem o que o clique faz: `recolher_menu`).
        self.botao_menu = blocos.botao("", variante="fantasma", largura=LADO_BOTAO_MENU,
                                       altura=estilo.ALTURA_BOTAO_MENU)
        self.botao_menu.clicked.connect(self.alternar_menu)
        lay.addWidget(self.botao_menu, 0, Qt.AlignmentFlag.AlignRight)
        area.setWidget(interno)
        return area

    def recolher_menu(self, recolhido: bool, *, gravar: bool = True) -> None:
        """O menu lateral só com os ícones (`recolhido`) ou com os nomes (2026-10-26).

        Recolhido: a barra fica com `LARGURA_BARRA_RECOLHIDA`, a marca vira só o
        logo, cada botão mostra só o ícone e leva o nome na dica (a dica de sempre
        vem depois do nome), e cada seção vira um traço fino. O item da tela aberta
        continua `ativo`. A área das telas ocupa o espaço que sobra (o layout já
        estica). `gravar`: lembra nas preferências (`menu_recolhido`)."""
        recolhido = bool(recolhido)
        self.menu_recolhido = recolhido
        self.barra_lateral.setFixedWidth(
            estilo.LARGURA_BARRA_RECOLHIDA if recolhido else estilo.LARGURA_BARRA_LATERAL)
        self._lay_barra.setContentsMargins(
            *(MARGENS_DA_BARRA_RECOLHIDA if recolhido else MARGENS_DA_BARRA))
        self.marca.recolher(recolhido)
        for rotulo in self._rotulos_secao:
            rotulo.setVisible(not recolhido)
        for traco in self._tracos_secao:
            traco.setVisible(recolhido)
        for botao, nome, dica in self._nomes_do_menu:
            if recolhido:
                botao.setText("")
                botao.setToolTip(f"{nome}\n\n{dica}" if dica else nome)
            else:
                botao.setText(f" {nome}")
                botao.setToolTip(dica)
            estilo.definir_propriedade(botao, "recolhido", recolhido)
        icones.aplicar(self.botao_menu,
                       catalogo.ICONE_EXPANDIR_MENU if recolhido else catalogo.ICONE_RECOLHER_MENU,
                       tamanho=16)
        dica_seta = t(catalogo.TEXTO_EXPANDIR_MENU if recolhido else catalogo.TEXTO_RECOLHER_MENU)
        self.botao_menu.setToolTip(dica_seta)
        self.botao_menu.setAccessibleName(dica_seta)
        self._lay_barra.setAlignment(
            self.botao_menu, Qt.AlignmentFlag.AlignHCenter if recolhido else Qt.AlignmentFlag.AlignRight)
        if gravar:
            _guardar_menu_recolhido(recolhido)

    def alternar_menu(self, *_args) -> None:
        """A seta do pé do menu e o "Recolher menu"/"Expandir menu" do Ctrl+K."""
        self.recolher_menu(not self.menu_recolhido)
```

5. Em `abrir_paleta`, troque

```python
        paleta = PaletaDeComandos(self, catalogo.comandos())
```

por

```python
        paleta = PaletaDeComandos(self, catalogo.comandos(menu_recolhido=self.menu_recolhido))
```

6. Em `executar_comando`, troque

```python
        elif alvo == "logs":
            self.abrir_pasta_de_logs()
```

por

```python
        elif alvo == "logs":
            self.abrir_pasta_de_logs()
        elif alvo == "menu":
            self.alternar_menu()
```

- [ ] **Step 8: As traduções**

```bash
.venv/bin/python - <<'EOF'
import json
import pathlib

NOVOS = {
    "es": {"Recolher menu": "Contraer menú", "Expandir menu": "Expandir menú",
           "menu lateral barra esconder mostrar recolher expandir":
               "menú lateral barra ocultar mostrar contraer expandir"},
    "en": {"Recolher menu": "Collapse menu", "Expandir menu": "Expand menu",
           "menu lateral barra esconder mostrar recolher expandir":
               "side menu sidebar hide show collapse expand"},
}
for codigo, pares in NOVOS.items():
    caminho = pathlib.Path("sigft/app/idiomas") / f"{codigo}.json"
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    dados.update(pares)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
EOF
.venv/bin/python tools/textos_da_interface.py --arrumar
.venv/bin/python tools/textos_da_interface.py
```

Expected: `es: 0 faltando, 0 sobrando` e `en: 0 faltando, 0 sobrando`.

- [ ] **Step 9: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q tests/test_qt_menu_recolhivel.py tests/test_qt_paleta.py tests/test_qt_main.py tests/test_qt_marca.py tests/test_qt_icones.py tests/test_qt_dicas.py tests/test_qt_idioma_telas.py tests/test_qt_idioma_varredura.py tests/test_qt_letra.py tests/test_qt_tema.py tests/test_icone_do_aplicativo.py tests/test_tela_correcao_pdm.py tests/test_textos_da_interface.py tests/test_qt_sem_cor_crua.py tests/test_propriedades.py`
Expected: PASS.

Run (os três idiomas):
`for i in pt es en; do QT_QPA_PLATFORM=offscreen timeout 180 .venv/bin/python frontend.py --smoke --idioma $i | tail -1; done`
Expected: três vezes `[smoke] a janela principal Qt montou, as 12 telas abriram e ela fechou sem erro.`

- [ ] **Step 10: Gate completo e commit**

Run: `SIGFT_PY=.venv/bin/python bash scripts/check.sh` e `.venv/bin/python -m ruff check .`
Expected: verde (a falha conhecida do `test_qt_saida.py` à parte); `All checks passed!`.

```bash
git add assets/icons/chevrons-left.svg assets/icons/chevrons-right.svg sigft/app_qt/icones.py \
    sigft/app_qt/estilo.py sigft/app_qt/widgets/marca.py sigft/app_qt/catalogo.py sigft/app_qt/main.py \
    tests/test_qt_menu_recolhivel.py tests/test_qt_paleta.py sigft/app/idiomas/es.json sigft/app/idiomas/en.json
git -c user.name=Jonathan -c user.email=jas.espinola.2022@aluno.unila.edu.br commit -F - <<'EOF'
Menu lateral recolhivel, lembrado, com a acao no Ctrl+K

<linhas de atribuicao da sessao>
EOF
```

---

### Task 5: Fechamento (CHANGELOG, base de conhecimento, suíte em 3.10 e 3.12)

**Files:**
- Modify: `CHANGELOG.md` (bloco novo `## 1.3.1` acima de `## 1.3.0`)
- Modify: `docs/base-conhecimento/00-frontend.md` (seção nova antes de `## Pontos de Atenção`)

**Interfaces:**
- Consumes: tudo das Tasks 1 a 4 (nomes citados na documentação).
- Produces: nada de código.

- [ ] **Step 1: Conferir o bloco em aberto (skill `sigft-lancar-versao`)**

Run: `grep -n '^## ' CHANGELOG.md | head -3` e `git ls-remote --tags origin | grep -v -- '-rc' | tail -3`
Expected: o topo é `## 1.3.0 - 2026-10-23` e o último release normal é `v1.3.0`: não há bloco
em aberto, então abre-se **um** bloco PATCH `1.3.1` (melhoria do que já existe; MINOR só com o
"sim" do Luan). Se já houver um bloco acima do `1.3.0` (outra frente abriu), as três linhas
entram NELE e nenhum bloco novo é criado.

- [ ] **Step 2: O CHANGELOG**

Em `CHANGELOG.md`, logo antes da linha `## 1.3.0 - 2026-10-23`, acrescente:

```markdown
## 1.3.1 - 2026-10-26

- Interface: o SIG-FT guarda um **diário** de cada abertura e fechamento em `Documentos\SIG-FT\logs\diario.log`. Se da última vez ele fechou de forma inesperada, ou foi encerrado sem fechar a janela (pelo Gerenciador de Tarefas ou ao desligar o computador), a Home avisa no topo, com o botão "Abrir o registro" para mandar o arquivo a quem cuida do SIG-FT; "Entendido" tira o aviso.
- Interface: na seleção de fichas e no Resumo do lote, as colunas podem ser **reordenadas** (arrastando o cabeçalho), **alargadas** (arrastando a borda) e **escondidas** (botão direito no cabeçalho). O SIG-FT lembra do jeito que ficou, também ao trocar de idioma, e "Restaurar colunas" volta ao padrão. O Resumo ganhou a coluna Tipo (Erro ou Aviso).
- Interface: o **menu lateral recolhe** para só os ícones, dando mais espaço às telas: a seta no pé do menu, ou "Recolher menu" no Ctrl+K. O nome de cada tela aparece na dica, a tela aberta continua destacada, e o SIG-FT lembra se o menu estava recolhido.

```

(Sem travessão; a primeira palavra de cada linha é a área, como nas linhas do 1.3.0.)

- [ ] **Step 3: A base de conhecimento**

Em `docs/base-conhecimento/00-frontend.md`, logo antes de `## Pontos de Atenção`, acrescente:

```markdown
### Diário, colunas e menu recolhível (2026-10-26)

- **Diário de quedas** (`sigft/core/diario.py`, sem Qt): `main()` chama `diario.abrir(versao=, idioma=)`
  depois da pergunta do idioma e antes da janela; ele lê a sessão anterior (`classificar`: `NORMAL`,
  `CAIU`, `ENCERRADO`) ANTES de gravar a nova `ABERTURA`, e liga `sys.excepthook`,
  `threading.excepthook` e o `faulthandler` (`logs/queda.log`; o com rastro vira `queda.log.anterior`).
  `SIG_FT_App.closeEvent` aceito grava `FECHAMENTO pela janela`. Passou de 1 MB, vira `diario.log.1`.
  Nunca levanta. A Home mostra `aviso_sessao` (cartão `#cartao[borda="aviso"]`) quando
  `diario.aviso_pendente()`; "Entendido" é `diario.dispensar_aviso()`. Nos testes vem desligado
  (`SIGFT_SEM_DIARIO`, no `conftest`); quem testa tira a variável e troca o `faulthandler` por um dublê.
- **Colunas lembradas** (`sigft/app_qt/widgets/colunas.py`): `instalar_colunas(tabela, chave,
  colunas_internas)` liga mover, largura e o menu do botão direito (esconder, "Restaurar colunas");
  guarda em `prefs` (seção `colunas`) pela chave da tabela e pela chave interna de cada coluna.
  `juntar` (pura) ignora coluna sumida, põe a nova no fim e trata preferência estragada como padrão.
  Na `tabela_ttk`, mexer desliga o `EsticaColunas` e a última coluna estica; restaurar o religa.
  Usam: `TabelaSelecaoDialog(chave_colunas=, colunas_internas=)` (`selecao_de_itens`,
  `selecao_duplicadas`) e o Resumo do lote (`resumo_do_lote`, colunas Mensagem e Tipo).
- **Menu recolhível** (`SIG_FT_App.recolher_menu`/`alternar_menu`): barra com
  `estilo.LARGURA_BARRA_RECOLHIDA`, só ícones (o nome na dica, antes da dica de sempre), seções como
  `#traco_secao`, a marca só com o símbolo (`Marca.recolher`). Lembrado em
  `prefs.get_opcao("menu_recolhido")`; Ctrl+K `acao:menu` (o texto diz "Recolher menu" ou
  "Expandir menu", `catalogo.comandos(menu_recolhido=)`). Cor só pela folha
  (`QPushButton[menu="true"][recolhido="true"]`, `#home[recolhido="true"]`).
```

- [ ] **Step 4: A suíte inteira em 3.10 e em 3.12**

Run:

```bash
SIGFT_PY=.venv/bin/python bash scripts/check.sh
.venv/bin/python -m ruff check .
/tmp/claude-0/-home-user/111ccf73-6723-5e3b-a4c3-03916583ae47/scratchpad/venv310/bin/python -m pytest -q
/tmp/claude-0/-home-user/111ccf73-6723-5e3b-a4c3-03916583ae47/scratchpad/venv312b/bin/python -m pytest -q
for i in pt es en; do QT_QPA_PLATFORM=offscreen timeout 180 .venv/bin/python frontend.py --smoke --idioma $i | tail -1; done
```

Expected: as três suítes verdes, exceto `tests/test_qt_saida.py::test_sessao_que_vaza_uma_tela_sai_com_zero`
(falha conhecida deste contêiner); ruff `All checks passed!`; os três smokes terminam com
`[smoke] a janela principal Qt montou, as 12 telas abriram e ela fechou sem erro.`
Se o 3.10 acusar `none_dealloc`, procure `.property(` novo (use `propriedades.ler`).

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md docs/base-conhecimento/00-frontend.md
git -c user.name=Jonathan -c user.email=jas.espinola.2022@aluno.unila.edu.br commit -F - <<'EOF'
CHANGELOG 1.3.1 e base de conhecimento: diario, colunas e menu recolhivel

<linhas de atribuicao da sessao>
EOF
```

---

## Cobertura da spec

| Spec | Onde |
|---|---|
| `diario.py` só biblioteca padrão, `ABERTURA` com versão, idioma e sistema | Task 1 (`abrir`, `test_modulo_nao_importa_interface`) |
| `FECHAMENTO pela janela` no `closeEvent` aceito; recusado não grava | Task 2 (`main.closeEvent`, dois testes) |
| `ERRO NAO TRATADO` por `sys.excepthook` e `threading.excepthook` | Task 1 (`_instalar_ganchos`, dois testes) |
| `faulthandler` em `queda.log`, aberto e mantido; o anterior vira `.anterior` | Task 1 |
| Rotação a 1 MB (`diario.log.1`, uma cópia) | Task 1 |
| Sessão anterior lida antes da nova `ABERTURA` (normal, caiu, encerrado) | Task 1 |
| Nunca impede a abertura; nada levanta | Task 1 (pasta que não grava, arquivo estragado) |
| Fora do `.exe` também grava | Task 2 (`main()` chama sem olhar `sys.frozen`) |
| Desligado nos testes pelo `conftest` | Task 2 |
| Aviso no topo da Home, sem modal, "Abrir o registro" e "Entendido", `t()` com `es`/`en` | Task 2 |
| Colunas: largura, ordem, esconder pelo botão direito, "Restaurar colunas", última não se esconde | Task 3 |
| Chave da tabela e chave interna da coluna; coluna sumida ignorada, nova no fim; estragada = padrão | Task 3 |
| `widgets/colunas.py` com `instalar_colunas` e a função pura testada sem tabela | Task 3 |
| As duas tabelas (seleção de fichas, Resumo do lote) | Task 3 |
| Menu: botão no pé com ícone de seta, `LARGURA_BARRA_RECOLHIDA` (~60 px) | Task 4 |
| Recolhido: só o logo, só ícones com o nome na dica, seções como traço; ativo destacado | Task 4 |
| Lembrado (`menu_recolhido`); Ctrl+K "Recolher menu"/"Expandir menu" achável em português | Task 4 |
| Expandido sem nome cortado em pt/es/en e letra Grande; cor só por papel | Task 4 |
| Uma linha no CHANGELOG por peça; suíte em 3.10 e 3.12; smoke em pt/es/en | Task 5 |
