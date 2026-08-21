r"""
Condições lidas da ficha ORIGINAL em modo de VISUALIZAÇÃO.

É a última peça que faltava para fechar a Fase 6. O usuário fechou a porta da
leitura em edição em 2026-08-20 (*"TUDO é para pegar do modo de visualização.
Somente a ficha ALVO é para entrar no modo de edição"*), e na visualização os
campos de Condições não são `input` -- são pares rótulo→valor. Copiar exige um
mapa RÓTULO VISÍVEL → campo de edição.

**O mapa nasceu VAZIO de propósito, e isso não era preguiça.** A redação exata
de cada rótulo não estava em lugar nenhum do repositório: `upload_conditions.py`
dá o SIGNIFICADO de alguns (`Input_PackingLength` é o comprimento da embalagem),
mas significado não é o texto que a tela mostra, e um rótulo escrito de memória
erra em SILÊNCIO -- a chave não casa, o campo não copia, ninguém fica sabendo. É
a classe de falha que este módulo inteiro existe para combater.

O que a versão vazia trazia era o **log de todo rótulo desconhecido**, e ele
funcionou: a rodada das 16:16 na ficha 4500063671.1257 devolveu os 17 rótulos da
tela, e a tabela (§5) é transcrição daquela lista.

Os testes cobrem as duas metades: a MÁQUINA (normalizar, converter, logar o que
falta) e a TABELA (cada rótulo real no seu campo, e o que ficou de fora com o
motivo).
"""
import pytest

from sigft.core.rpa import seletores_duplicada as sel
from sigft.services import duplicadas_condicoes as cond


# ===========================================================================
# 1. A chave de busca do rótulo
# ===========================================================================
# Por que normalizar em vez de casar o texto cru: o portal escreve o mesmo
# rótulo com acento, sem acento, com dois-pontos no fim e com espaço duplo
# dependendo da tela. Casar cru transformaria cada variação numa falha
# silenciosa.

def test_chave_de_rotulo_tira_acento_caixa_e_dois_pontos():
    assert cond.chave_de_rotulo("Comprimento da Embalagem Unitária:") == \
        "comprimento da embalagem unitaria"


def test_chave_de_rotulo_colapsa_espaco():
    assert cond.chave_de_rotulo("  PESO\n  LÍQUIDO  ") == "peso liquido"


def test_chave_de_rotulo_aceita_none_sem_estourar():
    """Rótulo ausente vira chave vazia -- a varredura da tela devolve `None`
    quando o `<span>` do rótulo não tem texto, e estourar aqui derrubaria a
    leitura inteira por causa de um campo."""
    assert cond.chave_de_rotulo(None) == ""


# ===========================================================================
# 2. A conversão rótulo→valor  ->  sub-aba→{sufixo: valor}
# ===========================================================================

@pytest.fixture
def mapa_de_teste(monkeypatch):
    """Um mapa MÍNIMO, injetado. Os testes exercitam a máquina; a tabela real
    é dado que vem da próxima rodada contra o portal."""
    monkeypatch.setattr(sel, "CONDICOES_ROTULO_PARA_CAMPO", {
        "comprimento da embalagem unitaria": ("Armazenamento", "Input_PackingLength"),
        "peso liquido": ("Armazenamento", "Input_LiquidWeight"),
        "cuidados no transporte": ("Transporte", "TextArea_TransportPackagingPT"),
    })


def test_converter_mapeia_rotulo_para_a_subaba_e_o_sufixo(mapa_de_teste):
    assert cond.converter_da_visualizacao(
        {"Comprimento da embalagem unitária": "40"}
    ) == {"Armazenamento": {"Input_PackingLength": "40"}}


def test_converter_junta_rotulos_da_mesma_subaba(mapa_de_teste):
    convertido = cond.converter_da_visualizacao({
        "Comprimento da embalagem unitária": "40",
        "Peso líquido": "12,5",
    })
    assert convertido == {"Armazenamento": {
        "Input_PackingLength": "40", "Input_LiquidWeight": "12,5"}}


def test_converter_separa_subabas_diferentes(mapa_de_teste):
    convertido = cond.converter_da_visualizacao({
        "Peso líquido": "12,5",
        "Cuidados no transporte": "Manter na horizontal",
    })
    assert sorted(convertido) == ["Armazenamento", "Transporte"]


