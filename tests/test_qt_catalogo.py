"""Os dados da navegação (`sigft/app_qt/catalogo.py`).

Até 2026-10-15 eram comparados com os da interface antiga (a Home e o
`main.py` dela). Ela saiu do SIG-FT; os valores ficam travados aqui, para
mudar só de propósito.
"""
from sigft.app_qt import catalogo

MODULOS_DA_HOME = [('CriaFichas',
  'Cria Fichas PMIB',
  'Lê a lista de materiais, escolhe o PDM de cada item com IA e cria as fichas no portal. Tem também a '
  'edição do código de projeto em massa.'),
 ('PDM',
  'Planilhas PMIB',
  'Cria as planilhas das fichas PMIB a partir do template, com as características da planilha de PDMs, em '
  'português ou em inglês.'),
 ('Analyzer',
  'Analyzer (IA)',
  'Dá nota às fichas preenchidas e separa as que passam das que voltam para correção. Gera o relatório de '
  'pendências para mandar ao fornecedor.'),
 ('UploadConditions',
  'Upload de Condições',
  'Preenche no portal as condições de armazenamento, transporte, manutenção e descarte, a partir da ficha, '
  'com a tradução para o espanhol.'),
 ('UploadSpecs',
  'Upload de Características',
  'Preenche as características técnicas da ficha no portal, uma linha por especificação.'),
 ('CorrecaoPDM',
  'Correção de PDM',
  'Troca ou atualiza o PDM das fichas no portal sem perder as características: fotografa antes, repõe o que '
  'o PDM novo também tem, e lista o que não voltou.'),
 ('Translator',
  'Tradutor Técnico',
  'Traduz as características das fichas de português para espanhol, no próprio computador, e grava numa aba '
  'nova da própria planilha.'),
 ('CopiaFichas',
  'Fichas Duplicadas',
  'Copia uma ficha existente do portal para outra: campos, condições, características, PDM, documentos e '
  'imagens.'),
 ('AutoSpec',
  'AutoSpec AI (RAG)',
  'Preenche ficha vazia lendo manuais em PDF e buscando datasheets na web, com conferência dos documentos '
  'duvidosos.'),
 ('LMR',
  'Aplicação LMR',
  'Cadastra as aplicações (TAGs) das fichas no portal, e apaga quando preciso. As duas coisas ficam em abas '
  'da mesma seção.'),
 ('PMIBManager',
  'PMIB Manager',
  'Atualiza o mapeamento a partir do Aconex: renomeia arquivos pelo RDS-PP, calcula o avanço, e mantém as '
  'abas de lista de preços e de atividades.'),
 ('SearchPMIB',
  'Busca PMIB',
  'Procura um código ou descrição nas planilhas de uma pasta inteira, sem abrir arquivo por arquivo.')]


def test_modulos_iguais_aos_da_home():
    assert catalogo.MODULOS == MODULOS_DA_HOME


def test_bloqueadas():
    assert catalogo.TELAS_BLOQUEADAS == frozenset({"CorrecaoPDM"})


def test_mensagem_da_tarefa_em_andamento():
    assert catalogo.MSG_TAREFA_EM_ANDAMENTO == (
        "Há uma tarefa em andamento (um robô, uma tradução ou uma consulta à IA).\n\n"
        "Se fechar agora, ela é interrompida no ponto em que está, e uma planilha "
        "que estava sendo gravada pode ficar pela metade.\n\n"
        "Fechar o SIG-FT mesmo assim?")


def test_mensagem_da_abertura_que_falhou_da_o_caminho_do_log_e_nao_manda_para_a_antiga():
    """A interface antiga saiu (2026-10-15): a caixa diz o motivo e onde está o
    log, e não oferece mais um comando para abrir outra interface."""
    assert catalogo.MSG_ABERTURA_FALHOU == (
        "O SIG-FT não conseguiu abrir a janela principal.\n\n{erro}\n\n"
        "O detalhe completo está em Documentos\\SIG-FT\\logs\\sigft.log. "
        "Mande esse arquivo para quem cuida do SIG-FT.")


def test_abertura_que_falha_mostra_o_motivo_e_sai_com_1(qt_interface, monkeypatch):
    from sigft.app_qt import main as qmain
    from sigft.core import dados_usuario, instancia
    from sigft.core.rpa import navegador

    codigos, caixas, ligados = [], [], []

    class SplashFalsa:
        pronta = type("S", (), {"connect": lambda self, f: ligados.append(f)})()

        def show(self):
            pass

        def carregar(self):
            ligados[0]()

        def close(self):
            pass

    def quebra():
        raise ValueError("api_config.json corrompido")

    monkeypatch.setattr(instancia, "preparar", lambda: None)
    monkeypatch.setattr(instancia, "encerrar", lambda codigo=0: codigos.append(codigo))
    monkeypatch.setattr(dados_usuario, "migrar_se_preciso", lambda: [])
    monkeypatch.setattr(navegador, "preparar_ambiente_do_rpa", lambda: None)
    monkeypatch.setattr(qmain, "_preparar_qt",
                        lambda: type("A", (), {"exec": lambda self: None})())
    monkeypatch.setattr(qmain, "SplashScreen", SplashFalsa)
    monkeypatch.setattr(qmain, "SIG_FT_App", quebra)
    monkeypatch.setattr(qmain.QMessageBox, "critical",
                        lambda pai, titulo, texto: caixas.append(texto))
    qmain.main()
    assert codigos[0] == 1
    assert "api_config.json corrompido" in caixas[0]
    assert "sigft.log" in caixas[0] and "interface antiga" not in caixas[0]


def test_menu_tem_as_telas_dos_cards_e_na_ordem_da_barra():
    telas_menu = [item[2] for item in catalogo.MENU if item[0] == "botao"]
    assert telas_menu == ["CriaFichas", "PDM", "Analyzer", "UploadConditions", "Translator",
                          "UploadSpecs", "CorrecaoPDM", "CopiaFichas", "AutoSpec", "LMR",
                          "PMIBManager", "SearchPMIB"]
    assert {m[0] for m in catalogo.MODULOS} == set(telas_menu)
