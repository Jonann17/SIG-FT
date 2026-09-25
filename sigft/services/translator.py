r"""Tradutor Técnico PT -> ES (tela 4.2): traduz as respostas das
características técnicas e grava a aba que o Upload (4.3) lê.

O QUE MUDOU EM 2026-09-25 (spec
`docs/superpowers/specs/2026-09-25-tradutor-local-design.md`)
------------------------------------------------------------------------
Era uma chamada ao Google Tradutor por resposta, com 1 s de espera fixa
(e MyMemory quando o Google falhava): ~80 s por ficha, e cada resposta
saindo para dois serviços públicos. Quando os dois falhavam, o PORTUGUÊS ia
para a coluna do espanhol sem aviso.

Agora:

* a tradução é LOCAL (`sigft.core.tradutor_local`): nada sai deste
  computador, e uma ficha inteira vai ao modelo de uma vez;
* as regras (o que não se traduz, glossário da casa, conferências) moram em
  `services/traducao_respostas.py`, testadas sem Excel;
* **um Excel por lote**. O código antigo abria um `xw.App(visible=False)` por
  ficha, com a pasta em branco do `add_book`, e o `quit()` só rodava com
  `books.count == 0` -- que nunca acontecia: cada ficha deixava um Excel
  invisível aberto até o SIG-FT fechar;
* uma leitura e uma escrita por ficha (eram 5 chamadas ao Excel por linha).

O CONTRATO COM O UPLOAD (4.3) NÃO MUDOU: a aba `Especificações técnicas
copiar`, os três cabeçalhos, a pergunta com o número na frente
(`tech_specs.preparar_dados_ia` tira o número e casa o nome com o Master).
"""
from __future__ import annotations

import os
import shutil
import tempfile
import time
import unicodedata
from datetime import date, datetime
from types import SimpleNamespace

from unidecode import unidecode

from sigft import config
from sigft.core import tradutor_local
from sigft.core.excel import locking
from sigft.services import traducao_respostas as tr

ABA_ORIGEM = "Ficha Técnica Padrão"
ABA_DESTINO = "Especificações técnicas copiar"
CABECALHO = [
    "Pergunta",
    "Resposta (Espanhol s/ caracteres especiais)",
    "Resposta (Português s/ caracteres especiais)",
]
COLUNA_PERGUNTA = 3    # C
COLUNA_RESPOSTA = 13   # M
# Quantas linhas a leitura cobre de uma vez a partir da linha das
# características. O PDM com mais características tem 74 (planilha de
# 23/09/2026); a leitura para na primeira pergunta vazia.
MAX_LINHAS = 300

# Palavras que o gerador devolve para a tela saber o que houve, e que ela não
# mostra no log. "ABORTADO" = o lote nem começou (modelo ausente, por exemplo).
STATUS = frozenset({"SUCESSO", "ERRO", "ERRO_MOVER", "PARADO", "ABORTADO"})

_ABA_EN = "standard technical sheet"


# =============================================================================
# Célula -> texto
# =============================================================================
def texto_da_celula(valor) -> str:
    """O que a célula mostra, como texto.

    O Excel entrega número como `float`: o código antigo gravava `220.0` na
    coluna do português (e mandava `220.0` ao Google).
    """
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if isinstance(valor, float):
        if valor.is_integer():
            return str(int(valor))
        return format(valor, ".15g").replace(".", ",")
    if isinstance(valor, datetime):
        if (valor.hour, valor.minute, valor.second) == (0, 0, 0):
            return valor.strftime("%d/%m/%Y")
        return valor.strftime("%d/%m/%Y %H:%M")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    return str(valor).strip()


def _grupos_de_topo(texto: str):
    """`[(inicio, fim), ...]` dos parênteses de primeiro nível, ou `None` se
    eles não fecham."""
    grupos, profundidade, inicio = [], 0, None
    for i, c in enumerate(texto):
        if c == "(":
            if profundidade == 0:
                inicio = i
            profundidade += 1
        elif c == ")":
            profundidade -= 1
            if profundidade < 0:
                return None
            if profundidade == 0:
                grupos.append((inicio, i))
    return grupos if profundidade == 0 else None


