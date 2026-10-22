# Configuração (engrenagem) e idioma: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** juntar numa janela "Configuração" (a engrenagem da Home) tudo o que hoje é
configurável e está espalhado pela Home, e deixar a interface do SIG-FT em espanhol,
português e inglês, perguntado na primeira abertura e trocável na engrenagem
(spec `docs/superpowers/specs/2026-10-22-configuracao-e-idioma-design.md`), num PR só.

**Architecture:** a engrenagem é uma `JanelaPainel` nova (`sigft/app_qt/views/configuracao.py`)
que só reorganiza o que existe: cada controle chama a mesma função que o controle da Home
chamava. O idioma é um módulo sem Qt (`sigft/app/idioma.py`) com `t(texto_pt, **valores)`:
a chave é o próprio texto em português, as traduções moram em `sigft/app/idiomas/es.json` e
`en.json`, e a ferramenta `tools/textos_da_interface.py` lê o código (`ast`) para listar as
chaves, o que falta nos catálogos e os literais de interface que escaparam do `t()`. O idioma
vale ao reiniciar: cada tela lê os textos uma vez, ao ser montada; a primeira abertura
pergunta antes de montar a janela principal.

**Tech Stack:** Python 3.10+, PySide6 (QtWidgets, `QTranslator` do `qtbase`), pytest-qt
(offscreen), `ast` e `json` da biblioteca padrão. Nenhuma dependência nova.

## Global Constraints

- Código, comentários, docs e commits em **português**; mensagem de commit sem acento; pé
  do commit com as duas linhas do lembrete de atribuição da sessão
  (`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` e
  `Claude-Session: https://claude.ai/code/session_01RSbK7jX9qvsvyZKqnojmij`).
- Texto que o usuário lê: **sem travessão** (`—` nem `–`), em português E nas traduções
  (`tests/test_texto_da_ui.py` para o código; `tests/test_textos_da_interface.py` para os
  catálogos). Vale também para as linhas novas do `CHANGELOG.md`.
- **Cor só em `sigft/app_qt/estilo.py`** (`tests/test_qt_sem_cor_crua.py`).
- **Serviço não importa Qt; módulo novo em `sigft/app/` não importa PySide6.** Nenhum arquivo
  de `sigft/services/`, `sigft/core/rpa/`, `sigft/core/web/` muda. O que os serviços escrevem
  (console, `pause`/`ask` vindos do serviço, planilhas, portal) **fica em português**: só se
  traduz texto escrito em `sigft/app_qt/` e em `sigft/app/textos_dialogos.py`,
  `textos_dicas.py`, `atualizacao_textos.py` e `resumo_lote.py`.
- Sinal de widget filho **não** recebe `lambda` que capture a tela ou a janela (mural de
  2026-10-14): use método ligado; o botão de escolha guarda a escolha na propriedade
  `escolha` e o método lê `self.sender().property("escolha")`. (A `HomeView` vive o app
  inteiro e já usa `lambda` na barra: fica como está.)
- **Fronteira do Rafael:** a tela `ModuloAutoSpec` (`sigft/app_qt/views/autospec.py`) só troca
  literal por `t()`, sem mudar comportamento nem layout. Os testes de tela dele
  (`tests/test_autospec_*_tela.py`, `tests/test_qt_tela_autospec.py`) **não mudam**: rodam em
  português, onde `t(x) == x`.
- **Os testes rodam em português.** `tests/conftest.py` põe `idioma.definir("pt")` antes e
  depois de cada teste; teste de idioma troca com `tests/_idioma.em_idioma(...)`. Por isso
  todo teste que compara texto literal continua valendo, e **nenhum teste de medida em
  português muda** (exceto os da Home na Task 1, reescritos com o motivo no commit).
- Constante de módulo que é texto de interface vira `marcar("...")` (mesmo texto; a
  ferramenta a reconhece como chave) e é traduzida **onde aparece na tela**: `t(CONSTANTE)`.
  Texto com valor usa `{nome}`: `t("Ficha {atual} de {total}", atual=3, total=8)`. Nunca
  `t(f"...")`.
- **Quem chama traduz.** Função ou widget que recebe texto (`titulo=`, `mensagem=`,
  `texto_botao=`) mostra o que recebeu; parâmetro com texto padrão vira `None` e o padrão é
  `t(...)` dentro da função.
- Testes com `.venv/bin/python -m pytest -q <arquivos>`; antes de cada commit
  `bash scripts/check.sh` verde (o `tests/test_qt_saida.py` falha só neste contêiner:
  preexistente, ver o plano 1a). Mexeu em `main.py` ou numa tela:
  `QT_QPA_PLATFORM=offscreen .venv/bin/python frontend.py --smoke` (e, a partir da Task 3,
  também com `--idioma es` e `--idioma en`).
- Nada de reformatação em massa; commit pequeno por tarefa, sem `git add -A`.

---

## Mapa de arquivos

| Arquivo | Responsabilidade | Tarefa |
|---|---|---|
| `sigft/app_qt/views/configuracao.py` (novo) | `JanelaConfiguracao`: as seções e os controles | 1, 3 |
| `sigft/app_qt/views/home.py` | engrenagem no título; perde seletores, caixas e 3 botões; `abrir_configuracao` | 1, 5 |
| `sigft/app_qt/catalogo.py` | `ACOES_DA_HOME` (2), `ACAO_CONFIGURACAO`, `ACOES_DA_CONFIGURACAO`, `SECOES_DA_CONFIGURACAO`, Ctrl+K | 1, 3, 5 |
| `sigft/app_qt/main.py` | `ACAO_NA_HOME`; idioma na abertura; `--idioma`; tradução do Qt; smoke confere catálogos | 1, 2, 3, 5 |
| `sigft/app/textos_dicas.py` | dicas da janela Configuração | 1, 4 |
| `sigft/app_qt/estilo.py` | `#seletor_idioma` na regra dos seletores | 3 |
| `sigft/app/idioma.py` (novo) | `IDIOMAS`, `NOMES`, `t`, `marcar`, `definir`, `atual`, `escolhido`, `guardar`, `conferir` | 2 |
| `sigft/app/idiomas/es.json`, `en.json` (novos) | as traduções (`{"texto pt": "tradução"}`) | 2, 4 a 9 |
| `tools/textos_da_interface.py` (novo) | chaves do código, faltando/sobrando, `t(f"...")`, literais soltos, `--arrumar` | 2 |
| `SIG-FT.spec` | catálogos no pacote; `qtbase_es.qm` | 2, 3 |
| `sigft/app/conferencia.py` | confere `qtbase_pt_BR` e `qtbase_es` | 3 |
| `sigft/app_qt/escolha_de_idioma.py` (novo) | a caixa "Idioma / Language" da primeira abertura | 3 |
| `sigft/app_qt/reinicio.py` (novo) | "Reiniciar agora": abre outra instância e fecha esta | 3 |
| `tests/conftest.py` | português por padrão; sem pergunta de idioma nem reinício nos testes | 2, 3, 10 |
| `tests/_idioma.py` (novo) | `em_idioma`, `textos_visiveis`, `ainda_em_portugues` | 2 |
| `tests/test_textos_da_interface.py` (novo) | ferramenta, catálogos, guarda (`CONVERTIDOS`, `NAO_E_INTERFACE`) | 2, 4 a 9 |
| `tests/test_qt_idioma_telas.py` (novo) | cada grupo convertido em es/en: nada sobra em português | 4 a 9 |
| `sigft/app_qt/widgets/*.py`, `sigft/app/textos_*.py`, `resumo_lote.py` | literais em `t()` | 4 |
| `main.py`, `catalogo.py`, `home.py`, `configuracao.py`, `nome.py`, `aviso_windows.py`, `atualizacao.py`, `novidades.py`, `pasta_de_logs.py`, `views/nao_migrada.py`, `escolha_de_idioma.py`, `reinicio.py`, `sigft/app/atualizacao_textos.py` | literais em `t()` | 5 |
| as 12 telas e `views/janelas.py`, `_upload_comum.py`, `lmr.py`, `apagar_lmr.py` | literais em `t()` | 6 a 9 |
| `sigft/app_qt/letra.py` | largura fixa alarga também fora do português | 10 |
| `tests/_varredura.py` (novo), `tests/test_qt_idioma_varredura.py` (novo) | as 12 telas em es/en sem corte nem rolagem lateral | 10 |
| `CHANGELOG.md`, `docs/base-conhecimento/00-frontend.md`, `CLAUDE.md`, `docs/refatoracao/PENDENCIAS.md` | fechamento | 11 |

Ordem: 1 engrenagem (Parte A); 2 infraestrutura do idioma; 3 primeira abertura, seção
Idioma e reinício; 4 e 5 textos compartilhados (peças e casca); 6 a 9 as telas, de três em
três; 10 medidas; 11 fechamento e PR. Tudo no mesmo PR, nenhuma tarefa vai à branch oficial
antes das outras.

---

## Glossário e estilo das traduções (vale para as Tasks 4 a 9)

Quem implementa cada tarefa escreve as traduções `es` e `en` das chaves novas, seguindo
isto. O Jonathan revisa o espanhol antes do Release (a spec prevê).

**Não se traduzem** (ficam iguais nos três idiomas; os que aparecem sozinhos num literal estão
em `idioma.NAO_SE_TRADUZ`): SIG-FT, PMIB, Portal PMIB, PDM, SAM-GM, STATUS_PMIB,
_STATUS_PMIB, LMR, TAG/TAGs, AutoSpec, AutoSpec AI (RAG), Analyzer, PMIB Manager, Search,
Gestão PMIB (nome de módulo), Excel, PDF, JSON, RDS-PP, Aconex, DocManager, Box, GE Vernova,
Itaipu, Gemini, OpenRouter, LlamaCloud, Google, API, RAG, rc, Ctrl+K, Windows, OK, os nomes
dos idiomas (Español, Português, English), código de ficha (`4500063671.1234`), nome de
arquivo e de pasta.

**Termos fixos:**

| pt | es | en |
|---|---|---|
| ficha (técnica) | ficha (técnica) | (technical) sheet |
| planilha | planilla | spreadsheet |
| robô | robot | robot |
| portal | portal | portal |
| característica técnica | característica técnica | technical characteristic |
| condições | condiciones | conditions |
| lote | lote | batch |
| console | consola | console |
| aviso / erro | aviso / error | warning / error |
| atualização | actualización | update |
| versão de teste | versión de prueba | test version |
| Chaves de API | Claves de API | API keys |
| Modelos de IA | Modelos de IA | AI models |
| Gastos de IA | Gastos de IA | AI costs |
| IA | IA | AI |
| fornecedor | proveedor | supplier |
| código do projeto | código del proyecto | project code |
| mapeamento | mapeo | mapping |
| duplicada | duplicada | duplicate |
| aplicação (TAG) | aplicación | application |
| pasta | carpeta | folder |
| arquivo | archivo | file |
| tela | pantalla | screen |
| Home | Inicio | Home |
| Configuração | Configuración | Settings |
| Escuro / Claro / Sistema | Oscuro / Claro / Sistema | Dark / Light / System |
| Letra Normal / Grande | Normal / Grande | Normal / Large |
| Salvar / Selecionar / Buscar | Guardar / Seleccionar / Buscar | Save / Select / Search |
| Bom dia / Boa tarde / Boa noite | Buenos días / Buenas tardes / Buenas noches | Good morning / Good afternoon / Good evening |

**Estilo:** espanhol com "usted" (imperativo formal: "Seleccione", "Cierre el archivo");
inglês com imperativo simples ("Select", "Close the file"). Mesma caixa do original (botão em
MAIÚSCULAS continua em maiúsculas: "PARAR AGORA" → "DETENER AHORA" / "STOP NOW"). Mantêm-se
iguais ao original: os `{valores}` (mesmos nomes; a ferramenta confere), as quebras `\n`, o
`:` e o `...` do fim, os números e as siglas. **Curto:** botão e rótulo de uma linha com no
máximo uns 20% a mais que o português; se a varredura da Task 10 acusar corte, encurte a
tradução antes de mexer em layout. Reticências com três pontos ASCII, nunca `…`.

**Catálogo:** `sigft/app/idiomas/<codigo>.json`, objeto JSON com as chaves em ordem,
`indent=2`, sem escapar acento, linha final. Depois de editar, rode
`.venv/bin/python tools/textos_da_interface.py --arrumar` (reescreve os dois na forma certa).

## Regras de conversão (vale para as Tasks 4 a 9)

1. **Literal na montagem:** `QLabel("Pasta de Saída")` → `QLabel(t("Pasta de Saída"))`. O
   import é `from sigft.app.idioma import marcar, t` (só o que o arquivo usa: ruff F401).
2. **Constante de módulo ou de classe:** `TEXTO_X = "Copiar"` → `TEXTO_X = marcar("Copiar")`;
   cada lugar que a põe na tela ganha `t(TEXTO_X)`. Os testes que comparam
   `botao.text() == mod.TEXTO_X` continuam valendo (rodam em português). Dicionário de
   textos (`ROTULOS_TAREFA_IA`, `TEXTOS_TRAVADOS`, `DICAS`): cada valor em `marcar(...)`.
3. **f-string:** `f"Selecionado: {nome_arquivo}"` → `t("Selecionado: {nome}", nome=nome_arquivo)`.
   Formatação de número sai antes: `f"Concluído em {s:.1f}s"` →
   `t("Concluído em {segundos}s", segundos=f"{s:.1f}")`. Plural feito por concatenação vira
   frase inteira (`t("{n} erro", n=n)` / `t("{n} erros", n=n)`).
4. **Frase montada com pedaços** (`inicio + ", mas " + ...`): vira uma chave com valores
   (`t("{inicio}, mas {partes}.", inicio=..., partes=...)`).
5. **Texto que é mostrado E comparado** (a opção "Usar o global" de um menu, o cabeçalho de
   coluna que é chave do dicionário de larguras): `t()` nos dois lugares, ou separe a chave
   interna do rótulo mostrado. Nunca compare o texto traduzido com o literal cru.
6. **Fica em português (dado, não interface):** cabeçalho e aba de planilha que o código lê
   ou grava (`"CÓDIGO PMIB"`, `"Lista de Materiais"`), valor do portal, status gravado na
   planilha (`"VERIFICAR (PULADO)"`), relatório do `--smoke`, nome de fonte, o que vai ao
   console (`self.log`, `print`). Cada um desses literais que a guarda acusar entra em
   `NAO_E_INTERFACE[arquivo]` em `tests/test_textos_da_interface.py`, num bloco com o motivo.
7. **Parâmetro com texto padrão** (`titulo: str = "Seleção"`) → `titulo: str | None = None` e,
   dentro, `titulo if titulo is not None else t("Seleção")`. Quem chama passa já traduzido.
8. **Variável local chamada `t`** num arquivo convertido (`for t in ...`) é renomeada: ela
   esconderia a função (ruff F402 acusa).
9. **Mensagem que vem do serviço** (o `pausar_e_esperar(msg)` do callback, o
   `ultimo_erro`): fica como veio. Só a escolhida pela tela (`MSG_LOGIN_*`) ganha `t()`.

---

### Task 1: A engrenagem (janela Configuração)

**Files:**
- Create: `sigft/app_qt/views/configuracao.py`
- Modify: `sigft/app_qt/catalogo.py` (as ações da Home e do Ctrl+K; `SECOES_DA_CONFIGURACAO`)
- Modify: `sigft/app_qt/views/home.py` (título com a engrenagem; sai o que mudou de lugar)
- Modify: `sigft/app_qt/main.py:139-141` (`ACAO_NA_HOME`)
- Modify: `sigft/app/textos_dicas.py` (`"HomeView"`, `"JanelaConfiguracao"`, `DICAS_DA_BARRA_DA_HOME`)
- Create: `tests/test_qt_configuracao.py`
- Modify (testes que olhavam a Home): `tests/test_qt_home.py`, `tests/test_qt_home_paineis.py`,
  `tests/test_qt_tema.py`, `tests/test_qt_letra.py`, `tests/test_qt_paleta.py`,
  `tests/test_qt_aviso_windows.py`, `tests/test_qt_dicas.py`, `tests/test_qt_nome.py`,
  `tests/test_qt_estilo_controles.py`

**Interfaces:**
- Produces: `catalogo.ACOES_DA_HOME` (só `atividades` e `gastos`), `catalogo.ACAO_CONFIGURACAO`
  (`AcaoDaHome("configuracao", "Configuração", "settings", "fantasma", "abrir_configuracao", ...)`),
  `catalogo.ACOES_DA_CONFIGURACAO` (`modelos`, `chaves`, `atualizacoes`),
  `catalogo.ACOES_QUE_A_HOME_FAZ`, `catalogo.SECOES_DA_CONFIGURACAO: tuple[tuple[str, str], ...]`.
- Produces: `HomeView.abrir_configuracao() -> JanelaConfiguracao`, `HomeView.btn_configuracao`,
  `HomeView.escolher_tema(escolha) -> str`, `HomeView.escolher_letra(escolha)`,
  `HomeView.procurar_atualizacoes(botao=None)`, `home.LADO_ENGRENAGEM = 36`.
- Produces: `configuracao.JanelaConfiguracao(home)` com `secoes: dict[str, QLabel]`,
  `botoes_tema`, `botoes_letra`, `campo_nome`, `caixa_avisos_windows`, `btn_modelos`,
  `btn_chaves`, `caixa_canal_testes`, `btn_atualizacoes`, `marcar_tema(escolha)`,
  `marcar_letra(escolha)`; constantes `TITULO`, `TEXTO_AVISOS_WINDOWS`, `DICA_AVISOS_WINDOWS`,
  `TEXTO_CANAL_TESTES`, `ACAO`. A seção de idioma entra na Task 3 (`_secao_idioma`).

Decisões desta tarefa (spec ambígua):
- A janela é uma `JanelaPainel` (como os painéis da Home), não um `QDialog`: o `QDialog` não
  tem minimizar no Windows (`painel_janela.py`). Continua não modal, uma só aberta, "Fechar"
  no rodapé.
- O botão de atualização na janela diz "Procurar atualizações" (a spec); como o texto mora em
  `catalogo.ACOES_DA_CONFIGURACAO`, o Ctrl+K passa a dizer o mesmo.
- O Ctrl+K "Atualizações" procura sem botão para pôr "Procurando..." (`procurar_atualizacoes()`
  sem argumento): o aviso de resultado (`atualizacao.procurar_agora`) aparece igual.
- A Home perde a linha de baixo da barra (`_linha_sob_a_barra`, `_arrumar_barra`): com dois
  botões na barra, a letra grande não precisa mais descer a caixa.

- [ ] **Step 1: o teste da janela (`tests/test_qt_configuracao.py`)**

```python
"""A janela Configuração, a engrenagem da Home (2026-10-22).

Tudo o que se ajusta no SIG-FT saiu da Home para esta janela: aparência (tema e
letra), seu nome, avisos do Windows, inteligência artificial (chaves e modelos) e
atualizações. Cada controle faz o MESMO que o da Home fazia.
"""
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QPushButton

from sigft.app import tokens
from sigft.app_qt import aviso_windows, catalogo, estilo, letra, nome, tema
from sigft.app_qt.views import configuracao as config_mod
from sigft.app_qt.views import home as home_mod
from sigft.services import updater


class Controller:
    api_keys: dict = {}

    def get_key(self, _chave):
        return ""

    def save_keys(self, _novas):
        pass

    def show_frame(self, _nome):
        pass


@pytest.fixture
def prefs(tmp_path, monkeypatch):
    arquivo = tmp_path / "p.json"
    for modulo in (tema, letra, aviso_windows):
        monkeypatch.setattr(modulo, "_arquivo_de_prefs", lambda: arquivo)
    monkeypatch.setattr(updater, "canal_testes_ligado", lambda **_k: False)
    return arquivo


@pytest.fixture
def home(qt_interface, qtbot, prefs):
    folha, atual = qt_interface.styleSheet(), estilo.TEMA_ATUAL
    tela = home_mod.HomeView(controller=Controller())
    qtbot.addWidget(tela)
    yield tela
    letra.aplicar(qt_interface, "normal", gravar=False)
    estilo.TEMA_ATUAL = atual
    qt_interface.setStyleSheet(folha)


def _visiveis(janela):
    return [j for j in janela.parent().findChildren(config_mod.JanelaConfiguracao) if j.isVisible()]


def test_a_engrenagem_abre_a_janela_e_o_segundo_clique_traz_a_mesma(home, qtbot):
    home.show()
    qtbot.mouseClick(home.btn_configuracao, Qt.MouseButton.LeftButton)
    janela = home._janelas["configuracao"]
    assert isinstance(janela, config_mod.JanelaConfiguracao)
    assert janela.isVisible() and janela.windowTitle() == "Configuração"
    assert janela.windowModality() == Qt.WindowModality.NonModal
    qtbot.mouseClick(home.btn_configuracao, Qt.MouseButton.LeftButton)
    assert _visiveis(janela) == [janela]
    janela.close()
    # Fechada, a próxima nasce de novo, com o que vale agora (como os painéis).
    assert home.abrir_configuracao() is not janela


@pytest.mark.parametrize("nome_tema", ["escuro", "claro"])
@pytest.mark.parametrize("escolha", ["normal", "grande"])
def test_a_engrenagem_fica_a_direita_do_titulo_sem_alargar_a_home(home, qtbot, escolha, nome_tema):
    estilo.TEMA_ATUAL = nome_tema          # a folha que a letra aplica sai neste tema
    letra.aplicar(QApplication.instance(), escolha, gravar=False)
    home.resize(1280 - estilo.LARGURA_BARRA_LATERAL, 850)
    home.show()
    qtbot.waitExposed(home)
    corpo = home.widget()
    qtbot.waitUntil(lambda: corpo.width() == home.viewport().width(), timeout=1000)
    qtbot.waitUntil(lambda: not home.horizontalScrollBar().isVisible(), timeout=1000)
    titulo = home.label_titulo.geometry()
    engrenagem = home.btn_configuracao
    topo = engrenagem.mapTo(corpo, QPoint(0, 0))
    assert topo.y() >= titulo.y() and topo.y() + engrenagem.height() <= titulo.y() + titulo.height()
    assert topo.x() + engrenagem.width() == corpo.width() - 57
    assert engrenagem.property("icone") == "settings" and not engrenagem.icon().isNull()
    assert engrenagem.property("variante") == "fantasma"
    assert engrenagem.toolTip() == "Configuração"
    if escolha == "normal":
        assert (titulo.x(), titulo.y(), titulo.height()) == (46, 46, 38)


def test_as_secoes_na_ordem_da_spec(home):
    janela = home.abrir_configuracao()
    assert list(janela.secoes) == [chave for chave, _titulo in catalogo.SECOES_DA_CONFIGURACAO]
    assert [r.text() for r in janela.secoes.values()] == \
        [titulo for _chave, titulo in catalogo.SECOES_DA_CONFIGURACAO]


def test_tema_muda_na_hora_e_fica_lembrado(home):
    janela = home.abrir_configuracao()
    assert set(janela.botoes_tema) == set(tema.TEMAS)
    assert janela.botoes_tema["escuro"].property("ativo") is True
    janela.botoes_tema["claro"].click()
    assert estilo.TEMA_ATUAL == "claro" and tema.escolhido() == "claro"
    assert janela.botoes_tema["claro"].property("ativo") is True
    assert janela.botoes_tema["escuro"].property("ativo") is False


def test_tema_de_fora_marca_a_janela_aberta(home):
    # O Ctrl+K chama `HomeView.escolher_tema`: a janela aberta acompanha.
    janela = home.abrir_configuracao()
    home.escolher_tema("sistema")
    assert janela.botoes_tema["sistema"].property("ativo") is True
    assert janela.botoes_tema["escuro"].property("ativo") is False


def test_letra_muda_na_hora_e_fica_lembrada(home):
    janela = home.abrir_configuracao()
    assert janela.botoes_letra["normal"].property("ativo") is True
    janela.botoes_letra["grande"].click()
    assert estilo.AUMENTO_LETRA == tokens.AUMENTO_DA_LETRA["grande"]
    assert letra.escolhido() == "grande"
    assert janela.botoes_letra["grande"].property("ativo") is True
    letra.aplicar(QApplication.instance(), "normal", gravar=False)   # de fora (Ctrl+K)
    assert janela.botoes_letra["normal"].property("ativo") is True


def test_seu_nome_guarda_e_a_saudacao_muda_na_hora(home):
    janela = home.abrir_configuracao()
    janela.campo_nome.setText("  Ana  ")
    janela.campo_nome.editingFinished.emit()
    assert nome.guardado() == "Ana"
    assert home.label_titulo.text().endswith(", Ana")
    janela.campo_nome.setText("")
    janela.campo_nome.editingFinished.emit()
    assert nome.guardado() == ""
    assert "," not in home.label_titulo.text()


def test_aviso_do_windows_liga_e_desliga(home):
    janela = home.abrir_configuracao()
    caixa = janela.caixa_avisos_windows
    assert caixa.text() == config_mod.TEXTO_AVISOS_WINDOWS
    assert caixa.isChecked()
    caixa.click()
    assert aviso_windows.ligado() is False


def test_chaves_e_modelos_abrem_as_mesmas_janelas_da_home(home, monkeypatch):
    janela = home.abrir_configuracao()
    chamados = []
    monkeypatch.setattr(home, "abrir_janela_chaves_api", lambda: chamados.append("chaves"))
    monkeypatch.setattr(home, "abrir_janela_modelos_ia", lambda: chamados.append("modelos"))
    janela.btn_chaves.click()
    janela.btn_modelos.click()
    assert chamados == ["chaves", "modelos"]
    assert janela.btn_chaves.text() == "Chaves de API"
    assert janela.btn_modelos.text() == "Modelos de IA"


def test_versoes_de_teste_lembra(home, monkeypatch):
    escolhas = []
    monkeypatch.setattr(updater, "ligar_canal_testes", lambda ligado, **_k: escolhas.append(ligado))
    janela = home.abrir_configuracao()
    caixa = janela.caixa_canal_testes
    assert caixa.text() == config_mod.TEXTO_CANAL_TESTES
    assert not caixa.isChecked()
    caixa.click()
    assert escolhas == [True]


def test_versoes_de_teste_que_nao_se_le_fica_desmarcada(home, monkeypatch):
    def quebra(*_a, **_k):
        raise OSError("sem permissão")

    monkeypatch.setattr(updater, "canal_testes_ligado", quebra)
    monkeypatch.setattr(updater, "ligar_canal_testes", quebra)
    janela = home.abrir_configuracao()
    assert not janela.caixa_canal_testes.isChecked()
    janela.caixa_canal_testes.click()   # lembrar não pode atrapalhar o clique
    assert janela.caixa_canal_testes.isChecked()


def test_procurar_atualizacoes_pergunta_agora_e_o_botao_volta(home, monkeypatch):
    from sigft.app_qt import atualizacao

    pedidos = []
    monkeypatch.setattr(atualizacao, "procurar_agora", lambda janela, **kw: pedidos.append((janela, kw)))
    janela = home.abrir_configuracao()
    botao = janela.btn_atualizacoes
    assert botao.text() == "Procurar atualizações"
    botao.click()
    assert not botao.isEnabled(), "dois cliques seriam duas consultas"
    assert botao.text() == home_mod.TEXTO_PROCURANDO
    [(quem, kw)] = pedidos
    assert quem is home.controller, "o aviso nasce da janela principal"
    kw["ao_terminar"]()
    assert botao.isEnabled() and botao.text() == "Procurar atualizações"


def test_procurar_atualizacoes_sem_botao_e_o_do_ctrl_k(home, monkeypatch):
    from sigft.app_qt import atualizacao

    pedidos = []
    monkeypatch.setattr(atualizacao, "procurar_agora", lambda janela, **kw: pedidos.append(kw))
    home.procurar_atualizacoes()
    [kw] = pedidos
    kw["ao_terminar"]()   # sem botão: nada a devolver, e não quebra


def _cortados(janela):
    achados = []
    for w in janela.findChildren(QPushButton) + janela.findChildren(QCheckBox) + janela.findChildren(QLabel):
        if not w.isVisible() or not w.text().strip():
            continue
        if isinstance(w, QLabel) and w.wordWrap():
            continue
        if w.width() < w.sizeHint().width():
            achados.append(w.text())
    return achados


@pytest.mark.parametrize("escolha", ["normal", "grande"])
def test_nada_corta_nem_rola_de_lado(home, qtbot, escolha):
    letra.aplicar(QApplication.instance(), escolha, gravar=False)
    janela = home.abrir_configuracao()
    qtbot.waitExposed(janela)
    qtbot.waitUntil(lambda: not janela.area.horizontalScrollBar().isVisible(), timeout=1000)
    assert _cortados(janela) == []


def test_nenhum_botao_nem_caixa_pega_o_foco(home):
    # Como os da Home: um Espaço perdido não troca o tema nem fecha a janela.
    janela = home.abrir_configuracao()
    controles_ = janela.findChildren(QPushButton) + janela.findChildren(QCheckBox)
    assert len(controles_) >= 9
    for controle in controles_:
        assert controle.focusPolicy() == Qt.FocusPolicy.NoFocus, controle.text()


def test_a_home_ficou_so_com_o_que_e_dela(home):
    assert list(home.botoes_barra) == ["atividades", "gastos"]
    for saiu in ("caixa_canal_testes", "caixa_avisos_windows", "botoes_tema", "botoes_letra",
                 "btn_atualizacoes"):
        assert not hasattr(home, saiu), saiu


def test_ctrl_k_abre_a_configuracao(qt_interface, qtbot, tmp_path, monkeypatch, prefs):
    from sigft.app_qt import main as qmain

    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    principal = qmain.SIG_FT_App()
    principal.fechar_sem_perguntar = True
    qtbot.addWidget(principal)
    assert "acao:configuracao" in {c.chave for c in catalogo.comandos()}
    principal.show_frame("Translator")
    principal.executar_comando("acao:configuracao")
    janela = principal.telas["Home"]._janelas["configuracao"]
    assert janela.isVisible()
```

- [ ] **Step 2:** `.venv/bin/python -m pytest -q tests/test_qt_configuracao.py` → FAIL
  (`ModuleNotFoundError: sigft.app_qt.views.configuracao`).