def test_converter_pula_valor_em_branco(mapa_de_teste):
    """Campo vazio na original não pode virar escrita na alvo: `fill("")` é
    uma chance a mais de disparar validação do portal sem acrescentar nada --
    e, na ficha que já tem conteúdo, apagaria."""
    assert cond.converter_da_visualizacao({
        "Comprimento da embalagem unitária": "   ",
        "Peso líquido": "12,5",
    }) == {"Armazenamento": {"Input_LiquidWeight": "12,5"}}


def test_converter_sem_nada_reconhecido_devolve_vazio(mapa_de_teste):
    """Vazio e não `{"Armazenamento": {}}`: `escrever` decide pela verdade do
    dicionário, e uma sub-aba vazia faria o robô abrir a seção e salvar quatro
    abas sem escrever nada."""
    assert cond.converter_da_visualizacao({"Rótulo que ninguém mapeou": "x"}) == {}


def test_converter_com_mapa_vazio_devolve_vazio(monkeypatch):
    """Tabela vazia copia NADA -- não "copia o que der".

    Este teste nasceu descrevendo o estado do dia (2026-08-21 de manhã, com a
    tabela ainda por preencher) e foi reescrito na mesma tarde, quando ela
    ficou pronta: o que ele protege não é o vazio, é a regra. Enquanto um
    rótulo não estiver na tabela, ele não vira escrita -- que é o que mantém
    CONDIÇÕES fora do COMPLETO em vez de fechar pela metade.
    """
    monkeypatch.setattr(sel, "CONDICOES_ROTULO_PARA_CAMPO", {})
    assert cond.converter_da_visualizacao({"Peso líquido": "12,5"}) == {}


def test_converter_ignora_subaba_que_nao_existe_no_mapa_de_edicao(monkeypatch):
    """Defesa contra erro de digitação na tabela, que é preenchida À MÃO.

    Uma sub-aba inventada faria `escrever` procurar um campo que não existe --
    e como `escrever_subaba` percorre `condicoes.get(nome)` por nome, a
    escrita simplesmente sumiria. Melhor recusar aqui, com o nome no log.
    """
    monkeypatch.setattr(sel, "CONDICOES_ROTULO_PARA_CAMPO", {
        "peso liquido": ("Armazenagem", "Input_LiquidWeight"),  # não existe
    })
    linhas = []
    assert cond.converter_da_visualizacao({"Peso líquido": "12,5"},
                                          callback_log=linhas.append) == {}
    assert any("Armazenagem" in linha for linha in linhas)


# ===========================================================================
# 3. O log dos rótulos NÃO mapeados — a razão de existir desta rodada
# ===========================================================================

def test_converter_loga_cada_rotulo_desconhecido(mapa_de_teste):
    linhas = []
    cond.converter_da_visualizacao(
        {"Peso líquido": "12,5", "Volume da caixa": "3", "Cor da etiqueta": "azul"},
        callback_log=linhas.append)
    texto = "\n".join(linhas)
    assert "Volume da caixa" in texto
    assert "Cor da etiqueta" in texto
    assert "Peso líquido" not in texto  # esse o mapa conhece


def test_converter_loga_rotulo_desconhecido_mesmo_com_valor_vazio(mapa_de_teste):
    """O log existe para CONSTRUIR o mapa, não para relatar esta ficha. Um
    rótulo é o mesmo rótulo em toda ficha; que ESTA o tenha deixado em branco
    não o torna menos necessário na tabela."""
    linhas = []
    cond.converter_da_visualizacao({"Volume da caixa": ""},
                                   callback_log=linhas.append)
    assert any("Volume da caixa" in linha for linha in linhas)


def test_converter_nao_repete_o_mesmo_rotulo_no_log(mapa_de_teste):
    """As sub-abas de visualização repetem rótulo (os pares PT/ES aparecem nas
    duas), e três linhas iguais no log só atrapalham quem vai transcrever."""
    linhas = []
    cond.converter_da_visualizacao(
        [("Volume da caixa", "3"), ("Volume da caixa", "3")],
        callback_log=linhas.append)
    assert sum("Volume da caixa" in linha for linha in linhas) == 1


def test_converter_aceita_lista_de_pares(mapa_de_teste):
    """A varredura da tela pode trazer o MESMO rótulo duas vezes com valores
    diferentes; um `dict` perderia um deles antes de chegar aqui. A assinatura
    aceita pares para que quem chama não precise achatar cedo demais."""
    assert cond.converter_da_visualizacao(
        [("Peso líquido", "12,5")]
    ) == {"Armazenamento": {"Input_LiquidWeight": "12,5"}}