def nome_da_pergunta(texto) -> str:
    """`"1 - PRESSÃO (Informar em bar):"` -> `"1 - PRESSÃO"`.

    O número fica: é o Upload (4.3) que o tira. A ajuda entre parênteses sai.
    Com DOIS grupos de parênteses, sai só o último: o nome também pode ter
    parênteses -- `FAIXA DE TENSAO DE ALIMENTACAO (CA)` e `(CC)` viravam o
    mesmo nome e o Upload não casava nenhum (PENDENCIAS, 2026-09-24).
    """
    bruto = str(texto or "").strip()
    corpo = bruto.rstrip(":. ").rstrip()
    grupos = _grupos_de_topo(corpo)
    if grupos and len(grupos) >= 2 and grupos[-1][1] == len(corpo) - 1:
        return corpo[:grupos[-1][0]].strip().rstrip(":. ")
    return bruto.split("(", 1)[0].strip().rstrip(":. ")


def ler_itens(linhas) -> list[tuple[str, str]]:
    """`[(pergunta, resposta), ...]` da faixa lida (C..M), até a primeira
    pergunta vazia -- o mesmo fim que o laço antigo tinha."""
    itens = []
    for linha in linhas or []:
        pergunta = linha[0] if linha else None
        if pergunta is None or str(pergunta).strip() == "":
            break
        indice = COLUNA_RESPOSTA - COLUNA_PERGUNTA
        resposta = linha[indice] if len(linha) > indice else None
        itens.append((nome_da_pergunta(pergunta), texto_da_celula(resposta)))
    return itens


def _sem_acento_minusculo(texto) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).lower().split())


def _sem_caracteres_especiais(texto) -> str:
    """Exigência do portal (era assim antes, e continua): sem acento."""
    return unidecode(str(texto or ""))


# =============================================================================
# Excel
# =============================================================================
def _excel_invisivel():
    """UM Excel para o lote, sem a pasta em branco que o `add_book=True`
    padrão do xlwings cria -- era ela que impedia o `quit()`."""
    import xlwings as xw

    app = xw.App(visible=False, add_book=False)
    for atributo, valor in (("display_alerts", False), ("screen_updating", False)):
        try:
            setattr(app, atributo, valor)
        except Exception:  # noqa: BLE001 -- conforto, não requisito
            pass
    return app


def _fechar_excel(app) -> None:
    try:
        app.quit()
    except Exception:  # noqa: BLE001
        pass
    try:
        app.kill()
    except Exception:  # noqa: BLE001 -- já saiu pelo quit()
        pass


def _aba_de_origem(livro):
    for aba in livro.sheets:
        if _sem_acento_minusculo(aba.name) == _sem_acento_minusculo(ABA_ORIGEM):
            return aba
    nomes = [aba.name for aba in livro.sheets]
    if any(_sem_acento_minusculo(n) == _ABA_EN for n in nomes):
        raise ValueError(
            "esta ficha e a versao em ingles (aba 'Standard Technical Sheet'). O "
            "tradutor traduz respostas em portugues para o espanhol.")
    raise ValueError(f"aba '{ABA_ORIGEM}' nao encontrada (abas: {', '.join(nomes)})")


def _escrever_aba(livro, linhas) -> None:
    """A aba copiar, recriada, numa escrita só, com a formatação de sempre
    (cabeçalho azul, zebrado, bordas, texto quebrado)."""
    if any(aba.name == ABA_DESTINO for aba in livro.sheets):
        livro.sheets[ABA_DESTINO].delete()
    aba = livro.sheets.add(ABA_DESTINO, after=livro.sheets[-1])

    matriz = [CABECALHO] + linhas
    ultima = len(matriz)
    # Texto ANTES de gravar: sem isso o Excel converte `1/2` em data e `0,5`
    # em número ao receber o valor.
    aba.range("A:C").number_format = "@"
    aba.range("A1").value = matriz

    aba.range("A:A").column_width = 40
    aba.range("B:C").column_width = 50
    if ultima >= 2:
        aba.range(f"2:{ultima}").row_height = 50
    tudo = aba.range(f"A1:C{ultima}")
    tudo.api.WrapText = True
    tudo.api.VerticalAlignment = -4108            # xlCenter
    tudo.api.Borders.LineStyle = 1
    tudo.api.Borders.Weight = 2
    cabecalho = aba.range("A1:C1")
    cabecalho.api.Font.Bold = True
    cabecalho.api.HorizontalAlignment = -4108
    cabecalho.color = (47, 117, 181)
    cabecalho.api.Font.Color = 0xFFFFFF
    for linha in range(2, ultima + 1):
        aba.range(f"A{linha}:C{linha}").color = (
            (221, 235, 247) if linha % 2 == 0 else (189, 215, 238))