- [ ] **Step 3: `catalogo.py`.** Troque o bloco de `ACOES_DA_HOME` (do comentário "As ações da
  Home NUM LUGAR SÓ" até o fecho da tupla) por:

```python
# As ações da Home NUM LUGAR SÓ (2026-10-21; a engrenagem, 2026-10-22): a barra
# da Home (`views/home.BARRA`), a janela Configuração (`views/configuracao`), o
# Ctrl+K (`ACOES`) e quem faz cada uma (`main.ACAO_NA_HOME`) saem daqui. Todas
# são métodos da `HomeView`.
ACOES_DA_HOME = (
    AcaoDaHome("atividades", "Atividades do dia", "clipboard-check", "primario",
               "abrir_mural_atividades", "mural"),
    AcaoDaHome("gastos", "Gastos de IA", "circle-dollar-sign", "primario",
               "abrir_janela_gastos_ia", "custo uso"),
)
# A engrenagem, à direita do título da Home, e o item do Ctrl+K que abre a janela.
ACAO_CONFIGURACAO = AcaoDaHome("configuracao", "Configuração", "settings", "fantasma",
                               "abrir_configuracao", "engrenagem opcoes preferencias ajustes")
# Os botões que moram na janela Configuração: saíram da barra da Home em 2026-10-22.
ACOES_DA_CONFIGURACAO = (
    AcaoDaHome("modelos", "Modelos de IA", "bot", "primario",
               "abrir_janela_modelos_ia", "ia llm provedor"),
    AcaoDaHome("chaves", "Chaves de API", "key-round", "secundario",
               "abrir_janela_chaves_api", "api key senha"),
    AcaoDaHome("atualizacoes", "Procurar atualizações", "refresh-cw", "secundario",
               "procurar_atualizacoes", "procurar versao nova atualizar"),
)
# Tudo o que a Home faz pelo Ctrl+K, na ordem da caixa.
ACOES_QUE_A_HOME_FAZ = (ACAO_CONFIGURACAO, *ACOES_DA_HOME, *ACOES_DA_CONFIGURACAO)

# As seções da janela Configuração, de cima para baixo: chave e título. A chave
# é o método que monta a seção (`JanelaConfiguracao._secao_<chave>`).
SECOES_DA_CONFIGURACAO = (
    ("aparencia", "Aparência"),
    ("nome", "Seu nome"),
    ("avisos", "Avisos"),
    ("ia", "Inteligência artificial"),
    ("atualizacoes", "Atualizações"),
)
```

  Nos comentários de `SELETOR_TEMA` e `SELETOR_LETRA`, troque "O seletor de tema da Home" por
  "O seletor de tema da janela Configuração" e "na linha do título, à direita do de tema" por
  "na seção Aparência, abaixo do de tema"; o "faz por `HomeView.escolher_*`" fica. Em `ACOES`,
  troque a linha `*((a.chave, a.texto, a.icone, a.palavras) for a in ACOES_DA_HOME),` por
  `*((a.chave, a.texto, a.icone, a.palavras) for a in ACOES_QUE_A_HOME_FAZ),`.

- [ ] **Step 4: `main.py`.** Troque o comentário e a linha de `ACAO_NA_HOME` por:

```python
# Ctrl+K (etapa 1b, 2026-10-21): o método da Home que cada `acao:` chama, das
# listas únicas de `catalogo` (a barra, a engrenagem e a janela Configuração). As
# outras ações (`inicio`, `logs`, `tema_*`, `letra_*`) estão em `executar_comando`.
ACAO_NA_HOME = {acao.chave: acao.metodo for acao in catalogo.ACOES_QUE_A_HOME_FAZ}
```

- [ ] **Step 5: `sigft/app_qt/views/configuracao.py` (novo, inteiro)**

```python
"""A janela Configuração: o que se ajusta no SIG-FT, num lugar só (2026-10-22).

Abre pela engrenagem da Home (`HomeView.abrir_configuracao`) e pelo Ctrl+K
("Configuração"). Não tem regra nova: cada controle chama a MESMA função que o
controle da Home chamava até 2026-10-21 (`tema`, `letra`, `nome`,
`aviso_windows`, `updater` e os métodos da Home que abrem Chaves de API, Modelos
de IA e a busca de versão nova). Cada mudança vale e é guardada na hora: não há
"Salvar".

É uma `JanelaPainel`, como os painéis da Home, e não um `QDialog`: no Windows o
QDialog não tem o botão de minimizar. Uma só aberta por vez (a Home guarda a
referência em `_janelas["configuracao"]`) e "Fechar" no rodapé.

Os botões de escolha guardam a escolha na propriedade `escolha` e ligam a um
MÉTODO da janela, que lê `self.sender()`: `lambda` com `self` no sinal de um
filho vaza a janela, que morre antes do app (aviso do mural de 2026-10-14).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from sigft.app_qt import aviso_windows, estilo, icones, letra, nome, tema
from sigft.app_qt.catalogo import (
    ACOES_DA_CONFIGURACAO, SECOES_DA_CONFIGURACAO, SELETOR_LETRA, SELETOR_TEMA,
)
from sigft.app_qt.widgets import blocos, controles, dialogs
from sigft.app_qt.widgets.module_frame import aplicar_dicas
from sigft.app_qt.widgets.painel_janela import JanelaPainel
from sigft.services import updater

TITULO = "Configuração"
GEOMETRIA = "720x620"
# A coluna dos títulos das seções, à esquerda.
LARGURA_TITULO_SECAO = 190
ESPACO_ENTRE_SECOES = 18
LARGURA_CAMPO_NOME = 360
TEXTO_AVISOS_WINDOWS = "Avisar no Windows quando uma tarefa terminar ou pedir algo"
DICA_AVISOS_WINDOWS = ("Com o SIG-FT atrás de outra janela, um aviso do Windows diz quando uma "
                       "tarefa termina ou quando o robô espera você (o login no portal, por exemplo).")
TEXTO_CANAL_TESTES = "Receber versões de teste"
# Os botões que vieram da barra da Home, pela chave (`catalogo.ACOES_DA_CONFIGURACAO`).
ACAO = {a.chave: a for a in ACOES_DA_CONFIGURACAO}


def _sem_conteudo(_pai) -> None:
    """O `montar` da `JanelaPainel`: o conteúdo desta janela é montado depois do
    `super().__init__`, porque usa `self`."""


class JanelaConfiguracao(JanelaPainel):
    def __init__(self, home) -> None:
        super().__init__(home, titulo=TITULO, montar=_sem_conteudo, geometria=GEOMETRIA)
        self.home = home
        # Chave da seção -> o rótulo do título dela, na ordem de `SECOES_DA_CONFIGURACAO`.
        self.secoes: dict = {}
        quadro = QFrame(objectName="painel_home")
        grade = QGridLayout(quadro)
        grade.setContentsMargins(16, 16, 16, 16)
        grade.setHorizontalSpacing(16)
        grade.setVerticalSpacing(ESPACO_ENTRE_SECOES)
        grade.setColumnMinimumWidth(0, LARGURA_TITULO_SECAO)
        grade.setColumnStretch(1, 1)
        for linha, (chave, titulo) in enumerate(SECOES_DA_CONFIGURACAO):
            rotulo = blocos.rotulo(titulo, tamanho=15, negrito=True, papel="destaque",
                                   alinhar="esquerda")
            rotulo.setWordWrap(False)
            self.secoes[chave] = rotulo
            grade.addWidget(rotulo, linha, 0, Qt.AlignmentFlag.AlignTop)
            grade.addWidget(getattr(self, f"_secao_{chave}")(), linha, 1, Qt.AlignmentFlag.AlignTop)
        self._layout_conteudo.addWidget(quadro)
        aplicar_dicas(self)

    # --- peças ----------------------------------------------------------------------
    @staticmethod
    def _coluna(espaco: int = 8) -> tuple[QWidget, QVBoxLayout]:
        caixa = QWidget()
        coluna = QVBoxLayout(caixa)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(espaco)
        return caixa, coluna

    @staticmethod
    def _seletor(nome_do_quadro: str) -> tuple[QFrame, QHBoxLayout]:
        """O quadro dos botões de escolha; a folha pinta o `ativo` por objectName."""
        quadro = QFrame(objectName=nome_do_quadro)
        linha = QHBoxLayout(quadro)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(4)
        return quadro, linha

    @staticmethod
    def _botao_de_escolha(texto: str, escolha: str, dica: str = ""):
        botao = blocos.botao(texto, variante="secundario", tamanho_fonte=12)
        botao.setProperty("escolha", escolha)
        if dica:
            botao.setToolTip(dica)
        dialogs.sem_tecla(botao)
        return botao

    @staticmethod
    def _botao_de_acao(chave: str):
        acao = ACAO[chave]
        botao = blocos.botao(acao.texto, variante=acao.variante, altura=32,
                             largura_minima=estilo.LARGURA_BOTAO_CTK)
        icones.aplicar(botao, acao.icone)
        dialogs.sem_tecla(botao)
        return botao

    # --- Aparência --------------------------------------------------------------
    def _secao_aparencia(self) -> QWidget:
        caixa, coluna = self._coluna()
        coluna.addWidget(self._seletor_tema())
        coluna.addWidget(self._seletor_letra())
        return caixa

    def _seletor_tema(self) -> QFrame:
        quadro, linha = self._seletor("seletor_tema")
        self.botoes_tema = {}
        for escolha, texto, icone, dica in SELETOR_TEMA:
            botao = self._botao_de_escolha(texto, escolha, dica)
            icones.aplicar(botao, icone, papel_cor_ativo=estilo.PAPEL_MENU_ESCOLHIDO, tamanho=16)
            botao.clicked.connect(self._clicou_tema)
            self.botoes_tema[escolha] = botao
            linha.addWidget(botao)
        linha.addStretch()
        self.marcar_tema(tema.escolhido())
        return quadro

    def _clicou_tema(self) -> None:
        # Pela Home, que aplica e marca esta janela (`HomeView.escolher_tema`).
        self.home.escolher_tema(self.sender().property("escolha"))

    def marcar_tema(self, escolha: str) -> None:
        """Marca o tema que VALEU, não o das prefs: gravar pode ter falhado."""
        for chave, botao in self.botoes_tema.items():
            estilo.definir_propriedade(botao, "ativo", chave == escolha)
            icones.reaplicar(botao)

    def _seletor_letra(self) -> QFrame:
        quadro, linha = self._seletor("seletor_letra")
        self.botoes_letra = {}
        for escolha, texto, dica in SELETOR_LETRA:
            botao = self._botao_de_escolha(texto, escolha, dica)
            botao.clicked.connect(self._clicou_letra)
            self.botoes_letra[escolha] = botao
            linha.addWidget(botao)
        linha.addStretch()
        self.marcar_letra(letra.atual())
        # A troca pode vir de fora (o Ctrl+K): o aviso marca o seletor. Método
        # ligado: o Qt desliga sozinho quando a janela morre.
        letra.mudou.connect(self.marcar_letra)
        return quadro

    def _clicou_letra(self) -> None:
        self.home.escolher_letra(self.sender().property("escolha"))

    def marcar_letra(self, escolha: str) -> None:
        for chave, botao in self.botoes_letra.items():
            estilo.definir_propriedade(botao, "ativo", chave == escolha)

    # --- Seu nome ---------------------------------------------------------------
    def _secao_nome(self) -> QWidget:
        # O nome só aparece na saudação da Home (`nome.py`): nunca vai para log.
        self.campo_nome = QLineEdit(nome.guardado())
        self.campo_nome.setMaxLength(nome.LIMITE)
        self.campo_nome.setPlaceholderText(nome.TITULO)
        self.campo_nome.setMaximumWidth(LARGURA_CAMPO_NOME)
        self.campo_nome.editingFinished.connect(self._guardar_nome)
        return self.campo_nome

    def _guardar_nome(self) -> None:
        """Sair do campo ou Enter: guarda (vazio tira o nome) e a Home refaz a saudação."""
        nome.guardar(self.campo_nome.text())
        self.home.atualizar_saudacao()

    # --- Avisos -----------------------------------------------------------------
    def _secao_avisos(self) -> QWidget:
        caixa = controles.CaixaDeMarcar(TEXTO_AVISOS_WINDOWS, tamanho_fonte=12)
        caixa.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        caixa.setChecked(aviso_windows.ligado())
        caixa.setToolTip(DICA_AVISOS_WINDOWS)
        caixa.toggled.connect(aviso_windows.ligar)
        self.caixa_avisos_windows = caixa
        return caixa

    # --- Inteligência artificial ------------------------------------------------
    def _secao_ia(self) -> QWidget:
        caixa = QWidget()
        linha = QHBoxLayout(caixa)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(10)
        self.btn_modelos = self._botao_de_acao("modelos")
        self.btn_modelos.clicked.connect(self._abrir_modelos)
        self.btn_chaves = self._botao_de_acao("chaves")
        self.btn_chaves.clicked.connect(self._abrir_chaves)
        linha.addWidget(self.btn_modelos)
        linha.addWidget(self.btn_chaves)
        linha.addStretch()
        return caixa

    def _abrir_modelos(self) -> None:
        self.home.abrir_janela_modelos_ia()

    def _abrir_chaves(self) -> None:
        self.home.abrir_janela_chaves_api()

    # --- Atualizações -------------------------------------------------------------
    def _secao_atualizacoes(self) -> QWidget:
        caixa, coluna = self._coluna()
        self.caixa_canal_testes = controles.CaixaDeMarcar(TEXTO_CANAL_TESTES, tamanho_fonte=12)
        self.caixa_canal_testes.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        try:
            ligado = updater.canal_testes_ligado()
        except Exception:  # noqa: BLE001 -- preferência é conveniência
            ligado = False
        self.caixa_canal_testes.setChecked(bool(ligado))
        self.caixa_canal_testes.toggled.connect(self._lembrar_canal_testes)
        coluna.addWidget(self.caixa_canal_testes)
        self.btn_atualizacoes = self._botao_de_acao("atualizacoes")
        self.btn_atualizacoes.clicked.connect(self._procurar_atualizacoes)
        coluna.addWidget(self.btn_atualizacoes, 0, Qt.AlignmentFlag.AlignLeft)
        return caixa

    @staticmethod
    def _lembrar_canal_testes(ligado: bool) -> None:
        try:
            updater.ligar_canal_testes(bool(ligado))
        except Exception:  # noqa: BLE001 -- lembrar não pode atrapalhar o clique
            pass

    def _procurar_atualizacoes(self) -> None:
        self.home.procurar_atualizacoes(self.btn_atualizacoes)
```

- [ ] **Step 6: `home.py`, o cabeçalho.** No import de `catalogo`, troque
  `ACOES_DA_HOME, ICONE_DA_TELA, MODULOS, SELETOR_LETRA, SELETOR_TEMA` por
  `ACAO_CONFIGURACAO, ACOES_DA_CONFIGURACAO, ACOES_DA_HOME, ICONE_DA_TELA, MODULOS`. No import
  de `sigft.app_qt`, tire `aviso_windows` (a caixa saiu). Tire `from sigft.services import updater`
  se nenhum uso sobrar (ruff F401 diz). Troque o bloco de constantes de `# A barra e o seletor
  de tema saem de catalogo` até o comentário `# O seletor de tema (2026-10-20)...` (inclusive as
  três linhas dele) por:

```python
# A barra e a engrenagem saem de `catalogo` (2026-10-21; a engrenagem, 2026-10-22):
# as ações da Home moram num lugar só (`catalogo.ACOES_DA_HOME`, `ACAO_CONFIGURACAO`
# e `ACOES_DA_CONFIGURACAO`), de onde saem também o Ctrl+K e o `main.ACAO_NA_HOME`.
_ATUALIZACOES = next(a for a in ACOES_DA_CONFIGURACAO if a.chave == "atualizacoes")
# O texto do botão que procura versão nova (na janela Configuração desde
# 2026-10-22). Constante porque dois lugares precisam concordar: quem o põe em
# "Procurando..." e quem o devolve (`HomeView.procurar_atualizacoes`).
TEXTO_BOTAO_ATUALIZACOES = _ATUALIZACOES.texto
TEXTO_PROCURANDO = "Procurando..."

# A barra (`_criar_barra_de_botoes` de lá): chave, texto, variante do botão e o que
# abre. A cor de cada um é a da variante, na folha do tema. Desde 2026-10-22 só
# "Atividades do dia" e "Gastos de IA": o resto foi para a janela Configuração.
BARRA = [(a.chave, a.texto, a.variante, a.metodo) for a in ACOES_DA_HOME]
# O ícone de cada botão da barra (Lucide, `sigft/app_qt/icones.py`).
ICONE_DA_BARRA = {a.chave: a.icone for a in ACOES_DA_HOME}
# A engrenagem (2026-10-22): quadrada, só o ícone, à direita do título.
LADO_ENGRENAGEM = 36
TAMANHO_ICONE_ENGRENAGEM = 20
```

- [ ] **Step 7: `home.py`, o `__init__`.** Troque as linhas da `linha_titulo` até
  `layout.addSpacing(30)` (o título, os seletores, o subtítulo e a caixa de avisos) por:

```python
        linha_titulo = QHBoxLayout()
        linha_titulo.setSpacing(0)
        linha_titulo.addWidget(self.label_titulo, 1)
        linha_titulo.addWidget(self._criar_engrenagem(), 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(linha_titulo)
        layout.addSpacing(5)
        self.label_subtitulo = QLabel("Sistema Integrado de Gestão de Fichas Técnicas - GE Vernova",
                                      objectName="subtitulo_home")
        self.label_subtitulo.setMinimumHeight(blocos.ALTURA_MINIMA_ROTULO)
        self.label_subtitulo.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.label_subtitulo)
        layout.addSpacing(30)
```

  E apague as três linhas `# [2026-10-21] A linha de baixo da barra...`,
  `# letra normal; com a grande...` e `layout.addLayout(self._linha_sob_a_barra)`.

- [ ] **Step 8: `home.py`, a barra e os métodos.** Troque `_aplicar_dicas`,
  `_criar_barra_de_botoes` e `_arrumar_barra` por:

```python
    def _aplicar_dicas(self) -> None:
        """As dicas de `sigft/app/textos_dicas.py`. Chamada de novo a cada
        painel aberto: os botões dele só existem depois de montado."""
        aplicar_dicas(self)
        for chave, botao in self.botoes_barra.items():
            dica = textos_dicas.DICAS_DA_BARRA_DA_HOME.get(chave)
            if dica and not botao.toolTip():
                botao.setToolTip(dica)

    # =====================================================================
    # BARRA DE BOTÕES  [2026-09-03; 2026-10-22: só atividades e gastos]
    # =====================================================================
    def _criar_barra_de_botoes(self) -> QHBoxLayout:
        barra = QHBoxLayout()
        barra.setSpacing(0)
        self.botoes_barra = {}
        for chave, texto, variante, metodo in BARRA:
            botao = self._botao_da_barra(texto, variante, ICONE_DA_BARRA[chave])
            botao.clicked.connect(lambda _=False, m=metodo: getattr(self, m)())
            self.botoes_barra[chave] = botao
            barra.addWidget(botao)
            barra.addSpacing(10)                        # pack(side="left", padx=(0, 10))
        barra.addStretch()
        return barra

    # =====================================================================
    # ENGRENAGEM  [2026-10-22]
    # =====================================================================
    def _criar_engrenagem(self):
        """A engrenagem: abre a janela Configuração. Botão fantasma quadrado, só
        o ícone; o nome vai na dica e no nome acessível (leitor de tela)."""
        botao = blocos.botao("", variante=ACAO_CONFIGURACAO.variante, largura=LADO_ENGRENAGEM,
                             altura=LADO_ENGRENAGEM)
        icones.aplicar(botao, ACAO_CONFIGURACAO.icone, tamanho=TAMANHO_ICONE_ENGRENAGEM)
        botao.setToolTip(ACAO_CONFIGURACAO.texto)
        botao.setAccessibleName(ACAO_CONFIGURACAO.texto)
        dialogs.sem_tecla(botao)
        botao.clicked.connect(self.abrir_configuracao)
        self.btn_configuracao = botao
        return botao

    def abrir_configuracao(self):
        """A janela Configuração (a engrenagem e o Ctrl+K); aberta, vem para a frente.
        Fechada (só escondida), dá lugar a uma nova, com o que vale agora."""
        aberta = self._trazer_para_frente("configuracao")
        if aberta is not None:
            return aberta
        velha = self._janelas.pop("configuracao", None)
        if _vivo(velha):
            velha.deleteLater()
        from sigft.app_qt.views.configuracao import JanelaConfiguracao

        janela = JanelaConfiguracao(self)
        self._janelas["configuracao"] = janela
        return janela

    def _configuracao_viva(self):
        janela = self._janelas.get("configuracao")
        return janela if _vivo(janela) else None
```

  Apague os métodos `_criar_seletor_tema`, `_marcar_tema`, `_criar_seletor_letra`,
  `_marcar_letra`, `_letra_mudou`, `_criar_caixa_avisos` e `_lembrar_canal_testes`. Troque
  `escolher_tema`, `escolher_letra` e `procurar_atualizacoes` por:

```python
    def escolher_tema(self, escolha: str) -> str:
        """Troca o tema do app inteiro e lembra a escolha (`tema.aplicar`). A janela
        Configuração, se existe, marca o que VALEU (gravar pode ter falhado)."""
        valeu = tema.aplicar(QApplication.instance(), escolha)
        if (janela := self._configuracao_viva()) is not None:
            janela.marcar_tema(valeu)
        return valeu

    def escolher_letra(self, escolha: str) -> None:
        """Troca a letra do app inteiro e lembra a escolha (`letra.aplicar`); o
        `letra.mudou` marca o seletor da janela Configuração."""
        letra.aplicar(QApplication.instance(), escolha)

    def procurar_atualizacoes(self, botao=None) -> None:
        """Pergunta ao GitHub agora e SEMPRE responde (ver `app_qt/atualizacao.py`).
        `botao` é o da janela Configuração, que fica em "Procurando..." até a
        resposta; o Ctrl+K chama sem botão."""
        if botao is not None:
            botao.setEnabled(False)
            botao.setText(TEXTO_PROCURANDO)

        def ao_terminar():
            if _vivo(botao):
                botao.setEnabled(True)
                botao.setText(TEXTO_BOTAO_ATUALIZACOES)

        atualizacao.procurar_agora(self.controller, ao_terminar=ao_terminar)
```

  No docstring do módulo e no comentário do `__init__` que citam o seletor de tema, troque a
  menção por "a engrenagem (janela Configuração)".

- [ ] **Step 9: `textos_dicas.py`.** Em `DICAS["HomeView"]` apague a linha `"btn_atualizacoes": ...`.
  Logo depois do bloco `"HomeView"`, acrescente:

```python
    # A janela Configuração (2026-10-22): os botões que vieram da barra da Home.
    "JanelaConfiguracao": {
        "btn_modelos": "Escolhe qual modelo de IA cada módulo usa.",
        "btn_chaves": "Cadastra as chaves de API (Gemini, OpenRouter, busca na web).",
        "caixa_canal_testes": "Marcado, o aviso de atualização oferece também as versões de teste (rc).",
        "btn_atualizacoes": "Pergunta agora se há versão nova do SIG-FT.",
    },
```

  E troque `DICAS_DA_BARRA_DA_HOME` por:

```python
# Os botões da barra da Home, pela CHAVE de `home.BARRA`.
DICAS_DA_BARRA_DA_HOME: dict[str, str] = {
    "atividades": "Mostra o que cada pessoa tem para fazer hoje, lido da planilha de mapeamento.",
    "gastos": "Mostra quanto se gastou com IA neste computador.",
}
```

- [ ] **Step 10:** `.venv/bin/python -m pytest -q tests/test_qt_configuracao.py` → PASS.

- [ ] **Step 11: os testes que olhavam a Home.** Cada mudança abaixo vai no mesmo commit; o
  motivo de todas é o mesmo (os itens saíram da Home para a janela Configuração).

  `tests/test_qt_home.py`: apague `test_canal_de_testes_lembra_a_escolha` (coberto por
  `test_qt_configuracao.py::test_versoes_de_teste_lembra`).

  `tests/test_qt_home_paineis.py`:
  - no topo, acrescente `from sigft.app_qt.views import configuracao as config_mod`;
  - em `test_textos_iguais_aos_da_home_antiga`, troque as duas primeiras asserções por
    `assert config_mod.ACAO["atualizacoes"].texto == "Procurar atualizações"` e
    `assert config_mod.TEXTO_CANAL_TESTES == "Receber versões de teste"`;
  - `test_barra_na_ordem_e_com_as_cores_da_tela_antiga`: `esperado` passa a ter só
    `("atividades", "Atividades do dia", "primario", "clipboard-check")` e
    `("gastos", "Gastos de IA", "primario", "circle-dollar-sign")`; apague a última linha
    (`home.btn_atualizacoes is ...`);
  - apague `test_atualizacoes_pergunta_agora_e_o_botao_volta_ao_normal`,
    `test_versoes_de_teste_e_a_caixa_do_ctk_e_lembra` e
    `test_versoes_de_teste_preferencia_ilegivel_e_desmarcada` (foram para `test_qt_configuracao.py`);
  - troque `test_cada_botao_abre_o_seu_painel_em_janela` por:

```python
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
```

  - `test_nenhum_controle_dos_paineis_pega_o_foco`: troque
    `controles_ = [home.caixa_canal_testes, *home.botoes_barra.values()]` por
    `controles_ = [home.btn_configuracao, *home.botoes_barra.values()]` e acrescente
    `home.abrir_configuracao()` à lista `janelas`;
  - `test_medidas_da_home`: no comentário, troque "caixa y 193 h 24" por "a engrenagem à
    direita do título (2026-10-22: tema, letra e a caixa saíram da Home)"; troque as três
    linhas da `caixa` por:

```python
    engrenagem = _geo(tela.btn_configuracao, corpo)
    assert engrenagem[0] + engrenagem[2] == corpo.width() - 57
    assert 46 <= engrenagem[1] and engrenagem[1] + engrenagem[3] <= 46 + 38
```

  `tests/test_qt_tema.py`: troque `test_home_tem_o_seletor_de_tema` e
  `test_clicar_claro_muda_o_fundo_da_tela` pelas versões abaixo, e apague
  `test_o_seletor_cabe_na_linha_do_titulo_sem_alargar_a_home` (coberto por
  `test_qt_configuracao.py::test_a_engrenagem_fica_a_direita_do_titulo_sem_alargar_a_home`).
  Renomeie a seção `# --- o seletor da Home ---` para `# --- o seletor da janela Configuração ---`.

```python
def test_a_configuracao_tem_o_seletor_de_tema(volta_ao_escuro, qt_interface, tmp_path, monkeypatch):
    janela = _janela(qt_interface, tmp_path, monkeypatch)
    try:
        config = janela.telas["Home"].abrir_configuracao()
        assert set(config.botoes_tema) == set(tema.TEMAS)
        icone_esperado = {"escuro": "moon", "claro": "sun", "sistema": "monitor"}
        for escolha, botao in config.botoes_tema.items():
            assert botao.property("icone") == icone_esperado[escolha]
            assert botao.toolTip()
            assert "—" not in botao.toolTip() and "–" not in botao.toolTip()
        assert config.botoes_tema["escuro"].property("ativo") is True
    finally:
        _fechar(janela)


def test_clicar_claro_muda_o_fundo_da_tela(volta_ao_escuro, qt_interface, qtbot, tmp_path, monkeypatch):
    from PySide6.QtCore import Qt

    qt_interface.setStyleSheet(estilo.folha_de_estilo("escuro"))
    estilo.TEMA_ATUAL = "escuro"
    janela = _janela(qt_interface, tmp_path, monkeypatch)
    try:
        janela.resize(1280, 850)
        janela.show()
        qtbot.waitExposed(janela)
        janela.show_frame("Translator")
        janela.show_frame("Home")
        config = janela.telas["Home"].abrir_configuracao()
        tela = janela.findChild(QWidget, "tela")
        assert tela is not None
        assert tela.palette().color(tela.backgroundRole()).name().upper() == tokens.ESCURO["fundo"]

        qtbot.mouseClick(config.botoes_tema["claro"], Qt.MouseButton.LeftButton)

        assert estilo.TEMA_ATUAL == "claro"
        assert tema.escolhido() == "claro"
        assert tela.palette().color(tela.backgroundRole()).name().upper() == tokens.CLARO["fundo"]
        assert config.botoes_tema["claro"].property("ativo") is True
        assert config.botoes_tema["escuro"].property("ativo") is False
        assert config.botoes_tema["claro"].icon().cacheKey() == \
            icones.icone("sun", estilo.MENU_ESCOLHIDO["claro"]["texto"], 16).cacheKey()
    finally:
        _fechar(janela)
```

  `tests/test_qt_letra.py`: troque `test_seletor_de_letra_num_lugar_so`,
  `test_seletor_na_home_marca_e_aplica` e `test_seletor_marca_a_letra_que_esta_valendo` pelas
  versões abaixo; apague `test_seletores_cabem_na_linha_do_titulo` e
  `test_troca_na_hora_leva_a_caixa_e_traz_de_volta` (a caixa saiu da Home; a engrenagem tem
  o seu teste de medida em `test_qt_configuracao.py`).

```python
def test_seletor_de_letra_num_lugar_so():
    # Como o de tema: a janela Configuração e o Ctrl+K saem de `catalogo.SELETOR_LETRA`.
    from sigft.app_qt.views import configuracao as config_mod

    assert config_mod.SELETOR_LETRA is catalogo.SELETOR_LETRA
    assert tuple(e for e, *_ in catalogo.SELETOR_LETRA) == letra.TAMANHOS
    na_paleta = {a[0]: a[1] for a in catalogo.ACOES}
    for escolha, texto, _dica in catalogo.SELETOR_LETRA:
        assert na_paleta[f"letra_{escolha}"] == f"Letra: {texto}"


def _configuracao(qtbot):
    from sigft.app_qt.views import home as home_mod

    tela = home_mod.HomeView(controller=Controller())
    qtbot.addWidget(tela)
    return tela.abrir_configuracao()


def test_seletor_da_configuracao_marca_e_aplica(letra_temporaria, qtbot):
    config = _configuracao(qtbot)
    assert set(config.botoes_letra) == set(letra.TAMANHOS)
    assert config.botoes_letra["normal"].property("ativo") is True
    config.botoes_letra["grande"].click()
    assert estilo.AUMENTO_LETRA == tokens.AUMENTO_DA_LETRA["grande"]
    assert config.botoes_letra["grande"].property("ativo") is True
    assert config.botoes_letra["normal"].property("ativo") is False


def test_seletor_marca_a_letra_que_esta_valendo(letra_temporaria, qtbot):
    # `--smoke --letra grande` não grava: o seletor marca a que vale, não a das prefs.
    letra.aplicar(letra_temporaria, "grande", gravar=False)
    assert letra.escolhido() == "normal" and letra.atual() == "grande"
    config = _configuracao(qtbot)
    assert config.botoes_letra["grande"].property("ativo") is True
```

  (O `Controller` de `test_qt_letra.py` só tem `api_keys`; a janela não pede mais nada dele.)

  `tests/test_qt_paleta.py`: troque `test_acoes_da_home_num_lugar_so` e
  `test_tema_pela_paleta_marca_o_seletor_da_home` por:

```python
def test_acoes_da_home_num_lugar_so():
    """A barra da Home, a janela Configuração, o Ctrl+K e quem faz cada ação saem de
    `catalogo` (`ACOES_DA_HOME`, `ACAO_CONFIGURACAO`, `ACOES_DA_CONFIGURACAO`)."""
    from sigft.app_qt.views import configuracao, home

    assert [(a.chave, a.texto, a.variante, a.metodo) for a in catalogo.ACOES_DA_HOME] == list(home.BARRA)
    assert home.ICONE_DA_BARRA == {a.chave: a.icone for a in catalogo.ACOES_DA_HOME}
    assert configuracao.ACAO == {a.chave: a for a in catalogo.ACOES_DA_CONFIGURACAO}
    assert home.TEXTO_BOTAO_ATUALIZACOES == configuracao.ACAO["atualizacoes"].texto
    assert configuracao.SELETOR_TEMA is catalogo.SELETOR_TEMA
    acoes = catalogo.ACOES_QUE_A_HOME_FAZ
    assert qmain.ACAO_NA_HOME == {a.chave: a.metodo for a in acoes}
    na_paleta = {a[0]: (a[1], a[2]) for a in catalogo.ACOES}
    for a in acoes:
        assert na_paleta[a.chave] == (a.texto, a.icone)
        assert callable(getattr(home.HomeView, a.metodo))


def test_tema_pela_paleta_marca_o_seletor_da_configuracao(volta_ao_escuro, janela):
    config = janela.telas["Home"].abrir_configuracao()
    janela.executar_comando("acao:tema_claro")
    assert estilo.TEMA_ATUAL == "claro" and tema.escolhido() == "claro"
    assert config.botoes_tema["claro"].property("ativo") is True
    assert config.botoes_tema["escuro"].property("ativo") is False
```

  `tests/test_qt_aviso_windows.py`: apague `test_caixa_da_home_liga_e_desliga` (foi para
  `test_qt_configuracao.py::test_aviso_do_windows_liga_e_desliga`).

  `tests/test_qt_dicas.py`: no fixture `todas_as_telas`, depois de
  `home.abrir_janela_gastos_ia()`, acrescente `config = home.abrir_configuracao()` e, depois de
  montar `instancias`, `instancias["JanelaConfiguracao"] = config`. Em
  `test_painel_da_home_aberto_depois_tambem_ganha_dica`, troque
  `assert home.caixa_canal_testes.toolTip()` por
  `assert instancias["JanelaConfiguracao"].caixa_canal_testes.toolTip()` e acrescente
  `assert home.btn_configuracao.toolTip() == "Configuração"`.

  `tests/test_qt_nome.py`, em `test_o_nome_nao_vai_para_o_log`: `permitidos` ganha
  `"sigft/app_qt/views/configuracao.py"` (o campo "Seu nome" mostra o nome guardado; só tela).

  `tests/test_qt_estilo_controles.py`, em `test_home_e_dialogos_usam_primario_onde_o_ctk_pintava_primary`:
  troque as duas linhas do corpo por

```python
    from sigft.app_qt import catalogo
    cores = {a.chave: a.variante for a in (*catalogo.ACOES_DA_HOME, *catalogo.ACOES_DA_CONFIGURACAO)}
    assert cores["modelos"] == "primario" and cores["gastos"] == "primario"
```

- [ ] **Step 12: verificação**

```bash
.venv/bin/python -m pytest -q tests/test_qt_configuracao.py tests/test_qt_home.py \
  tests/test_qt_home_paineis.py tests/test_qt_tema.py tests/test_qt_letra.py tests/test_qt_paleta.py \
  tests/test_qt_aviso_windows.py tests/test_qt_dicas.py tests/test_qt_nome.py \
  tests/test_qt_estilo_controles.py tests/test_qt_catalogo.py tests/test_qt_main.py
bash scripts/check.sh
QT_QPA_PLATFORM=offscreen .venv/bin/python frontend.py --smoke | tail -1
QT_QPA_PLATFORM=offscreen .venv/bin/python frontend.py --smoke --letra grande --tema claro | tail -1
```

  Esperado: PASS; check verde; smoke `[smoke] a janela principal Qt montou, as 11 telas abriram e ela fechou sem erro.`

- [ ] **Step 13: commit**

```bash
git add sigft/app_qt/views/configuracao.py sigft/app_qt/views/home.py sigft/app_qt/catalogo.py \
  sigft/app_qt/main.py sigft/app/textos_dicas.py tests/test_qt_configuracao.py tests/test_qt_home.py \
  tests/test_qt_home_paineis.py tests/test_qt_tema.py tests/test_qt_letra.py tests/test_qt_paleta.py \
  tests/test_qt_aviso_windows.py tests/test_qt_dicas.py tests/test_qt_nome.py tests/test_qt_estilo_controles.py
git commit -m "$(cat <<'EOF'
Engrenagem: janela Configuracao com aparencia, nome, avisos, IA e atualizacoes

Tema, letra, aviso do Windows, chaves, modelos e atualizacoes saem da Home para a
janela Configuracao (engrenagem a direita do titulo e Ctrl+K). Cada controle chama
a mesma funcao de antes.

Testes de medida da Home reescritos: a linha do titulo tem so a saudacao e a
engrenagem, a do subtitulo perdeu a caixa e a barra tem dois botoes; a letra
grande nao precisa mais descer a caixa de versoes de teste.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RSbK7jX9qvsvyZKqnojmij
EOF
)"
```

---
### Task 2: Infraestrutura do idioma (`idioma.py`, catálogos, ferramenta, guarda, pacote)

**Files:**
- Create: `sigft/app/idioma.py`
- Create: `sigft/app/idiomas/es.json`, `sigft/app/idiomas/en.json` (os dois com `{}` e linha final)
- Create: `tools/textos_da_interface.py`
- Create: `tests/test_idioma.py`, `tests/test_textos_da_interface.py`, `tests/_idioma.py`
- Modify: `tests/conftest.py` (fixture autouse nova, item 7)
- Modify: `SIG-FT.spec:47-62` (`datas`), `tests/test_qt_no_pacote.py` (seção C)
- Modify: `sigft/app_qt/main.py` (`_smoke` confere os catálogos), `tests/test_qt_smoke.py`

**Interfaces:**
- Produces: `idioma.IDIOMAS = ("es", "pt", "en")`, `PADRAO = "pt"`, `CHAVE_PREFERENCIA = "idioma"`,
  `NOMES: dict[str, str]`, `PASTA_CATALOGOS: Path`, `NAO_SE_TRADUZ: frozenset[str]`,
  `valido(codigo) -> str`, `catalogo(codigo) -> dict[str, str]`, `conferir() -> list[str]`,
  `atual() -> str`, `definir(codigo) -> str`, `escolhido() -> str | None`, `guardar(codigo) -> str`,
  `t(texto: str, **valores) -> str`, `marcar(texto: str) -> str`, `_arquivo_de_prefs()`.
- Produces (ferramenta, carregada por caminho): `Uso(arquivo, linha, texto)`,
  `parece_texto(valor) -> bool`, `chaves_do_codigo(fonte, arquivo="") -> (list[Uso], list[Uso])`,
  `literais_soltos(fonte, arquivo="") -> list[Uso]`, `arquivos(raiz) -> list[Path]`,
  `chaves(raiz) -> (dict[str, list[Uso]], list[Uso])`, `catalogo(codigo, raiz) -> dict`,
  `faltando(codigo, raiz) -> list[str]`, `sobrando(codigo, raiz) -> list[str]`,
  `arrumar(raiz) -> None`, `main(argv) -> int`; `IDIOMAS_COM_CATALOGO = ("es", "en")`.
- Produces (testes): `tests/_idioma.em_idioma(codigo)` (gerenciador de contexto),
  `textos_visiveis(raiz) -> set[str]`, `ainda_em_portugues(raiz, codigo) -> set[str]`;
  em `tests/test_textos_da_interface.py`: `CONVERTIDOS: tuple[str, ...]` (vazio aqui; as
  Tasks 4 a 9 acrescentam) e `NAO_E_INTERFACE: dict[str, set[str]]`.

Decisões desta tarefa:
- Constante de módulo NÃO pode ser traduzida no import: os módulos da interface são importados
  antes da pergunta da primeira abertura, e os testes trocam de idioma no meio da sessão. Por
  isso `marcar()` (o `N_()` do gettext) e `t()` na hora de mostrar.
- Preferência que não se lê vale como português **já escolhido** (`escolhido()` devolve `"pt"`):
  como no nome (`nome.precisa_perguntar`), perguntar a cada abertura sem conseguir lembrar é
  pior que não perguntar.
- A guarda é heurística (a ferramenta diz o que fica de fora). O que ela não vê, a conferência
  em tela (`tests/_idioma.ainda_em_portugues`) pega: monta a tela em `es`/`en` e acusa texto à
  vista que tem tradução diferente no catálogo.

- [ ] **Step 1: testes do idioma (`tests/test_idioma.py`)**

```python
"""O idioma da interface (2026-10-22): `t()`, os catálogos e a preferência."""
import json
import pathlib

import pytest

from sigft.app import idioma


@pytest.fixture
def catalogos(tmp_path, monkeypatch):
    (tmp_path / "es.json").write_text(json.dumps({
        "Salvar": "Guardar",
        "Ficha {atual} de {total}": "Ficha {atual} de {total}",
        "Abrir {nome}": "Abrir {name}",
        "Vazio": "",
    }), encoding="utf-8")
    (tmp_path / "en.json").write_text(json.dumps({"Salvar": "Save"}), encoding="utf-8")
    monkeypatch.setattr(idioma, "PASTA_CATALOGOS", tmp_path)
    monkeypatch.setattr(idioma, "_catalogos", {})
    return tmp_path


def test_os_testes_rodam_em_portugues():
    assert idioma.atual() == "pt"


def test_portugues_e_a_propria_chave(catalogos):
    assert idioma.t("Salvar") == "Salvar"


def test_traduz_no_idioma_definido(catalogos):
    assert idioma.definir("es") == "es"
    assert idioma.t("Salvar") == "Guardar"
    idioma.definir("en")
    assert idioma.t("Salvar") == "Save"


def test_sem_traducao_cai_no_portugues(catalogos):
    idioma.definir("es")
    assert idioma.t("Não existe no catálogo") == "Não existe no catálogo"
    assert idioma.t("Vazio") == "Vazio"     # tradução vazia vale como nenhuma


def test_valores_entram_no_lugar(catalogos):
    assert idioma.t("Ficha {atual} de {total}", atual=3, total=8) == "Ficha 3 de 8"
    idioma.definir("es")
    assert idioma.t("Ficha {atual} de {total}", atual=3, total=8) == "Ficha 3 de 8"


def test_traducao_com_valor_que_nao_casa_cai_no_portugues(catalogos):
    idioma.definir("es")
    assert idioma.t("Abrir {nome}", nome="x.xlsx") == "Abrir x.xlsx"


def test_sem_valores_as_chaves_ficam_como_estao(catalogos):
    assert idioma.t("Use {nome} no campo") == "Use {nome} no campo"


def test_idioma_invalido_vira_portugues(catalogos):
    assert idioma.definir("fr") == "pt"
    assert idioma.valido(None) == "pt"


def test_marcar_nao_muda_o_texto():
    assert idioma.marcar("Texto qualquer") == "Texto qualquer"


def test_catalogo_que_nao_se_le_nao_derruba(tmp_path, monkeypatch):
    (tmp_path / "es.json").write_text("isto não é json", encoding="utf-8")
    (tmp_path / "en.json").write_text("[1, 2]", encoding="utf-8")
    monkeypatch.setattr(idioma, "PASTA_CATALOGOS", tmp_path)
    monkeypatch.setattr(idioma, "_catalogos", {})
    idioma.definir("es")
    assert idioma.t("Salvar") == "Salvar"
    assert idioma.conferir() == ["es", "en"]


def test_os_catalogos_de_verdade_se_leem():
    assert idioma.conferir() == []


def test_escolhido_e_guardar(tmp_path, monkeypatch):
    monkeypatch.setattr(idioma, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    assert idioma.escolhido() is None
    assert idioma.guardar("en") == "en"
    assert idioma.escolhido() == "en"
    assert idioma.guardar("fr") == "pt"
    assert idioma.escolhido() == "pt"


def test_valor_invalido_nas_prefs_e_nao_escolhido(tmp_path, monkeypatch):
    monkeypatch.setattr(idioma, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    (tmp_path / "p.json").write_text('{"preferencias": {"idioma": "klingon"}}', encoding="utf-8")
    assert idioma.escolhido() is None


def test_preferencia_que_nao_se_le_vale_portugues(monkeypatch):
    from sigft.core import prefs

    def quebra(*_a, **_k):
        raise OSError("sem permissão")

    monkeypatch.setattr(prefs, "ler_preferencia", quebra)
    assert idioma.escolhido() == "pt"


def test_idioma_nao_conhece_qt():
    fonte = (pathlib.Path(idioma.__file__)).read_text(encoding="utf-8")
    assert "PySide6" not in fonte
```

- [ ] **Step 2:** `.venv/bin/python -m pytest -q tests/test_idioma.py` → FAIL (`ImportError: cannot import name 'idioma'`).

- [ ] **Step 3: `sigft/app/idioma.py` (novo, inteiro)**

```python
"""O idioma da interface: espanhol, português ou inglês (2026-10-22).

Só a INTERFACE muda de idioma: botões, títulos, rótulos, dicas, janelas, caixas
de aviso e de pergunta, Ctrl+K, resumo do lote, aviso do Windows. NÃO mudam o
console (o que serviços e robôs escrevem), o portal PMIB, as planilhas e fichas
geradas, nem o CHANGELOG.

A chave de cada tradução é o próprio texto em português que está no código:
`t("Selecionar Excel")`. O português não tem catálogo (é a chave); `es` e `en`
moram em `sigft/app/idiomas/<codigo>.json` (`{"texto pt": "tradução"}`). Texto
com valores usa `{nome}`: `t("Ficha {atual} de {total}", atual=3, total=8)`.
Sem tradução, ou com uma que não casa com os valores, vale o português: nunca
vazio.

Constante de módulo que é texto de interface vai em `marcar("...")`: o texto
não muda (o import acontece antes de o idioma ser escolhido), mas a ferramenta
`tools/textos_da_interface.py` a reconhece como chave; quem a põe na tela
chama `t(CONSTANTE)`.

A troca vale ao REINICIAR: cada tela lê os textos uma vez, ao ser montada. O
idioma da sessão é `definir`; o guardado nas preferências (chave `idioma`) é
`escolhido`/`guardar`. Sem Qt: serviço e regra nunca conhecem a interface.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

_log = logging.getLogger(__name__)

IDIOMAS = ("es", "pt", "en")
PADRAO = "pt"
CHAVE_PREFERENCIA = "idioma"
# O nome de cada idioma, escrito NO PRÓPRIO idioma: é assim que quem não lê
# português acha o seu.
NOMES = {"es": "Español", "pt": "Português", "en": "English"}
PASTA_CATALOGOS = Path(__file__).resolve().parent / "idiomas"

# Termos que ficam iguais em todos os idiomas: nomes próprios, siglas, nomes de
# módulo que são marca. Um literal IGUAL a um deles não precisa de `t()`
# (`tests/test_textos_da_interface.py`). O glossário inteiro, com os termos que
# se traduzem de um jeito fixo, está em `docs/base-conhecimento/00-frontend.md`.
NAO_SE_TRADUZ = frozenset({
    "SIG-FT", "PMIB", "PDM", "SAM-GM", "STATUS_PMIB", "_STATUS_PMIB", "LMR", "TAG", "TAGs",
    "AutoSpec", "AutoSpec AI (RAG)", "Analyzer", "PMIB Manager", "Search", "Gestão PMIB",
    "Excel", "PDF", "JSON", "RDS-PP", "Aconex", "GE Vernova", "Itaipu", "Gemini", "OpenRouter",
    "LlamaCloud", "Google", "Windows", "OK", "Español", "Português", "English",
})

_atual = PADRAO
_catalogos: dict[str, dict[str, str]] = {}


def _arquivo_de_prefs():
    """O `config_path` das preferências: `None` é o `user_prefs.json` da pasta de
    dados. Função para os testes apontarem outro arquivo."""
    return None


def valido(codigo: object) -> str:
    return codigo if codigo in IDIOMAS else PADRAO


def _ler_catalogo(codigo: str) -> dict[str, str] | None:
    """O catálogo do disco, só com pares de texto não vazios; `None` se o arquivo
    não existe ou não é um objeto JSON."""
    try:
        dados = json.loads((PASTA_CATALOGOS / f"{codigo}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(dados, dict):
        return None
    return {k: v for k, v in dados.items() if isinstance(k, str) and isinstance(v, str) and v}


def catalogo(codigo: str) -> dict[str, str]:
    """As traduções de `codigo` (o português: nenhuma). Lido uma vez por sessão."""
    codigo = valido(codigo)
    if codigo == PADRAO:
        return {}
    if codigo not in _catalogos:
        lido = _ler_catalogo(codigo)
        if lido is None:
            _log.warning("catalogo do idioma %s nao foi lido em %s", codigo, PASTA_CATALOGOS)
        _catalogos[codigo] = lido or {}
    return _catalogos[codigo]


def conferir() -> list[str]:
    """Os idiomas cujo catálogo não se lê. O `--smoke` do Release reprova: um
    catálogo fora do `.exe` deixaria o app em português, em silêncio."""
    return [codigo for codigo in IDIOMAS if codigo != PADRAO and _ler_catalogo(codigo) is None]


def atual() -> str:
    """O idioma desta sessão."""
    return _atual


def definir(codigo: object) -> str:
    """O idioma desta sessão (inválido: português). Devolve o que valeu. Não grava:
    quem lembra a escolha é `guardar`."""
    global _atual
    _atual = valido(codigo)
    catalogo(_atual)
    return _atual


def escolhido() -> str | None:
    """O idioma guardado, ou `None` se a pessoa ainda não escolheu (é o que faz a
    primeira abertura perguntar). Preferência que não se lê vale como português
    escolhido: perguntar a cada abertura sem conseguir lembrar seria pior."""
    from sigft.core import prefs

    try:
        valor = prefs.ler_preferencia(CHAVE_PREFERENCIA, "", config_path=_arquivo_de_prefs())
    except Exception:  # noqa: BLE001 -- preferência é conveniência
        _log.warning("nao consegui ler o idioma escolhido", exc_info=True)
        return PADRAO
    return valor if valor in IDIOMAS else None


def guardar(codigo: object) -> str:
    """Lembra o idioma (inválido: português) para a próxima abertura e devolve o
    que gravou. Gravar que falha fica no log: não impede nada."""
    from sigft.core import prefs

    codigo = valido(codigo)
    try:
        prefs.gravar_preferencia(CHAVE_PREFERENCIA, codigo, config_path=_arquivo_de_prefs())
    except Exception:  # noqa: BLE001 -- lembrar não pode derrubar a tela
        _log.warning("nao consegui gravar o idioma escolhido", exc_info=True)
    return codigo


def t(texto: str, **valores) -> str:
    """`texto` (em português) no idioma da sessão, com os `{valores}` no lugar."""
    traduzido = catalogo(_atual).get(texto, texto) if _atual != PADRAO else texto
    if not valores:
        return traduzido
    try:
        return traduzido.format(**valores)
    except (KeyError, IndexError, ValueError):
        _log.warning("traducao com valores que nao casam com o portugues: %r", texto)
        return texto.format(**valores)


def marcar(texto: str) -> str:
    """Marca uma constante de módulo como texto de interface. Devolve o próprio
    texto; quem o mostra chama `t(...)`."""
    return texto
```

  E os dois catálogos vazios: `sigft/app/idiomas/es.json` e `sigft/app/idiomas/en.json`, cada um
  com o conteúdo `{}` seguido de uma quebra de linha.

- [ ] **Step 4: `tests/conftest.py`.** Logo depois da fixture `_sem_janelas_do_fim_da_tarefa`:

```python
# 7. [2026-10-22] O idioma da interface (`sigft/app/idioma.py`) é estado do
#    processo. Todo teste começa e termina em português, onde `t(x) == x`: é por
#    isso que os testes que comparam texto literal continuam valendo. Quem testa
#    outro idioma usa `tests/_idioma.em_idioma(...)`.
@pytest.fixture(autouse=True)
def _interface_em_portugues():
    from sigft.app import idioma as _idioma

    _idioma.definir(_idioma.PADRAO)
    yield
    _idioma.definir(_idioma.PADRAO)
```

- [ ] **Step 5:** `.venv/bin/python -m pytest -q tests/test_idioma.py` → PASS.

- [ ] **Step 6: testes da ferramenta e da guarda (`tests/test_textos_da_interface.py`)**

```python
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
```

- [ ] **Step 7:** `.venv/bin/python -m pytest -q tests/test_textos_da_interface.py` → FAIL
  (`FileNotFoundError: ... tools/textos_da_interface.py`).

- [ ] **Step 8: `tools/textos_da_interface.py` (novo, inteiro)**

```python
"""Os textos de interface do SIG-FT e os catálogos de tradução (2026-10-22).

A chave de cada tradução é o próprio texto em português, escrito no código
dentro de `t("...")` (traduzido na hora) ou de `marcar("...")` (constante de
módulo, traduzida onde aparece na tela). Ver `sigft/app/idioma.py`.

Esta ferramenta lê o código (sem importá-lo: `ast`) e responde três perguntas:

  * que chaves o código usa, e quais faltam ou sobram em cada catálogo
    (`sigft/app/idiomas/<codigo>.json`);
  * onde há `t(f"...")` ou `marcar(f"...")`: o f-string vira OUTRA chave a cada
    valor, e a tradução nunca casa. O certo é `t("... {nome} ...", nome=...)`;
  * que literais de um arquivo parecem texto de interface e não passam por
    `t()`/`marcar()` (a guarda de `tests/test_textos_da_interface.py`).

A terceira é heurística: um literal "parece texto" quando tem espaço, começa
com maiúscula seguida de minúscula, tem letra acentuada ou termina em ":" ou
"...". Fica de fora o que é identificador (`"primario"`, `"CriaFichas"`,
`"GEMINI"`), folha de estilo, nome de fonte, docstring, e o que vai para log,
`print`, `objectName`, propriedade, chave de dicionário ou exceção. Palavra
única toda em maiúsculas e sem acento ("ATRASADO") escapa: a conferência em
tela (`tests/_idioma.py`) a pega quando a constante está marcada.

Uso:
    python tools/textos_da_interface.py                 # o que falta e sobra em es e en
    python tools/textos_da_interface.py --faltando es   # JSON {"chave": ""} para preencher
    python tools/textos_da_interface.py --literais sigft/app_qt/views/home.py
    python tools/textos_da_interface.py --arrumar       # catálogos em ordem, sem escapar acento
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

RAIZ = Path(__file__).resolve().parent.parent
IDIOMAS_COM_CATALOGO = ("es", "en")
# Fora de `sigft/app_qt`, os módulos sem Qt que guardam texto de interface.
ARQUIVOS_DE_TEXTO = (
    "sigft/app/textos_dialogos.py",
    "sigft/app/textos_dicas.py",
    "sigft/app/atualizacao_textos.py",
    "sigft/app/resumo_lote.py",
)
FUNCOES_DE_TRADUCAO = frozenset({"t", "marcar"})
# Chamadas cujos argumentos nunca são interface: log, saída, identificadores.
CHAMADAS_SEM_INTERFACE = frozenset({
    "log", "_log", "print", "logar", "setObjectName", "setProperty", "property",
    "findChild", "findChildren", "getattr", "hasattr", "setattr", "startswith", "endswith",
    "removeprefix", "removesuffix", "split", "rsplit", "partition", "replace", "strip",
    "strftime", "strptime", "compile", "match", "search", "sub", "fullmatch", "join", "Path",
    "getenv", "get_opcao", "set_opcao", "ler_preferencia", "gravar_preferencia", "backend",
    "exigir", "setStyleSheet", "folha_fonte_tk", "fonte_tk", "QFont", "QKeySequence",
    "definir_papel", "definir_propriedade", "Arrastavel",
})
DONOS_SEM_INTERFACE = frozenset({"logging", "_log", "logger", "log", "os", "re", "json", "sys"})
ARGUMENTOS_SEM_INTERFACE = frozenset({
    "objectName", "papel", "variante", "alinhar", "papel_cor", "papel_cor_ativo", "encoding",
})
NOMES_DE_FONTE = frozenset({
    "Roboto", "Segoe UI", "Consolas", "Menlo", "DejaVu Sans Mono", "Noto Emoji", "Arial",
    "Cascadia Mono",
})
_IDENTIFICADOR = re.compile(
    r"^[a-z0-9_.:\-/\\*%<>= ]+$"          # chave, objectName, caminho, formato
    r"|^[A-Z0-9_]+$"                       # constante, chave de API
    r"|^[A-Z][a-z0-9]*[A-Z][A-Za-z0-9]*$"  # CamelCase: nome de tela ou de classe
)
_FOLHA = re.compile(
    r"\b(font|color|background|border|padding|margin|min|max|height|width|text|selection"
    r"|lineedit|line|white)[-a-z]*\s*:\s*[^;]*;"   # propriedade: valor;
    r"|\bQ[A-Z]\w*\s*[\[{:]|#[a-z_]+\s*[{\[]"     # seletor de folha do Qt
)


class Uso(NamedTuple):
    arquivo: str
    linha: int
    texto: str


def parece_texto(valor: str) -> bool:
    """A heurística do "texto de interface" (ver o docstring do módulo)."""
    texto = valor.strip()
    if len(texto) < 2 or not re.search(r"[A-Za-zÀ-ÿ]", texto):
        return False
    if texto in NOMES_DE_FONTE or _IDENTIFICADOR.match(texto) or _FOLHA.search(texto):
        return False
    return bool(" " in texto or re.match(r"^[A-ZÀ-Ý][a-zà-ÿ]", texto)
                or re.search(r"[À-ÿ]", texto) or texto.endswith((":", "...")))


def _nome_da_chamada(no: ast.Call) -> tuple[str | None, str | None]:
    funcao = no.func
    if isinstance(funcao, ast.Name):
        return funcao.id, None
    if isinstance(funcao, ast.Attribute):
        dono = funcao.value
        nome_do_dono = dono.id if isinstance(dono, ast.Name) else getattr(dono, "attr", None)
        return funcao.attr, nome_do_dono
    return None, None


def _docstrings(arvore: ast.AST) -> set[int]:
    achadas = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) \
                and no.body and isinstance(no.body[0], ast.Expr) \
                and isinstance(no.body[0].value, ast.Constant) \
                and isinstance(no.body[0].value.value, str):
            achadas.add(id(no.body[0].value))
    return achadas


def chaves_do_codigo(fonte: str, arquivo: str = "") -> tuple[list[Uso], list[Uso]]:
    """`(chaves, fstrings)`: o 1º argumento literal de cada `t()`/`marcar()`, e os
    `t(f"...")`/`marcar(f"...")`, que não viram chave."""
    chaves_, fstrings = [], []
    for no in ast.walk(ast.parse(fonte)):
        if not isinstance(no, ast.Call) or not no.args:
            continue
        nome, _dono = _nome_da_chamada(no)
        if nome not in FUNCOES_DE_TRADUCAO:
            continue
        primeiro = no.args[0]
        if isinstance(primeiro, ast.Constant) and isinstance(primeiro.value, str):
            chaves_.append(Uso(arquivo, no.lineno, primeiro.value))
        elif isinstance(primeiro, ast.JoinedStr):
            fstrings.append(Uso(arquivo, no.lineno, ast.unparse(primeiro)))
    return chaves_, fstrings


def literais_soltos(fonte: str, arquivo: str = "") -> list[Uso]:
    """Os literais que parecem texto de interface e não passam por tradução."""
    arvore = ast.parse(fonte)
    pulados = _docstrings(arvore)
    for no in ast.walk(arvore):
        dentro = []
        if isinstance(no, ast.Call):
            nome, dono = _nome_da_chamada(no)
            if nome in FUNCOES_DE_TRADUCAO or nome in CHAMADAS_SEM_INTERFACE \
                    or dono in DONOS_SEM_INTERFACE:
                dentro += list(no.args) + [k.value for k in no.keywords]
            else:
                dentro += [k.value for k in no.keywords if k.arg in ARGUMENTOS_SEM_INTERFACE]
        elif isinstance(no, ast.Raise) and no.exc is not None:
            dentro.append(no.exc)
        elif isinstance(no, ast.Subscript):
            dentro.append(no.slice)
        elif isinstance(no, ast.JoinedStr):
            pulados.update(id(parte) for parte in no.values)
        for raiz in dentro:
            pulados.update(id(filho) for filho in ast.walk(raiz))
    achados = []
    for no in ast.walk(arvore):
        if id(no) in pulados:
            continue
        if isinstance(no, ast.Constant) and isinstance(no.value, str) and parece_texto(no.value):
            achados.append(Uso(arquivo, no.lineno, no.value))
        elif isinstance(no, ast.JoinedStr):
            fixo = "".join(p.value for p in no.values if isinstance(p, ast.Constant))
            if parece_texto(fixo):
                achados.append(Uso(arquivo, no.lineno, ast.unparse(no)))
    return sorted(achados, key=lambda u: u.linha)


def arquivos(raiz: Path = RAIZ) -> list[Path]:
    return sorted((raiz / "sigft" / "app_qt").rglob("*.py")) + [raiz / a for a in ARQUIVOS_DE_TEXTO]


def chaves(raiz: Path = RAIZ) -> tuple[dict[str, list[Uso]], list[Uso]]:
    """Todas as chaves do código (`texto -> usos`) e todos os f-strings em `t()`."""
    todas: dict[str, list[Uso]] = {}
    fstrings: list[Uso] = []
    for caminho in arquivos(raiz):
        relativo = caminho.relative_to(raiz).as_posix()
        achadas, ruins = chaves_do_codigo(caminho.read_text(encoding="utf-8"), relativo)
        for uso in achadas:
            todas.setdefault(uso.texto, []).append(uso)
        fstrings += ruins
    return todas, fstrings


def _caminho_do_catalogo(codigo: str, raiz: Path) -> Path:
    return raiz / "sigft" / "app" / "idiomas" / f"{codigo}.json"


def catalogo(codigo: str, raiz: Path = RAIZ) -> dict[str, str]:
    return json.loads(_caminho_do_catalogo(codigo, raiz).read_text(encoding="utf-8"))


def faltando(codigo: str, raiz: Path = RAIZ) -> list[str]:
    usadas, _ = chaves(raiz)
    traducoes = catalogo(codigo, raiz)
    return sorted(c for c in usadas if not traducoes.get(c))


def sobrando(codigo: str, raiz: Path = RAIZ) -> list[str]:
    usadas, _ = chaves(raiz)
    return sorted(c for c in catalogo(codigo, raiz) if c not in usadas)


def arrumar(raiz: Path = RAIZ) -> None:
    """Reescreve os catálogos na forma única: chaves em ordem, `indent=2`, acento
    como acento e linha final (um diff por tradução, sem reordenar o arquivo)."""
    for codigo in IDIOMAS_COM_CATALOGO:
        caminho = _caminho_do_catalogo(codigo, raiz)
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        caminho.write_text(json.dumps(dict(sorted(dados.items())), ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--faltando", metavar="CODIGO", choices=IDIOMAS_COM_CATALOGO)
    parser.add_argument("--literais", nargs="+", metavar="ARQUIVO")
    parser.add_argument("--arrumar", action="store_true")
    args = parser.parse_args(argv)
    if args.arrumar:
        arrumar()
        return 0
    if args.faltando:
        print(json.dumps({c: "" for c in faltando(args.faltando)}, ensure_ascii=False, indent=2))
        return 0
    if args.literais:
        soltos = []
        for nome in args.literais:
            soltos += literais_soltos(Path(nome).read_text(encoding="utf-8"), nome)
        for uso in soltos:
            print(f"{uso.arquivo}:{uso.linha}: {uso.texto!r}")
        return 1 if soltos else 0
    _usadas, fstrings = chaves()
    problemas = 0
    for uso in fstrings:
        print(f"f-string em t(): {uso.arquivo}:{uso.linha}: {uso.texto}")
        problemas += 1
    for codigo in IDIOMAS_COM_CATALOGO:
        falta, sobra = faltando(codigo), sobrando(codigo)
        print(f"{codigo}: {len(falta)} faltando, {len(sobra)} sobrando")
        for chave in falta:
            print(f"  falta: {chave!r}")
        for chave in sobra:
            print(f"  sobra: {chave!r}")
        problemas += len(falta) + len(sobra)
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 9: `tests/_idioma.py` (novo, inteiro)**

```python
"""Ajudantes dos testes de idioma (2026-10-22).

`em_idioma` troca o idioma da sessão e volta ao português no fim (a fixture
autouse do conftest volta de qualquer jeito; isto é para trocar no meio de um
teste). `ainda_em_portugues` é a conferência em tela: o texto à vista que tem,
no catálogo, uma tradução DIFERENTE dele mesmo. Pega a constante marcada
(`marcar`) que chegou à tela sem `t()`, que a guarda estática não vê.
"""
from __future__ import annotations

import contextlib

from PySide6.QtWidgets import QAbstractButton, QComboBox, QLabel, QLineEdit, QTreeWidget, QWidget

from sigft.app import idioma


@contextlib.contextmanager
def em_idioma(codigo: str):
    idioma.definir(codigo)
    try:
        yield
    finally:
        idioma.definir(idioma.PADRAO)


def textos_visiveis(raiz: QWidget) -> set[str]:
    """Os textos de `raiz` e dos filhos: título de janela, dica, rótulo, botão,
    caixa, placeholder, itens de menu e cabeçalho de tabela."""
    textos: set[str] = set()
    for w in [raiz, *raiz.findChildren(QWidget)]:
        if w.isWindow() and w.windowTitle():
            textos.add(w.windowTitle())
        if w.toolTip():
            textos.add(w.toolTip())
        if isinstance(w, (QLabel, QAbstractButton)) and w.text().strip():
            textos.add(w.text().strip())
        if isinstance(w, QLineEdit) and w.placeholderText():
            textos.add(w.placeholderText())
        if isinstance(w, QComboBox):
            textos.update(w.itemText(i) for i in range(w.count()))
        if isinstance(w, QTreeWidget):
            cabecalho = w.headerItem()
            textos.update(cabecalho.text(c) for c in range(cabecalho.columnCount()))
    return {texto for texto in textos if texto}


def ainda_em_portugues(raiz: QWidget, codigo: str) -> set[str]:
    traducoes = idioma.catalogo(codigo)
    return {texto for texto in textos_visiveis(raiz) if traducoes.get(texto, texto) != texto}
```

- [ ] **Step 10:** `.venv/bin/python -m pytest -q tests/test_textos_da_interface.py tests/test_idioma.py` → PASS
  (o teste parametrizado por `CONVERTIDOS` sai como "skipped": a lista está vazia).

- [ ] **Step 11: os catálogos no pacote.** No `SIG-FT.spec`, na lista `datas`, depois da
  entrada do `painel_template.html`:

```python
    # Os catálogos de tradução da interface (2026-10-22, `sigft/app/idioma.py`).
    # Vão para `sigft/app/idiomas/`, onde o `idioma` os procura
    # (`Path(__file__).parent / "idiomas"`, também dentro do .exe). Sem eles o app
    # abre em português sem aviso: o `--smoke` do Release reprova (`idioma.conferir`).
    (os.path.join("sigft", "app", "idiomas"), os.path.join("sigft", "app", "idiomas")),
```

  Em `tests/test_qt_no_pacote.py`, na seção C, depois de
  `test_as_fontes_da_interface_vao_para_onde_o_estilo_as_procura`:

```python
def test_os_catalogos_de_idioma_vao_para_onde_o_idioma_os_procura(spec_executado):
    """`idioma.PASTA_CATALOGOS` sai de `__file__`: no pacote, `_MEIPASS/sigft/app/
    idioma.pyc` -> `_MEIPASS/sigft/app/idiomas`. Os catálogos têm de cair aí."""
    from sigft.app import idioma

    esperado = Path(os.path.relpath(idioma.PASTA_CATALOGOS, RAIZ)).as_posix()
    for codigo in ("es", "en"):
        arquivo = RAIZ / esperado / f"{codigo}.json"
        assert arquivo.exists(), arquivo
        destino = _destino_no_pacote(spec_executado["analysis"]["datas"], arquivo)
        assert destino == f"{esperado}/{codigo}.json", (codigo, destino)
```

- [ ] **Step 12: o smoke confere os catálogos.** Em `sigft/app_qt/main.py`, no import de
  `sigft.app`, troque `from sigft.app import backends, tokens` por
  `from sigft.app import backends, idioma, tokens`. Em `_smoke`, logo depois do bloco
  `if (sem_desenho := icones.conferir()):` (antes de `backends.carregar_todos`):

```python
        # Os catálogos de idioma se leem? Fora do `.exe`, o app abriria só em
        # português, sem erro: a mesma classe dos ícones (2026-10-22).
        if (sem_catalogo := idioma.conferir()):
            relatorio = (f"[smoke] FALHOU: catalogos de idioma que nao se leem: "
                         f"{', '.join(sem_catalogo)} (pasta {idioma.PASTA_CATALOGOS})")
            gravar_relatorio(ARQUIVO_JANELA, relatorio)
            print(relatorio)
            return 1
```

  Em `tests/test_qt_smoke.py`, depois de `test_icone_que_nao_desenha_reprova_o_smoke`:

```python
def test_catalogo_de_idioma_que_nao_se_le_reprova_o_smoke(relatorio, monkeypatch):
    """Sem o `es.json` no `.exe` o app abriria em português, sem erro nenhum."""
    from sigft.app import idioma

    monkeypatch.setattr(idioma, "conferir", lambda: ["es"])

    assert qmain._smoke() == 1
    texto = _ler(relatorio)
    assert "FALHOU" in texto and "catalogos de idioma" in texto and "es" in texto
```

- [ ] **Step 13: verificação**

```bash
.venv/bin/python -m pytest -q tests/test_idioma.py tests/test_textos_da_interface.py \
  tests/test_qt_no_pacote.py tests/test_qt_smoke.py tests/test_qt_main.py
.venv/bin/python tools/textos_da_interface.py      # "es: 0 faltando, 0 sobrando" e o mesmo para en
bash scripts/check.sh
QT_QPA_PLATFORM=offscreen .venv/bin/python frontend.py --smoke | tail -1
```

- [ ] **Step 14: commit**

```bash
git add sigft/app/idioma.py sigft/app/idiomas/es.json sigft/app/idiomas/en.json tools/textos_da_interface.py \
  tests/test_idioma.py tests/test_textos_da_interface.py tests/_idioma.py tests/conftest.py SIG-FT.spec \
  tests/test_qt_no_pacote.py sigft/app_qt/main.py tests/test_qt_smoke.py
git commit -m "$(cat <<'EOF'
Idioma: t() com o texto em portugues como chave, catalogos es/en e a ferramenta

sigft/app/idioma.py (sem Qt) traduz pelo catalogo da sessao e cai no portugues;
marcar() marca constante de modulo. tools/textos_da_interface.py le o codigo e
lista o que falta e sobra nos catalogos, os t(f"...") e os literais soltos. Os
testes rodam em portugues (conftest). Catalogos no pacote e conferidos no smoke.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RSbK7jX9qvsvyZKqnojmij
EOF
)"
```

---

### Task 3: Primeira abertura, seção Idioma e "Reiniciar agora"

**Files:**
- Create: `sigft/app_qt/escolha_de_idioma.py`
- Create: `sigft/app_qt/reinicio.py`
- Modify: `sigft/app_qt/main.py` (`_instalar_traducao`, `_preparar_qt`, `_aplicar_idioma`, `main`, `_smoke`)
- Modify: `sigft/app_qt/views/configuracao.py` (`_secao_idioma`), `sigft/app_qt/catalogo.py` (`SECOES_DA_CONFIGURACAO`)
- Modify: `sigft/app_qt/estilo.py` (regra dos seletores ganha `#seletor_idioma`)
- Modify: `SIG-FT.spec` (`_TRADUCOES_DO_QT`), `sigft/app/conferencia.py` (`TRADUCOES_DA_QT`)
- Modify: `tests/conftest.py`, `tests/test_qt_no_pacote.py`, `tests/test_conferencia_do_pacote.py`,
  `tests/test_qt_main.py`, `tests/test_qt_robustez.py`, `tests/test_qt_configuracao.py`
