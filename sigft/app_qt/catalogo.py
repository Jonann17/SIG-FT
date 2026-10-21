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
     "Fatia a lista geral de PDMs da Itaipu por sistema, aplica o template das "
     "fichas e organiza as pastas de trabalho."),
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
    """Os módulos liberados (na ordem dos cartões da Home) e as ações. O módulo
    bloqueado fica fora: `show_frame` o recusaria."""
    no_menu = {item[2]: item[1] for item in MENU if item[0] == "botao"}
    lista = [Comando(f"tela:{alvo}", titulo, ICONE_DA_TELA[alvo], f"{no_menu.get(alvo, '')} {alvo}")
             for alvo, titulo, _descricao in MODULOS if alvo not in TELAS_BLOQUEADAS]
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
