"""Os dados da navegação, sem widget nenhum.

Eram cópia dos da interface antiga (a Home e o `main.py` dela), que saiu do
SIG-FT em 2026-10-15; `tests/test_qt_catalogo.py` trava os valores.
"""
from __future__ import annotations

from typing import NamedTuple

from sigft.app import busca

MENU = [
    ("secao", "Início da Ficha"),
    ("botao", "1. Cria Fichas PMIB", "CriaFichas"),
    ("botao", "2. Planilhas PMIB", "PDM"),
    ("botao", "3. Analyzer (IA)", "Analyzer"),
    ("secao", "Dados Técnicos & Upload"),
    ("botao", "4.1. Upload Condições", "UploadConditions"),
    ("botao", "4.2. Tradutor", "Translator"),
    ("botao", "4.3. Upload Specs", "UploadSpecs"),
    ("botao", "4.4. Correção de PDM", "CorrecaoPDM"),
    ("botao", "5. Upload duplicadas", "CopiaFichas"),
    ("botao", "6. AutoSpec AI (RAG)", "AutoSpec"),
    ("botao", "7. Aplicação LMR", "LMR"),
    ("secao", "Gestão"),
    ("botao", "8. PMIB Manager", "PMIBManager"),
    ("botao", "9. Search", "SearchPMIB"),
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
    ("CriaFichas", "Cria Fichas PMIB",
     "Lê a lista de materiais, escolhe o PDM de cada item com IA e cria as "
     "fichas no portal. Tem também a edição do código de projeto em massa."),
    ("PDM", "Planilhas PMIB",
     "Cria as planilhas das fichas PMIB a partir do template, com as "
     "características da planilha de PDMs, em português ou em inglês."),
    ("Analyzer", "Analyzer (IA)",
     "Dá nota às fichas preenchidas e separa as que passam das que voltam para "
     "correção. Gera o relatório de pendências para mandar ao fornecedor."),
    ("UploadConditions", "Upload de Condições",
     "Preenche no portal as condições de armazenamento, transporte, manutenção "
     "e descarte, a partir da ficha, com a tradução para o espanhol."),
    ("UploadSpecs", "Upload de Características",
     "Preenche as características técnicas da ficha no portal, uma linha por "
     "especificação."),
    ("CorrecaoPDM", "Correção de PDM",
     "Troca ou atualiza o PDM das fichas no portal sem perder as "
     "características: fotografa antes, repõe o que o PDM novo também tem, e "
     "lista o que não voltou."),
    ("Translator", "Tradutor Técnico",
     "Traduz as características das fichas de português para espanhol, no "
     "próprio computador, e grava numa aba nova da própria planilha."),
    ("CopiaFichas", "Fichas Duplicadas",
     "Copia uma ficha existente do portal para outra: campos, condições, "
     "características, PDM, documentos e imagens."),
    ("AutoSpec", "AutoSpec AI (RAG)",
     "Preenche ficha vazia lendo manuais em PDF e buscando datasheets na web, "
     "com conferência dos documentos duvidosos."),
    ("LMR", "Aplicação LMR",
     "Cadastra as aplicações (TAGs) das fichas no portal, e apaga quando "
     "preciso. As duas coisas ficam em abas da mesma seção."),
    ("PMIBManager", "PMIB Manager",
     "Atualiza o mapeamento a partir do Aconex: renomeia arquivos pelo RDS-PP, "
     "calcula o avanço, e mantém as abas de lista de preços e de atividades."),
    ("SearchPMIB", "Busca PMIB",
     "Procura um código ou descrição nas planilhas de uma pasta inteira, sem "
     "abrir arquivo por arquivo."),
]

TELAS_BLOQUEADAS = frozenset({"CorrecaoPDM"})


def dica_do_menu(alvo: str) -> str:
    """A dica do botão do menu lateral: a mesma descrição do cartão da Home."""
    descricao = next((d for chave, _t, d in MODULOS if chave == alvo), "")
    if alvo in TELAS_BLOQUEADAS:
        return (descricao + "\n\n" if descricao else "") + "Bloqueado nesta versão."
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