def _traduzir_com_memoria(respostas, motor, glossario, memoria):
    """`traduzir_respostas`, mas só com o que o lote ainda não traduziu."""
    novas = list(dict.fromkeys(r for r in respostas if r not in memoria))
    if novas:
        memoria.update(zip(novas, tr.traduzir_respostas(novas, motor, glossario)))
    return [memoria[r] for r in respostas]


# =============================================================================
# O tradutor
# =============================================================================
class TechnicalTranslator:
    """`processar_arquivos(caminhos)` é um gerador de linhas de log, com as
    palavras de `STATUS` no meio para a tela saber o que houve.

    `motor`, `abrir_excel` e `glossario` existem para os testes; na tela, os
    três vêm dos padrões (o tradutor local, o Excel invisível e o glossário
    da casa com o do usuário por cima).
    """

    def __init__(self, motor=None, abrir_excel=None, glossario=None):
        self.stop_flag = False
        self._motor = motor
        self._abrir_excel = abrir_excel or _excel_invisivel
        self._glossario = glossario

    def request_stop(self):
        """Sinaliza para o lote parar antes da próxima ficha."""
        self.stop_flag = True

    # -- preparo ------------------------------------------------------------
    def caminho_do_glossario(self):
        """O arquivo do glossário do usuário, criado com as instruções se
        ainda não existir. É o que o botão "Abrir glossário" da tela abre."""
        caminho = tr.caminho_glossario_do_usuario()
        tr.criar_glossario_do_usuario(caminho)
        return caminho

    def _glossario_do_lote(self):
        if self._glossario is not None:
            return self._glossario
        caminho = tr.caminho_glossario_do_usuario()
        try:
            tr.criar_glossario_do_usuario(caminho)
        except OSError:
            pass  # sem o arquivo do usuário, vale o da casa
        return tr.glossario_em_uso(caminho)

    def _preparar_motor(self):
        motor = self._motor if self._motor is not None else tradutor_local.obter()
        preparar = getattr(motor, "preparar", None)
        if callable(preparar):
            preparar()
        return motor

    # -- o lote -------------------------------------------------------------
    def processar_arquivo(self, caminho_original, retry_lock=None):
        """Uma ficha só. Mantido para quem chamava o nome antigo."""
        yield from self.processar_arquivos([caminho_original], retry_lock=retry_lock)

    def processar_arquivos(self, caminhos, retry_lock=None):
        self.stop_flag = False
        caminhos = list(caminhos)
        inicio = time.monotonic()

        try:
            motor = self._preparar_motor()
            glossario = self._glossario_do_lote()
        except tradutor_local.TradutorIndisponivel as erro:
            yield f"[ERRO] {erro}"
            yield "ABORTADO"
            return
        yield (f"Tradução local de {len(caminhos)} ficha(s): nada sai deste computador. "
               f"Glossário: {len(glossario)} termo(s).")

        # Memória do LOTE: a mesma resposta em outra ficha não volta ao motor.
        # Vale só aqui dentro, porque o glossário não muda no meio do lote.
        memoria = {}
        excel = None
        feitas, contagem = 0, {}
        try:
            for indice, caminho in enumerate(caminhos, start=1):
                if self.stop_flag:
                    yield "[PARADO] Interrupção solicitada pelo usuário."
                    yield "PARADO"
                    return
                if excel is None:
                    excel = self._abrir_excel()
                for mensagem in self._uma_ficha(excel, caminho, motor, glossario, memoria,
                                                retry_lock, indice, len(caminhos), contagem):
                    if mensagem == "SUCESSO":
                        feitas += 1
                    yield mensagem
        finally:
            if excel is not None:
                _fechar_excel(excel)

        duracao = time.monotonic() - inicio
        partes = [f"{contagem.get(k, 0)} {rotulo}" for k, rotulo in (
            ("tradutor", "pelo tradutor"), ("glossario", "pelo glossário"),
            ("igual", "iguais (número, código)"), ("conferir", "para conferir"))
            if contagem.get(k)]
        yield (f"Tradução concluída: {feitas} de {len(caminhos)} ficha(s) em {duracao:.1f} s"
               + (f". Respostas: {', '.join(partes)}." if partes else "."))

    def _uma_ficha(self, excel, caminho_original, motor, glossario, memoria, retry_lock,
                   indice, total, contagem):
        nome = os.path.basename(caminho_original)
        yield f"[{indice}/{total}] {nome}"

        # Caminho longo: o Excel não abre acima de ~218 caracteres.
        caminho_trabalho, temporario = caminho_original, False
        if len(str(caminho_original)) > 240:
            yield "   [AVISO] Caminho longo. Usando uma cópia temporária..."
            try:
                caminho_trabalho = os.path.join(
                    tempfile.gettempdir(), f"temp_{int(time.time())}_{nome}")
                shutil.copy2(caminho_original, caminho_trabalho)
                temporario = True
            except Exception as erro:  # noqa: BLE001
                yield f"   [ERRO] Falha ao criar a cópia temporária: {erro}"
                yield "ERRO"
                return

        livro = None
        try:
            livro = excel.books.open(caminho_trabalho)
            aba = _aba_de_origem(livro)
            linha = config.LINHA_SPECS_FICHA
            faixa = aba.range((linha, COLUNA_PERGUNTA),
                              (linha + MAX_LINHAS - 1, COLUNA_RESPOSTA))
            itens = ler_itens(faixa.options(ndim=2).value)
            if not itens:
                yield f"   [AVISO] Nenhuma característica a partir da linha {linha}."

            traducoes = _traduzir_com_memoria([r for _, r in itens], motor, glossario, memoria)
            linhas = []
            for (pergunta, resposta), traducao in zip(itens, traducoes):
                if traducao.aviso:
                    yield f"   [CONFERIR] {pergunta}: {traducao.aviso}"
                linhas.append([pergunta,
                               _sem_caracteres_especiais(traducao.texto),
                               _sem_caracteres_especiais(resposta)])
            for origem, quantas in tr.resumo(traducoes).items():
                contagem[origem] = contagem.get(origem, 0) + quantas

            _escrever_aba(livro, linhas)
            # O `save()` do xlwings grava onde o arquivo já está; o adaptador
            # põe a gravação atrás da janela "feche o arquivo" de sempre.
            adaptador = SimpleNamespace(save=lambda _caminho: livro.save())
            locking.salvar_perguntando(adaptador, caminho_original, retry_lock=retry_lock)
        except Exception as erro:  # noqa: BLE001 -- uma ficha ruim não para o lote
            yield f"   [ERRO] {nome}: {erro}"
            yield "ERRO"
            return
        finally:
            if livro is not None:
                try:
                    livro.close()
                except Exception:  # noqa: BLE001
                    pass
            if temporario and os.path.exists(caminho_trabalho) and livro is None:
                try:
                    os.remove(caminho_trabalho)
                except OSError:
                    pass

        if temporario:
            try:
                shutil.copy2(caminho_trabalho, caminho_original)
                os.remove(caminho_trabalho)
            except Exception as erro:  # noqa: BLE001
                yield f"   [ERRO] Falha ao devolver a cópia temporária: {erro}"
                yield "ERRO_MOVER"
                return

        traduzidas = sum(1 for t in traducoes if t.origem in ("tradutor", "glossario"))
        yield f"   OK: {len(itens)} resposta(s), {traduzidas} traduzida(s)."
        yield "SUCESSO"
