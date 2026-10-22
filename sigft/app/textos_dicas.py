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

PORTAL = "Abre o navegador no Portal PMIB (o login é feito por você)."

DICAS: dict[str, dict[str, str]] = {
    "TelaDeUpload": {
        "btn_ia": "Lê as fichas selecionadas com a IA e monta os dados para o portal. "
                  "Nada é enviado ao portal nesta etapa.",
        "btn_parar_ia": "Pede para a leitura com IA parar. O que já foi lido fica.",
        "btn_web_mem": f"Envia ao portal o que a IA acabou de processar, sem precisar do Excel. {PORTAL}",
        "btn_web_file": f"Envia ao portal os dados de um Excel de resultados salvo antes. {PORTAL}",
        "btn_parar_web": "Pede para o robô parar. As fichas já enviadas ficam no portal.",
    },
    "ModuloAnalyzer": {
        "btn_config": "Ajusta quanto cada critério pesa na nota da ficha.",
        "btn_run": "Dá nota às fichas selecionadas e separa as que passam das que voltam "
                   "para correção.",
        "btn_relatorio": "Grava o .xlsx de pendências na pasta de saída, para mandar ao fornecedor.",
    },
    "ModuloApagarLMR": {
        "btn_run": f"Apaga do portal as aplicações (TAGs) da ficha informada. {PORTAL}",
    },
    "ModuloLMR": {
        "btn_run": f"Escolha o Excel com as TAGs; o robô as cadastra nas fichas. {PORTAL}",
    },
    "ModuloAutoSpec": {
        "btn_status": "Escolha o _STATUS_PMIB: é dele que saem as fichas e para ele voltam os resultados.",
        "btn_add": "Põe na fila as fichas e documentos escolhidos acima.",
        "btn_run": "Processa a fila: lê os PDFs, busca datasheets na web e preenche as fichas "
                   "com a IA.",
        "btn_conf": "Processa de novo só os documentos que você marcou na conferência.",
        "btn_conf_salvar": "Grava a conferência num .txt, para continuar outro dia.",
        "btn_conf_importar": "Retoma uma conferência salva antes, inclusive de outra sessão.",
    },
    "ModuloBuscaPMIB": {
        "btn_pasta": "Escolha a pasta onde estão as planilhas a pesquisar.",
        "btn_search": "Procura o termo em todas as planilhas da pasta, sem abrir uma por uma.",
    },
    "ModuloCopiaFichas": {
        "btn_status": "Escolha o _STATUS_PMIB com as fichas duplicadas a copiar.",
        "btn_resumo": "Revise e corrija a lista de fichas antes de mandar o robô.",
        "btn_robo_novo": "Copia cada ficha original para a sua duplicada e confere cada aba "
                         f"depois de salvar. {PORTAL}",
    },
    "ModuloCorrecaoPDM": {
        "btn_status": "Escolha o _STATUS_PMIB com as fichas a corrigir.",
        "btn_catalogo": "Opcional: a planilha de PDMs, para escolher o PDM novo pelo nome.",
        "btn_so_revisao": "Marca as fichas selecionadas para só atualizar a revisão do PDM.",
        "btn_escolher_pdm": "Escolhe o PDM novo para as fichas selecionadas.",
        "btn_limpar": "Desfaz a escolha das fichas selecionadas.",
        "btn_parar": "Pede para o robô parar.",
        "btn_rodar": "Troca o PDM no portal sem perder as características: fotografa antes, "
                     f"repõe depois e lista o que não voltou. {PORTAL}",
    },
    "ModuloCriaFichas": {
        "btn_pmib": "Escolha o Excel com a lista de materiais do lote.",
        "btn_pdm": "Escolha a planilha mestra de PDMs: é dela que a IA escolhe o PDM de cada item.",
        "btn_run_ai": "A IA escolhe o PDM de cada item. Você revisa antes de qualquer coisa ir "
                      "ao portal.",
        "btn_run_auto": f"Cria no portal as fichas revisadas. {PORTAL}",
        "btn_resumo": "Mostra o que a IA escolheu para cada item, para revisar e corrigir.",
        "btn_save": "Grava no Excel o resultado do lote.",
        "btn_reset": "Limpa o lote atual para começar outro. Nada no portal é desfeito.",
        "btn_excel_edicao": "Escolha o Excel com as fichas e o código de projeto novo.",
        "btn_run_edicao": f"Troca o código de projeto das fichas no portal, em massa. {PORTAL}",
    },
    "ModuloPDM": {
        "btn_pmib": "Escolha o _STATUS_PMIB que lista as fichas a criar.",
        "btn_template": "Escolha o template de ficha (.xlsx) que será preenchido.",
        "btn_sam_gm": "Escolha a planilha de PDMs (SAM-GM): dela saem as características de cada ficha.",
        "btn_criar_fichas": "Gera as planilhas de ficha PMIB a partir do template escolhido.",
    },
    "ModuloPMIBManager": {
        "btn_api": "Escolha o histórico exportado do Aconex DocManager (.xlsx).",
        "btn_buscar": "Escolha a pasta raiz dos arquivos do projeto.",
        "btn_master": "Escolha a planilha de Mapeamento Sobressalentes que será atualizada.",
        "btn_run": "Renomeia os arquivos pelo RDS-PP, calcula o avanço e atualiza o mapeamento.",
        "btn_painel": "Gera só o painel de acompanhamento, sem rodar a gestão inteira.",
        "btn_autorizados": "Escolha o export de autorizados baixado do portal (.xlsx).",
        "btn_aplicar": "Marca no mapeamento as fichas que o export diz que foram autorizadas.",
        "btn_conferir": f"Confere no próprio portal se as autorizações estão lá. {PORTAL}",
    },
    "ModuloTranslator": {
        "btn_run": "Escolha as planilhas; a tradução para o espanhol roda no computador e vai "
                   "para uma aba nova da própria planilha.",
        "btn_stop": "Pede para a tradução parar.",
        "btn_glossario": "Abre a lista de termos que a tradução sempre corrige.",
    },
    "HomeView": {
        "btn_salvar_chaves": "Grava as chaves de API neste computador (Documentos\\SIG-FT).",
        "btn_atualizar_catalogo_ia": "Baixa do provedor a lista atual de modelos e preços.",
        "btn_aplicar_recomendados_ia": "Escolhe para cada tarefa o modelo recomendado.",
        "btn_salvar_selecao_ia": "Grava os modelos escolhidos para cada tarefa.",
        "btn_atualizar_gastos_ia": "Recalcula o gasto com IA a partir dos logs deste computador.",
        "btn_pasta_logs_ia": "Abre a pasta de logs do SIG-FT no Explorador.",
    },
    # A janela Configuração (2026-10-22): os botões que vieram da barra da Home.
    "JanelaConfiguracao": {
        "btn_modelos": "Escolhe qual modelo de IA cada módulo usa.",
        "btn_chaves": "Cadastra as chaves de API (Gemini, OpenRouter, busca na web).",
        "caixa_canal_testes": "Marcado, o aviso de atualização oferece também as versões de teste (rc).",
        "btn_atualizacoes": "Pergunta agora se há versão nova do SIG-FT.",
    },
}


# Os botões da barra da Home, pela CHAVE de `home.BARRA`.
DICAS_DA_BARRA_DA_HOME: dict[str, str] = {
    "atividades": "Mostra o que cada pessoa tem para fazer hoje, lido da planilha de mapeamento.",
    "gastos": "Mostra quanto se gastou com IA neste computador.",
}


def dicas_da_classe(classe) -> dict[str, str]:
    """As dicas de `classe` e das classes-mãe dela (a filha ganha)."""
    juntas: dict[str, str] = {}
    for mae in reversed(classe.__mro__):
        juntas.update(DICAS.get(mae.__name__, {}))
    return juntas
