# Sistema visual 1a — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** trocar a aparência das 12 telas do SIG-FT para o sistema visual da spec
`docs/superpowers/specs/2026-10-20-sistema-visual-design.md` (etapa 1a), com tema
escuro/claro/sistema, botões com hierarquia, ícones Lucide, logo com hover e o
nome na saudação — sem mexer em fluxo, texto de tela ou serviço.

**Architecture:** as cores e escalas saem de um módulo sem Qt (`sigft/app/tokens.py`);
`estilo.folha_de_estilo(tema)` monta a folha QSS a partir dele; nenhuma tela guarda
cor própria (um teste varre o código). Os ícones são SVG em `assets/icons/`,
recoloridos na carga. Trocar o tema = regerar a folha e reaplicar no `QApplication`.

**Tech Stack:** Python 3.10+, PySide6 (QtWidgets, QtSvg, QtGui), pytest-qt (offscreen),
PyInstaller (`SIG-FT.spec`).

## Global Constraints

- Código, comentários, commits em **português**; commit sem acento, autor Jonathan,
  pé com `Co-Authored-By` e `Claude-Session` (ver CLAUDE.md).
- Texto que o usuário lê: **sem travessão** (`tests/test_texto_da_ui.py`).
- Contraste mínimo **4,5:1** para texto (WCAG AA), medido em teste.
- O console é escuro nos dois temas (`console_fundo` `#0E1012`).
- Paleta exata da spec (tabela "Tokens"), inclusive `primaria` escuro `#00C975` com
  `texto_sobre_primaria` `#0B1A12`, e `perigo_fundo` `#C9302C` com texto branco.
- Nenhuma dependência nova no `requirements.txt` (QtSvg já vem no PySide6).
- `scripts/check.sh` verde antes de cada commit (o `test_qt_saida` falha só neste
  contêiner: preexistente); `QT_QPA_PLATFORM=offscreen python frontend.py --smoke`
  depois de mexer em `main.py` ou numa tela.
- Fluxos, textos de botão, ordem do menu e serviços: **não mudam**.

---

## Mapa de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `sigft/app/tokens.py` (novo) | as duas paletas, escala de fonte, espaço e raio; `contraste()` |
| `sigft/app/theme.py` | `COLORS` passa a ser derivado de `tokens.ESCURO` (compatibilidade) |
| `sigft/app_qt/estilo.py` | `folha_de_estilo(tema="escuro")`; variantes de botão; papéis de texto |
| `sigft/app_qt/tema.py` (novo) | escolher, guardar e aplicar o tema em execução |
| `sigft/core/prefs.py` | `tema`, `nome_de_quem_usa`, `ja_perguntou_nome` |
| `sigft/app_qt/icones.py` (novo) + `assets/icons/*.svg` + `assets/icons/LICENSE` | ícones Lucide recoloridos |
| `sigft/app_qt/widgets/blocos.py` | `botao` sem cor própria; `variante_da_cor` |
| `sigft/app_qt/main.py` | barra lateral com ícones, logo com hover, splash novo, tema na abertura |
| `sigft/app_qt/widgets/marca.py` (novo) | o bloco logo + nome com o brilho |
| `sigft/app_qt/views/home.py` | seletor de tema, saudação com nome, cartões com ícone |
| `sigft/app_qt/nome.py` (novo) | a pergunta do nome, uma vez |
| telas e widgets com cor crua | cor → papel/variante |
| `SIG-FT.spec` | `assets/icons` no pacote; plugin `iconengines/qsvgicon` |
| testes | ver cada tarefa |

---

### Task 1: Tokens e contraste

**Files:**
- Create: `sigft/app/tokens.py`
- Test: `tests/test_tokens.py`

**Interfaces:**
- Produces: `tokens.ESCURO: dict[str, str]`, `tokens.CLARO: dict[str, str]`,
  `tokens.paleta(tema: str) -> dict[str, str]` (`"escuro"`/`"claro"`, outro valor → escuro),
  `tokens.contraste(a: str, b: str) -> float`, `tokens.FONTE = {"titulo": 22, "secao": 15, "corpo": 13, "legenda": 12}`,
  `tokens.ESPACO = (4, 8, 12, 16, 24)`, `tokens.RAIO = {"controle": 6, "cartao": 10}`.