# ===========================================================================
# 4. A rodada: o robô abre as sub-abas da VISUALIZAÇÃO e lê
# ===========================================================================
# Até 2026-08-21 `ler_condicoes_da_original` só ABRIA a seção e fotografava o
# HTML no log de auditoria -- que é grande, cortado em 20 000 caracteres e mora
# num arquivo separado. Os rótulos precisam sair no log NORMAL, que é o que o
# usuário lê e cola.

class _PortalDeLeitura:
    """Portal falso que responde por sub-aba de visualização.

    `blocos_por_subaba` mapeia o nome da sub-aba para o que a varredura
    devolveria ali: `[(título do bloco, {rótulo: valor})]`.
    """

    def __init__(self, blocos_por_subaba, abre_secao=True, subabas_que_falham=()):
        self.engine = self
        self.blocos_por_subaba = dict(blocos_por_subaba)
        self.abre_secao = abre_secao
        self.subabas_que_falham = set(subabas_que_falham)
        self.subabas_abertas = []
        self.subaba_atual = None


@pytest.fixture
def robo_lendo(monkeypatch):
    """Instala os dublês de `extrator` que `ler_condicoes_da_original` usa."""
    from sigft.services import duplicadas_robo as robo

    def _instalar(portal):
        monkeypatch.setattr(robo.extrator, "abrir_secao",
                            lambda *_a, **_k: portal.abre_secao)

        def _abrir_subaba(_portal, nome, *_a, **_k):
            portal.subabas_abertas.append(nome)
            if nome in portal.subabas_que_falham:
                return False
            portal.subaba_atual = nome
            return True

        monkeypatch.setattr(robo.extrator, "abrir_subaba_de_condicoes", _abrir_subaba)
        monkeypatch.setattr(
            robo.extrator, "ler_secao_visivel",
            lambda *_a, **_k: list(portal.blocos_por_subaba.get(portal.subaba_atual, [])))
        return robo

    return _instalar


def test_ler_condicoes_abre_as_subabas_de_visualizacao(robo_lendo):
    portal = _PortalDeLeitura({})
    robo = robo_lendo(portal)
    robo.ler_condicoes_da_original(portal)
    assert portal.subabas_abertas == list(sel.SUBABAS_CONDICOES_VISUALIZACAO)


def test_ler_condicoes_devolve_o_que_o_mapa_reconheceu(robo_lendo, mapa_de_teste):
    portal = _PortalDeLeitura({
        "Armazenamento e transporte": [("Embalagem", {"Peso líquido": "12,5"})],
    })
    robo = robo_lendo(portal)
    assert robo.ler_condicoes_da_original(portal) == {
        "Armazenamento": {"Input_LiquidWeight": "12,5"}}


def test_ler_condicoes_junta_as_duas_subabas(robo_lendo, mapa_de_teste):
    portal = _PortalDeLeitura({
        "Armazenamento e transporte": [
            ("Embalagem", {"Peso líquido": "12,5"}),
            ("Transporte", {"Cuidados no transporte": "Na horizontal"}),
        ],
        "Manutenção e descarte": [
            ("Embalagem", {"Comprimento da embalagem unitária": "40"})],
    })
    robo = robo_lendo(portal)
    convertido = robo.ler_condicoes_da_original(portal)
    assert convertido["Armazenamento"] == {
        "Input_LiquidWeight": "12,5", "Input_PackingLength": "40"}
    assert convertido["Transporte"] == {
        "TextArea_TransportPackagingPT": "Na horizontal"}


def test_ler_condicoes_loga_os_rotulos_que_faltam_mapear(robo_lendo, mapa_de_teste):
    """O motivo desta rodada existir. Sem esta linha no log normal, a tabela
    de `CONDICOES_ROTULO_PARA_CAMPO` não tem como ser preenchida."""
    portal = _PortalDeLeitura({
        "Armazenamento e transporte": [("Embalagem", {"Volume da caixa": "3"})],
    })
    robo = robo_lendo(portal)
    linhas = []
    robo.ler_condicoes_da_original(portal, callback_log=linhas.append)
    assert any("Volume da caixa" in linha for linha in linhas)