# O seletor de tema da janela Configuração (2026-10-20): escolha, texto, ícone e dica. O Ctrl+K
# oferece os três como "Tema: <texto>" e os faz por `HomeView.escolher_tema`.
SELETOR_TEMA = (
    ("escuro", "Escuro", "moon", "Tema escuro: fundo grafite, o padrão do SIG-FT."),
    ("claro", "Claro", "sun", "Tema claro: fundo branco, para ambiente bem iluminado."),
    ("sistema", "Sistema", "monitor",
     "Segue o tema do Windows (claro ou escuro) e muda junto quando ele mudar."),
)

# O seletor de letra da janela Configuração (2026-10-21, etapa 1b): escolha, texto e dica.
# Na seção Aparência, abaixo do de tema; sem ícone no botão (o pacote Lucide do
# SIG-FT não tem um de letra). O Ctrl+K oferece os dois como "Letra: <texto>" e os
# faz por `HomeView.escolher_letra`. As escolhas são as de `letra.TAMANHOS`.
SELETOR_LETRA = (
    ("normal", "Normal", "Letra do tamanho de sempre."),
    ("grande", "Grande", "Letra 2 px maior em todo o SIG-FT, para ler com mais folga."),
)

# As ações do Ctrl+K além dos módulos: chave, texto, ícone e palavras. Quem faz
# cada uma é `main.SIG_FT_App.executar_comando`; `tests/test_qt_paleta.py` cobra
# que toda chave tenha quem a faça.
ACOES = (
    ("inicio", "Início", "house", "home tela inicial"),
    *((a.chave, a.texto, a.icone, a.palavras) for a in ACOES_QUE_A_HOME_FAZ),
    ("logs", "Abrir logs", "folder-open", "pasta log"),
    *((f"tema_{escolha}", f"Tema: {texto}", icone, "aparencia cor")
      for escolha, texto, icone, _dica in SELETOR_TEMA),
    *((f"letra_{escolha}", f"Letra: {texto}", "settings", "tamanho fonte aparencia")
      for escolha, texto, _dica in SELETOR_LETRA),
)


SUFIXO_BLOQUEADO = " (bloqueado)"


def comandos() -> list[Comando]:
    """Os módulos (na ordem dos cartões da Home) e as ações. O módulo bloqueado
    aparece como no menu: apagado, com a mesma dica, e não se escolhe."""
    no_menu = {item[2]: item[1] for item in MENU if item[0] == "botao"}
    lista = []
    for alvo, titulo, _descricao in MODULOS:
        bloqueado = alvo in TELAS_BLOQUEADAS
        lista.append(Comando(
            f"tela:{alvo}", titulo + (SUFIXO_BLOQUEADO if bloqueado else ""), ICONE_DA_TELA[alvo],
            f"{no_menu.get(alvo, '')} {alvo}", bloqueado=bloqueado, dica=dica_do_menu(alvo)))
    lista += [Comando(f"acao:{chave}", texto, icone, palavras) for chave, texto, icone, palavras in ACOES]
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

    achados = [c for c in lista if all(t in onde(c) for t in termos)]
    return sorted(achados, key=lambda c: not busca.normalizar(c.texto).startswith(termos[0]))


MSG_TAREFA_EM_ANDAMENTO = (
    "Há uma tarefa em andamento (um robô, uma tradução ou uma consulta à IA).\n\n"
    "Se fechar agora, ela é interrompida no ponto em que está, e uma planilha "
    "que estava sendo gravada pode ficar pela metade.\n\n"
    "Fechar o SIG-FT mesmo assim?"
)

# A janela principal não montou (a Qt subiu, mas `SIG_FT_App()` levantou).
MSG_ABERTURA_FALHOU = (
    "O SIG-FT não conseguiu abrir a janela principal.\n\n{erro}\n\n"
    "O detalhe completo está em Documentos\\SIG-FT\\logs\\sigft.log. "
    "Mande esse arquivo para quem cuida do SIG-FT."
)
