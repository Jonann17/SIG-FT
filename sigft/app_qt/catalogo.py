"""Os dados da navegação, sem widget nenhum.

Eram cópia dos da interface antiga (a Home e o `main.py` dela), que saiu do
SIG-FT em 2026-10-15; `tests/test_qt_catalogo.py` trava os valores.
"""
from __future__ import annotations

from typing import NamedTuple

from sigft.app import busca
from sigft.app.idioma import marcar, t

MENU = [
    ("secao", marcar("Início da Ficha")),
    ("botao", marcar("1. Cria Fichas PMIB"), "CriaFichas"),
    ("botao", marcar("2. Planilhas PMIB"), "PDM"),
    ("botao", marcar("3. Analyzer (IA)"), "Analyzer"),
    ("secao", marcar("Dados Técnicos & Upload")),
    ("botao", marcar("4.1. Upload Condições"), "UploadConditions"),
    ("botao", marcar("4.2. Tradutor"), "Translator"),
    ("botao", marcar("4.3. Upload Specs"), "UploadSpecs"),
    ("botao", marcar("4.4. Correção de PDM"), "CorrecaoPDM"),
    ("botao", marcar("5. Upload duplicadas"), "CopiaFichas"),
    ("botao", marcar("6. AutoSpec AI (RAG)"), "AutoSpec"),
    ("botao", marcar("7. Aplicação LMR"), "LMR"),
    ("secao", marcar("Gestão")),
    ("botao", marcar("8. PMIB Manager"), "PMIBManager"),
    ("botao", marcar("9. Search"), "SearchPMIB"),
]

# O ícone de cada tela, no menu e no card da Home (sistema visual, 2026-10-20):
# nomes de `sigft/app_qt/icones.NOMES` (Lucide).
ICONE_DA_TELA = {
    "Home": "house",
    "CriaFichas": "file-plus",
    "PDM": "table",
    "Analyzer": "chart-column",
    "UploadConditions": "upload",
    "Translator": "languages",
    "UploadSpecs": "list",
    "CorrecaoPDM": "wrench",
    "CopiaFichas": "copy",
    "AutoSpec": "sparkles",
    "LMR": "tag",
    "PMIBManager": "folder-kanban",
    "SearchPMIB": "search",
}

MODULOS = [
    ("CriaFichas", marcar("Cria Fichas PMIB"),
     marcar("Lê a lista de materiais, escolhe o PDM de cada item com IA e cria as "
            "fichas no portal. Tem também a edição do código de projeto em massa.")),
    ("PDM", marcar("Planilhas PMIB"),
     marcar("Cria as planilhas das fichas PMIB a partir do template, com as "
            "características da planilha de PDMs, em português ou em inglês.")),
    ("Analyzer", marcar("Analyzer (IA)"),
     marcar("Dá nota às fichas preenchidas e separa as que passam das que voltam para "
            "correção. Gera o relatório de pendências para mandar ao fornecedor.")),
    ("UploadConditions", marcar("Upload de Condições"),
     marcar("Preenche no portal as condições de armazenamento, transporte, manutenção "
            "e descarte, a partir da ficha, com a tradução para o espanhol.")),
    ("UploadSpecs", marcar("Upload de Características"),
     marcar("Preenche as características técnicas da ficha no portal, uma linha por "
            "especificação.")),
    ("CorrecaoPDM", marcar("Correção de PDM"),
     marcar("Troca ou atualiza o PDM das fichas no portal sem perder as "
            "características: fotografa antes, repõe o que o PDM novo também tem, e "
            "lista o que não voltou.")),
    ("Translator", marcar("Tradutor Técnico"),
     marcar("Traduz as características das fichas de português para espanhol, no "
            "próprio computador, e grava numa aba nova da própria planilha.")),
    ("CopiaFichas", marcar("Fichas Duplicadas"),
     marcar("Copia uma ficha existente do portal para outra: campos, condições, "
            "características, PDM, documentos e imagens.")),
    ("AutoSpec", marcar("AutoSpec AI (RAG)"),
     marcar("Preenche ficha vazia lendo manuais em PDF e buscando datasheets na web, "
            "com conferência dos documentos duvidosos.")),
    ("LMR", marcar("Aplicação LMR"),
     marcar("Cadastra as aplicações (TAGs) das fichas no portal, e apaga quando "
            "preciso. As duas coisas ficam em abas da mesma seção.")),
    ("PMIBManager", marcar("PMIB Manager"),
     marcar("Atualiza o mapeamento a partir do Aconex: renomeia arquivos pelo RDS-PP, "
            "calcula o avanço, e mantém as abas de lista de preços e de atividades.")),
    ("SearchPMIB", marcar("Busca PMIB"),
     marcar("Procura um código ou descrição nas planilhas de uma pasta inteira, sem "
            "abrir arquivo por arquivo.")),
]

TELAS_BLOQUEADAS = frozenset({"CorrecaoPDM"})


def dica_do_menu(alvo: str) -> str:
    """A dica do botão do menu lateral: a mesma descrição do cartão da Home."""
    descricao = next((t(d) for chave, _t, d in MODULOS if chave == alvo), "")
    if alvo in TELAS_BLOQUEADAS:
        return (descricao + "\n\n" if descricao else "") + t("Bloqueado nesta versão.")
    return descricao


# --- Ctrl+K (etapa 1b, 2026-10-21) ------------------------------------------------

class Comando(NamedTuple):
    """Um item da caixa do Ctrl+K."""
    chave: str          # "tela:CriaFichas" ou "acao:modelos"
    texto: str
    icone: str          # nome de `icones.NOMES`
    palavras: str = ""  # o que mais a busca acha (o texto do menu, sinônimos)
    bloqueado: bool = False  # aparece apagado e não se escolhe (como no menu)
    dica: str = ""