- Create: `tests/test_qt_idioma_abertura.py`

**Interfaces:**
- Consumes: `idioma.IDIOMAS`, `NOMES`, `PADRAO`, `definir`, `atual`, `escolhido`, `guardar` (Task 2);
  `JanelaConfiguracao._seletor`, `_botao_de_escolha`, `home.controller` (Task 1).
- Produces: `escolha_de_idioma.ENV_DESLIGAR = "SIGFT_SEM_PERGUNTA_DO_IDIOMA"`,
  `PerguntaDoIdioma(QDialog)` (`botoes: dict[str, QPushButton]`, `escolha: str | None`),
  `perguntar_na_abertura(*, abrir=None) -> str | None`.
- Produces: `reinicio.ENV_DESLIGAR = "SIGFT_SEM_REINICIO"`, `TITULO`, `MSG_TAREFA_EM_ANDAMENTO`,
  `MSG_NAO_REABRIU`, `comando_para_reabrir(*, congelado, executavel, argv, raiz) -> list[str]`,
  `_abrir_processo(comando, pasta) -> None`, `reiniciar(janela, *, pai=None) -> bool`.
- Produces: `main.LOCALE_DO_QT = {"pt": "pt_BR", "es": "es"}`, `main._aplicar_idioma(app, codigo)`,
  `_preparar_qt(escolha_tema=None, escolha_letra=None, escolha_idioma=None)`, `--idioma` no smoke.