- [ ] **Step 1: teste que falha**

```python
"""Tokens do sistema visual (2026-10-20): cada cor tem um papel, e o texto se lê."""
import pytest

from sigft.app import tokens

PAPEIS = {"fundo", "superficie", "superficie_alta", "borda", "texto", "texto_suave",
          "primaria", "primaria_hover", "texto_sobre_primaria", "marca", "sucesso",
          "aviso", "perigo", "perigo_fundo", "info", "console_fundo", "console_texto"}


@pytest.mark.parametrize("tema", ["escuro", "claro"])
def test_os_dois_temas_tem_os_mesmos_papeis(tema):
    assert set(tokens.paleta(tema)) == PAPEIS


def test_contraste_conhecido():
    assert tokens.contraste("#FFFFFF", "#000000") == pytest.approx(21.0, abs=0.01)
    assert tokens.contraste("#FFFFFF", "#00A86B") < 4.5   # o verde que reprovou na spec


PARES = [("texto", "fundo"), ("texto", "superficie"), ("texto", "superficie_alta"),
         ("texto_suave", "fundo"), ("texto_suave", "superficie"),
         ("texto_sobre_primaria", "primaria"), ("texto_sobre_primaria", "primaria_hover"),
         ("perigo", "superficie"), ("aviso", "superficie"), ("sucesso", "superficie"),
         ("info", "superficie")]


@pytest.mark.parametrize("tema", ["escuro", "claro"])
@pytest.mark.parametrize("texto,fundo", PARES)
def test_texto_se_le_nos_dois_temas(tema, texto, fundo):
    p = tokens.paleta(tema)
    assert tokens.contraste(p[texto], p[fundo]) >= 4.5, (tema, texto, fundo)


def test_botao_de_perigo_tem_texto_branco_legivel():
    for tema in ("escuro", "claro"):
        assert tokens.contraste("#FFFFFF", tokens.paleta(tema)["perigo_fundo"]) >= 4.5


def test_console_e_escuro_nos_dois_temas():
    assert tokens.ESCURO["console_fundo"] == tokens.CLARO["console_fundo"] == "#0E1012"


def test_tema_desconhecido_cai_no_escuro():
    assert tokens.paleta("roxo") is tokens.ESCURO
```

- [ ] **Step 2:** `.venv/bin/python -m pytest -q tests/test_tokens.py` → falha (módulo não existe).

- [ ] **Step 3: implementação** — `sigft/app/tokens.py` com as tabelas da spec. Valores
  que a spec não fixou: `console_texto` `#C9CFD6` nos dois; `aviso` claro `#B26A00`;
  `sucesso` claro `#00875A`; `info` escuro `#3B9EFF`, claro `#0B6BCB`; `perigo` escuro
  `#F2555A`. `contraste()` pela fórmula WCAG (luminância relativa, `(L1+0.05)/(L2+0.05)`).
  Se algum par do teste reprovar, **escurecer/clarear o valor e anotar na spec**, nunca
  baixar o limite.

- [ ] **Step 4:** teste passa.
- [ ] **Step 5:** commit `Sistema visual: tokens com dois temas e contraste medido`.

---

### Task 2: `theme.COLORS` derivado dos tokens

**Files:**
- Modify: `sigft/app/theme.py:29-42`
- Test: `tests/test_tokens.py` (acrescentar)

**Interfaces:**
- Consumes: `tokens.ESCURO`.
- Produces: `theme.COLORS` com as MESMAS chaves de hoje (`primary`, `primary_hover`,
  `accent`, `accent_hover`, `danger`, `warning`, `sidebar`, `background`, `text_light`,
  `text_white`), valores: `primary`=`marca`, `primary_hover`=`#047A83`,
  `accent`=`sucesso`, `accent_hover`=`primaria_hover`, `danger`=`perigo_fundo`,
  `warning`=`aviso`, `sidebar`=`superficie`, `background`=`fundo`,
  `text_light`=`texto`, `text_white`=`#FFFFFF`; `theme.COR_CARTAO`=`superficie`.