class AcaoDaHome(NamedTuple):
    """Um botão da barra da Home, que o Ctrl+K também oferece."""
    chave: str
    texto: str          # o do botão (os testes de medida da Home o travam)
    icone: str          # nome de `icones.NOMES`
    variante: str       # a variante do botão (a cor vem da folha do tema)
    metodo: str         # o método da `HomeView` que a faz
    palavras: str = ""  # o que mais a busca do Ctrl+K acha


# As ações da Home NUM LUGAR SÓ (2026-10-21; a engrenagem, 2026-10-22): a barra
# da Home (`views/home.BARRA`), a janela Configuração (`views/configuracao`), o
# Ctrl+K (`ACOES`) e quem faz cada uma (`main.ACAO_NA_HOME`) saem daqui. Todas
# são métodos da `HomeView`.
ACOES_DA_HOME = (
    AcaoDaHome("atividades", marcar("Atividades do dia"), "clipboard-check", "primario",
               "abrir_mural_atividades", marcar("mural")),
    AcaoDaHome("gastos", marcar("Gastos de IA"), "circle-dollar-sign", "primario",
               "abrir_janela_gastos_ia", marcar("custo uso")),
)
# A engrenagem, à direita do título da Home, e o item do Ctrl+K que abre a janela.
ACAO_CONFIGURACAO = AcaoDaHome("configuracao", marcar("Configuração"), "settings", "fantasma",
                               "abrir_configuracao", marcar("engrenagem opcoes preferencias ajustes"))
# Os botões que moram na janela Configuração: saíram da barra da Home em 2026-10-22.
ACOES_DA_CONFIGURACAO = (
    AcaoDaHome("modelos", marcar("Modelos de IA"), "bot", "primario",
               "abrir_janela_modelos_ia", marcar("ia llm provedor")),
    AcaoDaHome("chaves", marcar("Chaves de API"), "key-round", "secundario",
               "abrir_janela_chaves_api", marcar("api key senha")),
    AcaoDaHome("atualizacoes", marcar("Procurar atualizações"), "refresh-cw", "secundario",
               "procurar_atualizacoes", marcar("procurar versao nova atualizar")),
)
# Tudo o que a Home faz pelo Ctrl+K, na ordem da caixa.
ACOES_QUE_A_HOME_FAZ = (ACAO_CONFIGURACAO, *ACOES_DA_HOME, *ACOES_DA_CONFIGURACAO)

# As seções da janela Configuração, de cima para baixo: chave e título. A chave
# é o método que monta a seção (`JanelaConfiguracao._secao_<chave>`).
SECOES_DA_CONFIGURACAO = (
    ("aparencia", marcar("Aparência")),
    ("idioma", marcar("Idioma")),
    ("nome", marcar("Seu nome")),
    ("avisos", marcar("Avisos")),
    ("ia", marcar("Inteligência artificial")),
    ("atualizacoes", marcar("Atualizações")),
)

# O seletor de tema da janela Configuração (2026-10-20): escolha, texto, ícone e dica. O Ctrl+K
# oferece os três como "Tema: <texto>" e os faz por `HomeView.escolher_tema`.
SELETOR_TEMA = (
    ("escuro", marcar("Escuro"), "moon", marcar("Tema escuro: fundo grafite, o padrão do SIG-FT.")),
    ("claro", marcar("Claro"), "sun", marcar("Tema claro: fundo branco, para ambiente bem iluminado.")),
    ("sistema", marcar("Sistema"), "monitor",
     marcar("Segue o tema do Windows (claro ou escuro) e muda junto quando ele mudar.")),
)

# O seletor de letra da janela Configuração (2026-10-21, etapa 1b): escolha, texto e dica.
# Na seção Aparência, abaixo do de tema; sem ícone no botão (o pacote Lucide do
# SIG-FT não tem um de letra). O Ctrl+K oferece os dois como "Letra: <texto>" e os
# faz por `HomeView.escolher_letra`. As escolhas são as de `letra.TAMANHOS`.
SELETOR_LETRA = (
    ("normal", marcar("Normal"), marcar("Letra do tamanho de sempre.")),
    ("grande", marcar("Grande"), marcar("Letra 2 px maior em todo o SIG-FT, para ler com mais folga.")),
)


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


def filtrar(lista, consulta: str) -> list[Comando]:
    """Os comandos que têm TODAS as palavras da `consulta` (sem acento, sem caixa)
    no texto ou nas palavras; os que COMEÇAM pela primeira vêm antes (ordem
    estável: no empate, a da lista)."""
    termos = busca.normalizar(consulta).split()
    if not termos:
        return list(lista)

    def onde(comando: Comando) -> str:
        return busca.normalizar(f"{comando.texto} {comando.palavras}")

    achados = [c for c in lista if all(termo in onde(c) for termo in termos)]
    return sorted(achados, key=lambda c: not busca.normalizar(c.texto).startswith(termos[0]))


MSG_TAREFA_EM_ANDAMENTO = marcar(
    "Há uma tarefa em andamento (um robô, uma tradução ou uma consulta à IA).\n\n"
    "Se fechar agora, ela é interrompida no ponto em que está, e uma planilha "
    "que estava sendo gravada pode ficar pela metade.\n\n"
    "Fechar o SIG-FT mesmo assim?"
)

# A janela principal não montou (a Qt subiu, mas `SIG_FT_App()` levantou).
MSG_ABERTURA_FALHOU = marcar(
    "O SIG-FT não conseguiu abrir a janela principal.\n\n{erro}\n\n"
    "O detalhe completo está em Documentos\\SIG-FT\\logs\\sigft.log. "
    "Mande esse arquivo para quem cuida do SIG-FT."
)