def test_ler_condicoes_segue_quando_uma_subaba_nao_abre(robo_lendo, mapa_de_teste):
    """Sub-aba que não abre não pode custar a outra: meia seção copiada, com o
    log dizendo qual faltou, é melhor do que seção nenhuma."""
    portal = _PortalDeLeitura(
        {"Manutenção e descarte": [("x", {"Peso líquido": "12,5"})]},
        subabas_que_falham=("Armazenamento e transporte",))
    robo = robo_lendo(portal)
    linhas = []
    convertido = robo.ler_condicoes_da_original(portal, callback_log=linhas.append)
    assert convertido == {"Armazenamento": {"Input_LiquidWeight": "12,5"}}
    assert any("Armazenamento e transporte" in linha for linha in linhas)


def test_ler_condicoes_devolve_vazio_quando_a_secao_nao_abre(robo_lendo, mapa_de_teste):
    portal = _PortalDeLeitura(
        {"Armazenamento e transporte": [("x", {"Peso líquido": "12,5"})]},
        abre_secao=False)
    robo = robo_lendo(portal)
    linhas = []
    assert robo.ler_condicoes_da_original(portal, callback_log=linhas.append) == {}
    assert any("Condições" in linha for linha in linhas)


# ===========================================================================
# 5. A TABELA REAL — preenchida com os rótulos do log de 2026-08-21, 16:16
# ===========================================================================
# Os 17 rótulos abaixo são cópia literal do que o robô imprimiu na ficha
# 4500063671.1257. Nada aqui foi escrito de memória.

ROTULOS_DA_FICHA_1257 = (
    "Comprimento da embalagem unitária",
    "Largura da embalagem unitária",
    "Altura da embalagem unitária",
    "Necessidade de controle de temperatura e umidade",
    "Peso líquido",
    "Peso bruto",
    "Posição de armazenamento",
    "Empilhamento Máximo",
    "Nocivo",
    "Outros cuidados",
    "Embalagem para transporte",
    "Posições / Cuidados com içagem",
    "Cuidados durante a preservação e manuseio",
    "Métodos de limpeza ou secagem",
    "Tipo de legislação e/ou norma aplicada (brasileira e paraguaia) ou "
    "melhores práticas de mercado",
    "Classificação conforme NBR 10004",
    "Tipo de descarte de acordo com a legislação aplicada ou com as melhores "
    "práticas de mercado",
)

# Os que a tabela resolve, e para onde. O sufixo de cada um é EVIDÊNCIA, não
# tradução do rótulo: os seis primeiros vêm de `upload_conditions.py`, que roda
# contra o portal real e escreve nesses ids a partir de chaves de planilha
# (`dimensoes.comprimento`, `peso.liquido`, `empilhamento`).
ESPERADOS = {
    "Comprimento da embalagem unitária": ("Armazenamento", "Input_PackingLength"),
    "Largura da embalagem unitária": ("Armazenamento", "Input_PackagingWidth"),
    "Altura da embalagem unitária": ("Armazenamento", "Input_PackagingHeight"),
    "Peso líquido": ("Armazenamento", "Input_LiquidWeight"),
    "Peso bruto": ("Armazenamento", "Input_GrossWeight"),
    "Empilhamento Máximo": ("Armazenamento", "Input_Stacking"),
    "Embalagem para transporte": ("Transporte", "TextArea_TransportPackagingPT"),
    "Posições / Cuidados com içagem": ("Transporte", "TextArea_PositionCarePT"),
    "Cuidados durante a preservação e manuseio":
        ("Manutenção", "TextArea_PreservationCarePT"),
    "Métodos de limpeza ou secagem": ("Manutenção", "TextArea_CleaningMethodPT"),
    "Tipo de legislação e/ou norma aplicada (brasileira e paraguaia) ou "
    "melhores práticas de mercado": ("Descarte", "TextArea_TypeLegislationPT"),
    "Tipo de descarte de acordo com a legislação aplicada ou com as melhores "
    "práticas de mercado": ("Descarte", "TextArea_DiscardTypePT"),
}


@pytest.mark.parametrize("rotulo,destino", sorted(ESPERADOS.items()))
def test_a_tabela_resolve_o_rotulo_real(rotulo, destino):
    assert sel.CONDICOES_ROTULO_PARA_CAMPO[cond.chave_de_rotulo(rotulo)] == destino


@pytest.mark.parametrize("rotulo", [r for r in ROTULOS_DA_FICHA_1257
                                    if r not in ESPERADOS])