- [ ] **Step 1: teste**

```python
def test_colors_antigo_vem_dos_tokens():
    from sigft.app import theme
    assert theme.COLORS["background"] == tokens.ESCURO["fundo"]
    assert theme.COLORS["accent"] == tokens.ESCURO["sucesso"]
    assert theme.COLORS["danger"] == tokens.ESCURO["perigo_fundo"]
    assert theme.COR_CARTAO == tokens.ESCURO["superficie"]
```

- [ ] **Step 2:** falha. **Step 3:** derivar. **Step 4:** rodar a suíte inteira e
  anotar os testes que travavam o valor antigo (`#212121`, `#2B2B2B`, `#161616`…):
  atualizar cada um para o token, com o motivo na docstring ("a fidelidade à CTk caiu
  em 2026-10-15; o valor vem do token"). **Step 5:** commit.

---

### Task 3: Folha de estilo nova, por tema

**Files:**
- Modify: `sigft/app_qt/estilo.py` (`folha_de_estilo`, `_folha_e31`, `folha_rolagem_ctk`)
- Test: `tests/test_qt_estilo.py` (acrescentar), testes de medida que quebrarem

**Interfaces:**
- Consumes: `tokens.paleta`, `tokens.FONTE`, `tokens.RAIO`.
- Produces: `estilo.folha_de_estilo(tema: str = "escuro") -> str` (o tamanho de letra
  é da 1b e entra lá).
  Variantes de botão: `primario`, `secundario`, `perigo`, `fantasma`; as antigas viram
  sinônimos na folha: `acento`→primario, `cinza`/`neutro`/`contorno`/`contorno_padrao`
  →secundario. Papéis de texto por propriedade: `QLabel[papel="legenda"]`
  (`texto_suave`, 12px), `[papel="secao"]` (15 bold), `[papel="titulo"]` (22 bold),
  `[papel="aviso"|"erro"|"ok"]`.

- [ ] **Step 1: testes**

```python
import re

from sigft.app import tokens
from sigft.app_qt import estilo


def _regra(folha, seletor):
    achado = re.search(re.escape(seletor) + r"\s*\{([^}]*)\}", folha)
    assert achado, seletor
    return achado.group(1)


@pytest.mark.parametrize("tema", ["escuro", "claro"])
def test_folha_usa_a_paleta_do_tema(tema):
    p = tokens.paleta(tema)
    folha = estilo.folha_de_estilo(tema)
    assert p["fundo"] in _regra(folha, "QMainWindow, #conteudo, #tela")
    assert p["primaria"] in _regra(folha, 'QPushButton[variante="primario"]')
    assert p["texto_sobre_primaria"] in _regra(folha, 'QPushButton[variante="primario"]')
    assert p["perigo_fundo"] in _regra(folha, 'QPushButton[variante="perigo"]')
    assert p["console_fundo"] in _regra(folha, "#console")


def test_variantes_antigas_viram_as_novas():
    folha = estilo.folha_de_estilo("escuro")
    for antiga in ("acento", "cinza", "neutro", "contorno", "contorno_padrao"):
        assert f'[variante="{antiga}"]' in folha


def test_folhas_dos_dois_temas_sao_diferentes():
    assert estilo.folha_de_estilo("escuro") != estilo.folha_de_estilo("claro")
```

- [ ] **Step 2:** falha. **Step 3:** reescrever `folha_de_estilo` com os tokens
  (botão padrão = secundário; raio 6; padding 0 14px; `min-height` 32; menu lateral
  com item selecionado `marca` em 25% — no escuro `#0F3A3F`, no claro `#E3F1F2` —
  e texto `texto`/`#035D67`; `QLineEdit`/`QComboBox` com fundo `superficie_alta`,
  borda `borda`, foco borda `primaria`; `QCheckBox::indicator:checked` e
  `QRadioButton::indicator:checked` em `primaria`; `QProgressBar::chunk` `primaria`;
  tabela (`QTreeView`) e lista clara nas cores do tema, não mais o Tk nativo).
  Remover as constantes `*_CTK` que ficarem sem uso.
- [ ] **Step 4:** suíte inteira; os testes de medida que travavam pixel da CTk são
  reescritos para a medida nova, um a um (nunca apagados). Smoke.
- [ ] **Step 5:** commit.

---

### Task 4: Botão sem cor própria

**Files:**
- Modify: `sigft/app_qt/widgets/blocos.py` (`botao`)
- Modify: os 22 usos de `cor_fundo=` (lista: `grep -rn "cor_fundo=" sigft/app_qt`)
- Test: `tests/test_qt_botoes.py` (novo)

**Interfaces:**
- Produces: `blocos.variante_da_cor(cor: str | None) -> str | None`:
  `COLORS["primary"]`, `COLORS["accent"]`, `VERDE_TK`, `"#2E7D32"`→`"primario"`;
  `COLORS["danger"]`, `COR_PARAR`, `"#D32F2F"`→`"perigo"`; `"transparent"`→`"fantasma"`;
  qualquer cinza (`#3A3A3A`, `gray`, `#555555`…)→`"secundario"`; `None`→`None`.
  `botao(..., cor_fundo=X)` passa a chamar `variante_da_cor(X)` e NÃO escreve cor no
  `setStyleSheet` (só medidas).

- [ ] **Step 1: testes**

```python
from sigft.app.theme import COLORS
from sigft.app_qt.widgets import blocos


def test_cor_vira_variante():
    assert blocos.variante_da_cor(COLORS["primary"]) == "primario"
    assert blocos.variante_da_cor(COLORS["danger"]) == "perigo"
    assert blocos.variante_da_cor("transparent") == "fantasma"
    assert blocos.variante_da_cor("#3A3A3A") == "secundario"


def test_botao_nao_guarda_cor(qapp):
    b = blocos.botao("Salvar", cor_fundo=COLORS["primary"])
    assert b.property("variante") == "primario"
    assert "background" not in b.styleSheet()


def test_ninguem_passa_cor_fundo_novo():
    """Uso novo de cor crua no botão reprova: use `variante=`."""
    import pathlib, re
    usos = [p for p in pathlib.Path("sigft/app_qt").rglob("*.py")
            if re.search(r"botao\([^)]*cor_fundo=", p.read_text(encoding="utf-8"))]
    assert usos == []
```

- [ ] **Step 2:** falha. **Step 3:** implementar e trocar cada `cor_fundo=` por
  `variante=` (a tabela acima decide). **Step 4:** suíte + smoke. **Step 5:** commit.

---

### Task 5: Nenhuma cor crua fora do estilo

**Files:**
- Modify: os 15 arquivos com hexadecimal (`grep -rlE "#[0-9A-Fa-f]{6}" sigft/app_qt`),
  menos `estilo.py`
- Test: `tests/test_qt_sem_cor_crua.py` (novo)

**Interfaces:**
- Consumes: papéis de texto da Task 3 (`setProperty("papel", ...)`), variantes da Task 4.

- [ ] **Step 1: teste**

```python
"""Cor só no estilo (2026-10-20): uma cor escrita numa tela fica escura no tema claro."""
import pathlib
import re

COR = re.compile(r"#[0-9A-Fa-f]{6}\b|cinza_tk\(")
PERMITIDOS = {"sigft/app_qt/estilo.py"}


def test_nenhuma_tela_tem_cor_propria():
    achados = []
    for p in pathlib.Path("sigft/app_qt").rglob("*.py"):
        if str(p).replace("\\", "/") in PERMITIDOS:
            continue
        for n, linha in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if COR.search(linha.split("#", 1)[0] if linha.lstrip().startswith("#") else linha):
                achados.append(f"{p}:{n}")
    assert achados == []
```

  (A linha que é só comentário não conta.)

- [ ] **Step 2:** falha listando ~80 linhas. **Step 3:** trocar, arquivo por arquivo:
  rótulo cinza → `setProperty("papel", "legenda")`; cartão → `objectName="cartao"`;
  cor de aviso/erro/ok → papel `aviso`/`erro`/`ok`; `Abas(cor_fundo=...)` → as cores
  vêm do tema (o parâmetro some); `mural.py` e `busca_pmib.py` (cartões de resultado)
  → regras `#cartao_resultado` na folha. **Step 4:** suíte + smoke. **Step 5:** commit
  (pode ser um por arquivo grande: `home.py`, `autospec.py`, `busca_pmib.py`).

---

### Task 6: Ícones Lucide

**Files:**
- Create: `assets/icons/*.svg` (os listados abaixo, copiados de `lucide-static@0.460.0`
  — `npm pack lucide-static@0.460.0`, registro npm), `assets/icons/LICENSE` (ISC do pacote)
- Create: `sigft/app_qt/icones.py`
- Modify: `sigft/app_qt/main.py` (menu e Home), `sigft/app_qt/views/home.py` (barra e
  cartões), botões com emoji (`grep -rn "mono(" sigft/app_qt/views`)
- Modify: `SIG-FT.spec` (datas `assets/icons`; plugin `iconengines`)
- Modify: `sigft/app_qt/main.py` `--smoke` (confere um ícone)
- Test: `tests/test_qt_icones.py`

Ícones e onde vão: `house` (Home), `file-plus` (Cria Fichas), `table` (Planilhas),
`chart-column` (Analyzer), `upload` (Upload Condições), `languages` (Tradutor),
`list` (Upload Specs), `wrench` (Correção de PDM), `copy` (duplicadas),
`sparkles` (AutoSpec), `tag` (LMR), `folder-kanban` (PMIB Manager), `search` (Busca),
`clipboard-check` (Atividades), `bot` (Modelos de IA), `circle-dollar-sign` (Gastos),
`key-round` (Chaves), `refresh-cw` (atualizações), `folder-open` (abrir pasta),
`file` (abrir arquivo), `trash-2` (limpar), `play` (iniciar robô), `square` (parar),
`settings` (configurar pesos), `arrow-down` (adicionar à fila), `sun`, `moon`, `monitor`.

**Interfaces:**
- Produces: `icones.icone(nome: str, cor: str, tamanho: int = 18) -> QIcon` (troca
  `currentColor` pela cor; cache por `(nome, cor, tamanho)`); `icones.NOMES: frozenset[str]`;
  `icones.PASTA`. Nome desconhecido → `QIcon()` vazio e aviso no log (não derruba tela).

- [ ] **Step 1: testes**

```python
from sigft.app_qt import icones


def test_todo_icone_listado_existe():
    for nome in icones.NOMES:
        assert (icones.PASTA / f"{nome}.svg").is_file(), nome


def test_icone_carrega_colorido(qapp):
    i = icones.icone("house", "#00C975")
    assert not i.isNull()
    assert not i.pixmap(18, 18).isNull()


def test_nome_desconhecido_nao_derruba(qapp):
    assert icones.icone("nao-existe", "#FFFFFF").isNull()


def test_licenca_vai_junto():
    assert "ISC" in (icones.PASTA / "LICENSE").read_text(encoding="utf-8")


def test_pacote_leva_os_icones():
    spec = open("SIG-FT.spec", encoding="utf-8").read()
    assert "assets/icons" in spec or "assets\\\\icons" in spec
```

- [ ] **Step 2:** falha. **Step 3:** baixar com `npm pack`, copiar só os nomes da lista,
  implementar `icones.py` (`QSvgRenderer` sobre os bytes com `currentColor` trocado,
  pintado num `QPixmap` com `devicePixelRatio`), pôr ícone + texto nos botões (o texto
  fica: teste e leitor de tela leem), tirar o emoji do texto. **Step 4:** conferir no
  `SIG-FT.spec` que `_qt_que_a_interface_nao_usa` não descarta `qsvgicon`/`qsvg`; smoke
  com a checagem de ícone. **Step 5:** commit.

---

### Task 7: Tema escuro / claro / sistema, em execução

**Files:**
- Create: `sigft/app_qt/tema.py`
- Modify: `sigft/core/prefs.py` (`ler_preferencia(chave, padrao)`, `gravar_preferencia(chave, valor)`
  se não existir algo equivalente — conferir antes o que `updater.canal_testes_ligado` usa
  e REUSAR)
- Modify: `sigft/app_qt/main.py` (`_preparar_qt` aplica o tema salvo)
- Modify: `sigft/app_qt/views/home.py` (seletor de três botões na barra)
- Test: `tests/test_qt_tema.py`

**Interfaces:**
- Produces: `tema.TEMAS = ("escuro", "claro", "sistema")`; `tema.escolhido() -> str`
  (prefs, padrão `"escuro"`); `tema.efetivo(escolha: str) -> str` (`"sistema"` →
  `QGuiApplication.styleHints().colorScheme()`: `Light`→`"claro"`, resto→`"escuro"`);
  `tema.aplicar(app, escolha: str) -> None` (grava, regera a folha, `app.setStyleSheet`,
  e repinta os ícones: emite `tema.mudou` (sinal num `QObject` do módulo) para quem
  desenhou ícone se repintar).

- [ ] **Step 1: testes**

```python
from sigft.app import tokens
from sigft.app_qt import tema


def test_sistema_segue_o_windows(monkeypatch):
    monkeypatch.setattr(tema, "_esquema_do_sistema", lambda: "claro")
    assert tema.efetivo("sistema") == "claro"
    assert tema.efetivo("escuro") == "escuro"


def test_aplicar_troca_a_folha_e_lembra(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(tema, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    tema.aplicar(qapp, "claro")
    assert tokens.CLARO["fundo"] in qapp.styleSheet()
    assert tema.escolhido() == "claro"
    tema.aplicar(qapp, "escuro")
    assert tokens.ESCURO["fundo"] in qapp.styleSheet()


def test_escolha_invalida_vira_escuro(tmp_path, monkeypatch):
    monkeypatch.setattr(tema, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    (tmp_path / "p.json").write_text('{"tema": "roxo"}', encoding="utf-8")
    assert tema.escolhido() == "escuro"
```

- [ ] **Step 2–4:** implementar; seletor na Home com os ícones `moon`/`sun`/`monitor`,
  dica em cada um; teste de tela: clicar "Claro" muda o fundo de `#tela`.
  Smoke nos dois temas (`--smoke` aceita `--tema claro`). **Step 5:** commit.

---

### Task 8: Logo com hover e clique para a Home

**Files:**
- Create: `sigft/app_qt/widgets/marca.py`
- Modify: `sigft/app_qt/main.py` (barra lateral usa `Marca`)
- Test: `tests/test_qt_marca.py`

**Interfaces:**
- Produces: `marca.Marca(QPushButton)`: ícone = `assets/logo.png`, texto "SIG-FT";
  `objectName="marca"`; dica "Voltar ao início"; `QGraphicsDropShadowEffect` cor
  `primaria`, `blurRadius` animado 0→18 em 150 ms (`QPropertyAnimation`) no
  `enterEvent`/`focusInEvent`, e de volta no `leaveEvent`/`focusOutEvent`; sem
  animação se `QApplication.isEffectEnabled(Qt.UIEffect.UI_AnimateMenu)` for falso.
  Sinal `clicked` ligado a `show_home`.

- [ ] **Step 1: testes**

```python
from PySide6.QtCore import QEvent
from PySide6.QtGui import QEnterEvent
from PySide6.QtCore import QPointF

from sigft.app_qt.widgets.marca import Marca


def test_hover_acende_e_apaga(qapp, qtbot):
    m = Marca(); qtbot.addWidget(m); m.show()
    m.enterEvent(QEnterEvent(QPointF(), QPointF(), QPointF()))
    qtbot.waitUntil(lambda: m.graphicsEffect().blurRadius() >= 17, timeout=1000)
    m.leaveEvent(QEvent(QEvent.Type.Leave))
    qtbot.waitUntil(lambda: m.graphicsEffect().blurRadius() <= 1, timeout=1000)


def test_clique_volta_para_a_home(qt_interface, qtbot, tmp_path, monkeypatch):
    from sigft.app_qt import main as qmain
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "k.json"))
    j = qmain.SIG_FT_App(); qtbot.addWidget(j)
    j.show_frame("Translator")
    j.marca.click()
    assert j.pilha.currentWidget() is j.telas["Home"]
```

- [ ] **Step 2–4.** **Step 5:** commit.

---

### Task 9: Nome na saudação, perguntado uma vez

**Files:**
- Create: `sigft/app_qt/nome.py`
- Modify: `sigft/app_qt/main.py` (depois da janela aparecer, antes das novidades: se
  `precisa_perguntar()`, abre a caixa)
- Modify: `sigft/app_qt/views/home.py` (título vira saudação; clicar troca o nome)
- Test: `tests/test_qt_nome.py`

**Interfaces:**
- Produces: `nome.guardado() -> str` (`""` sem nome); `nome.precisa_perguntar() -> bool`
  (sem nome E sem `ja_perguntou_nome`); `nome.guardar(texto: str) -> None` (aparar,
  máx. 40 caracteres, marca `ja_perguntou_nome`); `nome.recusar() -> None` (só marca);
  `nome.saudacao(agora: datetime, quem: str) -> str` ("Bom dia"/"Boa tarde"/"Boa noite"
  + `", " + quem` se houver); `nome.PerguntaDoNome(QDialog)` com campo e botões
  "Salvar" (primario) / "Agora não" (secundario).

- [ ] **Step 1: testes**

```python
from datetime import datetime

from sigft.app_qt import nome


def test_saudacao_pelo_relogio():
    assert nome.saudacao(datetime(2026, 10, 20, 9), "Ana") == "Bom dia, Ana"
    assert nome.saudacao(datetime(2026, 10, 20, 14), "") == "Boa tarde"
    assert nome.saudacao(datetime(2026, 10, 20, 19), "Ana") == "Boa noite, Ana"


def test_pergunta_uma_vez_so(tmp_path, monkeypatch):
    monkeypatch.setattr(nome, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    assert nome.precisa_perguntar()
    nome.recusar()
    assert not nome.precisa_perguntar()
    assert nome.guardado() == ""


def test_guardar_apara_e_limita(tmp_path, monkeypatch):
    monkeypatch.setattr(nome, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    nome.guardar("   Jonathan   ")
    assert nome.guardado() == "Jonathan"
    nome.guardar("x" * 100)
    assert len(nome.guardado()) == 40


def test_o_nome_nao_vai_para_o_log(qt_interface, qtbot, tmp_path, monkeypatch):
    """Só aparece na tela: nada de log, planilha, IA ou portal."""
    import pathlib, re
    usos = [p for p in pathlib.Path("sigft").rglob("*.py")
            if "nome.guardado(" in p.read_text(encoding="utf-8")]
    permitidos = {"sigft/app_qt/nome.py", "sigft/app_qt/views/home.py"}
    assert {str(p).replace("\\", "/") for p in usos} <= permitidos
```

- [ ] **Step 2–4.** Smoke não pode travar na pergunta: com `--smoke`, `precisa_perguntar`
  é ignorado. **Step 5:** commit.

---

### Task 10: Splash novo

**Files:**
- Modify: `sigft/app_qt/main.py` (`SplashScreen`)
- Test: `tests/test_qt_splash.py` (acrescentar ao que existir)

**Interfaces:**
- Consumes: `tokens.paleta(tema.efetivo(tema.escolhido()))`.

- [ ] **Step 1:** teste: o fundo do splash é o `fundo` do tema escolhido e a barra é
  `primaria`; o texto da versão vem de `_build_info.VERSAO`.
- [ ] **Step 2–4:** fundo `fundo`, logo centralizado, "SIG-FT" 22 bold, versão em
  `texto_suave`, barra de 4 px `primaria`, cantos 10. **Step 5:** commit.

---

### Task 11: Fechamento

- [ ] `scripts/check.sh` inteiro; smoke nos dois temas.
- [ ] Capturas das telas principais nos dois temas (`QWidget.grab()` num script em
  scratchpad, offscreen) e mandar ao Jonathan.
- [ ] `CHANGELOG.md`: bloco em aberto, itens com o nome "Interface" na frente.
- [ ] `docs/base-conhecimento/`: o doc da interface ganha a seção "Sistema visual".
- [ ] Mural do `CLAUDE.md`: aviso para o Rafael (a tela do AutoSpec mudou de cor, as
  invariantes de teste dele seguem; cor nova só por papel/variante).
- [ ] PR para a branch oficial.