- Produces: `JanelaConfiguracao.botoes_idioma`, `aviso_idioma`, `btn_reiniciar`,
  `TEXTO_IDIOMA_AO_REINICIAR`, `TEXTO_REINICIAR`.
- Produces: `conferencia.TRADUCOES_DA_QT = (("pt_BR", "qtbase"), ("es", "qtbase"))`.

Decisões desta tarefa (spec ambígua):
- "Reiniciar agora" com tarefa rodando **recusa** (caixa informativa, nada fecha): é o que a spec
  diz em "se houver tarefa, não reinicia"; não há "reiniciar mesmo assim".
- A escolha na seção Idioma é **guardada no clique** (como tema e letra); "Reiniciar agora" só
  abre a outra instância. Assim, quem escolhe e fecha o app pelo X também abre no idioma novo.
- Do código-fonte o reinício roda `frontend.py` com o mesmo Python (não `sys.argv[0]`: com
  `python -m sigft.app_qt.main` ele é o `main.py`, que como script não acha o pacote). No `.exe`,
  o próprio `SIG-FT.exe`. Os argumentos da linha de comando vão juntos, menos o `--smoke`.
- Os botões padrão do Qt ("Sim", "Não", "Cancelar") seguem o idioma: `qtbase_pt_BR` no português,
  `qtbase_es` no espanhol, nenhuma tradução no inglês (o Qt já é inglês). O pacote passa a levar
  as duas (`SIG-FT.spec`) e a conferência do pacote confere as duas.

- [ ] **Step 1: os testes (`tests/test_qt_idioma_abertura.py`)**

```python
"""O idioma na abertura e na engrenagem (2026-10-22): a pergunta da primeira
abertura, a seção Idioma da janela Configuração, o reinício e a tradução do Qt."""
import sys

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from sigft.app import idioma
from sigft.app_qt import escolha_de_idioma, reinicio
from sigft.app_qt import main as qmain
from sigft.core import instancia


@pytest.fixture
def prefs(tmp_path, monkeypatch):
    monkeypatch.setattr(idioma, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    return tmp_path / "p.json"


# --- a pergunta da primeira abertura -------------------------------------------------

def test_a_caixa_tem_os_tres_idiomas_cada_um_no_seu(qt_interface, qtbot):
    caixa = escolha_de_idioma.PerguntaDoIdioma()
    qtbot.addWidget(caixa)
    assert [b.text() for b in caixa.botoes.values()] == ["Español", "Português", "English"]
    assert caixa.windowTitle() == "Idioma / Language"
    caixa.botoes["en"].click()
    assert caixa.escolha == "en"
    assert caixa.result() == caixa.DialogCode.Accepted.value


def test_primeira_abertura_pergunta_e_guarda(prefs, monkeypatch):
    monkeypatch.delenv(escolha_de_idioma.ENV_DESLIGAR, raising=False)
    assert escolha_de_idioma.perguntar_na_abertura(abrir=lambda: "es") == "es"
    assert idioma.escolhido() == "es"


def test_ja_escolhido_nao_pergunta(prefs, monkeypatch):
    monkeypatch.delenv(escolha_de_idioma.ENV_DESLIGAR, raising=False)
    idioma.guardar("en")
    perguntas = []
    assert escolha_de_idioma.perguntar_na_abertura(abrir=lambda: perguntas.append(1)) is None
    assert perguntas == []


def test_fechar_sem_escolher_e_portugues_e_pergunta_de_novo(prefs, monkeypatch):
    monkeypatch.delenv(escolha_de_idioma.ENV_DESLIGAR, raising=False)
    assert escolha_de_idioma.perguntar_na_abertura(abrir=lambda: None) is None
    assert idioma.escolhido() is None


def test_nos_testes_e_no_smoke_nunca_pergunta(prefs, monkeypatch):
    assert escolha_de_idioma.perguntar_na_abertura(abrir=lambda: "es") is None   # o conftest desliga
    monkeypatch.delenv(escolha_de_idioma.ENV_DESLIGAR, raising=False)
    monkeypatch.setattr(sys, "argv", ["frontend.py", "--smoke"])
    assert escolha_de_idioma.perguntar_na_abertura(abrir=lambda: "es") is None


def test_main_pergunta_o_idioma_antes_da_splash(qt_interface, monkeypatch):
    from sigft.core import dados_usuario
    from sigft.core.rpa import navegador

    eventos = []

    class SplashFalsa:
        pronta = type("S", (), {"connect": lambda self, f: None})()

        def __init__(self):
            eventos.append(("splash", idioma.atual()))

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
                        lambda: eventos.append("idioma") or "en")
    monkeypatch.setattr(qmain, "_aplicar_idioma", lambda app, codigo: idioma.definir(codigo))
    monkeypatch.setattr(qmain, "SplashScreen", SplashFalsa)
    qmain.main()
    assert eventos == ["qt", "idioma", ("splash", "en")]


# --- a tradução do Qt e a linha de comando ------------------------------------------

@pytest.mark.parametrize("codigo, cancelar", [("pt", "Cancelar"), ("es", "Cancelar"), ("en", "Cancel")])
def test_botoes_do_qt_no_idioma(qt_interface, codigo, cancelar):
    app = QApplication.instance()
    try:
        idioma.definir(codigo)
        assert qmain._instalar_traducao(app) is (codigo != "en")
        assert QApplication.translate("QPlatformTheme", "Cancel") == cancelar
    finally:
        idioma.definir("pt")
        qmain._instalar_traducao(app)


def test_preparar_qt_usa_o_idioma_da_linha_de_comando(qt_interface, prefs):
    app = QApplication.instance()
    folha = app.styleSheet()
    try:
        qmain._preparar_qt("escuro", "normal", "en")
        assert idioma.atual() == "en"
        assert idioma.escolhido() is None, "a abertura só lê"
    finally:
        idioma.definir("pt")
        qmain._instalar_traducao(app)
        app.setStyleSheet(folha)


def test_opcao_idioma_da_linha_de_comando():
    assert qmain._opcao_da_linha_de_comando(["f", "--smoke", "--idioma", "es"], "--idioma") == "es"


@pytest.mark.parametrize("codigo", ["es", "en"])
def test_smoke_em_outro_idioma(qt_interface, monkeypatch, tmp_path, codigo):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    monkeypatch.setattr(qmain.backends, "carregar_todos", lambda **k: None)
    monkeypatch.setattr(sys, "argv", ["frontend.py", "--smoke", "--idioma", codigo])
    try:
        assert qmain._smoke() == 0
        assert idioma.atual() == codigo
    finally:
        idioma.definir("pt")
        qmain._instalar_traducao(QApplication.instance())


def test_as_pontas_da_traducao_do_qt_andam_juntas():
    """O que o `main` carrega, o que a conferência do pacote procura e o que o
    `SIG-FT.spec` deixa no pacote são as mesmas traduções."""
    import pathlib

    from sigft.app import conferencia

    assert set(qmain.LOCALE_DO_QT.values()) == {local for local, _c in conferencia.TRADUCOES_DA_QT}
    spec = (pathlib.Path(qmain.__file__).resolve().parents[2] / "SIG-FT.spec").read_text(encoding="utf-8")
    for local in qmain.LOCALE_DO_QT.values():
        assert f'"qtbase_{local}.qm"' in spec


# --- o reinício ----------------------------------------------------------------------

def test_comando_para_reabrir():
    import os

    assert reinicio.comando_para_reabrir(congelado=True, executavel=r"C:\SIG-FT\SIG-FT.exe",
                                         argv=[r"C:\SIG-FT\SIG-FT.exe", "--tema", "claro"],
                                         raiz=r"C:\SIG-FT") == [r"C:\SIG-FT\SIG-FT.exe", "--tema", "claro"]
    assert reinicio.comando_para_reabrir(congelado=False, executavel="/venv/bin/python",
                                         argv=["/repo/sigft/app_qt/main.py", "--smoke", "--letra", "grande"],
                                         raiz="/repo") == ["/venv/bin/python",
                                                           os.path.join("/repo", "frontend.py"),
                                                           "--letra", "grande"]


class _Janela:
    def __init__(self):
        self.fechar_sem_perguntar = False
        self.fechada = False

    def close(self):
        self.fechada = True


def test_reiniciar_abre_outra_e_fecha_esta(monkeypatch):
    monkeypatch.delenv(reinicio.ENV_DESLIGAR, raising=False)
    abertos = []
    monkeypatch.setattr(reinicio, "_abrir_processo", lambda comando, pasta: abertos.append((comando, pasta)))
    monkeypatch.setattr(instancia, "tarefas_em_andamento", lambda: [])
    janela = _Janela()
    assert reinicio.reiniciar(janela) is True
    [(comando, _pasta)] = abertos
    assert comando[0] == sys.executable
    assert janela.fechar_sem_perguntar and janela.fechada


def test_reiniciar_com_tarefa_rodando_recusa(qt_interface, monkeypatch):
    monkeypatch.delenv(reinicio.ENV_DESLIGAR, raising=False)
    abertos, avisos = [], []
    monkeypatch.setattr(reinicio, "_abrir_processo", lambda *a: abertos.append(a))
    monkeypatch.setattr(instancia, "tarefas_em_andamento", lambda: ["robo"])
    monkeypatch.setattr(QMessageBox, "information", lambda pai, titulo, texto: avisos.append(texto))
    janela = _Janela()
    assert reinicio.reiniciar(janela) is False
    assert abertos == [] and not janela.fechada
    assert avisos == [reinicio.MSG_TAREFA_EM_ANDAMENTO]


def test_reiniciar_que_nao_abre_avisa_e_nao_fecha(qt_interface, monkeypatch):
    monkeypatch.delenv(reinicio.ENV_DESLIGAR, raising=False)
    avisos = []

    def falha(*_a):
        raise OSError("sem permissão")

    monkeypatch.setattr(reinicio, "_abrir_processo", falha)
    monkeypatch.setattr(instancia, "tarefas_em_andamento", lambda: [])
    monkeypatch.setattr(QMessageBox, "warning", lambda pai, titulo, texto: avisos.append(texto))
    janela = _Janela()
    assert reinicio.reiniciar(janela) is False
    assert not janela.fechada and "sem permissão" in avisos[0]


def test_nos_testes_nunca_reinicia(monkeypatch):
    abertos = []
    monkeypatch.setattr(reinicio, "_abrir_processo", lambda *a: abertos.append(a))
    assert reinicio.reiniciar(_Janela()) is False      # o conftest desliga
    assert abertos == []
```

  E em `tests/test_qt_configuracao.py`, no fim:

```python
# --- a seção Idioma (Task 3) ----------------------------------------------------------

@pytest.fixture
def prefs_do_idioma(tmp_path, monkeypatch):
    from sigft.app import idioma

    monkeypatch.setattr(idioma, "_arquivo_de_prefs", lambda: tmp_path / "idioma.json")
    return idioma


def test_idioma_guarda_no_clique_e_so_entao_libera_o_reiniciar(home, prefs_do_idioma):
    idioma = prefs_do_idioma
    janela = home.abrir_configuracao()
    assert [b.text() for b in janela.botoes_idioma.values()] == ["Español", "Português", "English"]
    assert janela.botoes_idioma["pt"].property("ativo") is True
    assert not janela.btn_reiniciar.isEnabled(), "o idioma escolhido é o que está valendo"
    assert janela.aviso_idioma.text() == config_mod.TEXTO_IDIOMA_AO_REINICIAR
    janela.botoes_idioma["es"].click()
    assert idioma.escolhido() == "es"
    assert janela.botoes_idioma["es"].property("ativo") is True
    assert janela.btn_reiniciar.isEnabled()
    janela.botoes_idioma["pt"].click()
    assert not janela.btn_reiniciar.isEnabled()


def test_reiniciar_agora_chama_o_reinicio_com_a_janela_principal(home, prefs_do_idioma, monkeypatch):
    from sigft.app_qt import reinicio

    pedidos = []
    monkeypatch.setattr(reinicio, "reiniciar", lambda janela, pai=None: pedidos.append((janela, pai)))
    janela = home.abrir_configuracao()
    janela.botoes_idioma["en"].click()
    janela.btn_reiniciar.click()
    assert pedidos == [(home.controller, janela)]
```

  Ainda em `tests/test_qt_configuracao.py`, `test_nenhum_botao_nem_caixa_pega_o_foco` passa a
  esperar `>= 13` controles (3 de idioma e o "Reiniciar agora" a mais).

- [ ] **Step 2:** `.venv/bin/python -m pytest -q tests/test_qt_idioma_abertura.py tests/test_qt_configuracao.py`
  → FAIL (`ImportError: cannot import name 'escolha_de_idioma'`).

- [ ] **Step 3: `tests/conftest.py`.** Na fixture `_interface_em_portugues` (Task 2), antes do
  primeiro `_idioma.definir`, acrescente o parâmetro `monkeypatch` e:

```python
    # A pergunta da primeira abertura e o "Reiniciar agora" nunca nos testes: a
    # pasta de dados de cada teste é nova (sem idioma escolhido), e um reinício
    # abriria outro SIG-FT de verdade. Quem testa tira a variável.
    monkeypatch.setenv("SIGFT_SEM_PERGUNTA_DO_IDIOMA", "1")
    monkeypatch.setenv("SIGFT_SEM_REINICIO", "1")
```

- [ ] **Step 4: `sigft/app_qt/escolha_de_idioma.py` (novo, inteiro)**

```python
"""A pergunta do idioma na primeira abertura (2026-10-22).

Sem idioma nas preferências (instalação nova, e também quem recebe a
atualização), antes de montar a janela principal: uma caixa pequena,
"Idioma / Language", com os três idiomas, cada um escrito no seu. A janela já
abre no escolhido (sem reiniciar). Fechar sem escolher: português, e pergunta de
novo na próxima abertura (nada é guardado).

Chamada pelo `main.main`, nunca pelo `SIG_FT_App` (nenhum teste que monta a
janela fica esperando) nem no `--smoke`. Nos testes, `ENV_DESLIGAR` (conftest).
"""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout

from sigft.app import idioma
from sigft.app_qt.widgets import blocos

ENV_DESLIGAR = "SIGFT_SEM_PERGUNTA_DO_IDIOMA"
# Nos dois idiomas de propósito: quem abre ainda não escolheu nenhum.
TITULO = "Idioma / Language"
LARGURA_BOTAO = 130
ALTURA_BOTAO = 36


class PerguntaDoIdioma(QDialog):
    """Três botões; o clique guarda a escolha em `escolha` e fecha."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(TITULO)
        self.setModal(True)
        self.escolha: str | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)
        lay.addWidget(blocos.rotulo(TITULO, tamanho=16, negrito=True))
        linha = QHBoxLayout()
        linha.setSpacing(10)
        self.botoes = {}
        for codigo in idioma.IDIOMAS:
            botao = blocos.botao(idioma.NOMES[codigo],
                                 variante="primario" if codigo == idioma.PADRAO else "secundario",
                                 largura=LARGURA_BOTAO, altura=ALTURA_BOTAO)
            botao.setAutoDefault(False)
            botao.setProperty("escolha", codigo)
            botao.clicked.connect(self._escolher)
            self.botoes[codigo] = botao
            linha.addWidget(botao, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addLayout(linha)

    def _escolher(self) -> None:
        self.escolha = self.sender().property("escolha")
        self.accept()


def _abrir_caixa() -> str | None:
    caixa = PerguntaDoIdioma()
    caixa.exec()
    return caixa.escolha


def perguntar_na_abertura(*, abrir=None) -> str | None:
    """Pergunta, se ainda não há idioma escolhido, e guarda a resposta. Devolve o
    idioma escolhido agora, ou `None` (não perguntou, ou fechou sem escolher).
    `abrir()` é a costura do teste."""
    if "--smoke" in sys.argv or os.environ.get(ENV_DESLIGAR) or idioma.escolhido() is not None:
        return None
    escolha = (abrir or _abrir_caixa)()
    if escolha not in idioma.IDIOMAS:
        return None
    return idioma.guardar(escolha)
```

- [ ] **Step 5: `sigft/app_qt/reinicio.py` (novo, inteiro)**

```python
"""O "Reiniciar agora" da seção Idioma (2026-10-22).

O idioma vale ao abrir (cada tela lê os textos uma vez). Reiniciar abre uma
nova instância do SIG-FT e fecha a atual, que é o mesmo que a pessoa fechar e
abrir. Com uma tarefa rodando (robô, tradução, IA), NÃO reinicia: diz por quê
e nada fecha.

No `.exe` a instância nova é o próprio `SIG-FT.exe`; do código-fonte, o
`frontend.py` com o mesmo Python. Os argumentos vão juntos, menos o `--smoke`.
Nunca nos testes (`ENV_DESLIGAR`, conftest) nem no `--smoke`.
"""
from __future__ import annotations

import os
import subprocess
import sys

from PySide6.QtWidgets import QMessageBox

from sigft.core import instancia

ENV_DESLIGAR = "SIGFT_SEM_REINICIO"
TITULO = "Reiniciar o SIG-FT"
MSG_TAREFA_EM_ANDAMENTO = (
    "Há uma tarefa em andamento (um robô, uma tradução ou uma consulta à IA).\n\n"
    "Espere ela terminar e clique de novo em Reiniciar agora. O idioma novo já "
    "está guardado e vale também na próxima vez que você abrir o SIG-FT."
)
MSG_NAO_REABRIU = (
    "Não consegui abrir o SIG-FT de novo ({erro}).\n\n"
    "O idioma novo já está guardado: feche e abra o SIG-FT para ele valer."
)
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def comando_para_reabrir(*, congelado: bool, executavel: str, argv: list[str], raiz: str) -> list[str]:
    """A linha de comando da instância nova."""
    extras = [arg for arg in argv[1:] if arg != "--smoke"]
    if congelado:
        return [executavel, *extras]
    return [executavel, os.path.join(raiz, "frontend.py"), *extras]


def _abrir_processo(comando: list[str], pasta: str) -> None:
    """Abre o processo solto deste: o fim do atual não o leva junto."""
    opcoes: dict = {"cwd": pasta, "close_fds": True}
    if os.name == "nt":
        opcoes["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        opcoes["start_new_session"] = True
    subprocess.Popen(comando, **opcoes)  # noqa: S603 -- o próprio SIG-FT, sem shell


def reiniciar(janela, *, pai=None) -> bool:
    """Abre outra instância e fecha `janela` (a principal). `True` se fechou.
    `pai` é de onde a caixa de aviso nasce (a janela Configuração)."""
    if "--smoke" in sys.argv or os.environ.get(ENV_DESLIGAR):
        return False
    if instancia.tarefas_em_andamento():
        QMessageBox.information(pai or janela, TITULO, MSG_TAREFA_EM_ANDAMENTO)
        return False
    congelado = bool(getattr(sys, "frozen", False))
    comando = comando_para_reabrir(congelado=congelado, executavel=sys.executable,
                                   argv=list(sys.argv), raiz=_RAIZ)
    pasta = os.path.dirname(sys.executable) if congelado else _RAIZ
    try:
        _abrir_processo(comando, pasta)
    except OSError as erro:
        QMessageBox.warning(pai or janela, TITULO, MSG_NAO_REABRIU.format(erro=erro))
        return False
    # Já conferimos que não há tarefa: fechar sem a pergunta de "tarefa em andamento".
    janela.fechar_sem_perguntar = True
    janela.close()
    return True
```

- [ ] **Step 6: a seção Idioma.** Em `catalogo.SECOES_DA_CONFIGURACAO`, entre `("aparencia", ...)`
  e `("nome", ...)`, acrescente `("idioma", "Idioma"),`. Em `views/configuracao.py`: no import de
  `sigft.app_qt`, acrescente `reinicio`; acrescente `from sigft.app import idioma`; nas
  constantes, depois de `TEXTO_CANAL_TESTES`:

```python
TEXTO_IDIOMA_AO_REINICIAR = "O idioma muda na próxima vez que o SIG-FT abrir."
TEXTO_REINICIAR = "Reiniciar agora"
```

  e, depois de `marcar_letra`, a seção:

```python
    # --- Idioma -----------------------------------------------------------------
    def _secao_idioma(self) -> QWidget:
        caixa, coluna = self._coluna()
        quadro, linha = self._seletor("seletor_idioma")
        self.botoes_idioma = {}
        for codigo in idioma.IDIOMAS:
            # O nome de cada idioma no próprio idioma (`idioma.NOMES`): não se traduz.
            botao = self._botao_de_escolha(idioma.NOMES[codigo], codigo)
            botao.clicked.connect(self._clicou_idioma)
            self.botoes_idioma[codigo] = botao
            linha.addWidget(botao)
        linha.addStretch()
        coluna.addWidget(quadro)
        self.aviso_idioma = blocos.rotulo(TEXTO_IDIOMA_AO_REINICIAR, tamanho=12, papel="legenda",
                                          alinhar="esquerda")
        coluna.addWidget(self.aviso_idioma)
        self.btn_reiniciar = blocos.botao(TEXTO_REINICIAR, variante="primario", altura=32,
                                          largura_minima=estilo.LARGURA_BOTAO_CTK)
        dialogs.sem_tecla(self.btn_reiniciar)
        self.btn_reiniciar.clicked.connect(self._reiniciar)
        coluna.addWidget(self.btn_reiniciar, 0, Qt.AlignmentFlag.AlignLeft)
        self._marcar_idioma(idioma.escolhido() or idioma.atual())
        return caixa

    def _clicou_idioma(self) -> None:
        # Guardado no clique (como tema e letra): fechar pelo X também vale.
        self._marcar_idioma(idioma.guardar(self.sender().property("escolha")))

    def _marcar_idioma(self, codigo: str) -> None:
        for chave, botao in self.botoes_idioma.items():
            estilo.definir_propriedade(botao, "ativo", chave == codigo)
        # Só faz sentido reiniciar para um idioma diferente do que está valendo.
        self.btn_reiniciar.setEnabled(codigo != idioma.atual())

    def _reiniciar(self) -> None:
        reinicio.reiniciar(self.home.controller, pai=self)
```

  Em `estilo.py` (`_folha_telas`), nas duas regras dos seletores, acrescente o de idioma:

```python
        f'#seletor_tema QPushButton[ativo="true"], #seletor_letra QPushButton[ativo="true"], '
        f'#seletor_idioma QPushButton[ativo="true"] '
        f'{{ background: {menu["fundo"]}; color: {menu["texto"]}; border-color: {menu["fundo"]}; }}',
        # Mouse em cima: o texto acompanha o ícone, que já vai para a cor do menu.
        f'#seletor_tema QPushButton:hover, #seletor_letra QPushButton:hover, '
        f'#seletor_idioma QPushButton:hover {{ color: {menu["texto"]}; }}',
```

  (e no docstring de `_folha_telas`, "seletores de tema e de letra da Home" vira "seletores de
  tema, letra e idioma da janela Configuração (`#seletor_tema`, `#seletor_letra`, `#seletor_idioma`)").

- [ ] **Step 7: `main.py`, a tradução do Qt e a abertura.** No import de `sigft.app_qt`,
  acrescente `escolha_de_idioma`. Troque `_instalar_traducao` por:

```python
# A tradução dos botões padrão do Qt ("Sim", "Não", "Cancelar") de cada idioma da
# interface (2026-10-22). O inglês não tem: o Qt já é inglês. O `SIG-FT.spec`
# leva estas e a `--conferir-pacote` confere (`conferencia.TRADUCOES_DA_QT`).
LOCALE_DO_QT = {"pt": "pt_BR", "es": "es"}


def _instalar_traducao(app) -> bool:
    """Botões dos diálogos do Qt no idioma da sessão (`idioma.atual()`). Troca a
    instalada antes, se houver. `True` se instalou uma."""
    from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator

    anterior = getattr(app, "_tradutor_qt", None)
    if anterior is not None:
        app.removeTranslator(anterior)
        app._tradutor_qt = None
    local = LOCALE_DO_QT.get(idioma.atual())
    if local is None:
        return False
    tradutor = QTranslator(app)
    pasta = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if tradutor.load(QLocale(local), "qtbase", "_", pasta):
        app.installTranslator(tradutor)
        app._tradutor_qt = tradutor  # segura a referência
        return True
    return False
```

  Troque `_preparar_qt` por:

```python
def _preparar_qt(escolha_tema: str | None = None, escolha_letra: str | None = None,
                 escolha_idioma: str | None = None) -> QApplication:
    """A QApplication pronta: idioma, tradução do Qt, fontes, cursor, a letra e o tema.

    Idioma, letra e tema são os guardados nas preferências, ou os da linha de
    comando (`--smoke --idioma es --tema claro --letra grande`), sem gravar: a
    abertura só lê. O idioma vem primeiro (a tradução do Qt e a largura das
    peças dependem dele); a letra antes do tema (a folha que o tema aplica já
    sai com o aumento)."""
    app = QApplication.instance() or _criar_qapplication()
    idioma.definir(escolha_idioma or idioma.escolhido() or idioma.PADRAO)
    _instalar_traducao(app)
    interface.instalar()
    estilo.carregar_fontes()
    letra.aplicar(app, escolha_letra or letra.escolhido(), gravar=False)
    tema.aplicar(app, escolha_tema or tema.escolhido(), gravar=False)
    tema.seguir_o_sistema(app)
    cursor.instalar(app)
    return app


def _aplicar_idioma(app, codigo: str) -> None:
    """O idioma escolhido na primeira abertura, antes de a janela principal
    existir: a sessão, a tradução do Qt e a largura das peças (`letra`)."""
    idioma.definir(codigo)
    _instalar_traducao(app)
    letra.aplicar(app, letra.atual(), gravar=False)
```

  Em `main()`, troque `app = _preparar_qt()` por:

```python
    app = _preparar_qt()
    # [2026-10-22] Sem idioma escolhido (instalação nova ou atualização): a pergunta,
    # antes da splash e da janela principal, que já nascem no idioma escolhido.
    if (escolhido := escolha_de_idioma.perguntar_na_abertura()) is not None:
        _aplicar_idioma(app, escolhido)
```

  Em `_smoke`, troque a chamada de `_preparar_qt(...)` por:

```python
        _preparar_qt(_tema_da_linha_de_comando(sys.argv),
                     _opcao_da_linha_de_comando(sys.argv, "--letra"),
                     _opcao_da_linha_de_comando(sys.argv, "--idioma"))
```

  e, no comentário de cima dela, "o smoke também no claro e com a letra grande" vira "o smoke
  também no claro, com a letra grande e em outro idioma (`--idioma es`)".

- [ ] **Step 8: a tradução `es` do Qt no pacote.** No `SIG-FT.spec`, troque
  `_TRADUCAO_DO_QT = "qtbase_pt_BR.qm"` por
  `_TRADUCOES_DO_QT = {"qtbase_pt_BR.qm", "qtbase_es.qm"}` e, em `_qt_que_a_interface_nao_usa`,
  `return nome != _TRADUCAO_DO_QT` por `return nome not in _TRADUCOES_DO_QT`. No comentário de
  cima, "a interface carrega UMA, a `qtbase_pt_BR`" vira "a interface carrega a do idioma
  escolhido: `qtbase_pt_BR` ou `qtbase_es` (o inglês não precisa)". Em `tests/test_qt_no_pacote.py`,
  troque `test_o_pacote_leva_so_a_traducao_pt_br_do_qt` por:

```python
def test_o_pacote_leva_so_as_traducoes_do_qt_que_a_interface_usa(spec_executado):
    """`_instalar_traducao` (sigft/app_qt/main.py) carrega `qtbase_pt_BR` ou
    `qtbase_es`; o PyInstaller traria as ~100 traducoes do Qt (7 MB no Windows)."""
    dados = {destino for destino, _origem, _tipo in spec_executado["datas"]}

    assert "PySide6/translations/qtbase_pt_BR.qm" in dados
    assert "PySide6/Qt/translations/qtbase_pt_BR.qm" in dados
    assert "PySide6/Qt/translations/qtbase_es.qm" in dados
    assert not dados & {"PySide6/translations/qtbase_de.qm", "PySide6/translations/qt_pt_BR.qm"}
    # O filtro e da Qt: traducao de outro pacote e dado comum fica.
    assert {"outro_pacote/translations/app_de.qm", "assets/logo.png"} <= dados
```

  Em `sigft/app/conferencia.py`, troque `TRADUCAO_DA_QT = ("pt_BR", "qtbase")` (e o comentário)
  por:

```python
# As traduções que `_instalar_traducao` (sigft/app_qt/main.py) carrega: os "Sim",
# "Não" e "Cancelar" dos diálogos em português e em espanhol (o inglês é o do Qt).
TRADUCOES_DA_QT = (("pt_BR", "qtbase"), ("es", "qtbase"))
```

  e `_conferir_traducao` por:

```python
def _conferir_traducao() -> tuple[str, bool]:
    from PySide6.QtCore import QLocale, QTranslator

    pasta = _pasta_do_qt("TranslationsPath")
    linhas, tudo_certo = [], True
    for idioma, catalogo in TRADUCOES_DA_QT:
        tradutor = QTranslator()
        if tradutor.load(QLocale(idioma), catalogo, "_", pasta):
            linhas.append(f"  OK     Qt: traducao {idioma} ({tradutor.filePath()})")
        else:
            linhas.append(f"  FALHA  Qt: a traducao {idioma} ({catalogo}_{idioma}.qm) nao esta em "
                          f"{pasta} -- os dialogos sairiam em ingles")
            tudo_certo = False
    return "\n".join(linhas), tudo_certo
```

  No docstring de `conferir_qt`, "a tradução pt_BR" vira "as traduções pt_BR e es". Em
  `tests/test_conferencia_do_pacote.py`, depois de `test_a_conferencia_reprova_sem_a_traducao_pt_br`:

```python
def test_a_conferencia_reprova_sem_a_traducao_es(monkeypatch, tmp_path):
    """Sem ela, em espanhol, os dialogos saem com "Yes"/"No"/"Cancel"."""
    conferencia = _qt_com_pasta_trocada(monkeypatch, "TranslationsPath", tmp_path)

    relatorio, ok = conferencia.conferir_qt()

    assert ok is False
    assert _linha(relatorio, "traducao es").lstrip().startswith("FALHA")
```

  Em `tests/test_qt_robustez.py`, `test_traducao_pt_br_instalada` continua (os testes rodam em
  português); não muda.

- [ ] **Step 9: verificação**

```bash
.venv/bin/python -m pytest -q tests/test_qt_idioma_abertura.py tests/test_qt_configuracao.py \
  tests/test_qt_main.py tests/test_qt_robustez.py tests/test_qt_no_pacote.py \
  tests/test_conferencia_do_pacote.py tests/test_qt_tema.py tests/test_qt_letra.py
bash scripts/check.sh
for args in "" "--idioma es" "--idioma en --letra grande"; do
  QT_QPA_PLATFORM=offscreen .venv/bin/python frontend.py --smoke $args | tail -1
done
```

- [ ] **Step 10: commit**

```bash
git add sigft/app_qt/escolha_de_idioma.py sigft/app_qt/reinicio.py sigft/app_qt/main.py \
  sigft/app_qt/views/configuracao.py sigft/app_qt/catalogo.py sigft/app_qt/estilo.py SIG-FT.spec \
  sigft/app/conferencia.py tests/conftest.py tests/test_qt_idioma_abertura.py tests/test_qt_configuracao.py \
  tests/test_qt_no_pacote.py tests/test_conferencia_do_pacote.py
git commit -m "$(cat <<'EOF'
Idioma: pergunta na primeira abertura, secao Idioma e Reiniciar agora

Sem idioma guardado, a caixa Idioma / Language aparece antes da janela principal,
que ja nasce no escolhido. Na Configuracao a escolha e guardada no clique e
Reiniciar agora abre outra instancia (recusa com tarefa rodando). Os botoes do
Qt seguem o idioma (qtbase_es no pacote e na conferencia); --idioma no smoke.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RSbK7jX9qvsvyZKqnojmij
EOF
)"
```

---
### Task 4: Textos compartilhados I (textos de diálogo, dicas, resumo do lote e as peças de `widgets/`)

**Files:**
- Modify: `sigft/app/textos_dialogos.py`, `sigft/app/textos_dicas.py`, `sigft/app/resumo_lote.py`
- Modify: todos os `sigft/app_qt/widgets/*.py` com texto: `arrastar.py`, `atividade.py`, `console.py`,
  `dialogos_selecao.py`, `dialogs.py`, `espera.py`, `marca.py`, `module_frame.py`, `mural.py`,
  `painel_janela.py`, `paleta.py`, `pickers.py`, `puxador_console.py`, `resumo_lote.py`,
  `revisao_portal.py`, `trava_robo.py` (e entram na guarda sem mudar: `abas.py`, `blocos.py`,
  `controles.py`, `__init__.py`)
- Modify: `sigft/app_qt/views/home.py` (uma linha: a dica da barra por `textos_dicas.dica_da_barra`)
- Modify: `sigft/app/idiomas/es.json`, `en.json`
- Modify: `tests/test_textos_da_interface.py` (`CONVERTIDOS`, `NAO_E_INTERFACE`), `tests/test_qt_dicas.py`
- Create: `tests/test_qt_idioma_telas.py`

**Interfaces:**
- Consumes: `idioma.t`, `idioma.marcar` (Task 2); `tests/_idioma.em_idioma`, `ainda_em_portugues` (Task 2).
- Produces: `textos_dicas.dicas_da_classe(classe) -> dict[str, str]` **já traduzido** (com
  `{portal}` preenchido); `textos_dicas.dica_da_barra(chave) -> str`; `textos_dicas.PORTAL`
  continua (marcado). `resumo_lote.frase_da_contagem`, `frase_do_fim` e `Grupo.rotulo` devolvem no
  idioma da sessão. Os widgets que recebem texto (`PausaLoginDialog(texto_botao=)`,
  `RetryLockDialog(mensagem=)`, `SelecaoMultiplaDialog(titulo=, instrucao=, texto_confirmar=)`,
  `TabelaSelecaoDialog(titulo=, instrucao=, texto_confirmar=)`, `FileQueueList(rotulo=, texto_adicionar=)`,
  `DialogosDeEspera.pausar_e_esperar(texto_botao=)`) passam a ter padrão `None`, traduzido dentro.

- [ ] **Step 1: a guarda acusa.** Em `tests/test_textos_da_interface.py`, troque `CONVERTIDOS` por:

```python
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
)
```

  Rode `.venv/bin/python -m pytest -q tests/test_textos_da_interface.py -k passa_por_t` → FAIL, com
  a lista dos literais de cada arquivo (cerca de 160). A mesma lista sai de
  `.venv/bin/python tools/textos_da_interface.py --literais <arquivo>`.

- [ ] **Step 2: o teste em tela (`tests/test_qt_idioma_telas.py`, novo)**

```python
"""Cada parte convertida da interface, montada em espanhol e em inglês (2026-10-22).

`ainda_em_portugues` (tests/_idioma.py) acusa o texto à vista que tem, no
catálogo, uma tradução diferente dele mesmo: a constante marcada (`marcar`) que
chegou à tela sem `t()`, que a guarda estática não vê. Cada tarefa do plano
`docs/superpowers/plans/2026-10-22-configuracao-e-idioma.md` acrescenta as suas.
"""
import threading

import pytest

from _idioma import ainda_em_portugues, em_idioma

IDIOMAS = ["es", "en"]


def _sem_conteudo(_pai):
    pass


@pytest.mark.parametrize("codigo", IDIOMAS)
def test_pecas_compartilhadas(qt_interface, qtbot, codigo):
    from sigft.app_qt.widgets import atividade, console, dialogos_selecao, dialogs, painel_janela, pickers
    from sigft.app_qt.widgets import resumo_lote as janela_resumo

    with em_idioma(codigo):
        pecas = [
            console.ConsoleFrame(),
            janela_resumo.JanelaResumoDoLote(None, "Upload duplicadas", [
                ("4500063671.0001: [Erro] ficha não encontrada", "erro"),
                ("[Aviso] tabela vazia", "aviso")]),
            dialogs.PausaLoginDialog(None, mensagem="x", evento_espera=threading.Event()),
            dialogs.RetryLockDialog(None, evento_espera=threading.Event(), resultado={}),
            dialogos_selecao.SelecaoMultiplaDialog(None, itens=["A", "B"], com_selecionar_todos=True),
            pickers.FileQueueList(chave="t.fila"),
            atividade.FaixaDeAtividade(),
            painel_janela.JanelaPainel(None, titulo="x", montar=_sem_conteudo),
        ]
        for peca in pecas:
            qtbot.addWidget(peca)
            assert ainda_em_portugues(peca, codigo) == set(), type(peca).__name__


@pytest.mark.parametrize("codigo", IDIOMAS)
def test_frases_do_resumo_e_dicas_no_idioma(codigo):
    from sigft.app import idioma, resumo_lote, textos_dicas

    with em_idioma(codigo):
        traducoes = idioma.catalogo(codigo)
        erros, juncao, aviso = idioma.t("{n} erros", n=2), idioma.t(" e "), idioma.t("{n} aviso", n=1)
        assert resumo_lote.frase_da_contagem(2, 1) == erros + juncao + aviso
        assert resumo_lote.frase_da_contagem(2, 1) != "2 erros e 1 aviso"
        dicas = textos_dicas.dicas_da_classe(type("ModuloCopiaFichas", (), {}))
        assert "{portal}" not in dicas["btn_robo_novo"]
        assert traducoes[textos_dicas.PORTAL] in dicas["btn_robo_novo"]
```

  (O `type("ModuloCopiaFichas", (), {})` é uma classe com o nome certo: `dicas_da_classe` olha o
  `__name__` de cada classe do MRO.)

  Rode `.venv/bin/python -m pytest -q tests/test_qt_idioma_telas.py` → FAIL (catálogos vazios,
  frases ainda montadas em português).

- [ ] **Step 3: `textos_dialogos.py`.** Acrescente `from sigft.app.idioma import marcar, t`. Cada
  constante de texto ganha `marcar(...)` em volta do valor (`TEXTO_CONTINUAR`, `MSG_LOGIN_SOLTAR_ROBO`,
  `MSG_LOGIN_LOTE`, `MSG_EXCEL_BLOQUEADO`, `MSG_LOGIN_APAGAR_LMR`, `MSG_LOGIN_LMR`,
  `MSG_LOGIN_CONFERIR_AUTORIZACOES`, `MSG_LOGIN_NOVA_FICHA`, `MSG_LOGIN_PAGINA_PRINCIPAL`,
  `TEXTO_COMECAR_EXCLUSAO`); em `TEXTOS_TRAVADOS`, cada valor de texto (`titulo`, `explicacao`,
  `rodape`, `repetir`, `seguir`). `LOGIN_NECESSARIO` NÃO (é sentinela). As funções:

```python
def msg_excel_bloqueado(caminho: object) -> str:
    """A mesma mensagem, NOMEANDO o arquivo travado.

    [CP D] Quando a janela passou a servir os 7 pontos de gravação que antes
    falhavam calados, "o arquivo _STATUS_PMIB" deixou de bastar: o `pdm` grava
    ficha e template, o `analyzer` grava relatório, o `autospec` grava a ficha
    preenchida. Dizer QUAL arquivo fechar é a diferença entre o usuário
    resolver em 5 segundos e ficar procurando.
    """
    import ntpath

    nome = ntpath.basename(str(caminho)) or str(caminho)
    return t("O arquivo '{nome}' está aberto em outro programa (provavelmente o Excel), e por "
             "isso não pôde ser salvo.\n\nFECHE O ARQUIVO e clique em 'Tentar Novamente'.", nome=nome)


def msg_falha_ao_salvar(nome_secao: str) -> str:
    """Mensagem do `ModuloUploadConditions` quando uma aba não salva."""
    return t("Falha ao salvar a aba '{secao}'. Ocorreu um erro no site.\n\n"
             "1. Resolva o problema no navegador.\n"
             "2. Clique em SALVAR no site.\n"
             "3. Clique no botão abaixo para continuar.", secao=nome_secao)


def msg_ficha_preenchida(pmib: str) -> str:
    """Mensagem do `ModuloCopiaFichas` ao terminar uma ficha."""
    return t("Ficha {pmib} preenchida!\n\n"
             "Verifique na tela e copie as pendências (se houverem) do painel ao lado.\n"
             "Após clicar em SALVAR no site, clique no botão abaixo.", pmib=pmib)


def texto_dos_avisos(inicio: str, avisos: int, nao_gravados: int) -> str:
    """O texto da janela "Concluído com avisos" do PMIB Manager (Gestão e
    autorizações de Itaipu). [2026-10-06] Os arquivos que ficaram sem gravar vêm
    primeiro, com a contagem do resumo do fim do log (`travas.TITULO_RESUMO`): é
    o que a pessoa precisa resolver. As duas interfaces usam esta (era uma cópia
    em cada tela).

    `inicio` chega traduzido (quem chama traduz).
    """
    partes = []
    if nao_gravados:
        partes.append(t("{n} arquivo(s) não foram gravados nesta rodada: o motivo de cada um "
                        "e o que fazer estão no fim do log", n=nao_gravados))
    outros = avisos - (1 if nao_gravados else 0)
    if outros > 0:
        partes.append(t("{n} aviso(s) pedem atenção (procure as linhas [AVISO] no log)", n=outros))
    return t("{inicio}, mas {partes}.", inicio=inicio, partes=t("; e ").join(partes))
```

  (Em `msg_excel_bloqueado`, o comentário longo sobre o `ntpath`, que fica entre o docstring e o
  `import ntpath`, continua lá, palavra por palavra.)

  Os usos dessas constantes nas telas ganham `t()` nas Tasks 6 a 9; os dos widgets, aqui (Step 6).

- [ ] **Step 4: `textos_dicas.py`.** Acrescente `from sigft.app.idioma import marcar, t`. `PORTAL`
  vira `marcar("Abre o navegador no Portal PMIB (o login é feito por você).")`. Todo valor de
  `DICAS` e de `DICAS_DA_BARRA_DA_HOME` ganha `marcar(...)`; os que eram f-string com `{PORTAL}`
  viram texto com o lugar `{portal}` (ex.: `"btn_web_mem": marcar("Envia ao portal o que a IA
  acabou de processar, sem precisar do Excel. {portal}")`). As duas funções:

```python
def dicas_da_classe(classe) -> dict[str, str]:
    """As dicas de `classe` e das classes-mãe dela (a filha ganha), no idioma da
    sessão, com a frase do portal no lugar de `{portal}`."""
    juntas: dict[str, str] = {}
    for mae in reversed(classe.__mro__):
        juntas.update(DICAS.get(mae.__name__, {}))
    portal = t(PORTAL)
    return {atributo: t(dica, portal=portal) for atributo, dica in juntas.items()}


def dica_da_barra(chave: str) -> str:
    """A dica do botão `chave` da barra da Home, no idioma da sessão ("" sem dica)."""
    dica = DICAS_DA_BARRA_DA_HOME.get(chave)
    return t(dica) if dica else ""
```

  Em `views/home.py` (`_aplicar_dicas`), troque `dica = textos_dicas.DICAS_DA_BARRA_DA_HOME.get(chave)`
  por `dica = textos_dicas.dica_da_barra(chave)`. Em `tests/test_qt_dicas.py`
  (`test_a_dica_chega_ao_botao`), troque as duas comparações por
  `textos_dicas.dicas_da_classe(type(tela))["btn_robo_novo"]` e
  `textos_dicas.dicas_da_classe(type(upload))["btn_ia"]` (o valor cru agora tem `{portal}`).

- [ ] **Step 5: `sigft/app/resumo_lote.py`.** Acrescente `from sigft.app.idioma import marcar, t`.
  `SEM_CODIGO = marcar("Sem código PMIB")`; `Grupo.rotulo` devolve `self.codigo or t(SEM_CODIGO)`.
  O prefixo que `nome_da_tela` tira passa a valer também em inglês (o título da tela chega
  traduzido): `_PREFIXO_MODULO = re.compile(r"^\s*(módulo|module)\s*:\s*", re.IGNORECASE)`. Troque
  `contagem`, `frase_da_contagem` e `frase_do_fim` por:

```python
def frase_da_contagem(erros: int, avisos: int) -> str:
    """"2 erros e 1 aviso", no idioma da sessão. Singular e plural são chaves
    inteiras (cada idioma faz o seu plural)."""
    partes = []
    if erros:
        partes.append(t("{n} erro", n=erros) if erros == 1 else t("{n} erros", n=erros))
    if avisos:
        partes.append(t("{n} aviso", n=avisos) if avisos == 1 else t("{n} avisos", n=avisos))
    return t(" e ").join(partes) if partes else t("nenhum erro nem aviso")


def frase_do_fim(titulo: str, erros: int, avisos: int, *, falhou: bool = False) -> str:
    """A frase do aviso do Windows no fim da tarefa."""
    if falhou:
        return t("{titulo} parou com erro. Veja o console.", titulo=titulo)
    if erros or avisos:
        return t("{titulo} terminou com {contagem}.", titulo=titulo,
                 contagem=frase_da_contagem(erros, avisos))
    return t("{titulo} terminou sem erro nem aviso.", titulo=titulo)
```

  (Procure outros usos de `contagem(`: `grep -rn "resumo_lote.contagem\|contagem(" sigft`. Hoje só
  `frase_da_contagem` a usa; se aparecer outro, troque pelas chaves inteiras do mesmo jeito.)
  `gravar_log` grava o que foi ao console: fica como está (o literal de data que a guarda acusar vai
  para `NAO_E_INTERFACE`, motivo "formato de data do log").

- [ ] **Step 6: as peças de `widgets/`.** Em cada arquivo, `from sigft.app.idioma import marcar, t`
  (só o que usar) e as trocas abaixo; todo o resto que a guarda acusar segue as Regras de conversão.

  `console.py`: `FILTROS = (("tudo", marcar("Tudo")), ("avisos", marcar("Avisos")), ("erros", marcar("Erros")))`;
  `TEXTO_BUSCA`, `TEXTO_COPIAR`, `TEXTO_COPIADO`, `DICA_COPIAR` em `marcar`; nos usos
  (`QPushButton(texto)` do laço dos filtros, `setPlaceholderText`, `QPushButton(TEXTO_COPIAR)`,
  `setToolTip`, os dois `setText`) entra `t(...)`.

  `espera.py`: `TEXTO_ESPERA_EXCEL` e `TEXTO_ESPERA_TRAVADOS` em `marcar`; as três frases do aviso
  viram `t("{titulo}: responda Sim ou Não.", titulo=titulo)`,
  `t("{titulo}: o SIG-FT espera a sua resposta.", titulo=titulo)` e
  `t("{titulo}: aperte OK para seguir.", titulo=titulo)`. As duas esperas com texto próprio:

```python
    def pausar_e_esperar(self, mensagem: str, texto_botao: str | None = None) -> None:
        # `texto_botao=None`: o diálogo põe o padrão traduzido (`PausaLoginDialog`).
        self._abrir_e_esperar(lambda evento, _res: dialogs.PausaLoginDialog(
            self, mensagem=mensagem, evento_espera=evento, texto_botao=texto_botao),
            aviso=aviso_windows.primeira_linha(mensagem))

    def perguntar_retry_excel(self, caminho: object = None) -> bool:
        mensagem = msg_excel_bloqueado(caminho) if caminho is not None else t(MSG_EXCEL_BLOQUEADO)
        resultado = self._abrir_e_esperar(lambda evento, res: dialogs.RetryLockDialog(
            self, mensagem=mensagem, evento_espera=evento, resultado=res), aviso=t(TEXTO_ESPERA_EXCEL))
        return bool(resultado.get("retry", False))
```

  e, em `perguntar_arquivos_travados`, `aviso=t(TEXTO_ESPERA_TRAVADOS)`. O import de `TEXTO_CONTINUAR`
  em `espera.py` sai (ruff F401), porque o padrão agora mora no diálogo.

  `dialogs.py`: `PausaLoginDialog(..., texto_botao: str | None = None)` com
  `texto_botao if texto_botao is not None else t(TEXTO_CONTINUAR)`; `RetryLockDialog(..., mensagem: str | None = None, ...)`
  com `mensagem if mensagem is not None else t(MSG_EXCEL_BLOQUEADO)`; `titulo=t("Ação Manual Necessária")`,
  `titulo=t("Arquivo Bloqueado")`, `t("Tentar Novamente")`, `t("Ignorar e Continuar")`, `t("Todos")`.

  `dialogos_selecao.py`: em `SelecaoMultiplaDialog` e `TabelaSelecaoDialog`, os parâmetros `titulo`,
  `instrucao` e `texto_confirmar` passam a `str | None = None`, e no começo do `__init__`:

```python
        titulo = titulo if titulo is not None else t("Seleção")
        instrucao = instrucao if instrucao is not None else t("Selecione um ou mais itens:")
        texto_confirmar = texto_confirmar if texto_confirmar is not None else t("Confirmar Seleção")
```

  (no `TabelaSelecaoDialog`, os padrões são `t("Seleção de Itens")` e `t("Selecione as linhas para processar:")`
  e `t("Confirmar Seleção")`). `t("Selecionar Todos")`, `t("Cancelar")`,
  `QMessageBox...(self, t("Aviso"), t("Selecione ao menos um item."))`. Em `ArquivosTravadosDialog`,
  `textos = TEXTOS_TRAVADOS[momento]` e cada `textos["..."]` que vai para a tela ganha `t(...)`; a linha
  do motivo vira `t("Motivo: {motivo}. {o_que_fazer}", motivo=motivo, o_que_fazer=o_que_fazer)`
  (o `motivo` e o `o_que_fazer` vêm de `core/travas` e ficam como vieram).

  `pickers.py`: `TEXTO_SEM_ARQUIVO`, `TEXTO_SEM_PASTA` em `marcar` e `t()` nos usos; em
  `FileQueueList`, `rotulo: str | None = None` e `texto_adicionar: str | None = None`, com
  `rotulo = rotulo if rotulo is not None else t("Planilhas PMIB Selecionadas")` e
  `texto_adicionar = texto_adicionar if texto_adicionar is not None else t("Adicionar Fichas")` no
  começo; `t("Remover Seleção")`, `t("Limpar Tudo")`.

  `arrastar.py`: `TEXTO_SEM_RECENTES`, `DICA_ARRASTAR`, `DICA_RECENTES` em `marcar`; o menu usa
  `t(TEXTO_SEM_RECENTES)`; a dica de arrasto:

```python
        dica_de_arrasto = t(DICA_ARRASTAR)
        if dica_de_arrasto not in dica:
            widget.setToolTip(f"{dica}\n\n{dica_de_arrasto}" if dica else dica_de_arrasto)
```

  e `setToolTip(t(DICA_RECENTES))` na seta.

  `atividade.py`: os símbolos ficam fora da chave:

```python
            self.rotulo.setText("✓  " + t("Terminou em {tempo}", tempo=decorrido))
            ...
            self.rotulo.setText("✗  " + t("Parou com erro depois de {tempo}. Veja o console.", tempo=decorrido))
            ...
        partes = ["⏳  " + t("Rodando"), relogio(time.monotonic() - self._inicio)]
```

  `module_frame.py`: `t("Módulo indisponível")` nos dois `QMessageBox.warning`; `aplicar_dicas` não
  muda (`dicas_da_classe` já traduz).

  `mural.py`: cada valor de `ROTULO_FAIXA` e de `EXPLICACAO_FAIXA` em `marcar` (os seis de cada, inclusive
  "ATRASADO" e "TRAVADA", que a guarda não vê: palavra única em maiúsculas); os usos
  `blocos.rotulo_tk(t(ROTULO_FAIXA[faixa]), ...)` e `t(EXPLICACAO_FAIXA[faixa])`;
  `t("{total} atividade(s) pedindo atenção", total=total)`,
  `t("Nada pendente para hoje nem para os próximos dias.")`, `t("(sem descrição)")`. O texto que vem
  da planilha (`item["descricao"]`, grupo, com quem) fica como veio.

  `painel_janela.py`: `t("Fechar")`. O `titulo=` que recebe chega traduzido.

  `paleta.py`: `TEXTO_DICA`, `TEXTO_VAZIO` em `marcar`, `t()` nos usos.

  `marca.py`: `DICA = marcar("Voltar ao início")`, `setToolTip(t(DICA))`,
  `setAccessibleName(t("SIG-FT, voltar ao início"))`. `NOME = "SIG-FT System"` é o nome do
  produto na marca: fica (vai para `NAO_E_INTERFACE`, Step 7).

  `puxador_console.py`: a dica em `marcar` e `t()` no `setToolTip`.

  `resumo_lote.py` (widget): `TEXTO_COPIAR`, `TEXTO_COPIADO`, `TEXTO_LOG`, `TEXTO_FECHAR`,
  `DICA_COPIAR`, `DICA_LOG` em `marcar` e `t()` nos usos;
  `self.setWindowTitle(t("Resumo: {tela}", tela=resumo_lote.nome_da_tela(titulo)))`;
  `blocos.rotulo(t("Terminou com {contagem}.", contagem=resumo_lote.frase_da_contagem(erros, avisos)), ...)`;
  `t("Não consegui abrir o log: {erro}", erro=erro)`.

  `revisao_portal.py`: `TITULO`, `TEXTO_SEM_ERROS`, `TEXTO_TODAS`, `TEXTO_CANCELAR`, `EXPLICACAO` e
  `MSG_NADA_SOBROU` em `marcar`; os nomes das `COLUNAS` em `marcar` (`(marcar("Ficha"), 160, "w")`...)
  e `t(nome)` onde o cabeçalho é montado; `QMessageBox.warning(parent, t(TITULO), t(MSG_NADA_SOBROU))`
  e `setWindowTitle(t(TITULO))`. As linhas que vão ao `log(...)` ficam em português (console):
  `MSG_CANCELADO` e `MSG_TODAS` só vão ao console e vão para `NAO_E_INTERFACE`; o
  `log(MSG_NADA_SOBROU)` continua com a constante crua.

  `trava_robo.py`: `NOME_DO_ROBO = "outro robô"` só aparece no console: `NAO_E_INTERFACE`.

- [ ] **Step 7: o que fica em português.** Rode a guarda de novo e, para o que sobrou e é dado (não
  interface), acrescente em `NAO_E_INTERFACE` (cada bloco com o comentário do motivo), por exemplo:

```python
NAO_E_INTERFACE: dict[str, set[str]] = {
    # O nome do produto na marca do menu: não se traduz.
    "sigft/app_qt/widgets/marca.py": {"SIG-FT System"},
    # Só vão ao console (o console não muda de idioma: spec, "O que muda de idioma").
    "sigft/app_qt/widgets/revisao_portal.py": {
        "Cancelado na revisão antes do portal.",
        "Seguindo com todas as fichas, inclusive as com erro.",
    },
    "sigft/app_qt/widgets/trava_robo.py": {"outro robô"},
}
```

  Acrescente outros só se forem dado de verdade (planilha, portal, log); texto que a pessoa lê vai
  para `t()`. Rode até `-k passa_por_t` e `-k ainda_existe` passarem.

- [ ] **Step 8: as traduções.** `.venv/bin/python tools/textos_da_interface.py --faltando es` imprime o
  JSON das chaves sem tradução. Escreva as traduções em `sigft/app/idiomas/es.json` (e o mesmo para
  `en`), seguindo o Glossário e o estilo (acima); depois
  `.venv/bin/python tools/textos_da_interface.py --arrumar` e
  `.venv/bin/python tools/textos_da_interface.py` → `es: 0 faltando, 0 sobrando` e `en: 0 faltando, 0 sobrando`.
  Exemplos do tom esperado (as chaves exatas são as do código):

```json
{
  " e ": " y ",
  "{n} erro": "{n} error",
  "{n} erros": "{n} errores",
  "{titulo} terminou com {contagem}.": "{titulo} terminó con {contagem}.",
  "Arquivo Bloqueado": "Archivo bloqueado",
  "Ignorar e Continuar": "Ignorar y continuar",
  "Tentar Novamente": "Reintentar",
  "Tudo": "Todo"
}
```

  e em `en.json` `" e ": " and "`, `"{n} erros": "{n} errors"`, `"Tentar Novamente": "Try again"`,
  `"Tudo": "All"`.

- [ ] **Step 9: verificação**

```bash
.venv/bin/python -m pytest -q tests/test_textos_da_interface.py tests/test_qt_idioma_telas.py \
  tests/test_textos_dialogos.py tests/test_resumo_lote.py tests/test_qt_dicas.py tests/test_qt_console.py \
  tests/test_qt_arrastar.py tests/test_qt_dialogos_da_tela.py tests/test_qt_dialogos_de_acao_medidas.py \
  tests/test_qt_dialogos_selecao.py tests/test_qt_aviso_windows.py tests/test_qt_home_paineis.py
bash scripts/check.sh
QT_QPA_PLATFORM=offscreen .venv/bin/python frontend.py --smoke --idioma es | tail -1
```

  Os testes de medida dos diálogos (`test_qt_dialogos_de_acao_medidas.py`) e do console rodam em
  português e não mudam. Se algum quebrar, é conversão errada (um `t()` que mudou o texto em
  português): corrija o código, não o teste.

- [ ] **Step 10: commit**

```bash
git add sigft/app/textos_dialogos.py sigft/app/textos_dicas.py sigft/app/resumo_lote.py \
  sigft/app_qt/widgets/ sigft/app_qt/views/home.py sigft/app/idiomas/es.json sigft/app/idiomas/en.json \
  tests/test_textos_da_interface.py tests/test_qt_idioma_telas.py tests/test_qt_dicas.py
git commit -m "$(cat <<'EOF'
Idioma: textos de dialogo, dicas, resumo do lote e as pecas de widgets em t()

Constantes marcadas e traduzidas onde aparecem; frases com valor viram chaves com
{nome}; plural por chave inteira. O que vai ao console fica em portugues.
Traducoes es/en dessas chaves; teste em tela das pecas nos dois idiomas.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RSbK7jX9qvsvyZKqnojmij
EOF
)"
```

---

### Task 5: Textos compartilhados II (menu, Home, engrenagem, Ctrl+K, splash, nome, atualização)

**Files:**
- Modify: `sigft/app_qt/catalogo.py`, `sigft/app_qt/main.py`, `sigft/app_qt/views/home.py`,
  `sigft/app_qt/views/configuracao.py`, `sigft/app_qt/nome.py`, `sigft/app_qt/aviso_windows.py`,
  `sigft/app_qt/atualizacao.py`, `sigft/app_qt/novidades.py`, `sigft/app_qt/pasta_de_logs.py`,
  `sigft/app_qt/views/nao_migrada.py`, `sigft/app_qt/reinicio.py`, `sigft/app_qt/escolha_de_idioma.py`,
  `sigft/app/atualizacao_textos.py`
- Modify: `sigft/app/idiomas/es.json`, `en.json`
- Modify: `tests/test_textos_da_interface.py`, `tests/test_qt_idioma_telas.py`, `tests/test_qt_letra.py`
  (`test_seletor_de_letra_num_lugar_so`), `tests/test_qt_paleta.py` (se algum teste ler `catalogo.ACOES[i][1]` de tema/letra)

**Interfaces:**
- Consumes: Tasks 1 a 4.
- Produces: `catalogo.AcaoDoCtrlK(chave, texto, icone, palavras, nome="")` (NamedTuple; `texto` pode ter
  `{nome}`); `catalogo.ACOES: tuple[AcaoDoCtrlK, ...]`; `catalogo.comandos()` devolve os textos e as
  palavras já traduzidos (as palavras em português continuam valendo na busca).

Decisão desta tarefa: o Ctrl+K busca pelo texto traduzido **e** pelas palavras em português e no
idioma (`palavras` traduzidas + as originais): quem trocou de idioma e ainda digita em português acha.

- [ ] **Step 1: a guarda e o teste em tela acusam.** Em `CONVERTIDOS`, acrescente:

```python
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
    "sigft/app_qt/tema.py",
    "sigft/app_qt/views/__init__.py",
    "sigft/app_qt/views/configuracao.py",
    "sigft/app_qt/views/home.py",
    "sigft/app_qt/views/nao_migrada.py",
```

  Em `tests/test_qt_idioma_telas.py`, acrescente:

```python
@pytest.fixture
def janela(qt_interface, qtbot, tmp_path, monkeypatch):
    """A janela principal, montada DENTRO do idioma do teste (cada tela lê os textos ao nascer)."""
    from sigft.app_qt import main as qmain

    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))

    def montar():
        principal = qmain.SIG_FT_App()
        principal.fechar_sem_perguntar = True
        qtbot.addWidget(principal)
        return principal
    return montar


@pytest.mark.parametrize("codigo", IDIOMAS)
def test_menu_home_configuracao_e_ctrl_k(janela, codigo, monkeypatch):
    with em_idioma(codigo):
        principal = janela()
        home = principal.telas["Home"]
        monkeypatch.setattr(principal, "get_key", lambda _chave: "chave-de-teste")
        abertas = [home.abrir_configuracao(), home.abrir_janela_chaves_api(),
                   home.abrir_janela_modelos_ia(), home.abrir_janela_gastos_ia()]
        assert ainda_em_portugues(principal, codigo) == set()
        for aberta in abertas:
            assert ainda_em_portugues(aberta, codigo) == set(), aberta.windowTitle()
        paleta = principal.abrir_paleta()
        assert ainda_em_portugues(paleta, codigo) == set()
        paleta.close()


@pytest.mark.parametrize("codigo", IDIOMAS)
def test_splash_pergunta_do_nome_e_do_idioma(qt_interface, qtbot, codigo):
    from sigft.app_qt import escolha_de_idioma, nome
    from sigft.app_qt.main import SplashScreen

    with em_idioma(codigo):
        for peca in (SplashScreen(), nome.PerguntaDoNome(), escolha_de_idioma.PerguntaDoIdioma()):
            qtbot.addWidget(peca)
            assert ainda_em_portugues(peca, codigo) == set(), type(peca).__name__


@pytest.mark.parametrize("codigo", IDIOMAS)
def test_saudacao_no_idioma(codigo):
    from datetime import datetime

    from sigft.app import idioma
    from sigft.app_qt import nome

    with em_idioma(codigo):
        manha = nome.saudacao(datetime(2026, 10, 22, 9), "Ana")
        assert manha == f"{idioma.t('Bom dia')}, Ana" and not manha.startswith("Bom dia")
```

  Rode os dois arquivos → FAIL.

- [ ] **Step 2: `catalogo.py`.** `from sigft.app.idioma import marcar, t`. Em `MENU`, o texto de cada
  item em `marcar` (`("secao", marcar("Início da Ficha"))`, `("botao", marcar("1. Cria Fichas PMIB"), "CriaFichas")`...).
  Em `MODULOS`, o título e a descrição de cada um em `marcar`. Em `ACOES_DA_HOME`,
  `ACAO_CONFIGURACAO` e `ACOES_DA_CONFIGURACAO`, o `texto` e as `palavras` em `marcar`. Em
  `SELETOR_TEMA` e `SELETOR_LETRA`, o texto e a dica em `marcar`. Em `SECOES_DA_CONFIGURACAO`, os
  títulos em `marcar`. `SUFIXO_BLOQUEADO`, `MSG_TAREFA_EM_ANDAMENTO` e `MSG_ABERTURA_FALHOU` em
  `marcar`. Troque `dica_do_menu`, o bloco de `ACOES` e `comandos` por:

```python
def dica_do_menu(alvo: str) -> str:
    """A dica do botão do menu lateral: a mesma descrição do cartão da Home."""
    descricao = next((t(d) for chave, _t, d in MODULOS if chave == alvo), "")
    if alvo in TELAS_BLOQUEADAS:
        return (descricao + "\n\n" if descricao else "") + t("Bloqueado nesta versão.")
    return descricao
```

```python
class AcaoDoCtrlK(NamedTuple):
    """Uma ação da caixa do Ctrl+K (além dos módulos)."""
    chave: str
    texto: str          # marcado; pode ter `{nome}` (o tema, a letra)
    icone: str          # nome de `icones.NOMES`
    palavras: str       # marcado; o que mais a busca acha
    nome: str = ""      # marcado; o valor de `{nome}` no texto


# As ações do Ctrl+K além dos módulos. Quem faz cada uma é
# `main.SIG_FT_App.executar_comando`; `tests/test_qt_paleta.py` cobra que toda
# chave tenha quem a faça. Os textos são traduzidos em `comandos()`.
ACOES = (
    AcaoDoCtrlK("inicio", marcar("Início"), "house", marcar("home tela inicial")),
    *(AcaoDoCtrlK(a.chave, a.texto, a.icone, a.palavras) for a in ACOES_QUE_A_HOME_FAZ),
    AcaoDoCtrlK("logs", marcar("Abrir logs"), "folder-open", marcar("pasta log")),
    *(AcaoDoCtrlK(f"tema_{escolha}", marcar("Tema: {nome}"), icone, marcar("aparencia cor"), texto)
      for escolha, texto, icone, _dica in SELETOR_TEMA),
    *(AcaoDoCtrlK(f"letra_{escolha}", marcar("Letra: {nome}"), "settings",
                  marcar("tamanho fonte aparencia"), texto)
      for escolha, texto, _dica in SELETOR_LETRA),
)


SUFIXO_BLOQUEADO = marcar(" (bloqueado)")


def comandos() -> list[Comando]:
    """Os módulos (na ordem dos cartões da Home) e as ações, no idioma da sessão.
    O módulo bloqueado aparece como no menu: apagado, com a mesma dica, e não se
    escolhe. A busca acha pelas palavras traduzidas E pelas em português."""
    no_menu = {item[2]: t(item[1]) for item in MENU if item[0] == "botao"}
    lista = []
    for alvo, titulo, _descricao in MODULOS:
        bloqueado = alvo in TELAS_BLOQUEADAS
        lista.append(Comando(
            f"tela:{alvo}", t(titulo) + (t(SUFIXO_BLOQUEADO) if bloqueado else ""), ICONE_DA_TELA[alvo],
            f"{no_menu.get(alvo, '')} {alvo}", bloqueado=bloqueado, dica=dica_do_menu(alvo)))
    for acao in ACOES:
        texto = t(acao.texto, nome=t(acao.nome)) if acao.nome else t(acao.texto)
        lista.append(Comando(f"acao:{acao.chave}", texto, acao.icone, f"{t(acao.palavras)} {acao.palavras}"))
    return lista
```

  Em `tests/test_qt_letra.py`, `test_seletor_de_letra_num_lugar_so`: troque as duas últimas linhas por

```python
    na_paleta = {c.chave: c.texto for c in catalogo.comandos()}
    for escolha, texto, _dica in catalogo.SELETOR_LETRA:
        assert na_paleta[f"acao:letra_{escolha}"] == f"Letra: {texto}"
```

  (`tests/test_qt_paleta.py::test_acoes_da_home_num_lugar_so` lê `a[1]` e `a[2]` só das ações da Home,
  que continuam sem `{nome}`: não muda.)

  Ficam em português e vão para `NAO_E_INTERFACE["sigft/app_qt/catalogo.py"]` (motivo: chave de tela,
  não texto): as chaves `"Home"` e `"Translator"` de `ICONE_DA_TELA` e qualquer outro nome de tela que a
  guarda acusar.

- [ ] **Step 3: `main.py`.** `from sigft.app.idioma import t` (o módulo `idioma` já está importado
  desde a Task 2; use `idioma.t` ou importe `t`, um só jeito no arquivo). Trocas:

```python
        home = QPushButton(f" {t('Home')}", objectName="home")
        ...
        home.setToolTip(t("Volta à tela inicial: os módulos, a engrenagem da configuração e os gastos de IA."))
        ...
                lay.addWidget(QLabel(t(item[1]).upper(), objectName="secao"))
        ...
            botao = QPushButton(f" {t(texto)}")
```

  (a dica do "Home" mudou de propósito: chaves e modelos não estão mais na Home.) No `closeEvent`:
  `QMessageBox.question(self, t("Fechar o SIG-FT"), t(catalogo.MSG_TAREFA_EM_ANDAMENTO), ...)`. Em
  `abrir_principal`: `catalogo.MSG_ABERTURA_FALHOU.format(erro=...)` vira
  `t(catalogo.MSG_ABERTURA_FALHOU, erro=f"{type(erro).__name__}: {erro}")`. Na splash:

```python
        self.status = QLabel(t("Iniciando..."))
        ...
        def progredir(exibido, fracao):
            interface.na_interface(self.status.setText, t("Carregando: {nome}...", nome=exibido))
            interface.na_interface(self.barra.setValue, int(fracao * 1000))

        def falhar(exibido, erro):
            print(f"Erro ao carregar {exibido}: {erro}")
            interface.na_interface(self.status.setText, t("Erro em {nome}", nome=exibido))

        try:
            backends.carregar_todos(ao_progredir=progredir, ao_falhar=falhar)
            interface.na_interface(self.status.setText,
                                   t("Concluído em {segundos}s", segundos=f"{time.time() - inicio:.1f}"))
```

  e `_texto_da_versao` devolve `t("versão {versao}", versao=versao) if versao else t("versão de desenvolvimento")`.
  Ficam em português e vão para `NAO_E_INTERFACE["sigft/app_qt/main.py"]`, num bloco com o motivo:
  as chaves de tela (`"Home"`, `"Translator"`, `"Analyzer"` como chave de `TELAS`/`show_frame`), o
  título da janela (`f"SIG-FT v{_build_info.VERSAO} - GE Vernova"`: nome e versão), o aviso de quando a
  Qt não sobe (`f"A Qt não conseguiu iniciar:\n{texto}"`: antes de o idioma valer) e todas as linhas do
  relatório do `--smoke` (lido pelo Release, não pela pessoa), copiadas como a ferramenta as imprime.

- [ ] **Step 4: `views/home.py`.** `from sigft.app.idioma import marcar, t`. Os pontos que pedem cuidado:
  - `TEXTO_PROCURANDO`, `DESCRICAO_MODELOS_IA`, `SEM_PROVEDOR_IA` em `marcar`; cada segundo elemento de
    `CHAVES_API` em `marcar` (`("GEMINI", marcar("Gemini API Key:"))`); os valores de
    `ROTULOS_TAREFA_IA` e de `HomeView.ROTULO_PROVIDER_IA` em `marcar`. Onde aparecem: `_rotulo(t(texto), ...)`,
    `_Texto(t(DESCRICAO_MODELOS_IA))`, `_rotulo(t(ROTULOS_TAREFA_IA[tarefa]), ...)`, e
    `_rotulo_provider_ia` devolve `t(self.ROTULO_PROVIDER_IA[provider]) if provider in self.ROTULO_PROVIDER_IA else provider`
    (o `_provider_por_rotulo` é montado por ela: rótulo e busca no mesmo idioma, Regra 5).
  - O rótulo neutro "Usar o global" e o "Padrão do sistema (modelos atuais)" são **mostrados e
    comparados**: os três usos de `"Usar o global"` viram `t("Usar o global")` e
    `_rotulo_padrao_sistema_ia` devolve `t("Padrão do sistema (modelos atuais)")`.
  - `_rotulo_modelo_ia`:

```python
        tier_legivel = {"padrao": t("Padrão"), "economia": t("Economia"), "poder": t("Poder")}.get(
            fav["tier"], fav["tier"])
        return t("{rotulo} ({tier}, ${entrada} / ${saida} por 1M tokens)", rotulo=fav["rotulo"],
                 tier=tier_legivel, entrada=f"{fav['preco_input']:.2f}",
                 saida=f"{fav['preco_output']:.2f}")
```

    (o `rotulo` do favorito vem de `core/llm`, é nome de modelo: fica como veio.)
  - As mensagens com valor (`f"Não foi possível atualizar a lista de modelos ({erro_catalogo})..."`,
    `f"{len(...)} modelos disponíveis (...)"`, `f"Ao salvar: {provider} / {model}  (veio do {origem})"`,
    `f"  |  {n} tarefa(s) com modelo próprio (...)"`, a pergunta dos recomendados) viram chaves com `{nome}`
    (Regra 3). `f"(salvo) {provider} / {model_id}"` vira `t("(salvo) {provider} / {modelo}", provider=..., modelo=...)`.
  - Títulos dos painéis (`abrir_janela_*`: `titulo=t("Chaves de API")`...), botões, rótulos e as caixas
    (`QMessageBox.information(..., t("Sucesso"), t("Chaves API salvas com sucesso!\nTodos os módulos usarão as novas chaves."))`).
  - Os cartões: `_Card(alvo, t(titulo), t(descricao), self._ir)`; os botões da barra:
    `self._botao_da_barra(t(texto), variante, ICONE_DA_BARRA[chave])`; a engrenagem:
    `setToolTip(t(ACAO_CONFIGURACAO.texto))` e `setAccessibleName(t(ACAO_CONFIGURACAO.texto))`;
    `procurar_atualizacoes`: `botao.setText(t(TEXTO_PROCURANDO))` e `botao.setText(t(TEXTO_BOTAO_ATUALIZACOES))`.
  - O subtítulo e o texto de cima dos cartões: `t("Sistema Integrado de Gestão de Fichas Técnicas - GE Vernova")`
    e `t("Clique num módulo abaixo para abri-lo. Os botões desta barra abrem painéis em janela, para a Home ficar limpa.")`.

- [ ] **Step 5: `views/configuracao.py`.** `from sigft.app.idioma import marcar, t` (o `idioma` do módulo
  continua importado para a seção Idioma). `TITULO`, `TEXTO_AVISOS_WINDOWS`, `DICA_AVISOS_WINDOWS`,
  `TEXTO_CANAL_TESTES`, `TEXTO_IDIOMA_AO_REINICIAR`, `TEXTO_REINICIAR` em `marcar`. Usos:
  `super().__init__(home, titulo=t(TITULO), ...)`; `blocos.rotulo(t(titulo), ...)` nas seções;
  `self._botao_de_escolha(t(texto), escolha, t(dica))` nos seletores de tema e letra; o de idioma passa
  `idioma.NOMES[codigo]` sem `t()` (não se traduz); `blocos.botao(t(acao.texto), ...)` em `_botao_de_acao`;
  `setPlaceholderText(t(nome.TITULO))`; `CaixaDeMarcar(t(TEXTO_AVISOS_WINDOWS), ...)`,
  `setToolTip(t(DICA_AVISOS_WINDOWS))`, `CaixaDeMarcar(t(TEXTO_CANAL_TESTES), ...)`,
  `blocos.rotulo(t(TEXTO_IDIOMA_AO_REINICIAR), ...)`, `blocos.botao(t(TEXTO_REINICIAR), ...)`.

- [ ] **Step 6: os outros módulos da casca.**
  - `nome.py`: `TITULO`, `PERGUNTA`, `EXPLICACAO`, `TEXTO_SALVAR`, `TEXTO_AGORA_NAO`, `DICA_DA_SAUDACAO` em
    `marcar` e `t()` nos usos de `PerguntaDoNome` (e em `views/home.py`, `_Saudacao`:
    `setToolTip(t(nome.DICA_DA_SAUDACAO))`); `setPlaceholderText(t(TITULO))`. A saudação:

```python
def saudacao(agora: datetime, quem: str) -> str:
    """Boa noite (até 5h), Bom dia (até 12h), Boa tarde (até 18h), Boa noite;
    mais o nome, se houver. A spec dizia "Bom dia até 12h"; às 2h soava
    estranho e a madrugada virou "Boa noite" (2026-10-20).
    """
    if agora.hour < 5:
        inicio = marcar("Boa noite")
    elif agora.hour < 12:
        inicio = marcar("Bom dia")
    elif agora.hour < 18:
        inicio = marcar("Boa tarde")
    else:
        inicio = marcar("Boa noite")
    quem = (quem or "").strip()
    return t("{saudacao}, {nome}", saudacao=t(inicio), nome=quem) if quem else t(inicio)
```

  - `aviso_windows.py`: `TITULO_ESPERA = marcar("O SIG-FT está esperando você")` e `t(TITULO_ESPERA)` onde
    ele vai para `_mostrar`/`showMessage`. `TITULO_FIM = "SIG-FT"` não se traduz.
  - `sigft/app/atualizacao_textos.py`: `from sigft.app.idioma import marcar, t`; `TITULO`, `MSG_UAC`,
    `MSG_COMO_FUNCIONA`, `MSG_TAREFA_AO_ATUALIZAR`, `MSG_DOWNLOAD_CONFERIDO`, `TEXTO_ATUALIZAR`,
    `TEXTO_ATUALIZANDO`, `TEXTO_TENTAR_DE_NOVO`, `TEXTO_AGORA_NAO`, `TEXTO_O_QUE_MUDOU` em `marcar`;
    `notas_para_exibir` devolve `... or t("(Esta versão não trouxe notas.)")` (as notas, que vêm do
    CHANGELOG, ficam como vieram); as funções de frase:

```python
def resumo_da_versao(info: Atualizacao, versao_atual: str) -> str:
    """A linha de baixo do título: onde a pessoa está e o que vai receber.

    [2026-10-07] Com o instalador pequeno, o tamanho é o DELE, comparado com o
    do completo: é o ganho que a pessoa precisa ver.
    """
    partes = [t("Você está na v{versao}.", versao=versao_atual)]
    if info.publicado_em:
        detalhe = t("A v{versao} saiu em {data}", versao=info.versao, data=data_br(info.publicado_em))
    else:
        detalhe = t("A v{versao}", versao=info.versao)
    if info.incremental and info.tamanho:
        partes.append(detalhe + ".")
        if info.tamanho_completo:
            partes.append(t("A atualização tem {mb} MB: só o que mudou (o instalador completo tem "
                            "{completo} MB).", mb=mb(info.tamanho_mb), completo=mb(info.tamanho_completo_mb)))
        else:
            partes.append(t("A atualização tem {mb} MB: só o que mudou.", mb=mb(info.tamanho_mb)))
        return " ".join(partes)
    if info.tamanho:
        detalhe = t("{detalhe} e tem {mb} MB", detalhe=detalhe, mb=mb(info.tamanho_mb))
    partes.append(detalhe + ".")
    return " ".join(partes)


def titulo_do_aviso(info: Atualizacao) -> str:
    """[2026-10-07] Pelo canal de testes chega pré-lançamento: o título diz."""
    if info.prerelease:
        return t("Nova versão de teste disponível: v{versao}", versao=info.versao)
    return t("Nova versão disponível: v{versao}", versao=info.versao)


def msg_sem_verificar(versao_atual: str, motivo: str) -> str:
    return t("Você está na v{versao}.\n\n{motivo}", versao=versao_atual, motivo=motivo)


def msg_em_dia(versao_atual: str) -> str:
    return t("Você já está na versão mais recente (v{versao}).", versao=versao_atual)


def msg_erro_ao_procurar(erro: BaseException) -> str:
    return t("Não foi possível procurar atualizações.\n\n{erro}", erro=erro)


def msg_baixando(info: Atualizacao) -> str:
    return t("Baixando a v{versao} ({mb} MB)...", versao=info.versao, mb=mb(info.tamanho_mb))


def msg_caiu_no_completo(completo: Atualizacao) -> str:
    return t("A atualização pequena falhou. Baixando o instalador completo ({mb} MB)...",
             mb=mb(completo.tamanho_mb))


def msg_falhou(erro: BaseException) -> str:
    return t("Não foi possível atualizar: {erro}\n\nO SIG-FT continua nesta versão. Tente de novo; "
             "se o erro se repetir, avise quem cuida do SIG-FT. O detalhe completo fica no log "
             "(Documentos\\SIG-FT\\logs\\sigft.log).", erro=erro_curto(erro))
```

    (as frases em português saem iguais às de hoje: `tests/test_atualizacao*.py` continua passando sem mudar.)
  - `atualizacao.py`: os usos das constantes importadas de `atualizacao_textos` ganham `t()`
    (`setWindowTitle(t(TITULO))`, `QMessageBox.information(janela, t(TITULO), ...)`,
    `blocos.botao(t(TEXTO_ATUALIZAR), ...)`, `setText(t(TEXTO_ATUALIZANDO))`, `t(TEXTO_TENTAR_DE_NOVO)`,
    `t(TEXTO_AGORA_NAO)`, `t(TEXTO_O_QUE_MUDOU)`, `t(MSG_UAC)`, `t(MSG_COMO_FUNCIONA)`,
    `t(MSG_TAREFA_AO_ATUALIZAR)`, `t(MSG_DOWNLOAD_CONFERIDO)`); as funções `msg_*`, já traduzem.
  - `novidades.py`: `t("O que mudou na v{versao}", versao=bloco.versao)`,
    `t("Você está usando a versão {versao} do SIG-FT", versao=bloco.versao)`,
    `t(", publicada em {data}", data=data_br(bloco.data))`; `TITULO`/`TEXTO_OK` do módulo em `marcar` + `t()`.
  - `pasta_de_logs.py`: `t("Não foi possível abrir a pasta de logs: {erro}", erro=erro)` e o título.
  - `views/nao_migrada.py`: `t('A tela "{nome}" não está disponível nesta versão do SIG-FT.', nome=nome)` e
    `t('A tela "{nome}" não conseguiu abrir.\n\n{erro}\n\nO detalhe está em Documentos\\SIG-FT\\logs\\sigft.log.', nome=nome, erro=f"{type(erro).__name__}: {erro}")`
    (copie o fim exato da frase de hoje: o texto em português não pode mudar).
  - `reinicio.py`: `TITULO`, `MSG_TAREFA_EM_ANDAMENTO`, `MSG_NAO_REABRIU` em `marcar`;
    `QMessageBox.information(pai or janela, t(TITULO), t(MSG_TAREFA_EM_ANDAMENTO))` e
    `QMessageBox.warning(pai or janela, t(TITULO), t(MSG_NAO_REABRIU, erro=erro))`. O teste
    `test_reiniciar_com_tarefa_rodando_recusa` compara com a constante e roda em português: não muda.
  - `escolha_de_idioma.py`: nada a traduzir (a pergunta é bilíngue de propósito e os nomes dos idiomas
    não se traduzem): `TITULO` vai para `NAO_E_INTERFACE` com esse motivo.
  - `estilo.py`: nenhum texto; os nomes de arquivo e de família de fonte que a guarda acusar vão para
    `NAO_E_INTERFACE` ("nome de fonte").

- [ ] **Step 7: as traduções** (como na Task 4, Step 8): `--faltando es`, `--faltando en`, escrever,
  `--arrumar`, e a ferramenta sem nada faltando nem sobrando. Atenção ao glossário: "Home" → "Inicio"/"Home",
  "Configuração" → "Configuración"/"Settings", nomes de módulo do menu com o número na frente igual
  ("1. Cria Fichas PMIB" → "1. Crear Fichas PMIB" / "1. Create PMIB Sheets").

- [ ] **Step 8: verificação**

```bash
.venv/bin/python -m pytest -q tests/test_textos_da_interface.py tests/test_qt_idioma_telas.py \
  tests/test_qt_catalogo.py tests/test_qt_paleta.py tests/test_qt_letra.py tests/test_qt_home.py \
  tests/test_qt_home_paineis.py tests/test_qt_configuracao.py tests/test_qt_nome.py tests/test_qt_main.py \
  tests/test_qt_dicas.py tests/test_novidades.py tests/test_qt_idioma_abertura.py
bash scripts/check.sh
for args in "" "--idioma es" "--idioma en"; do
  QT_QPA_PLATFORM=offscreen .venv/bin/python frontend.py --smoke $args | tail -1
done
```

- [ ] **Step 9: commit**

```bash
git add sigft/app_qt/catalogo.py sigft/app_qt/main.py sigft/app_qt/views/home.py sigft/app_qt/views/configuracao.py \
  sigft/app_qt/nome.py sigft/app_qt/aviso_windows.py sigft/app_qt/atualizacao.py sigft/app_qt/novidades.py \
  sigft/app_qt/pasta_de_logs.py sigft/app_qt/views/nao_migrada.py sigft/app_qt/reinicio.py \
  sigft/app/atualizacao_textos.py sigft/app/idiomas/es.json sigft/app/idiomas/en.json \
  tests/test_textos_da_interface.py tests/test_qt_idioma_telas.py tests/test_qt_letra.py
git commit -m "$(cat <<'EOF'
Idioma: menu, Home, Configuracao, Ctrl+K, splash, nome e atualizacao em t()

O Ctrl+K acha pelas palavras traduzidas e pelas em portugues; tema e letra viram
"Tema: {nome}". Relatorio do --smoke e chaves de tela ficam em portugues.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RSbK7jX9qvsvyZKqnojmij
EOF
)"
```

---
### Task 6: Telas I: Cria Fichas, Planilhas PMIB e Analyzer (com `views/janelas.py`)

**Files:**
- Modify: `sigft/app_qt/views/cria_fichas.py`, `sigft/app_qt/views/pdm.py`, `sigft/app_qt/views/analyzer.py`,
  `sigft/app_qt/views/janelas.py` (as janelas auxiliares: a maior parte é do Cria Fichas; as de
  duplicadas e de PDM, usadas nas telas da Task 8, entram aqui porque o arquivo é um só)
- Modify: `sigft/app/idiomas/es.json`, `en.json`
- Modify: `tests/test_textos_da_interface.py`, `tests/test_qt_idioma_telas.py`

**Interfaces:**
- Consumes: Tasks 2, 4 e 5 (`t`, `marcar`; `pausar_e_esperar(texto_botao=None)`; o fixture `janela`
  e `IDIOMAS` de `tests/test_qt_idioma_telas.py`; `TabelaSelecaoDialog` e `SelecaoMultiplaDialog` com
  padrão `None`).
- Produces: nada novo para as outras tarefas (só conversão).

Cerca de 240 literais. Os pontos que pedem cuidado (o resto segue as Regras de conversão):

- **Dado, fica em português** (`NAO_E_INTERFACE`, motivo "coluna/aba/valor da planilha"): em
  `cria_fichas.py`, `"DESCRIÇÃO"`, `"CÓDIGO PMIB"`, `"Lista de Materiais"` (colunas e aba lidas e
  gravadas pelo `data_manager`), `"Nacional"`, `"Não Reparável"`, `"Unidade"`, `"Catálogo"`,
  `"tipo de fabricação"` (valores que vão ao portal ou à planilha) e `"VERIFICAR (PULADO)"`
  (status gravado no resumo). Confirme cada um lendo a linha antes de pôr na lista.
- **Mostrado e comparado** (Regra 5): em `janelas.py`, os cabeçalhos de coluna que também são
  chave do dicionário `larguras=` (`JanelaSelecao`, `JanelaSelecaoDuplicadas`): monte a tupla
  traduzida uma vez e use os mesmos objetos nas duas pontas:

```python
    colunas = (t("Descrição"), t("PMIB Original (Base)"), t("PMIB Alvo (Novo)"))
    ...
        larguras={
            colunas[0]: {"width": 400},
            colunas[1]: {"width": 150, "anchor": "center"},
            colunas[2]: {"width": 150, "anchor": "center"},
        },
```

  Em `JanelaSelecao(parent, dataframe, ...)`, se a coluna mostrada é a mesma chave com que se lê o
  `dataframe`, separe: leia com a chave crua e mostre `t(...)` só no cabeçalho.
- **Botão cujo texto muda e é comparado** em `cria_fichas.py` ("3. Analisar (IA)" / "3. Processar
  (Direto)" / "3. Analisar (OK)"): toda comparação de `botao.text()` com literal vira comparação com
  `t("...")` do mesmo literal, ou (melhor) com um estado guardado na tela; não compare com o literal cru.
- `MSG_LOGIN_NOVA_FICHA` e `MSG_LOGIN_PAGINA_PRINCIPAL`: `self.pausar_e_esperar(t(MSG_LOGIN_NOVA_FICHA))`.
  As constantes de módulo do `cria_fichas.py` (títulos das abas, `MSG_PREPARO`, a mensagem do
  robô ocupado, o placeholder longo) em `marcar` e `t()` nos usos.
- `f"Selecionado: {nome_arquivo}"` → `t("Selecionado: {nome}", nome=nome_arquivo)`;
  `f"Planilha atualizada!\n{msg}"` → `t("Planilha atualizada!\n{mensagem}", mensagem=msg)` (o `msg`
  vem do serviço e fica como veio). Em `analyzer.py`, `f"Nota Mínima: {int(v)}%"` →
  `t("Nota Mínima: {nota}%", nota=int(v))` nos dois lugares.
- `pdm.py`: `"Português"` e `"English"` do "Idioma da ficha" são nomes de idioma (não se traduzem, já
  em `NAO_SE_TRADUZ`); o texto ao lado, `"(English traduz as características da planilha)"`, vai para `t()`.
  Os rádios de "Seleção de Itens" e "Formato de Saída": se o texto do rádio é comparado para decidir
  o modo, Regra 5.
- O título de cada tela (`super().__init__(..., titulo=t("Módulo de Criação"))`): o resumo e o aviso
  do Windows usam esse título (`resumo_lote.nome_da_tela`).
- `"Technical Datasheet Analyzer"` (título do Analyzer) já é o nome do módulo em inglês, que a equipe
  usa assim: vai para `t()` e a tradução é o próprio texto em `es` e em `en` (decidir no catálogo, e
  não fora dele, deixa a revisão do Jonathan mudar sem tocar no código).

- [ ] **Step 1: a guarda e o teste em tela acusam.** Em `CONVERTIDOS`, acrescente:

```python
    # Task 6: Cria Fichas, Planilhas PMIB, Analyzer e as janelas auxiliares
    "sigft/app_qt/views/analyzer.py",
    "sigft/app_qt/views/cria_fichas.py",
    "sigft/app_qt/views/janelas.py",
    "sigft/app_qt/views/pdm.py",
```

  Em `tests/test_qt_idioma_telas.py`, acrescente:

```python
@pytest.mark.parametrize("codigo", IDIOMAS)
def test_cria_fichas_planilhas_e_analyzer(janela, codigo):
    with em_idioma(codigo):
        principal = janela()
        for alvo in ("CriaFichas", "PDM", "Analyzer"):
            principal.show_frame(alvo)
            assert ainda_em_portugues(principal.telas[alvo], codigo) == set(), alvo


@pytest.mark.parametrize("codigo", IDIOMAS)
def test_janelas_auxiliares(qt_interface, qtbot, codigo):
    from sigft.app_qt.views import janelas
    from sigft.core.pdm_catalogo import PDM, CatalogoPDM

    catalogo = CatalogoPDM([PDM(codigo="PDM.4820.004", classe="4820", titulo="VALVULA ESFERA",
                                caracteristicas=("DIAMETRO",))])
    fila = [{"descricao": "Válvula", "pmib_original": "4500063671.0001", "pmib_alvo": "4500063671.0002"}]
    with em_idioma(codigo):
        for peca in (janelas.JanelaEscolherPDM(None, catalogo),
                     janelas.DialogoAcaoRobo(None, "erro", "PDM.4820.004"),
                     janelas.JanelaRevisaoEdicao(None, fila)):
            qtbot.addWidget(peca)
            assert ainda_em_portugues(peca, codigo) == set(), type(peca).__name__
```

  Rode `.venv/bin/python -m pytest -q tests/test_textos_da_interface.py -k passa_por_t tests/test_qt_idioma_telas.py`
  → FAIL.

- [ ] **Step 2: converter** os quatro arquivos (Regras de conversão e os pontos acima), com
  `.venv/bin/python tools/textos_da_interface.py --literais sigft/app_qt/views/cria_fichas.py ...`
  como lista de trabalho, até a guarda passar. O `NAO_E_INTERFACE` ganha um bloco por arquivo, com o
  motivo.

- [ ] **Step 3: as traduções** (`--faltando es`, `--faltando en`, escrever seguindo o Glossário,
  `--arrumar`, a ferramenta sem nada faltando nem sobrando).

- [ ] **Step 4: verificação**

```bash
.venv/bin/python -m pytest -q tests/test_textos_da_interface.py tests/test_qt_idioma_telas.py \
  tests/test_qt_janelas.py $(grep -l "cria_fichas\|views.pdm\|views.analyzer\|views import janelas" tests/test_qt_*.py)
bash scripts/check.sh
for args in "" "--idioma es" "--idioma en"; do
  QT_QPA_PLATFORM=offscreen .venv/bin/python frontend.py --smoke $args | tail -1
done
```

  Os testes de medida dessas telas (rodam em português) não mudam; se um quebrar, a conversão mudou
  o texto em português: corrija o código.

- [ ] **Step 5: commit**

```bash
git add sigft/app_qt/views/cria_fichas.py sigft/app_qt/views/pdm.py sigft/app_qt/views/analyzer.py \
  sigft/app_qt/views/janelas.py sigft/app/idiomas/es.json sigft/app/idiomas/en.json \
  tests/test_textos_da_interface.py tests/test_qt_idioma_telas.py
git commit -m "$(cat <<'EOF'
Idioma: Cria Fichas, Planilhas PMIB, Analyzer e janelas auxiliares em t()

Colunas e valores de planilha e do portal ficam em portugues (NAO_E_INTERFACE).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RSbK7jX9qvsvyZKqnojmij
EOF
)"
```

---

### Task 7: Telas II: Upload Condições, Tradutor e Upload Specs (com `_upload_comum.py`)

**Files:**
- Modify: `sigft/app_qt/views/upload_conditions.py`, `sigft/app_qt/views/_upload_comum.py`,
  `sigft/app_qt/views/translator.py`, `sigft/app_qt/views/upload_tech_specs.py`
- Modify: `sigft/app/idiomas/es.json`, `en.json`, `tests/test_textos_da_interface.py`, `tests/test_qt_idioma_telas.py`

**Interfaces:**
- Consumes: Tasks 2, 4 e 5. `msg_falha_ao_salvar` e `msg_ficha_preenchida` já traduzem (Task 4);
  `MSG_LOGIN_SOLTAR_ROBO` precisa de `t()` onde é devolvido.

Cerca de 100 literais. Pontos de cuidado:

- `TelaDeUpload` (`_upload_comum.py`) tem atributos de CLASSE de texto (`TEXTO_CONFIG`,
  `TEXTO_INTERRUPTOR`, `TEXTO_WEB`, `TEXTO_CARREGAR`, vazios na mãe) que as filhas preenchem
  (`upload_conditions.py`, `upload_tech_specs.py`): nas filhas, o valor vai em `marcar(...)`; na mãe,
  onde cada um vira widget, `t(self.TEXTO_CONFIG)` etc. As constantes de módulo da mãe
  (`TEXTO_NAO_SELECIONADO`, o título da aba do robô, a mensagem de robô ocupado) em `marcar` + `t()`.
- `_mensagem_de_pausa` (as duas filhas): `return t(MSG_LOGIN_SOLTAR_ROBO)` quando é login; o
  `msg_falha_ao_salvar(...)`/`msg_ficha_preenchida(...)` já vêm traduzidos.
- A pergunta "Como deseja salvar as fichas processadas?\n\nSIM = Novo Arquivo Excel\nNÃO = Anexar a um
  Excel Existente" cita os botões do Qt: a tradução cita os botões do idioma ("SÍ = ...", "NO = ..."
  no `es`; "YES = ...", "NO = ..." no `en`).
- Os itens da `SelecaoMultiplaDialog` (`f" Ficha PMIB: {...}"`, `f"PMIB: {...} | {...}"`) vão com
  `devolver_indices=True`: só exibição; viram `t(" Ficha PMIB: {pmib}", pmib=...)` e
  `t("PMIB: {pmib} | {arquivo}", pmib=..., arquivo=...)` (a segunda não tem palavra a traduzir: pode
  ficar como f-string, e a guarda não a acusa).
- `translator.py`: `self.avisar("Tradutor", ultimo_erro or "A tradução não pôde começar.", ...)` →
  `self.avisar(t("Tradutor"), ultimo_erro or t("A tradução não pôde começar."), ...)` (o `ultimo_erro`
  vem do serviço). O título `"Tradutor Técnico (PT -> ES)"` vai para `t()` (em `en`,
  "Technical Translator (PT -> ES)").

- [ ] **Step 1: a guarda e o teste em tela acusam.** Em `CONVERTIDOS`:

```python
    # Task 7: Upload Condições, Tradutor, Upload Specs
    "sigft/app_qt/views/_upload_comum.py",
    "sigft/app_qt/views/translator.py",
    "sigft/app_qt/views/upload_conditions.py",
    "sigft/app_qt/views/upload_tech_specs.py",
```

  Em `tests/test_qt_idioma_telas.py`:

```python
@pytest.mark.parametrize("codigo", IDIOMAS)
def test_uploads_e_tradutor(janela, codigo):
    with em_idioma(codigo):
        principal = janela()
        for alvo in ("UploadConditions", "Translator", "UploadSpecs"):
            principal.show_frame(alvo)
            assert ainda_em_portugues(principal.telas[alvo], codigo) == set(), alvo
```

  → FAIL.

- [ ] **Step 2: converter** os quatro arquivos até a guarda passar (com `--literais` como lista).
- [ ] **Step 3: as traduções** (como na Task 6).
- [ ] **Step 4: verificação**

```bash
.venv/bin/python -m pytest -q tests/test_textos_da_interface.py tests/test_qt_idioma_telas.py \
  tests/test_qt_tela_upload_tech_specs.py \
  $(grep -l "upload_conditions\|upload_tech_specs\|views.translator\|_upload_comum" tests/test_qt_*.py)
bash scripts/check.sh
for args in "" "--idioma es" "--idioma en"; do
  QT_QPA_PLATFORM=offscreen .venv/bin/python frontend.py --smoke $args | tail -1
done
```

- [ ] **Step 5: commit**

```bash
git add sigft/app_qt/views/_upload_comum.py sigft/app_qt/views/translator.py \
  sigft/app_qt/views/upload_conditions.py sigft/app_qt/views/upload_tech_specs.py \
  sigft/app/idiomas/es.json sigft/app/idiomas/en.json tests/test_textos_da_interface.py tests/test_qt_idioma_telas.py
git commit -m "$(cat <<'EOF'
Idioma: Upload Condicoes, Tradutor e Upload Specs em t()

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RSbK7jX9qvsvyZKqnojmij
EOF
)"
```

---

### Task 8: Telas III: Correção de PDM, Upload duplicadas e AutoSpec

**Files:**
- Modify: `sigft/app_qt/views/correcao_pdm.py`, `sigft/app_qt/views/copia_fichas.py`,
  `sigft/app_qt/views/autospec.py` (**frente do Rafael, cedida ao Jonathan**: só literal → `t()`)
- Modify: `sigft/app/idiomas/es.json`, `en.json`, `tests/test_textos_da_interface.py`, `tests/test_qt_idioma_telas.py`

**Interfaces:**
- Consumes: Tasks 2, 4, 5 e 6 (`janelas.JanelaEscolherPDM`, `JanelaSelecaoDuplicadas` e
  `JanelaRevisaoEdicao` já convertidas).

Cerca de 120 literais. Pontos de cuidado:

- **AutoSpec (`autospec.py`):** só troca literal por `t()`/`marcar()`, sem mexer em layout, ordem,
  nome de atributo ou comportamento. Os textos com travessão (`—`) são do Rafael e ficam como estão
  no português (a chave); as traduções não têm travessão (o teste dos catálogos cobra). Os testes de
  tela dele (`tests/test_autospec_conferencia_tela.py`, `tests/test_autospec_auditoria_tela.py`,
  `tests/test_qt_tela_autospec.py`) rodam em português e **não mudam**; rode-os. `"Docs"` e
  `"Texto"` em `filetypes` são rótulos do filtro do diálogo de arquivo: `t()`.
  `"Ficha: [Nenhuma]"` e `"Manuais: 0 arquivos"` são mostrados e depois trocados por
  `f"Ficha: {nome}"`/`f"Manuais: {n} arquivos"`: viram `t("Ficha: {nome}", nome=t("[Nenhuma]"))` e
  `t("Manuais: {n} arquivos", n=0)` (e as versões com valor), para o texto inicial e o atualizado
  serem a mesma chave.
- **Console, fica em português:** em `copia_fichas.py`, as linhas `registrar(...)` com `[Robô novo]`
  vão ao log (o `registrar` é o `log_auditoria.envolver(self.log)`): `NAO_E_INTERFACE`, motivo
  "console e log de auditoria". `"Sem Descrição"` em `copia_fichas.py` é o valor que entra na fila
  (`descricao` do item, que o robô e o log usam): dado, fica.
- `correcao_pdm.py`: os nomes de `COLUNAS` em `marcar` e `t(c)` onde a tabela é montada
  (`dialogos_selecao.tabela_ttk([(t(c), largura, "w") for c, largura in COLUNAS], ...)`); se algum
  código procura a coluna pelo texto, Regra 5. `MSG_LOGIN_NOVA_FICHA` com `t()`.
  `"Salvar relatorio"` (sem acento: é o título do diálogo de salvar) vai para `t()` como está.
- O título "Módulo: Cópia de Fichas PMIB" vai para `t()`; a tradução mantém o prefixo
  "Módulo:"/"Module:" (o `resumo_lote.nome_da_tela` tira os dois, Task 4).

- [ ] **Step 1: a guarda e o teste em tela acusam.** Em `CONVERTIDOS`:

```python
    # Task 8: Correção de PDM, Upload duplicadas, AutoSpec
    "sigft/app_qt/views/autospec.py",
    "sigft/app_qt/views/copia_fichas.py",
    "sigft/app_qt/views/correcao_pdm.py",
```

  Em `tests/test_qt_idioma_telas.py` (a Correção de PDM está bloqueada no menu: é montada pela
  fábrica, como no `tests/test_qt_dicas.py`):

```python
@pytest.mark.parametrize("codigo", IDIOMAS)
def test_correcao_duplicadas_e_autospec(janela, codigo):
    from sigft.app_qt import main as qmain

    with em_idioma(codigo):
        principal = janela()
        for alvo in ("CopiaFichas", "AutoSpec"):
            principal.show_frame(alvo)
            assert ainda_em_portugues(principal.telas[alvo], codigo) == set(), alvo
        correcao = qmain.TELAS["CorrecaoPDM"](principal.pilha, principal)
        assert ainda_em_portugues(correcao, codigo) == set()
```

  → FAIL.

- [ ] **Step 2: converter** os três arquivos até a guarda passar.
- [ ] **Step 3: as traduções** (como na Task 6).
- [ ] **Step 4: verificação**

```bash
.venv/bin/python -m pytest -q tests/test_textos_da_interface.py tests/test_qt_idioma_telas.py \
  tests/test_autospec_conferencia_tela.py tests/test_autospec_auditoria_tela.py tests/test_qt_tela_autospec.py \
  tests/test_qt_janelas.py tests/test_texto_da_ui.py \
  $(grep -l "correcao_pdm\|copia_fichas\|views.autospec" tests/test_qt_*.py)
bash scripts/check.sh
for args in "" "--idioma es" "--idioma en"; do
  QT_QPA_PLATFORM=offscreen .venv/bin/python frontend.py --smoke $args | tail -1
done
```

- [ ] **Step 5: commit** (mensagem explícita sobre a fronteira, como pede o `CLAUDE.md`):

```bash
git add sigft/app_qt/views/correcao_pdm.py sigft/app_qt/views/copia_fichas.py sigft/app_qt/views/autospec.py \
  sigft/app/idiomas/es.json sigft/app/idiomas/en.json tests/test_textos_da_interface.py tests/test_qt_idioma_telas.py
git commit -m "$(cat <<'EOF'
Idioma: Correcao de PDM, Upload duplicadas e AutoSpec em t()

AutoSpec (tela cedida pelo Rafael): so literal virou t(), sem mudar layout nem
comportamento; os testes de tela dele rodam em portugues e nao mudaram.
Linhas do console e do log de auditoria ficam em portugues.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RSbK7jX9qvsvyZKqnojmij
EOF
)"
```

---

### Task 9: Telas IV: Aplicação LMR, PMIB Manager e Busca PMIB (e a interface inteira na guarda)

**Files:**
- Modify: `sigft/app_qt/views/aplicacao_lmr.py`, `sigft/app_qt/views/lmr.py`, `sigft/app_qt/views/apagar_lmr.py`,
  `sigft/app_qt/views/pmib_manager.py`, `sigft/app_qt/views/busca_pmib.py`
- Modify: `sigft/app/idiomas/es.json`, `en.json`, `tests/test_textos_da_interface.py`, `tests/test_qt_idioma_telas.py`

**Interfaces:**
- Consumes: Tasks 2, 4 e 5 (`texto_dos_avisos(inicio, ...)` com `inicio` já traduzido;
  `pausar_e_esperar(..., texto_botao=)`).
- Produces: `test_toda_a_interface_esta_na_guarda` (nenhum `.py` de `sigft/app_qt` fora de `CONVERTIDOS`).

Cerca de 150 literais. Pontos de cuidado:

- `busca_pmib.py`: `"DESCRIÇÃO"`, `"CÓDIGO DO MATERIAL"`, `"CÓDIGO CMI"`, `"CÓDIGO PMIB"` (linha 24) são
  nomes de coluna das planilhas pesquisadas, mostrados no menu "Coluna Alvo" e passados ao serviço:
  dado, ficam (`NAO_E_INTERFACE`). Os modos "Direcionada (Rápida)" / "Generalista (Lenta)": se o
  texto escolhido decide o modo, Regra 5 (compare com `t(...)` ou guarde o modo pelo índice).
  `"📂 Caminho:"` e `"🔎 Amostra: "`: o símbolo fica fora da chave (`"📂 " + t("Caminho:")`).
- `pmib_manager.py`: `texto_dos_avisos(t("As autorizações foram aplicadas"), ...)` (e as outras duas
  aberturas); `self.pausar_e_esperar(t(MSG_LOGIN_CONFERIR_AUTORIZACOES))`. A janela "Novas Listas
  Encontradas" (classe do próprio arquivo): botões e rótulos em `t()`.
- `apagar_lmr.py`: `self.pausar_e_esperar(t(MSG_LOGIN_APAGAR_LMR), texto_botao=t(TEXTO_COMECAR_EXCLUSAO))`;
  `t("Tem certeza que deseja APAGAR todas as aplicações do PMIB {pmib}?", pmib=pmib)`.
- `lmr.py` e `apagar_lmr.py`: o `NOME_DO_ROBO` de cada um ("Upload de aplicações", "Exclusão de
  aplicações") só aparece no console (`ComTravaDeRobo.robo_ocupado`): `NAO_E_INTERFACE`.
- `aplicacao_lmr.py`: os nomes das duas abas ("Upload de Aplicações", "Exclusão de Aplicações") em
  `t()`; se a aba é achada pelo texto, Regra 5.

- [ ] **Step 1: a guarda e o teste em tela acusam.** Em `CONVERTIDOS`:

```python
    # Task 9: Aplicação LMR, PMIB Manager, Busca PMIB
    "sigft/app_qt/views/apagar_lmr.py",
    "sigft/app_qt/views/aplicacao_lmr.py",
    "sigft/app_qt/views/busca_pmib.py",
    "sigft/app_qt/views/lmr.py",
    "sigft/app_qt/views/pmib_manager.py",
```

  Em `tests/test_textos_da_interface.py`, depois de `test_o_que_fica_em_portugues_ainda_existe`:

```python
def test_toda_a_interface_esta_na_guarda():
    """Arquivo novo em `sigft/app_qt` (ou um que ficou de fora) entra na guarda:
    texto de interface sem `t()` não volta escondido."""
    todos = {p.relative_to(RAIZ).as_posix() for p in ferramenta.arquivos(RAIZ)}
    assert todos - set(CONVERTIDOS) == set()
```

  Em `tests/test_qt_idioma_telas.py`:

```python
@pytest.mark.parametrize("codigo", IDIOMAS)
def test_lmr_pmib_manager_e_busca(janela, codigo):
    with em_idioma(codigo):
        principal = janela()
        for alvo in ("LMR", "PMIBManager", "SearchPMIB"):
            principal.show_frame(alvo)
            assert ainda_em_portugues(principal.telas[alvo], codigo) == set(), alvo
```

  → FAIL (os cinco arquivos e o teste novo).

- [ ] **Step 2: converter** os cinco arquivos até a guarda passar.
- [ ] **Step 3: as traduções** (como na Task 6).
- [ ] **Step 4: verificação**

```bash
.venv/bin/python -m pytest -q tests/test_textos_da_interface.py tests/test_qt_idioma_telas.py \
  $(grep -l "aplicacao_lmr\|views.lmr\|apagar_lmr\|pmib_manager\|busca_pmib" tests/test_qt_*.py)
.venv/bin/python tools/textos_da_interface.py
bash scripts/check.sh
for args in "" "--idioma es" "--idioma en"; do
  QT_QPA_PLATFORM=offscreen .venv/bin/python frontend.py --smoke $args | tail -1
done
```

- [ ] **Step 5: commit**

```bash
git add sigft/app_qt/views/aplicacao_lmr.py sigft/app_qt/views/lmr.py sigft/app_qt/views/apagar_lmr.py \
  sigft/app_qt/views/pmib_manager.py sigft/app_qt/views/busca_pmib.py sigft/app/idiomas/es.json \
  sigft/app/idiomas/en.json tests/test_textos_da_interface.py tests/test_qt_idioma_telas.py
git commit -m "$(cat <<'EOF'
Idioma: Aplicacao LMR, PMIB Manager e Busca PMIB em t(); a interface inteira na guarda

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RSbK7jX9qvsvyZKqnojmij
EOF
)"
```

---
### Task 10: Medidas em outro idioma (largura fixa e a varredura das 12 telas)

**Files:**
- Modify: `sigft/app_qt/letra.py` (`_pede_folga`, `_ajustar_largura`, `_Vigia`, `aplicar`, `reavaliar_vigia`)
- Modify: `tests/conftest.py` (o fim da fixture `_interface_em_portugues`)
- Create: `tests/_varredura.py` (os ajudantes que estavam em `tests/test_qt_letra.py`)
- Modify: `tests/test_qt_letra.py` (importa de `_varredura`; dois testes novos)
- Create: `tests/test_qt_idioma_varredura.py`
- Modify (só se a varredura acusar): `sigft/app/idiomas/es.json`, `en.json` (tradução mais curta) e,
  em último caso, a tela com o texto cortado

**Interfaces:**
- Consumes: `idioma.atual`, `idioma.PADRAO`, `idioma.t` (Task 2); `tests/_idioma.em_idioma`.
- Produces: `letra._pede_folga(aumento_px: int) -> bool`, `letra.reavaliar_vigia(app=None) -> None`;
  `tests/_varredura.cortados(tela) -> set[str]`, `tests/_varredura.varrer(janela, qtbot) -> (dict[str, set[str]], list[str])`.

Decisão desta tarefa (spec: "o ajuste de largura da letra Grande é estendido para valer também na
troca de idioma"): o mecanismo é o MESMO da letra grande, com uma condição a mais. Peça de texto com
largura fixa (botão, rótulo de uma linha) alarga até o `sizeHint` quando a letra é grande **ou** o
idioma não é o português; o vigia, que hoje só existe com a letra grande, passa a existir também fora
do português. Em português com a letra normal nada muda (nem o vigia existe), e por isso nenhum teste
de medida em português muda. Como o idioma só muda ao abrir, não há "voltar à largura de antes" por
causa de idioma: só por causa da letra, como hoje.

- [ ] **Step 1: os testes da largura (`tests/test_qt_letra.py`, no fim)**

```python
# --- fora do português (2026-10-22) ------------------------------------------

def test_largura_fixa_alarga_em_outro_idioma_com_a_letra_normal(letra_temporaria, qtbot):
    # As larguras fixas foram medidas no português; em espanhol e inglês o texto
    # tem outro tamanho. O mesmo ajuste da letra grande vale fora do português.
    from sigft.app import idioma

    try:
        idioma.definir("es")
        letra.aplicar(letra_temporaria, "normal", gravar=False)
        assert len(letra._vigia) == 1
        botao = blocos.botao("APLICAR LAS AUTORIZACIONES DE ENTREGA", largura=200, tamanho_fonte=12,
                             negrito=True)
        qtbot.addWidget(botao)
        botao.show()
        qtbot.waitExposed(botao)
        qtbot.waitUntil(lambda: botao.width() >= botao.sizeHint().width(), timeout=1000)
        assert botao.minimumWidth() == botao.maximumWidth()
    finally:
        idioma.definir("pt")
        letra.aplicar(letra_temporaria, "normal", gravar=False)
    assert letra._vigia == []


def test_em_portugues_com_a_letra_normal_a_largura_fixa_e_a_de_sempre(letra_temporaria, qtbot):
    letra.aplicar(letra_temporaria, "normal", gravar=False)
    assert letra._vigia == []
    botao = blocos.botao("APLICAR LAS AUTORIZACIONES DE ENTREGA", largura=200, tamanho_fonte=12, negrito=True)
    qtbot.addWidget(botao)
    botao.show()
    qtbot.waitExposed(botao)
    assert (botao.minimumWidth(), botao.maximumWidth()) == (200, 200)


def test_reavaliar_o_vigia_segue_o_idioma(letra_temporaria):
    from sigft.app import idioma

    letra.aplicar(letra_temporaria, "normal", gravar=False)
    idioma.definir("en")
    letra.reavaliar_vigia(letra_temporaria)
    assert len(letra._vigia) == 1
    idioma.definir("pt")
    letra.reavaliar_vigia(letra_temporaria)
    assert letra._vigia == []
```

  `.venv/bin/python -m pytest -q tests/test_qt_letra.py -k "idioma or portugues or reavaliar"` → FAIL
  (`AttributeError: ... reavaliar_vigia` e o vigia que não liga em espanhol).

- [ ] **Step 2: `letra.py`.** Acrescente `from sigft.app import idioma` (ao lado de `tokens`) e
  `QApplication` no import de `PySide6.QtWidgets`. No docstring do módulo, no item 4, acrescente:
  "Fora do português (2026-10-22) vale o mesmo, com a letra normal também: as larguras fixas foram
  medidas no português (`_pede_folga`)." Depois de `aumento()`:

```python
def _pede_folga(aumento_px: int) -> bool:
    """Largura fixa alarga até caber o texto: com a letra grande, ou num idioma
    que não é o português (as larguras fixas foram medidas nele)."""
    return bool(aumento_px) or idioma.atual() != idioma.PADRAO
```

  Troque `_ajustar_largura` por:

```python
def _ajustar_largura(widget: QWidget, aumento_px: int) -> None:
    """Largura fixa com folga (`_pede_folga`): no mínimo o `sizeHint` (o texto
    inteiro). Sem folga, a largura de antes, ao pixel; peça nunca alargada: nada muda."""
    folga = _pede_folga(aumento_px)
    original = widget.property(_PROP_LARGURA_FIXA)
    if original is None:
        if not folga or not _texto_de_largura_fixa(widget):
            return
        original = widget.maximumWidth()
    alvo = max(original, widget.sizeHint().width()) if folga else original
    if (widget.minimumWidth(), widget.maximumWidth()) != (alvo, alvo):
        widget.setFixedWidth(alvo)
    widget.setProperty(_PROP_LARGURA_FIXA, original if folga else None)
```

  Troque o `eventFilter` do `_Vigia` por:

```python
    def eventFilter(self, obj, evento) -> bool:  # noqa: N802 -- nome do Qt
        if evento.type() in _TIPOS_VIGIADOS and isinstance(obj, QWidget) \
                and _pede_folga(estilo.AUMENTO_LETRA):
            try:
                if estilo.AUMENTO_LETRA:
                    _ajustar_folha_e_fonte(obj, estilo.AUMENTO_LETRA)
                _ajustar_largura(obj, estilo.AUMENTO_LETRA)
            except RuntimeError:
                pass   # peça já destruída
        return False
```

  Em `aplicar`, troque `_vigiar(app, bool(estilo.AUMENTO_LETRA))` por
  `_vigiar(app, _pede_folga(estilo.AUMENTO_LETRA))`. Depois de `_vigiar`:

```python
def reavaliar_vigia(app=None) -> None:
    """Liga ou desliga o vigia pelo estado de agora (letra e idioma), sem refazer
    folha nenhuma: para quem troca o idioma sem passar por `aplicar` (os testes)."""
    app = app or QApplication.instance()
    if app is not None:
        _vigiar(app, _pede_folga(estilo.AUMENTO_LETRA))
```

  No fim da fixture `_interface_em_portugues` do `tests/conftest.py`, depois do último
  `_idioma.definir(_idioma.PADRAO)`:

```python
    # A largura fixa alarga fora do português (`letra._pede_folga`): o vigia que um
    # teste de idioma ligou não pode ficar para o próximo.
    _letra = sys.modules.get("sigft.app_qt.letra")
    if _letra is not None:
        _letra.reavaliar_vigia()
```

  `.venv/bin/python -m pytest -q tests/test_qt_letra.py` → PASS (os testes de antes também).

- [ ] **Step 3: os ajudantes da varredura (`tests/_varredura.py`, novo).** Mova `_cortados` e `_varrer`
  de `tests/test_qt_letra.py` para cá, com os nomes `cortados` e `varrer` e o mesmo corpo:

```python
"""A varredura das telas: texto cortado e rolagem de lado (fix round 1, 2026-10-21).

Era de `tests/test_qt_letra.py` (letra grande); desde 2026-10-22 também serve à
varredura dos idiomas (`tests/test_qt_idioma_varredura.py`).
"""
from __future__ import annotations

from sigft.app_qt import catalogo
from sigft.app_qt.widgets import blocos


def cortados(tela) -> set[str]:
    """Os textos (botão, rótulo de uma linha, caixa) mais estreitos que o pedido."""
    from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton

    achados = set()
    for tipo in (QPushButton, QLabel, QCheckBox):
        for w in tela.findChildren(tipo):
            if not w.isVisible() or not w.text().strip():
                continue
            if isinstance(w, QLabel) and (w.wordWrap() or isinstance(w, blocos.RotuloElidido)):
                continue
            if w.width() < w.sizeHint().width():
                achados.add(w.text())
    return achados


def varrer(janela, qtbot) -> tuple[dict[str, set[str]], list[str]]:
    """Visita a Home e os módulos liberados: `(cortados por tela, áreas rolando de lado)`."""
    from PySide6.QtWidgets import QAbstractScrollArea

    achados, rolando = {}, []
    for alvo in ["Home", *(m[0] for m in catalogo.MODULOS if m[0] not in catalogo.TELAS_BLOQUEADAS)]:
        janela.show_home() if alvo == "Home" else janela.show_frame(alvo)
        qtbot.wait(30)
        tela = janela.telas[alvo]
        for area in [tela, *tela.findChildren(QAbstractScrollArea)]:
            if isinstance(area, QAbstractScrollArea) and area.isVisible() \
                    and area.horizontalScrollBar().isVisible():
                rolando.append(f"{alvo}:{type(area).__name__}")
        achados[alvo] = cortados(tela)
    return achados, rolando
```

  Em `tests/test_qt_letra.py`: apague `_cortados` e `_varrer`, acrescente `from _varredura import varrer`
  no topo e troque as chamadas `_varrer(` por `varrer(`.

- [ ] **Step 4: a varredura dos idiomas (`tests/test_qt_idioma_varredura.py`, novo)**

```python
"""As 12 telas em espanhol e em inglês, a 1280x850 (2026-10-22).

Nada cortado e nada rolando de lado, com a letra normal e com a grande. O que já
fica apertado em português (o "Limpar" de 100 px da Criação de Fichas, travado
pelo teste de medida) não conta: a referência é a mesma tela em português, com
os textos traduzidos. Se esta varredura acusar, encurte a tradução antes de
mexer no layout (Glossário e estilo, no plano de 2026-10-22).
"""
import pytest

from _idioma import em_idioma
from _varredura import varrer
from sigft.app import idioma
from sigft.app_qt import letra
from sigft.app_qt import main as qmain


@pytest.fixture
def montar(qt_interface, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(letra, "_arquivo_de_prefs", lambda: tmp_path / "p.json")
    monkeypatch.setattr(qmain, "_arquivo_de_chaves", lambda: str(tmp_path / "api_config.json"))
    anterior = qt_interface.styleSheet()

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
    qt_interface.setStyleSheet(anterior)


@pytest.mark.parametrize("codigo", ["es", "en"])
def test_nenhuma_tela_corta_texto_nem_rola_de_lado_em_outro_idioma(montar, qtbot, qt_interface, codigo):
    letra.aplicar(qt_interface, "normal", gravar=False)
    em_portugues, _ = varrer(montar(), qtbot)
    with em_idioma(codigo):
        ja_apertados = {alvo: {idioma.t(texto) for texto in textos} for alvo, textos in em_portugues.items()}
        letra.aplicar(qt_interface, "normal", gravar=False)   # o vigia do idioma liga aqui
        janela = montar()
        normal, rolando_normal = varrer(janela, qtbot)
        letra.aplicar(qt_interface, "grande", gravar=False)
        grande, rolando_grande = varrer(janela, qtbot)
        assert rolando_normal == [] and rolando_grande == []
        for medida in (normal, grande):
            sobra = {alvo: textos - ja_apertados[alvo] for alvo, textos in medida.items()
                     if textos - ja_apertados[alvo]}
            assert sobra == {}
    letra.aplicar(qt_interface, "normal", gravar=False)
```

- [ ] **Step 5:** `.venv/bin/python -m pytest -q tests/test_qt_idioma_varredura.py tests/test_qt_letra.py`.
  Para cada texto que a varredura acusar: primeiro encurte a tradução no catálogo (mesmo sentido,
  menos letras); se não houver tradução curta honesta, ajuste a tela (largura mínima em vez de fixa, ou
  `largura_minima=` do `blocos.botao`) e confira que os testes de medida em português continuam iguais.
  Rode até PASS.

- [ ] **Step 6: verificação**

```bash
bash scripts/check.sh
for args in "--idioma es" "--idioma en" "--idioma es --letra grande" "--idioma en --tema claro --letra grande"; do
  QT_QPA_PLATFORM=offscreen .venv/bin/python frontend.py --smoke $args | tail -1
done
```

- [ ] **Step 7: commit**

```bash
git add sigft/app_qt/letra.py tests/conftest.py tests/_varredura.py tests/test_qt_letra.py \
  tests/test_qt_idioma_varredura.py sigft/app/idiomas/es.json sigft/app/idiomas/en.json
git commit -m "$(cat <<'EOF'
Idioma: largura fixa alarga fora do portugues; varredura das 12 telas em es e en

O ajuste da letra grande (alargar ate o sizeHint) vale tambem com a letra normal
quando o idioma nao e o portugues. Em portugues nada muda: os testes de medida
ficam como estavam.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RSbK7jX9qvsvyZKqnojmij
EOF
)"
```

---

### Task 11: Fechamento (capturas, CHANGELOG, base de conhecimento, mural, PR)

**Files:**
- Modify: `CHANGELOG.md` (bloco em aberto `## 1.2.1 - 2026-10-16`)
- Modify: `docs/base-conhecimento/00-frontend.md` (seção nova antes de `## Pontos de Atenção`)
- Modify: `CLAUDE.md` (mural) e `docs/refatoracao/PENDENCIAS.md` (o aviso mais antigo do mural)
- Create (scratchpad, fora do repositório): `capturas_idioma.py`

**Interfaces:**
- Consumes: tudo das Tasks 1 a 10.

- [ ] **Step 1:** `bash scripts/check.sh` inteiro → verde (exceto o `test_qt_saida` deste contêiner).
  `.venv/bin/python tools/textos_da_interface.py` → `es: 0 faltando, 0 sobrando` e `en: 0 faltando, 0 sobrando`.

- [ ] **Step 2: smoke nos três idiomas, nos dois temas e nas duas letras**

```bash
for idioma in pt es en; do
  for args in "" "--tema claro --letra grande"; do
    QT_QPA_PLATFORM=offscreen .venv/bin/python frontend.py --smoke --idioma $idioma $args | tail -1
  done
done
```

  Esperado em cada um: `[smoke] a janela principal Qt montou, as 11 telas abriram e ela fechou sem erro.`

- [ ] **Step 3: capturas.** Salve no scratchpad como `capturas_idioma.py` e rode com a pasta de saída
  como argumento (os dados do usuário vão para dentro dela, nunca os reais):

```python
"""Capturas da engrenagem e do idioma nos três idiomas e nos dois temas (offscreen)."""
import os
import sys
from pathlib import Path

SAIDA = Path(sys.argv[1]).resolve()
SAIDA.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["SIGFT_DADOS_DIR"] = str(SAIDA / "dados")
os.environ["SIGFT_SEM_AVISO_DO_WINDOWS"] = "1"
os.environ["SIGFT_SEM_RESUMO_DO_LOTE"] = "1"
sys.path.insert(0, "/home/user/sig-ft")

from PySide6.QtTest import QTest  # noqa: E402

from sigft.app import backends, idioma  # noqa: E402
from sigft.app_qt import escolha_de_idioma, letra, tema  # noqa: E402
from sigft.app_qt import main as qmain  # noqa: E402

app = qmain._preparar_qt("escuro", "normal", "pt")
backends.carregar_todos(ao_falhar=lambda *_: None)
pergunta = escolha_de_idioma.PerguntaDoIdioma()
pergunta.show()
QTest.qWait(200)
pergunta.grab().save(str(SAIDA / "primeira_abertura.png"))
pergunta.close()
for codigo in ("pt", "es", "en"):
    for nome_tema in ("escuro", "claro"):
        qmain._aplicar_idioma(app, codigo)
        tema.aplicar(app, nome_tema, gravar=False)
        sufixo = f"{codigo}_{nome_tema}"
        janela = qmain.SIG_FT_App()
        janela.fechar_sem_perguntar = True
        janela.resize(1280, 850)
        janela.show()
        QTest.qWait(300)
        janela.grab().save(str(SAIDA / f"home_{sufixo}.png"))
        config = janela.telas["Home"].abrir_configuracao()
        QTest.qWait(300)
        config.grab().save(str(SAIDA / f"configuracao_{sufixo}.png"))
        config.close()
        for alvo in ("CriaFichas", "AutoSpec", "PMIBManager"):
            janela.show_frame(alvo)
            QTest.qWait(200)
            janela.grab().save(str(SAIDA / f"{alvo}_{sufixo}.png"))
        janela.close()
letra.aplicar(app, "normal", gravar=False)
idioma.definir("pt")
print(f"capturas em {SAIDA}")
```

  Rode: `.venv/bin/python <scratchpad>/capturas_idioma.py <scratchpad>/capturas_idioma`. Olhe cada PNG
  (o `Read` mostra imagem): a engrenagem à direita do título sem sobrepor nada; as seis seções da
  janela com os títulos à esquerda; nenhum texto cortado em espanhol e inglês; nada em português
  sobrando nas telas `es`/`en` (exceto o glossário). Mande ao Jonathan antes do PR, com a lista das
  traduções para ele revisar o espanhol (a spec: "o Jonathan (es) e quem ele indicar revisam antes do
  Release").

- [ ] **Step 4: CHANGELOG.** No bloco `## 1.2.1 - 2026-10-16` (o único em aberto; confira com a skill
  `sigft-lancar-versao`: um bloco só, sem número novo), as linhas que mandavam à Home mudam de lugar.
  Troque, palavra por palavra:
  - em "**tema claro**": `Na Home, à direita do título, escolha Escuro, Claro ou Sistema` →
    `Na Configuração (a engrenagem à direita do título da Home), em Aparência, escolha Escuro, Claro ou Sistema`;
  - em "**Ctrl+K**": `as ações da Home (Atividades do dia, Modelos de IA, Gastos de IA, Chaves de API, Atualizações, Abrir logs,` →
    `as ações da Home e da Configuração (Configuração, Atividades do dia, Gastos de IA, Modelos de IA, Chaves de API, Procurar atualizações, Abrir logs,`;
  - em "**letra grande**": `Na Home, ao lado do tema, escolha Normal ou Grande` →
    `Na Configuração, em Aparência, escolha Normal ou Grande`, e apague
    `, e o "Versões de teste" da Home desce para baixo da barra de botões` (a frase termina em "caber o texto.");
  - em "**aviso do Windows**": `Liga e desliga na Home, em "Avisar no Windows"; vem ligado.` →
    `Liga e desliga na Configuração, em Avisos; vem ligado.`

  E acrescente, logo depois da linha do aviso do Windows:

```markdown
- Interface: a **engrenagem** à direita do título da Home abre a janela **Configuração**, com tudo o que se ajusta no SIG-FT num lugar só: Aparência (tema e letra), Idioma, Seu nome, Avisos (aviso do Windows), Inteligência artificial (Chaves de API e Modelos de IA) e Atualizações (receber versões de teste e procurar atualizações). Cada mudança vale na hora, sem botão de salvar. A Home fica só com a saudação, as Atividades do dia e os Gastos de IA. O Ctrl+K também abre ("Configuração").
- Interface: o SIG-FT fala **espanhol, português e inglês**. Na primeira abertura (inclusive depois de atualizar) ele pergunta o idioma; depois, troca-se na Configuração, em Idioma, e vale na próxima abertura ("Reiniciar agora" fecha e abre de novo, se nenhuma tarefa estiver rodando). Muda a interface (botões, títulos, dicas, janelas, avisos, Ctrl+K, resumo do lote, aviso do Windows); o console, o portal, as planilhas e as fichas geradas continuam em português.
```

  `.venv/bin/python -m pytest -q tests/test_novidades.py tests/test_texto_da_ui.py` → PASS.

- [ ] **Step 5: base de conhecimento.** Em `docs/base-conhecimento/00-frontend.md`, logo antes de
  `## Pontos de Atenção`:

```markdown
### Configuração e idioma (2026-10-22)

- **Engrenagem** (`views/configuracao.py`, `JanelaConfiguracao`, uma `JanelaPainel`): à direita do
  título da Home (`HomeView.btn_configuracao`, `abrir_configuracao`) e no Ctrl+K. Seções e ordem em
  `catalogo.SECOES_DA_CONFIGURACAO`; os botões que vieram da barra em
  `catalogo.ACOES_DA_CONFIGURACAO`. Nenhuma regra nova: tema e letra pela Home
  (`escolher_tema`/`escolher_letra`), nome por `nome.guardar`, aviso por `aviso_windows.ligar`,
  canal de testes por `updater`, Chaves/Modelos/atualização pelos métodos da Home.
- **Idioma** (`sigft/app/idioma.py`, sem Qt): `t("texto em português", **valores)`; a chave é o
  próprio texto; `es`/`en` em `sigft/app/idiomas/*.json`; sem tradução vale o português. Constante de
  módulo em `marcar(...)` e `t()` onde aparece. Só a interface muda; console, portal e planilhas não.
  O idioma vale ao abrir: `main._preparar_qt` (`--idioma` no smoke), a pergunta da primeira abertura
  (`escolha_de_idioma.py`, antes da splash) e o "Reiniciar agora" (`reinicio.py`, recusa com tarefa
  rodando). Os botões do Qt seguem o idioma (`main.LOCALE_DO_QT`; `qtbase_pt_BR`/`qtbase_es` no pacote).
- **Ferramenta** `tools/textos_da_interface.py`: o que falta e sobra nos catálogos, `t(f"...")`,
  `--literais <arquivo>` (o que a guarda acusa), `--faltando es` (JSON para preencher), `--arrumar`.
- **Guardas:** `tests/test_textos_da_interface.py` (catálogos completos, mesmos `{valores}`, sem
  travessão, e todo `sigft/app_qt` sem texto de interface fora de `t()`, exceto `NAO_E_INTERFACE`, com
  o motivo); `tests/test_qt_idioma_telas.py` (cada parte montada em `es`/`en` sem português à vista);
  `tests/test_qt_idioma_varredura.py` (as 12 telas sem corte nem rolagem lateral). Os testes rodam em
  português (conftest); a largura fixa alarga fora do português (`letra._pede_folga`).
- **Tela nova ou texto novo:** escreva em português dentro de `t()`, rode a ferramenta e preencha
  `es` e `en` seguindo o glossário abaixo.

**Glossário** (não se traduzem: SIG-FT, PMIB, Portal PMIB, PDM, SAM-GM, STATUS_PMIB, LMR, TAG,
AutoSpec, Analyzer, PMIB Manager, Search, Gestão PMIB, Excel, PDF, JSON, RDS-PP, Aconex, Box,
GE Vernova, Itaipu, nomes de provedor de IA, os nomes dos idiomas):

| pt | es | en |
|---|---|---|
| ficha (técnica) | ficha (técnica) | (technical) sheet |
| planilha | planilla | spreadsheet |
| robô | robot | robot |
| característica técnica | característica técnica | technical characteristic |
| lote | lote | batch |
| console | consola | console |
| Configuração | Configuración | Settings |
| Chaves de API / Modelos de IA / Gastos de IA | Claves de API / Modelos de IA / Gastos de IA | API keys / AI models / AI costs |
| versão de teste | versión de prueba | test version |
| fornecedor | proveedor | supplier |
| pasta / arquivo / tela | carpeta / archivo / pantalla | folder / file / screen |

Espanhol com "usted"; inglês com imperativo simples; tradução curta (no máximo uns 20% a mais).
```

- [ ] **Step 6: mural do `CLAUDE.md`.** O mural tem 5 avisos (o máximo): mova o mais antigo
  (2026-10-15, Jonathan, a interface antiga saiu) para `docs/refatoracao/PENDENCIAS.md` como uma linha
  datada no fim da tabela (regra 2 do mural):

```markdown
| 2026-10-15 | Mural do CLAUDE.md (Jonathan) | A interface antiga (CustomTkinter) saiu do SIG-FT: `sigft/app/views/`, `widgets/`, `main.py` e o `--ctk` não existem mais; tela que muda é só `sigft/app_qt/views/`. A tela do AutoSpec é `sigft/app_qt/views/autospec.py`. Trava: `tests/test_sem_interface_antiga.py`. (Saiu do mural em 2026-10-22, quando o mural chegou a 6 avisos.) | Informativo |
```

  e acrescente no fim da tabela do mural:

```markdown
| 2026-10-22 | Jonathan | 🔴 **Engrenagem e idioma (es/pt/en):** tema, letra, aviso do Windows, chaves, modelos e atualizações saíram da Home para a janela Configuração (`views/configuracao.py`). Texto de interface agora é `t("texto em português")` (`sigft/app/idioma.py`; constante de módulo em `marcar()`), com tradução em `sigft/app/idiomas/es.json` e `en.json`; `tests/test_textos_da_interface.py` reprova literal de tela fora de `t()` e chave sem tradução.<br>Rafael: a tela do AutoSpec só trocou literal por `t()`; os teus testes de tela rodam em português e não mudaram. Texto novo na tela: `t()` + `python tools/textos_da_interface.py --faltando es` (e `en`); log de console continua em português. |
```

- [ ] **Step 7:** `bash scripts/check.sh` → verde. Commit:

```bash
git add CHANGELOG.md docs/base-conhecimento/00-frontend.md CLAUDE.md docs/refatoracao/PENDENCIAS.md
git commit -m "$(cat <<'EOF'
Engrenagem e idioma: CHANGELOG, doc da interface, glossario e mural

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RSbK7jX9qvsvyZKqnojmij
EOF
)"
```

- [ ] **Step 8: PR** para a branch oficial, depois da aprovação das capturas e da revisão final da
  branch inteira (a spec: um PR e uma rc só):

```bash
git push -u origin jonathan/configuracao-idioma
gh pr create --base claude/checkpoint-01-refactor-executor-5lawtu --head jonathan/configuracao-idioma \
  --title "Engrenagem de configuracao e idioma (es, pt, en)" --body "$(cat <<'EOF'
Spec: docs/superpowers/specs/2026-10-22-configuracao-e-idioma-design.md
Plano: docs/superpowers/plans/2026-10-22-configuracao-e-idioma.md

- Engrenagem na Home: janela Configuracao com Aparencia, Idioma, Seu nome, Avisos, Inteligencia artificial e Atualizacoes; a Home fica com a saudacao, Atividades do dia e Gastos de IA. Ctrl+K "Configuracao".
- Idioma: sigft/app/idioma.py (t() com o texto em portugues como chave), catalogos es/en, tools/textos_da_interface.py; pergunta na primeira abertura; Reiniciar agora (recusa com tarefa rodando); botoes do Qt no idioma.
- So a interface muda de idioma: console, portal e planilhas continuam em portugues.
- AutoSpec (tela cedida pelo Rafael): so literal virou t(); testes de tela dele intactos.

Verificacao: scripts/check.sh verde; --smoke nos tres idiomas, dois temas e duas letras; varredura das 12 telas em es/en sem corte nem rolagem; capturas aprovadas.
Revisao do espanhol pelo Jonathan antes do Release (rc).

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01RSbK7jX9qvsvyZKqnojmij
EOF
)"
```

---

## Autoconferência do plano

**Cobertura da spec:**
- Parte A, comportamento: engrenagem fantasma `settings` à direita do título, dica "Configuração",
  janela não modal e única (Task 1); as seis seções na ordem (Task 1, Idioma na Task 3); Aparência
  aplica na hora e marca o `ativo` (Task 1); Idioma com o aviso e "Reiniciar agora" só habilitado
  quando difere (Task 3); Seu nome com `nome.guardar` e a saudação na hora (Task 1); Avisos (Task 1);
  IA abre as MESMAS janelas (Task 1); Atualizações: versões de teste e procurar (Task 1); "Fechar" no
  rodapé, sem "Salvar" (Task 1, `JanelaPainel`); a Home perde o que a spec lista e fica com saudação,
  Atividades e Gastos (Task 1); Ctrl+K "Configuração" e as ações de antes (Task 1).
- Parte A, como: `views/configuracao.py`; `catalogo.py` fonte única com `SECOES_DA_CONFIGURACAO` e
  `ACOES_DA_HOME` só com o que fica na barra (Task 1); cor só no `estilo.py` (`#seletor_idioma`, Task 3);
  teste de medida da Home reescrito com o motivo (Task 1, Step 11 e commit).
- Parte A, testes: abrir pela Home e pelo Ctrl+K, uma instância; cada controle faz o mesmo; Home sem
  os itens; a engrenagem não cobre nem alarga, letra normal e grande (Task 1; nos dois temas, parametrizado).
- Parte B, comportamento: três idiomas guardados em `idioma` (Task 2); primeira abertura antes da
  janela, botões no próprio idioma, janela já no escolhido, nome depois, fechar = português e pergunta
  de novo (Task 3); reiniciar recusando com tarefa (Task 3); sem tradução cai no português (Task 2).
- Parte B, como: `idioma.py` com `atual`/`definir`/`t` e `{valores}` (Task 2); catálogos (Task 2);
  ferramenta com faltando/sobrando e `t(f"...")` (Task 2); guarda que cresce por etapa (Tasks 4 a 9);
  glossário e traduções feitas por quem implementa (Glossário; Tasks 4 a 9); diálogos, dicas e
  catálogo cedo (Tasks 4 e 5).
- Ordem da spec: 1 infraestrutura + primeira abertura + Idioma + menu/Home/engrenagem/Ctrl+K/splash/
  diálogos/dicas (Tasks 2 a 5); 2 as telas de três em três com as auxiliares (Tasks 6 a 9, na ordem
  da spec); 3 fechamento (Tasks 10 e 11; a revisão do espanhol é do Jonathan, Task 11 Step 3).
- AutoSpec: só literal → `t()`, testes do Rafael rodando em português (Task 8; ver Decisões abaixo).
- Riscos: medidas (Task 10: mecanismo da letra estendido + varredura nos três idiomas); testes que
  travam texto (conftest em português, Task 2); f-string (ferramenta e teste, Task 2).
- Entrega: um PR só, depois da revisão da branch inteira (Task 11 Step 8).

**Ambiguidades da spec resolvidas aqui:**
1. "QDialog não modal" → `JanelaPainel` (minimiza no Windows; mesmo comportamento de janela única dos
   painéis). Task 1.
2. "Reiniciar agora" com tarefa rodando → recusa com aviso, sem "mesmo assim". Task 3.
3. A escolha de idioma na engrenagem é guardada no clique, não no "Reiniciar agora". Task 3.
4. Testes do Rafael "passam a comparar com `t(...)`" → não precisam mudar: rodam em português, onde
   `t(x) == x`; não mexer nos arquivos dele é a leitura mais segura da fronteira. Task 8.
5. "Ajuste de largura estendido à troca de idioma" → o idioma só muda ao abrir; o ajuste vale com a
   letra normal fora do português, pelo mesmo vigia. Task 10.
6. Constante de módulo traduzida no import não funcionaria (import antes da pergunta; testes trocam de
   idioma) → `marcar()` + `t()` no uso. Task 2.
7. Botões padrão do Qt ("Sim"/"Não") também seguem o idioma (`qtbase_es`; inglês sem tradução), com o
   pacote e a conferência ajustados. Task 3.
8. "Procurar atualizações" no Ctrl+K: sem botão para pôr "Procurando...", o resultado chega pela caixa
   de sempre. Task 1.

**Nomes conferidos entre tarefas:** `catalogo.ACOES_DA_HOME`/`ACAO_CONFIGURACAO`/`ACOES_DA_CONFIGURACAO`/
`ACOES_QUE_A_HOME_FAZ`/`SECOES_DA_CONFIGURACAO` (1 → 3, 5); `HomeView.abrir_configuracao`,
`_configuracao_viva`, `escolher_tema` (devolve a escolha), `procurar_atualizacoes(botao=None)` (1);
`JanelaConfiguracao.marcar_tema`/`marcar_letra`/`_seletor`/`_botao_de_escolha` (1 → 3);
`idioma.t`/`marcar`/`definir`/`atual`/`escolhido`/`guardar`/`conferir`/`catalogo`/`NOMES`/`IDIOMAS`/
`PADRAO`/`NAO_SE_TRADUZ` (2 → 3 a 10); `escolha_de_idioma.perguntar_na_abertura`/`ENV_DESLIGAR`,
`reinicio.reiniciar`/`ENV_DESLIGAR` (3 → 5); `main._aplicar_idioma`/`LOCALE_DO_QT`/`_instalar_traducao`
(3 → 11); `textos_dicas.dicas_da_classe`/`dica_da_barra` (4 → 5); `tests/_idioma.em_idioma`/
`ainda_em_portugues` (2 → 4 a 10); fixture `janela` e `IDIOMAS` de `tests/test_qt_idioma_telas.py`
(5 → 6 a 9); `CONVERTIDOS`/`NAO_E_INTERFACE` (2 → 4 a 9); `letra._pede_folga`/`reavaliar_vigia`,
`tests/_varredura.varrer` (10).
