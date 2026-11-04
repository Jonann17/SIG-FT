"""As dicas que aparecem ao parar o mouse sobre um botão (2026-10-20).

Ficam TODAS aqui, e não espalhadas pelas telas, por dois motivos: quem for
revisar o texto lê num lugar só, e `tests/test_qt_dicas.py` confere que cada
chave aponta para um botão que existe -- botão renomeado não deixa dica órfã
em silêncio.

Chave: nome da CLASSE da tela (ou de uma classe-mãe, para o que vem de
`TelaDeUpload`) -> {atributo do botão: dica}. Escreva para quem usa: o que
acontece ao clicar, o que precisa estar pronto antes, e se mexe no portal.
"""
from __future__ import annotations

from sigft.app.idioma import marcar, t

# [2026-10-22] As dicas são marcadas (`marcar`) e traduzidas por
# `dicas_da_classe` e `dica_da_barra`; a frase do portal entra no lugar de
# `{portal}` já no idioma da sessão.
PORTAL = marcar("Abre o navegador no Portal PMIB (o login é feito por você).")

DICAS: dict[str, dict[str, str]] = {
    "TelaDeUpload": {
        "btn_ia": marcar("Lê as fichas selecionadas com a IA e monta os dados para o portal. "
                         "Nada é enviado ao portal nesta etapa."),
        "btn_parar_ia": marcar("Pede para a leitura com IA parar. O que já foi lido fica."),
        "btn_web_mem": marcar("Envia ao portal o que a IA acabou de processar, sem precisar do Excel. {portal}"),
        "btn_web_file": marcar("Envia ao portal os dados de um Excel de resultados salvo antes. {portal}"),
        "btn_parar_web": marcar("Pede para o robô parar. As fichas já enviadas ficam no portal."),
    },
    "ModuloAnalyzer": {
        "btn_config": marcar("Ajusta quanto cada critério pesa na nota da ficha."),
        "btn_run": marcar("Dá nota às fichas selecionadas e separa as que passam das que voltam "
                          "para correção."),
        "btn_relatorio": marcar("Grava o .xlsx de pendências na pasta de saída, para mandar ao fornecedor."),
    },
    "ModuloApagarLMR": {
        "btn_run": marcar("Apaga do portal as aplicações (TAGs) da ficha informada. {portal}"),
    },
    "ModuloLMR": {
        "btn_run": marcar("Escolha o Excel com as TAGs; o robô as cadastra nas fichas. {portal}"),
    },
    "ModuloAutoSpec": {
        "btn_status": marcar("Escolha o _STATUS_PMIB: é dele que saem as fichas e para ele voltam os resultados."),
        "btn_add": marcar("Põe na fila as fichas e documentos escolhidos acima."),
        "btn_run": marcar("Processa a fila: lê os PDFs, busca datasheets na web e preenche as fichas "
                          "com a IA."),
        "btn_conf": marcar("Processa de novo só os documentos que você marcou na conferência."),
        "btn_conf_salvar": marcar("Grava a conferência num .txt, para continuar outro dia."),
        "btn_conf_importar": marcar("Retoma uma conferência salva antes, inclusive de outra sessão."),
    },
    "ModuloBuscaPMIB": {
        "btn_pasta": marcar("Escolha a pasta onde estão as planilhas a pesquisar."),
        "btn_search": marcar("Procura o termo em todas as planilhas da pasta, sem abrir uma por uma."),
    },
    "ModuloCopiaFichas": {
        "btn_status": marcar("Escolha o _STATUS_PMIB com as fichas duplicadas a copiar."),
        "btn_resumo": marcar("Revise e corrija a lista de fichas antes de mandar o robô."),
        "btn_robo_novo": marcar("Copia cada ficha original para a sua duplicada e confere cada aba "
                                "depois de salvar. {portal}"),
    },
    "ModuloCorrecaoPDM": {
        "btn_status": marcar("Escolha o _STATUS_PMIB com as fichas a corrigir."),
        "btn_catalogo": marcar("Opcional: a planilha de PDMs, para escolher o PDM novo pelo nome."),
        "btn_so_revisao": marcar("Marca as fichas selecionadas para só atualizar a revisão do PDM."),
        "btn_escolher_pdm": marcar("Escolhe o PDM novo para as fichas selecionadas."),
        "btn_limpar": marcar("Desfaz a escolha das fichas selecionadas."),
        "btn_parar": marcar("Pede para o robô parar."),
        "btn_rodar": marcar("Troca o PDM no portal sem perder as características: fotografa antes, "
                            "repõe depois e lista o que não voltou. {portal}"),
    },
    "ModuloCriaFichas": {
        "btn_pmib": marcar("Escolha o Excel com a lista de materiais do lote."),
        "btn_pdm": marcar("Escolha a planilha mestra de PDMs: é dela que a IA escolhe o PDM de cada item."),
        "btn_run_ai": marcar("A IA escolhe o PDM de cada item. Você revisa antes de qualquer coisa ir "
                             "ao portal."),
        "btn_run_auto": marcar("Cria no portal as fichas revisadas. {portal}"),
        "btn_resumo": marcar("Mostra o que a IA escolheu para cada item, para revisar e corrigir."),
        "btn_save": marcar("Grava no Excel o resultado do lote."),
        "btn_reset": marcar("Limpa o lote atual para começar outro. Nada no portal é desfeito."),
        "btn_excel_edicao": marcar("Escolha o Excel com as fichas e o código de projeto novo."),
        "btn_run_edicao": marcar("Troca o código de projeto das fichas no portal, em massa. {portal}"),
    },
    "ModuloPDM": {
        "btn_pmib": marcar("Escolha o _STATUS_PMIB que lista as fichas a criar."),
        "btn_template": marcar("Escolha o template de ficha (.xlsx) que será preenchido."),
        "btn_sam_gm": marcar("Escolha a planilha de PDMs (SAM-GM): dela saem as características de cada ficha."),
        "btn_criar_fichas": marcar("Gera as planilhas de ficha PMIB a partir do template escolhido."),
    },
    "ModuloPMIBManager": {
        "btn_api": marcar("Escolha o histórico exportado do Aconex DocManager (.xlsx)."),
        "btn_buscar": marcar("Escolha a pasta raiz dos arquivos do projeto."),
        "btn_master": marcar("Escolha a planilha de Mapeamento Sobressalentes que será atualizada."),
        "btn_run": marcar("Renomeia os arquivos pelo RDS-PP, calcula o avanço e atualiza o mapeamento."),
        "btn_painel": marcar("Gera só o painel de acompanhamento, sem rodar a gestão inteira."),
        "btn_autorizados": marcar("Escolha o export de autorizados baixado do portal (.xlsx)."),
        "btn_aplicar": marcar("Marca no mapeamento as fichas que o export diz que foram autorizadas."),
        "btn_conferir": marcar("Confere no próprio portal se as autorizações estão lá. {portal}"),
    },
    "ModuloRevisaoAmp": {
        "btn_amp": marcar("Manda ao AMP, uma por vez, as listas marcadas. Cada uma volta como um HTML na "
                          "pasta dela; nada é aplicado no Excel."),
        "btn_testar_amp": marcar("Confere a rede, a chave e o workflow publicado (ping). Não manda documento e "
                                 "não chama o agente."),
        "btn_webhook": marcar("O endereço e a chave do workflow da revisão de listas no AMP. A chave fica "
                              "mascarada."),
        "btn_copiar_diag": marcar("Copia o diagnóstico das listas que falharam, sem texto de documento e sem a "
                                  "chave, para colar numa conversa nova com o Claude."),
        "btn_parar": marcar("Para depois da lista que está no AMP. As que já voltaram ficam."),
        "btn_marcar": marcar("Marca todas as listas que podem ir ao AMP."),
        "btn_desmarcar": marcar("Desmarca todas as listas."),
    },
    "ModuloTranslator": {
        "btn_run": marcar("Escolha as planilhas; a tradução para o espanhol roda no computador e vai "
                          "para uma aba nova da própria planilha."),
        "btn_stop": marcar("Pede para a tradução parar."),
        "btn_glossario": marcar("Abre a lista de termos que a tradução sempre corrige."),
    },
    "HomeView": {
        "btn_salvar_chaves": marcar("Grava as chaves de API neste computador (Documentos\\SIG-FT)."),
        "btn_atualizar_catalogo_ia": marcar("Baixa do provedor a lista atual de modelos e preços."),
        "btn_aplicar_recomendados_ia": marcar("Escolhe para cada tarefa o modelo recomendado."),
        "btn_salvar_selecao_ia": marcar("Grava os modelos escolhidos para cada tarefa."),
        "btn_atualizar_gastos_ia": marcar("Recalcula o gasto com IA a partir dos logs deste computador."),
        "btn_pasta_logs_ia": marcar("Abre a pasta de logs do SIG-FT no Explorador."),
    },
    # A janela Configuração (2026-10-22): os botões que vieram da barra da Home.
    "JanelaConfiguracao": {
        "btn_modelos": marcar("Escolhe qual modelo de IA cada módulo usa."),
        "btn_chaves": marcar("Cadastra as chaves de API (Gemini, OpenRouter, busca na web)."),
        "caixa_canal_testes": marcar("Marcado, o aviso de atualização oferece também as versões de teste (rc)."),
        "btn_atualizacoes": marcar("Pergunta agora se há versão nova do SIG-FT."),
    },
}


# Os botões da barra da Home, pela CHAVE de `home.BARRA`.
DICAS_DA_BARRA_DA_HOME: dict[str, str] = {
    "atividades": marcar("Mostra o que cada pessoa tem para fazer hoje, lido da planilha de mapeamento."),
    "gastos": marcar("Mostra quanto se gastou com IA neste computador."),
}


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