def test_o_que_a_visualizacao_nao_entrega_fica_de_fora(rotulo):
    """Rádio, checkbox e o rótulo sem sufixo conhecido NÃO entram na tabela.

    Na visualização eles são texto ("Horizontal", "Sem necessidade"); na edição
    são `RadioButtonN-input`/`CheckboxN`, e QUAL deles é qual não está em lugar
    nenhum. Mapear no chute escreveria no campo errado -- e um radio errado numa
    ficha de armazenamento é pior do que um campo vazio, porque parece resposta.
    """
    assert cond.chave_de_rotulo(rotulo) not in sel.CONDICOES_ROTULO_PARA_CAMPO


def test_todo_destino_da_tabela_existe_no_mapa_de_edicao():
    """Guarda contra erro de digitação: a tabela é escrita à mão."""
    for chave, (subaba, sufixo) in sel.CONDICOES_ROTULO_PARA_CAMPO.items():
        assert subaba in sel.CONDICOES_POR_SUBABA, chave
        assert sufixo in sel.CONDICOES_POR_SUBABA[subaba]["textos"], chave


def test_toda_chave_da_tabela_ja_esta_normalizada():
    """Chave com acento ou maiúscula nunca casaria -- `chave_de_rotulo`
    normaliza o que vem da tela, não o que está na tabela."""
    for chave in sel.CONDICOES_ROTULO_PARA_CAMPO:
        assert chave == cond.chave_de_rotulo(chave)


# ===========================================================================
# 6. A METADE EM ESPANHOL — o que a visualização não entrega
# ===========================================================================
# Cada texto longo tem PAR na edição (`..._PT` e `..._ES`) e a visualização
# mostra UM valor só: o bloco é o `Block_ExpressionBothLenguage`, e o que fica
# visível é o português -- o espanhol, se está em algum lugar, está atrás do
# tooltip, que a varredura não abre.
#
# Copiar o texto português para dentro do campo espanhol seria INVENTAR uma
# tradução na ficha de outra pessoa. Então o robô copia o PT e diz que a seção
# não está completa -- porque não está. Fechar CONDIÇÕES = COMPLETO com metade
# dos campos em branco é a mesma mentira de planilha que este módulo inteiro
# combate, e ela dura mais do que qualquer erro de tela.

def test_o_par_em_espanhol_do_que_foi_escrito_e_reportado():
    faltando = cond.sufixos_em_espanhol_nao_copiados(
        {"Transporte": {"TextArea_TransportPackagingPT": "Manter seco"}})
    assert faltando == ["TextArea_TransportPackagingES"]


def test_campo_numerico_nao_tem_par_em_espanhol():
    """Número é número nos dois idiomas -- `Input_LiquidWeight` é um campo só."""
    assert cond.sufixos_em_espanhol_nao_copiados(
        {"Armazenamento": {"Input_LiquidWeight": "0,035"}}) == []


def test_condicoes_nao_fecha_completa_com_o_espanhol_vazio():
    portal = _PortalQueAceitaTudo()
    resultado = cond.escrever(
        portal, {"Transporte": {"TextArea_TransportPackagingPT": "Manter seco"}})

    assert not resultado.ok
    assert "espanhol" in resultado.detalhe


def test_condicoes_so_com_numeros_fecha_completa():
    """Sem texto bilíngue não há metade faltando -- e recusar aqui seria
    inventar pendência para a ficha que está certa."""
    portal = _PortalQueAceitaTudo()
    resultado = cond.escrever(
        portal, {"Armazenamento": {"Input_LiquidWeight": "0,035"}})

    assert resultado.ok


class _PortalQueAceitaTudo:
    """Portal em que tudo dá certo: escreve, salva e relê igual."""

    def __init__(self):
        self.engine = self
        self.valores = {}

    @staticmethod
    def _sufixo(seletor):
        import re
        achado = re.search(r"contains\(@id, '([^']+)'\)", seletor)
        return achado.group(1) if achado else seletor

    def safe_click(self, _seletor):
        pass

    def safe_fill(self, seletor, texto):
        self.valores[self._sufixo(seletor)] = texto

    def valor_se_existir(self, seletor):
        return self.valores.get(self._sufixo(seletor))

    def esta_marcado(self, _seletor):
        return False

    def check_or_uncheck(self, _seletor, _valor, _log=None):
        return True

    def salvar_e_confirmar(self, _nome, _log=None, **_kwargs):
        return True
