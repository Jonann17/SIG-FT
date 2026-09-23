"""Tela inicial — Checkpoint 7.3 (Fase 7 do plano).

O painel de abertura: atalhos para os módulos, configuração das chaves de API,
escolha do modelo de IA (global e por tarefa) e o relatório de gastos.

É a maior das telas porque concentra a configuração que antes estava espalhada
em caixas de diálogo.
"""
from __future__ import annotations

import threading
from tkinter import messagebox

from sigft import config as sigft_config
from sigft.app.theme import COLORS, COR_CARTAO
from sigft.core import plataforma
from sigft.core.llm import catalogo, selecao
from sigft.core.llm import usage as llm_usage
# [2026-09-03] Janelas que a Home abre, e o desenho do mural.
from sigft.app.widgets.painel_janela import JanelaPainel
from sigft.app.widgets.mural import montar as montar_mural

import customtkinter as ctk


# =============================================================================
# OS MÓDULOS, como aparecem nos cards  [2026-09-03]
# =============================================================================
# `(nome do frame, título, descrição)`. O nome do frame é a chave de
# `SIG_FT_App.frames` — é ele que o clique usa para navegar, e por isso ele e a
# barra lateral têm de concordar.
#
# As descrições foram reescritas: as antigas agrupavam módulos ("1 & 2. Criação
# e Estruturação") e descreviam o fluxo, não o que cada tela faz. O usuário
# pediu "descrevê-los diferente, atualizá-los e torná-los clicáveis".
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
     "Traduz as características das fichas de português para espanhol e grava "
     "numa aba nova da própria planilha."),
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


# =============================================================================
# NOVA CLASSE: HOME SCREEN (DASHBOARD ESTILO BASELINE)
# =============================================================================
class HomeView(ctk.CTkScrollableFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Ajuste de layout para expandir
        self.grid_columnconfigure(0, weight=1)

        # --- CABEÇALHO ---
        self.lbl_titulo = ctk.CTkLabel(self, text="SIG-FT", font=ctk.CTkFont(size=32, weight="bold"))
        self.lbl_titulo.grid(row=0, column=0, pady=(20, 5), sticky="w", padx=20)

        self.lbl_subtitulo = ctk.CTkLabel(self, text="Sistema Integrado de Gestão de Fichas Técnicas - GE Vernova",
                                          font=ctk.CTkFont(size=16), text_color="gray70")
        self.lbl_subtitulo.grid(row=1, column=0, pady=(0, 20), sticky="w", padx=20)

        # Descrição Geral
        resumo = ("Clique num módulo abaixo para abri-lo. Os botões desta barra "
                  "abrem painéis em janela, para a Home ficar limpa.")
        self.criar_texto_simples(resumo, row=2)

        # --- BARRA DE BOTÕES ---------------------------------------------
        # [2026-09-03] Pedido do usuário: "precisamos diminuir a densidade de
        # informação da home criando botões que abrem janelas". Os painéis de
        # configuração e de gastos de IA saíram daqui e viraram janelas.
        self._criar_barra_de_botoes(row=3)

        # --- MÓDULOS, CLICÁVEIS ------------------------------------------
        self._criar_cards_dos_modulos(row=4)

    # =====================================================================
    # BARRA DE BOTÕES  [2026-09-03]
    # =====================================================================
    def _criar_barra_de_botoes(self, row):
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 16))

        botoes = [
            ("\U0001F4CB  Atividades do dia", self.abrir_mural_atividades, COLORS["accent"]),
            ("\U0001F916  Modelos de IA", self.abrir_janela_modelos_ia, COLORS["primary"]),
            ("\U0001F4B0  Gastos de IA", self.abrir_janela_gastos_ia, COLORS["primary"]),
            ("\U0001F511  Chaves de API", self.abrir_janela_chaves_api, "#3A3A3A"),
        ]
        for texto, comando, cor in botoes:
            ctk.CTkButton(
                barra, text=texto, command=comando, fg_color=cor,
                height=40, font=("Roboto", 13, "bold"),
            ).pack(side="left", padx=(0, 10))

    def abrir_janela_chaves_api(self):
        JanelaPainel(
            self, titulo="Chaves de API",
            montar=lambda pai: self.criar_area_config_api(row=None, parent=pai),
            geometria="760x520",
        )

    def abrir_janela_modelos_ia(self):
        JanelaPainel(
            self, titulo="Modelos de IA",
            montar=lambda pai: self.criar_painel_modelos_ia(row=None, parent=pai),
        )

    def abrir_janela_gastos_ia(self):
        JanelaPainel(
            self, titulo="Gastos de IA",
            montar=lambda pai: self.criar_painel_gastos_ia(row=None, parent=pai),
            geometria="860x600",
        )

    # =====================================================================
    # MURAL DE ATIVIDADES  [2026-09-03]
    # =====================================================================
    # Abre por BOTÃO, não na abertura do app -- decisão do usuário. Ler a
    # planilha do Box a cada abertura faria o SIG-FT depender do Box estar
    # sincronizado só para abrir.
    def abrir_mural_atividades(self):
        from datetime import date

        gavetas, erro = self._ler_mural()
        JanelaPainel(
            self, titulo="Atividades do dia",
            montar=lambda pai: montar_mural(
                pai, gavetas, date.today().strftime("%d/%m/%Y"), erro),
            geometria="820x640",
        )

    def _ler_mural(self):
        """`(gavetas, erro)` -- le a aba Atividades do mapeamento.

        Devolve o erro como TEXTO em vez de levantar: o mural e informativo, e
        uma planilha ausente nao pode virar traceback na cara do usuario.
        """
        from datetime import date

        from sigft.services import atividades as at

        # As gavetas saem de `at.FAIXAS`, NUNCA de uma lista escrita aqui.
        # A primeira versao listava as faixas a mao; quando o mural passou a
        # ser por PRAZO os nomes mudaram no servico e esta linha ficou para
        # tras, com `at.PARA_COMECAR` e `at.TRAVADA` inexistentes. O
        # AttributeError subia antes do try e o botao simplesmente nao abria
        # janela nenhuma. Derivando de `FAIXAS` os dois lados nao tem como
        # divergir de novo.
        vazio = {faixa: [] for faixa in at.FAIXAS}

        caminho = self._caminho_do_mapeamento()
        if not caminho:
            return vazio, (
                "Nao encontrei o arquivo de mapeamento.\n\n"
                "Rode o PMIB Manager uma vez apontando a planilha gerenciadora -- "
                "o mural passa a ler dela."
            )

        try:
            import openpyxl

            # `data_only=True` e obrigatorio: as celulas de agregacao da aba
            # sao formulas, e sem isto `.value` devolveria a string "=FALSE()"
            # em vez do valor. Foi um defeito real nesta mesma frente.
            wb = openpyxl.load_workbook(caminho, data_only=True, read_only=True)
            if "Atividades" not in wb.sheetnames:
                wb.close()
                return vazio, "A planilha nao tem a aba 'Atividades'.\n\n" + str(caminho)

            ws = wb["Atividades"]

            # ⚠️ `iter_rows`, NUNCA `ws.cell(...)` numa planilha `read_only`.
            #
            # Em modo read-only a aba e um FLUXO so-para-frente: cada
            # `ws.cell(linha, coluna)` re-percorre o XML desde o comeco. Eram
            # 84 linhas x 10 colunas = 840 varreduras, e o mural levava
            # 3,9 s para abrir num arquivo de 40 KB. `iter_rows` passa uma
            # vez so: caiu para centesimos de segundo.
            def _celula(valores, coluna):
                indice = coluna - 1
                return valores[indice] if indice < len(valores) else None

            linhas = []
            for valores in ws.iter_rows(min_row=at.LINHA_CABECALHO + 1, values_only=True):
                linhas.append({
                    "nv": _celula(valores, at.COL_NV),
                    "descricao": _celula(valores, at.COL_DESCRICAO),
                    "concluida": _celula(valores, at.COL_CONCLUIDA),
                    "status": _celula(valores, at.COL_STATUS),
                    "com_quem": _celula(valores, at.COL_COM_QUEM),
                    "criticidade": _celula(valores, at.COL_CRITICIDADE),
                    "data_prevista_inicio": _celula(valores, at.COL_DATA_PREVISTA_INICIO) or "",
                    "previsao_termino": _celula(valores, at.COL_PREVISAO_TERMINO) or "",
                    # As datas REAIS. Antes iam como "" fixo, e a regra que
                    # decide "ja comecou" ficava cega: atividade com DATA DE
                    # INICIO preenchida aparecia como "era para comecar ha N
                    # dias".
                    "data_inicio": _celula(valores, at.COL_DATA_INICIO) or "",
                    "data_termino": _celula(valores, at.COL_DATA_TERMINO) or "",
                })
            wb.close()
            return at.mural(linhas, date.today()), None
        except Exception as e:
            return vazio, "Nao consegui ler as atividades:\n{}: {}\n\n{}".format(
                type(e).__name__, e, caminho)

    def _caminho_do_mapeamento(self):
        """O ultimo arquivo gerenciadora que o usuario escolheu, se existir."""
        import os

        from sigft.core import prefs

        # 1. O arquivo que o PMIB Manager registrou ao ser usado.
        try:
            salvo = prefs.get_last_file(prefs.CHAVE_MAPEAMENTO)
        except Exception:
            salvo = None
        if salvo:
            return salvo

        # 2. Reserva: a PASTA lembrada do seletor, procurando o arquivo nela.
        #    Cobre quem já usou o PMIB Manager ANTES desta versão, quando só a
        #    pasta era guardada.
        try:
            pasta = prefs.get_initial_dir("pmib_manager.master", "excel")
        except Exception:
            pasta = None
        if pasta and os.path.isdir(pasta):
            for nome in sorted(os.listdir(pasta)):
                if "mapeamento" in nome.lower() and nome.lower().endswith((".xlsx", ".xlsm")):
                    return os.path.join(pasta, nome)
        return None

    # =====================================================================
    # CARDS DOS MODULOS  [2026-09-03] -- clicaveis
    # =====================================================================
    def _criar_cards_dos_modulos(self, row):
        """Um card por modulo, clicavel, que leva direto a tela.

        Antes eram 7 cards agrupando modulos ("1 & 2. Criacao e
        Estruturacao"), meramente informativos. O usuario pediu: "temos todos
        os modulos do SIG-FT explicado, precisamos mudar a forma que isso
        esta. Vamos descreve-los diferente, atualiza-los e torna-los clicaveis
        para levar direto pro modulo".
        """
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=row, column=0, sticky="nsew", padx=20, pady=(0, 20))
        container.grid_columnconfigure((0, 1), weight=1, uniform="cards")

        for indice, (frame_alvo, titulo, descricao) in enumerate(MODULOS):
            self._card_clicavel(
                container, frame_alvo, titulo, descricao,
                linha=indice // 2, coluna=indice % 2,
            )

    def _card_clicavel(self, pai, frame_alvo, titulo, descricao, linha, coluna):
        card = ctk.CTkFrame(pai, fg_color=COR_CARTAO, corner_radius=8,
                            border_width=1, border_color="#333333")
        card.grid(row=linha, column=coluna, sticky="nsew", padx=6, pady=6)

        lbl_titulo = ctk.CTkLabel(card, text=titulo, font=("Roboto", 15, "bold"),
                                  text_color=COLORS["accent"], anchor="w")
        lbl_titulo.pack(anchor="w", padx=14, pady=(12, 4), fill="x")

        lbl_desc = ctk.CTkLabel(card, text=descricao, font=("Roboto", 12),
                                text_color="gray70", justify="left",
                                wraplength=380, anchor="w")
        lbl_desc.pack(anchor="w", padx=14, pady=(0, 12), fill="x")

        # O clique vale no card INTEIRO, nao so no titulo: um card que so
        # responde numa palavra parece quebrado.
        def ir(_evento=None):
            try:
                self.controller.show_frame(frame_alvo)
            except Exception:
                pass

        def realce(_e=None):
            card.configure(border_color=COLORS["accent"])

        def normal(_e=None):
            card.configure(border_color="#333333")

        for widget in (card, lbl_titulo, lbl_desc):
            widget.bind("<Button-1>", ir)
            widget.bind("<Enter>", realce)
            widget.bind("<Leave>", normal)
            try:
                widget.configure(cursor="hand2")
            except Exception:
                pass

    def criar_area_config_api(self, row, parent=None):
        """Cria o painel de configuração de chaves API.

        [2026-09-03] `parent` permite hospedar o painel numa JANELA em vez de
        na Home -- ver `JanelaPainel`. Com `parent`, o frame é empacotado em
        vez de posicionado no grid da Home.
        """
        dono = parent if parent is not None else self
        frame = ctk.CTkFrame(dono, fg_color=("gray90", "gray16"), corner_radius=10)
        if parent is None:
            frame.grid(row=row, column=0, sticky="ew", padx=20, pady=10)
        else:
            frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(frame, text="🔑 Configuração de Chaves API (Global)", font=("Arial", 16, "bold")).pack(pady=10, padx=10, anchor="w")

        # Campos de Chave
        # [SEGURANÇA] Os valores default hardcoded foram removidos.
        # As chaves devem vir do .env ou do api_config.json (ambos fora do versionamento).
        self.entries = {}
        keys_info = [
            ("GEMINI", "Gemini API Key:", ""),
            ("GOOGLE_SEARCH", "Google Search API:", ""),
            ("GOOGLE_CSE", "Google CSE ID:", ""),
            ("LLAMA", "LlamaCloud API:", ""),
            # [CP 3.2] Gateway OpenRouter (padrão) + endpoint OpenAI-
            # compatível genérico da futura IA interna da empresa — ver
            # docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.2.
            ("OPENROUTER", "OpenRouter API Key:", ""),
            ("EMPRESA_LLM_BASE_URL", "IA Empresa (Base URL):", ""),
            ("EMPRESA_LLM_API_KEY", "IA Empresa (API Key):", "")
        ]

        for key_id, label_text, default_val in keys_info:
            f = ctk.CTkFrame(frame, fg_color="transparent")
            f.pack(fill="x", padx=10, pady=2)
            ctk.CTkLabel(f, text=label_text, width=140, anchor="w").pack(side="left")

            entry = ctk.CTkEntry(f, show="*")  # Mascarado por padrão
            entry.pack(side="left", fill="x", expand=True, padx=5)

            # Carrega valor atual do controller ou default
            current_val = self.controller.get_key(key_id)
            if not current_val: current_val = default_val
            entry.insert(0, current_val)

            self.entries[key_id] = entry

        btn_save = ctk.CTkButton(frame, text="Salvar Chaves", command=self.salvar_chaves_api, fg_color="green")
        btn_save.pack(pady=10)

    def salvar_chaves_api(self):
        # `.strip()`: uma chave colada com espaço/quebra de linha no fim vira
        # `400 API_KEY_INVALID` no Google, e a mensagem culpa a chave -- que
        # está certa. Limpar aqui (além de em `config.carregar_chaves`) evita
        # gravar o lixo no api_config.json em primeiro lugar.
        new_keys = {k: e.get().strip() for k, e in self.entries.items()}
        self.controller.save_keys(new_keys)

        # O painel "Modelos de IA" abaixo filtra os modelos pelos provedores
        # que TÊM chave -- e esse filtro era calculado uma única vez, quando a
        # Home foi construída. Sem esta linha, quem colava a chave do
        # OpenRouter aqui e clicava em Salvar continuava vendo só os modelos
        # Gemini, e o botão "Atualizar catálogo (OpenRouter)" nem aparecia: a
        # chave estava salva, o painel é que não sabia. A única saída era
        # fechar e reabrir o app -- e nada na tela dizia isso.
        # `save_keys` já atualizou `controller.api_keys`, então o painel
        # reconstruído aqui enxerga a chave nova na hora.
        try:
            self._recarregar_painel_modelos_ia()
        except Exception:
            # Salvar a chave é mais importante que redesenhar o painel: se o
            # painel não existir (Home construída pela metade) ou falhar ao
            # remontar, a chave JÁ foi gravada e não se perde por causa disso.
            pass

        messagebox.showinfo("Sucesso", "Chaves API salvas com sucesso!\nTodos os módulos usarão as novas chaves.")

    # =========================================================================
    # PAINEL "MODELOS DE IA" (Checkpoint 3.3 do plano de refatoração)
    # =========================================================================
    # Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.3, e
    # docs/refatoracao/MODELOS_IA.md. Persistência via `sigft.core.llm.
    # selecao` (mesmo arquivo das chaves de API, api_config.json, sob a
    # chave reservada "_modelos_ia") -- efeito imediato, sem reiniciar o
    # app: os 5 módulos de IA constroem o `LLMClient` de novo a cada
    # execução (via `get_llm()`, CP 3.1/3.3), então a próxima execução já lê
    # a seleção salva aqui.
    # -------------------------------------------------------------------
    # Redesenho de 2026-08-11 — PROVEDOR PRIMEIRO.
    #
    # O painel anterior oferecia TRÊS mecanismos sobrepostos para a mesma
    # decisão: uma lista curada que misturava provedores, um campo de texto
    # livre e um botão de catálogo que só existia para o OpenRouter. O
    # usuário descreveu o problema melhor que qualquer diagnóstico: não
    # entendia para que servia a caixa de texto, escolher "gemini" no
    # provedor não fazia nada, e o catálogo do OpenRouter abria uma lista
    # grande demais para achar um modelo sem busca.
    #
    # O desenho novo tem UMA pergunta de cada vez:
    #   1. com qual CHAVE você vai trabalhar (Gemini, OpenRouter, AMP)?
    #   2. qual MODELO daquela chave?  (e o mesmo vale para o modo avançado)
    #
    # Consequências que valem registrar:
    #   - a lista de modelos vem do catálogo AO VIVO daquele provedor
    #     (`core/llm/catalogo`), com os favoritos curados no topo -- eles são
    #     a única fonte de preço que o app tem;
    #   - a montagem lê SÓ O CACHE (`somente_cache=True`): a Home não pode
    #     ficar pendurada em rede. O botão "Atualizar lista" busca de fato,
    #     numa thread;
    #   - o filtro de texto existe porque o OpenRouter tem centenas de
    #     modelos, e um `CTkOptionMenu` não tem busca;
    #   - "modelo manual" continua, mas agora como o que sempre deveria ter
    #     sido: a saída para um id que não está na lista -- e o provedor dele
    #     é o provedor escolhido lá em cima, não um segundo seletor.
    # -------------------------------------------------------------------
    ROTULO_PROVIDER_IA = {
        "gemini": "Gemini (chave direta do Google)",
        "openrouter": "OpenRouter (vários modelos, uma chave)",
        "openai_compat": "AMP / IA da empresa",
    }

    def criar_painel_modelos_ia(self, row, parent=None):
        """Painel "Modelos de IA": provedor -> modelo, com filtro de texto,
        override por tarefa e campo manual. Provedores sem chave não
        aparecem."""
        self._row_modelos_ia = row
        # Zeradas antes de qualquer `return` curto: métodos disparados por
        # widgets checam estas referências, e apontar para widget destruído
        # (o painel é remontado várias vezes) é erro difícil de achar.
        self.lbl_resumo_modelo_ia = None
        self.lbl_catalogo_ia = None
        self.opts_modelo_ia = []

        dono = parent if parent is not None else self
        frame = ctk.CTkFrame(dono, fg_color=("gray90", "gray16"), corner_radius=10)
        if parent is None:
            frame.grid(row=row, column=0, sticky="ew", padx=20, pady=10)
        else:
            frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.frame_modelos_ia = frame
        # [2026-09-03] Guardado para o painel poder se remontar dentro da
        # janela quando o usuário troca de provedor -- `_recarregar_painel_
        # modelos_ia` precisa saber onde reconstruir.
        self._parent_modelos_ia = parent

        ctk.CTkLabel(frame, text="🤖 Modelos de IA", font=("Arial", 16, "bold")).pack(pady=10, padx=10, anchor="w")
        ctk.CTkLabel(
            frame,
            text="Escolha primeiro COM QUAL CHAVE trabalhar; a lista de modelos passa a ser a daquele "
                 "provedor. \"Aplicar recomendados\" usa os modelos sugeridos em "
                 "docs/refatoracao/MODELOS_IA.md, que são mais econômicos. Valide a qualidade numa amostra "
                 "antes de rodar em lote.",
            font=("Roboto", 12), text_color="gray70", justify="left", wraplength=800,
        ).pack(anchor="w", padx=10, pady=(0, 10))

        providers_com_chave = sorted(
            provider_id
            for provider_id, chave_id in sigft_config.CHAVE_POR_PROVIDER.items()
            if self.controller.get_key(chave_id)
        )

        if not providers_com_chave:
            ctk.CTkLabel(
                frame,
                text="Nenhum provedor de IA tem chave configurada acima. Configure ao menos uma "
                     "chave (ex.: Gemini ou OpenRouter) para escolher o modelo aqui.",
                font=("Roboto", 12), text_color=COLORS["danger"], justify="left", wraplength=800,
            ).pack(anchor="w", padx=10, pady=(0, 15))
            return

        estado_atual = selecao.carregar(config_path=sigft_config.CONFIG_FILE)

        # --- 1. PROVEDOR ---------------------------------------------------
        # Pré-seleciona o provedor da seleção já salva: reabrir a Home tem de
        # mostrar o que está valendo, não recomeçar do primeiro da lista.
        # A seleção GLOBAL pode estar vazia e mesmo assim haver provedor
        # escolhido -- é o caso de quem usa só overrides por tarefa (global em
        # "Padrão do sistema" e as 5 tarefas apontando para o OpenRouter).
        # Olhar só o global fazia o painel voltar para "gemini" (o 1º da lista
        # em ordem alfabética) depois de Salvar, desfazendo na cara do usuário
        # a escolha que ele acabou de fazer.
        provider_salvo = self._provider_ia_da_selecao(estado_atual)
        if provider_salvo not in providers_com_chave:
            provider_salvo = providers_com_chave[0]
        self.var_provider_ia = ctk.StringVar(value=self._rotulo_provider_ia(provider_salvo))
        self._provider_por_rotulo = {
            self._rotulo_provider_ia(p): p for p in providers_com_chave
        }

        f_prov = ctk.CTkFrame(frame, fg_color="transparent")
        f_prov.pack(fill="x", padx=10, pady=(0, 5))
        ctk.CTkLabel(f_prov, text="Provedor (chave a usar):", width=220, anchor="w").pack(side="left")
        ctk.CTkOptionMenu(
            f_prov, values=list(self._provider_por_rotulo), variable=self.var_provider_ia,
            command=self._trocou_provider_ia,
            fg_color="#3A3A3A", button_color="#454545", width=300,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            f_prov, text="Atualizar lista de modelos", command=self._atualizar_catalogo_ia,
            fg_color="#3A3A3A", hover_color="#454545",
        ).pack(side="left", padx=5)

        self.lbl_catalogo_ia = ctk.CTkLabel(
            frame, text="", font=("Roboto", 11), text_color="gray60",
            justify="left", wraplength=800, anchor="w",
        )
        self.lbl_catalogo_ia.pack(anchor="w", padx=10)

        # --- 2. FILTRO -----------------------------------------------------
        f_filtro = ctk.CTkFrame(frame, fg_color="transparent")
        f_filtro.pack(fill="x", padx=10, pady=(5, 5))
        ctk.CTkLabel(f_filtro, text="Filtrar modelos:", width=220, anchor="w").pack(side="left")
        self.entry_filtro_modelo_ia = ctk.CTkEntry(
            f_filtro, placeholder_text="ex.: flash, haiku, minimax (vazio mostra todos)", width=300,
        )
        self.entry_filtro_modelo_ia.pack(side="left", padx=5)
        self.entry_filtro_modelo_ia.bind("<KeyRelease>", lambda _e: self._refiltrar_modelos_ia())

        # --- 3. MODELO PADRÃO ----------------------------------------------
        f_global = ctk.CTkFrame(frame, fg_color="transparent")
        f_global.pack(fill="x", padx=10, pady=(0, 5))
        ctk.CTkLabel(f_global, text="Modelo padrão (todas as tarefas):", width=220, anchor="w").pack(side="left")
        self.var_modelo_ia_global = ctk.StringVar(value=self._rotulo_padrao_sistema_ia())
        self.opt_modelo_ia_global = ctk.CTkOptionMenu(
            f_global, values=[self._rotulo_padrao_sistema_ia()], variable=self.var_modelo_ia_global,
            command=self._escolheu_favorito_global_ia,
            fg_color="#3A3A3A", button_color="#454545", width=420,
        )
        self.opt_modelo_ia_global.pack(side="left", padx=5)
        self.opts_modelo_ia.append(
            (self.opt_modelo_ia_global, self.var_modelo_ia_global, self._rotulo_padrao_sistema_ia())
        )

        # --- 4. MODO AVANÇADO ----------------------------------------------
        self.var_modelos_ia_modo_avancado = ctk.BooleanVar(value=bool(estado_atual["por_tarefa"]))
        ctk.CTkCheckBox(
            frame, text="Configurar por tarefa (modo avançado)",
            variable=self.var_modelos_ia_modo_avancado,
            command=self._toggle_modelos_ia_modo_avancado,
            fg_color=COLORS["primary"],
        ).pack(anchor="w", padx=10, pady=(5, 5))

        self.frame_modelos_ia_avancado = ctk.CTkFrame(frame, fg_color="transparent")
        rotulos_tarefa = {
            "categorizar_pdm": "Categorizar PDM (Cria Fichas):",
            "validar_ficha": "Validar ficha (Analyzer):",
            "condicoes": "Condições (Upload Condições):",
            "tech_specs": "Caract. Técnicas (Upload Specs):",
            "autospec": "AutoSpec (RAG):",
        }
        self.vars_modelo_ia_por_tarefa = {}
        for tarefa in sorted(sigft_config.LLM_MODELOS_HOJE):
            f_tarefa = ctk.CTkFrame(self.frame_modelos_ia_avancado, fg_color="transparent")
            f_tarefa.pack(fill="x", pady=2)
            ctk.CTkLabel(f_tarefa, text=rotulos_tarefa.get(tarefa, tarefa), width=220, anchor="w").pack(side="left")
            var_tarefa = ctk.StringVar(value="Usar o global")
            opt_tarefa = ctk.CTkOptionMenu(
                f_tarefa, values=["Usar o global"], variable=var_tarefa,
                command=lambda _e: self._atualizar_resumo_modelo_ia(),
                fg_color="#3A3A3A", button_color="#454545", width=420,
            )
            opt_tarefa.pack(side="left", padx=5)
            self.vars_modelo_ia_por_tarefa[tarefa] = var_tarefa
            self.opts_modelo_ia.append((opt_tarefa, var_tarefa, "Usar o global"))

        if self.var_modelos_ia_modo_avancado.get():
            self.frame_modelos_ia_avancado.pack(fill="x", padx=10, pady=(0, 10))

        # --- 5. MANUAL -----------------------------------------------------
        f_livre = ctk.CTkFrame(frame, fg_color="transparent")
        f_livre.pack(fill="x", padx=10, pady=(10, 5))
        self._ancora_apos_avancado_ia = f_livre
        ctk.CTkLabel(
            f_livre, text="Modelo manual (se não estiver na lista):", width=220, anchor="w",
        ).pack(side="left")
        self.entry_modelo_ia_livre = ctk.CTkEntry(
            f_livre, placeholder_text="id exato, ex.: meta-llama/llama-4", width=300,
        )
        self.entry_modelo_ia_livre.pack(side="left", padx=5)
        self.entry_modelo_ia_livre.bind("<KeyRelease>", lambda _e: self._atualizar_resumo_modelo_ia())
        ctk.CTkButton(
            f_livre, text="Limpar", width=70, command=self._limpar_modelo_ia_livre,
            fg_color="#3A3A3A", hover_color="#454545",
        ).pack(side="left", padx=(0, 5))

        # --- 6. RESUMO -----------------------------------------------------
        self.lbl_resumo_modelo_ia = ctk.CTkLabel(
            frame, text="", font=("Roboto", 12), text_color="gray70",
            justify="left", wraplength=800, anchor="w",
        )
        self.lbl_resumo_modelo_ia.pack(anchor="w", padx=10, pady=(8, 0))

        # Popula as listas a partir do cache e restaura a seleção salva.
        self._recarregar_modelos_do_provider(estado_atual)

        # --- 7. BOTÕES -----------------------------------------------------
        f_botoes = ctk.CTkFrame(frame, fg_color="transparent")
        f_botoes.pack(fill="x", padx=10, pady=(10, 15))
        ctk.CTkButton(
            f_botoes, text="✨ Aplicar recomendados", command=self._aplicar_recomendados_ia,
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            f_botoes, text="Salvar seleção", command=self._salvar_selecao_modelos_ia, fg_color="green",
        ).pack(side="left")

    # ------------------------------------------------------------------
    # Rótulos
    # ------------------------------------------------------------------
    def _rotulo_padrao_sistema_ia(self):
        return "Padrão do sistema (modelos atuais)"

    def _rotulo_provider_ia(self, provider):
        return self.ROTULO_PROVIDER_IA.get(provider, provider)

    @staticmethod
    def _provider_ia_da_selecao(estado_atual):
        """Provedor que a seleção salva usa: o do global, ou -- se o global
        estiver vazio -- o da maioria dos overrides por tarefa.

        "Maioria" e não "o primeiro" porque `aplicar_recomendados` grava
        provedores MISTOS de propósito (Grok/OpenRouter só para o PDM, Gemini
        para o resto); reabrir o painel no provedor de uma única tarefa
        mostraria a exceção como se fosse a regra.
        """
        if not estado_atual:
            return None
        global_salvo = estado_atual.get("global") or {}
        if global_salvo.get("provider"):
            return global_salvo["provider"]

        contagem = {}
        for cfg in (estado_atual.get("por_tarefa") or {}).values():
            provider = (cfg or {}).get("provider")
            if provider:
                contagem[provider] = contagem.get(provider, 0) + 1
        if not contagem:
            return None
        return max(sorted(contagem), key=contagem.get)

    def _rotulo_modelo_ia(self, fav):
        """Rótulo de um favorito curado -- com preço, que é o que ele
        acrescenta sobre o id cru do catálogo."""
        tier_legivel = {"padrao": "Padrão", "economia": "Economia", "poder": "Poder"}.get(fav["tier"], fav["tier"])
        return (
            f"{fav['rotulo']} ({tier_legivel}, "
            f"${fav['preco_input']:.2f} / ${fav['preco_output']:.2f} por 1M tokens)"
        )

    # ------------------------------------------------------------------
    # Lista de modelos do provedor escolhido
    # ------------------------------------------------------------------
    def _provider_ia_atual(self):
        return self._provider_por_rotulo.get(self.var_provider_ia.get(), "gemini")

    def _modelos_do_provider_ia(self, provider, somente_cache=True, forcar=False):
        """[(rótulo, id, provider)] do provedor: favoritos curados primeiro
        (com preço), depois o catálogo ao vivo, sem repetir os que já
        entraram.

        O provider viaja JUNTO de cada opção, e não é lido do dropdown na
        hora de salvar. É o que permite uma seleção salva em outro provedor
        (o "Aplicar recomendados" grava Grok/OpenRouter para o PDM e Gemini
        para o resto) sobreviver a uma volta ao painel sem ser reescrita com
        o provedor errado -- que seria um estrago silencioso: id de um
        provedor gravado sob o nome de outro só falha na 1ª chamada real.
        """
        recomendados = catalogo.modelos_recomendados(provider)
        pares = [(self._rotulo_modelo_ia(fav), fav["model"], provider) for fav in recomendados]
        ja_listados = {fav["model"] for fav in recomendados}

        for model_id in catalogo.listar_modelos(
            provider, self.controller.api_keys, somente_cache=somente_cache, forcar=forcar,
        ):
            if model_id not in ja_listados:
                pares.append((model_id, model_id, provider))
        return pares

    def _acrescentar_selecoes_salvas_ia(self, estado_atual):
        """Garante que TODA seleção já gravada apareça na lista, mesmo que
        seja de outro provedor ou de um catálogo ainda não baixado.

        Sem isto, um modelo salvo que não estivesse na lista corrente sumiria
        do dropdown, e o "Salvar seleção" seguinte o APAGARIA sem ninguém
        pedir. O rótulo "(salvo)" deixa claro que aquilo veio do disco.
        """
        if not estado_atual:
            return
        gravadas = [estado_atual.get("global")] + list(
            (estado_atual.get("por_tarefa") or {}).values()
        )
        conhecidos = {model_id for _r, model_id, _p in self._pares_modelo_ia}
        for entrada in gravadas:
            if not entrada or entrada.get("model") in conhecidos:
                continue
            model_id = entrada["model"]
            provider = entrada.get("provider") or self._provider_ia_atual()
            self._pares_modelo_ia.append((f"(salvo) {provider} / {model_id}", model_id, provider))
            conhecidos.add(model_id)

    def _recarregar_modelos_do_provider(self, estado_atual=None, forcar=False):
        """Repopula TODOS os dropdowns de modelo com os do provedor atual.

        Chamado ao montar o painel, ao trocar de provedor e ao atualizar o
        catálogo. `estado_atual` só é passado na montagem, para pré-selecionar
        o que já estava salvo.
        """
        provider = self._provider_ia_atual()
        self._pares_modelo_ia = self._modelos_do_provider_ia(provider, forcar=forcar)
        # As seleções gravadas entram na lista SEMPRE, não só na montagem:
        # trocar de provedor e voltar não pode fazer o que está valendo
        # sumir do dropdown (e ser apagado no Salvar seguinte).
        self._acrescentar_selecoes_salvas_ia(
            estado_atual if estado_atual is not None
            else selecao.carregar(config_path=sigft_config.CONFIG_FILE)
        )

        if self.lbl_catalogo_ia is not None:
            # Conta só as entradas VINDAS do catálogo: nelas o rótulo é o
            # próprio id. Recomendados trazem preço no rótulo e as salvas
            # trazem o prefixo "(salvo)".
            do_catalogo = sum(1 for r, m, _p in self._pares_modelo_ia if r == m)
            if do_catalogo > 0:
                texto = f"{len(self._pares_modelo_ia)} modelos disponíveis ({do_catalogo} do catálogo do provedor)."
            else:
                texto = ("Catálogo ainda não baixado para este provedor. Clique em "
                         "\"Atualizar lista de modelos\". Enquanto isso valem os recomendados "
                         "e o campo manual.")
            self.lbl_catalogo_ia.configure(text=texto)

        # Pré-seleção vinda do disco (só na montagem).
        salvo_global = (estado_atual or {}).get("global") if estado_atual else None
        salvos_tarefa = (estado_atual or {}).get("por_tarefa", {}) if estado_atual else {}

        for opt, var, rotulo_neutro in self.opts_modelo_ia:
            valores = [rotulo_neutro] + [rotulo for rotulo, _m, _p in self._pares_modelo_ia]
            opt.configure(values=valores)
            if var.get() not in valores:
                var.set(rotulo_neutro)

        if estado_atual is not None:
            self._preselecionar_modelo_ia(self.var_modelo_ia_global, salvo_global,
                                          self._rotulo_padrao_sistema_ia())
            for tarefa, var in self.vars_modelo_ia_por_tarefa.items():
                self._preselecionar_modelo_ia(var, salvos_tarefa.get(tarefa), "Usar o global")

        self._refiltrar_modelos_ia()
        self._atualizar_resumo_modelo_ia()

    def _preselecionar_modelo_ia(self, var, salvo, rotulo_neutro):
        """Deixa o dropdown mostrando o que está gravado no disco.

        Sempre encontra: `_acrescentar_selecoes_salvas_ia` já garantiu que
        toda seleção gravada está na lista, com rótulo "(salvo)" quando não
        veio do catálogo do provedor corrente. O `set(rotulo_neutro)` do fim
        é a rede para o caso de o arquivo trazer uma entrada malformada."""
        if not salvo:
            var.set(rotulo_neutro)
            return
        for rotulo, model_id, _provider in self._pares_modelo_ia:
            if model_id == salvo.get("model"):
                var.set(rotulo)
                return
        var.set(rotulo_neutro)

    def _refiltrar_modelos_ia(self):
        """Aplica o filtro de texto às listas. Existe porque o OpenRouter tem
        centenas de modelos e `CTkOptionMenu` não tem busca -- era
        literalmente inviável achar um id específico."""
        termo = self.entry_filtro_modelo_ia.get().strip().lower()
        for opt, var, rotulo_neutro in self.opts_modelo_ia:
            casam = [
                rotulo for rotulo, model_id, _provider in self._pares_modelo_ia
                if not termo or termo in rotulo.lower() or termo in model_id.lower()
            ]
            # A opção escolhida NUNCA some por causa do filtro: sumir mudaria
            # a seleção sem o usuário pedir.
            escolhido = var.get()
            valores = [rotulo_neutro] + casam
            if escolhido not in valores:
                valores.append(escolhido)
            opt.configure(values=valores)

    def _trocou_provider_ia(self, _escolha):
        # Trocar de provedor troca a lista inteira -- e o modelo manual do
        # provedor antigo não vale para o novo.
        self.entry_modelo_ia_livre.delete(0, "end")
        self._recarregar_modelos_do_provider()

    def _atualizar_catalogo_ia(self):
        """Busca o catálogo do provedor atual (rede), numa thread."""
        provider = self._provider_ia_atual()
        if self.lbl_catalogo_ia is not None:
            self.lbl_catalogo_ia.configure(text="Buscando a lista de modelos do provedor...")
        threading.Thread(target=self._worker_catalogo_ia, args=(provider,), daemon=True).start()

    def _worker_catalogo_ia(self, provider):
        # `catalogo.listar_modelos` não levanta (devolve [] em falha), então
        # o worker não precisa de try/except para não matar a thread; o
        # `after` devolve o desenho para a thread da UI.
        catalogo.listar_modelos(provider, self.controller.api_keys, forcar=True)
        self.after(0, self._recarregar_modelos_do_provider)

    # ------------------------------------------------------------------
    # Precedência e resumo
    # ------------------------------------------------------------------
    def _toggle_modelos_ia_modo_avancado(self):
        if self.var_modelos_ia_modo_avancado.get():
            self.frame_modelos_ia_avancado.pack(
                fill="x", padx=10, pady=(0, 10), before=self._ancora_apos_avancado_ia,
            )
        else:
            self.frame_modelos_ia_avancado.pack_forget()
        self._atualizar_resumo_modelo_ia()

    def _recarregar_painel_modelos_ia(self):
        self.frame_modelos_ia.destroy()
        # [2026-09-03] Remonta ONDE ele estava: na janela, se veio de uma
        # janela; na Home, se não. Sem isto, trocar de provedor com o painel
        # aberto numa janela o reconstruiria na Home, atrás dela.
        self.criar_painel_modelos_ia(
            row=self._row_modelos_ia,
            parent=getattr(self, "_parent_modelos_ia", None),
        )

    def _escolheu_favorito_global_ia(self, _escolha):
        """Escolher na lista DESISTE do modelo manual -- vale sempre o último
        controle mexido. Sem isso, quem tivesse digitado um id manual ficava
        preso nele, porque o manual vence na hora de salvar."""
        self._limpar_modelo_ia_livre()

    def _limpar_modelo_ia_livre(self):
        self.entry_modelo_ia_livre.delete(0, "end")
        self._atualizar_resumo_modelo_ia()

    def _id_do_rotulo_modelo_ia(self, rotulo):
        """(model_id, provider) da opção, ou `(None, None)` para a opção
        neutra. O provider vem do PAR, nunca do dropdown de provedor -- ver
        `_modelos_do_provider_ia`."""
        for texto, model_id, provider in self._pares_modelo_ia:
            if texto == rotulo:
                return model_id, provider
        return None, None

    def _modelo_ia_global_efetivo(self):
        """(provider, model, origem) que "Salvar seleção" vai gravar como
        global. Fonte ÚNICA -- o resumo na tela e o salvamento leem daqui,
        então não têm como divergir."""
        provider = self._provider_ia_atual()
        manual = self.entry_modelo_ia_livre.get().strip()
        if manual:
            return provider, manual, "campo manual"
        model_id, provider_do_modelo = self._id_do_rotulo_modelo_ia(
            self.var_modelo_ia_global.get()
        )
        if model_id is None:
            return None, None, "padrão do sistema"
        return provider_do_modelo, model_id, "lista de modelos"

    def _atualizar_resumo_modelo_ia(self):
        if getattr(self, "lbl_resumo_modelo_ia", None) is None:
            return

        provider, model, origem = self._modelo_ia_global_efetivo()
        if provider is None:
            linha = "Ao salvar: todas as tarefas voltam ao padrão do sistema (modelos atuais)."
        else:
            linha = f"Ao salvar: {provider} / {model}  (veio do {origem})"

        if getattr(self, "vars_modelo_ia_por_tarefa", None) and self.var_modelos_ia_modo_avancado.get():
            com_override = [
                tarefa for tarefa, var in self.vars_modelo_ia_por_tarefa.items()
                if self._id_do_rotulo_modelo_ia(var.get())[0] is not None
            ]
            if com_override:
                linha += (
                    f"  |  {len(com_override)} tarefa(s) com modelo próprio "
                    f"({', '.join(sorted(com_override))}), que vence o padrão acima."
                )

        self.lbl_resumo_modelo_ia.configure(text=linha)

    def _aplicar_recomendados_ia(self):
        # Adotar os recomendados pode levar alguma tarefa para um provider
        # diferente do usado hoje (ex.: Grok 4.5 só é alcançável via
        # OpenRouter). Sem a chave desse provider, a troca só falharia no meio
        # da próxima execução — então avisamos ANTES de gravar.
        faltando = sorted(
            provider
            for provider in selecao.providers_exigidos_pelos_recomendados()
            if not self.controller.get_key(sigft_config.CHAVE_POR_PROVIDER[provider])
        )
        if faltando:
            chaves = ", ".join(sigft_config.CHAVE_POR_PROVIDER[p] for p in faltando)
            if not messagebox.askyesno(
                "Chave de API faltando",
                f"Os modelos recomendados exigem {chaves}, que ainda não está configurada "
                "no painel de chaves acima.\n\nSe aplicar assim, os módulos que dependem "
                "desse provedor vão falhar até a chave ser preenchida.\n\nAplicar mesmo assim?",
            ):
                return

        selecao.aplicar_recomendados(config_path=sigft_config.CONFIG_FILE)
        self._recarregar_painel_modelos_ia()
        messagebox.showinfo(
            "Recomendados aplicados",
            "Os modelos recomendados (docs/refatoracao/MODELOS_IA.md) foram aplicados: Gemini 3 Flash "
            "Preview como padrão global, com Grok 4.5 para a classificação de PDM.\n\n"
            "São modelos mais econômicos que os usados até agora. Vale validar a qualidade "
            "num punhado de fichas (comparando com o resultado anterior) antes de rodar em lote.",
        )

    def _salvar_selecao_modelos_ia(self):
        # A precedência (campo manual > dropdown > padrão) vive em
        # `_modelo_ia_global_efetivo`, que é a MESMA fonte do resumo na tela.
        # Duplicar a regra aqui era o caminho para a tela dizer uma coisa e o
        # arquivo guardar outra.
        provider_global, model_global, _origem = self._modelo_ia_global_efetivo()
        if provider_global is None:
            selecao.limpar_global(config_path=sigft_config.CONFIG_FILE)
        else:
            selecao.definir_global(
                provider_global, model_global, config_path=sigft_config.CONFIG_FILE,
            )

        # Os overrides por tarefa usam o MESMO provedor escolhido lá em cima
        # -- é o ponto central do redesenho: uma decisão de chave, não uma por
        # linha. Quem precisa misturar provedores entre tarefas salva um,
        # troca o provedor e salva o outro.
        for tarefa, var_tarefa in self.vars_modelo_ia_por_tarefa.items():
            model_id, provider_do_modelo = self._id_do_rotulo_modelo_ia(var_tarefa.get())
            if model_id is None:
                selecao.limpar_por_tarefa(tarefa, config_path=sigft_config.CONFIG_FILE)
            else:
                selecao.definir_por_tarefa(
                    tarefa, provider_do_modelo, model_id, config_path=sigft_config.CONFIG_FILE,
                )

        self._recarregar_painel_modelos_ia()
        messagebox.showinfo(
            "Seleção salva",
            "Seleção de modelos de IA salva. A próxima execução de cada módulo já usa o modelo "
            "escolhido. Não é preciso reiniciar o SIG-FT.",
        )

    # =========================================================================
    # PAINEL "GASTOS DE IA" (Checkpoint 3.4 do plano de refatoração)
    # =========================================================================
    # Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.4. Resumo do
    # "UsageTracker" (`sigft.core.llm.usage`): cada `LLMClient.generate()`
    # grava um registro em `logs/llm_usage.jsonl` (ver `core/llm/client.py`/
    # `core/llm/usage.py`). Mesmo padrão visual dos 2 painéis acima
    # (`criar_area_config_api`/`criar_painel_modelos_ia`: `CTkFrame`,
    # `fg_color=("gray90","gray16")`, `corner_radius=10`, título em negrito
    # com emoji). A leitura fica inteiramente dentro de
    # `_atualizar_texto_gastos_ia` (try/except) -- o painel NUNCA pode
    # impedir a Home de abrir, mesmo se `logs/` estiver corrompido/
    # inacessível.
    def criar_painel_gastos_ia(self, row, parent=None):
        """Painel "Gastos de IA": resumo em texto (total gasto, nº de
        chamadas, período coberto) + gasto por módulo e por modelo (via
        `usage.formatar_relatorio_texto` -- CP 3.4), botão "Atualizar" e
        botão "Abrir pasta de logs". Sem registros ainda -> mensagem
        amigável ("Nenhuma chamada de IA registrada ainda.", já produzida
        por `formatar_relatorio_texto`), nunca uma tabela vazia ou erro."""
        self._row_gastos_ia = row
        dono = parent if parent is not None else self
        frame = ctk.CTkFrame(dono, fg_color=("gray90", "gray16"), corner_radius=10)
        if parent is None:
            frame.grid(row=row, column=0, sticky="ew", padx=20, pady=10)
        else:
            frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.frame_gastos_ia = frame

        ctk.CTkLabel(frame, text="💰 Gastos de IA", font=("Arial", 16, "bold")).pack(pady=10, padx=10, anchor="w")

        self.lbl_gastos_ia = ctk.CTkLabel(
            frame, text="Carregando...", font=("Roboto", 12), justify="left", anchor="w", wraplength=800,
        )
        self.lbl_gastos_ia.pack(anchor="w", padx=10, pady=(0, 10), fill="x")
        self._atualizar_texto_gastos_ia()

        f_botoes_gastos = ctk.CTkFrame(frame, fg_color="transparent")
        f_botoes_gastos.pack(fill="x", padx=10, pady=(0, 15))
        ctk.CTkButton(
            f_botoes_gastos, text="Atualizar", command=self._atualizar_texto_gastos_ia,
            fg_color="#3A3A3A", hover_color="#454545",
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            f_botoes_gastos, text="Abrir pasta de logs", command=self._abrir_pasta_logs_gastos_ia,
            fg_color="#3A3A3A", hover_color="#454545",
        ).pack(side="left")

    def _atualizar_texto_gastos_ia(self):
        """Recalcula o texto do painel a partir de `logs/llm_usage.jsonl`.
        Leitura local (rápida) -- síncrona, sem thread (ao contrário do
        catálogo de modelos do provedor, que é rede -- ver
        `_atualizar_catalogo_ia`). NUNCA levanta: qualquer falha
        (ex.: arquivo sem permissão de leitura, JSON corrompido além do que
        `ler_registros` já tolera) degrada para uma mensagem amigável, sem
        impedir a Home de abrir/continuar funcionando."""
        try:
            relatorio = llm_usage.usage_report()
            texto = llm_usage.formatar_relatorio_texto(relatorio)
        except Exception as e:
            texto = f"Não foi possível carregar os gastos de IA agora ({e})."
        self.lbl_gastos_ia.configure(text=texto)

    def _abrir_pasta_logs_gastos_ia(self):
        """Abre `logs/` no explorador de arquivos do sistema.

        [CP 8.4] A mecânica de abrir mudou para `core/plataforma.py`, junto
        com as outras 2 cópias. Cria a pasta se ainda não existir (nenhuma
        tarefa de IA rodou ainda) para não confrontar o usuário com "pasta
        não encontrada" por algo que é responsabilidade do próprio app criar.
        Tudo dentro de try/except: nunca deixa uma exceção do SO subir até
        travar a UI."""
        pasta = sigft_config.PASTA_LOGS
        try:
            plataforma.abrir_pasta_criando_se_preciso(pasta)
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível abrir a pasta de logs: {e}")

    def criar_texto_simples(self, texto, row):
        label = ctk.CTkLabel(self, text=texto, font=("Arial", 14), justify="left", wraplength=800)
        label.grid(row=row, column=0, sticky="w", padx=20, pady=10)

    def criar_card_instrucao(self, row, titulo, descricao, inputs, outputs):
        # Card com cor levemente mais clara que o fundo (#2B2B2B se o fundo for #212121)
        card = ctk.CTkFrame(self, fg_color="#2B2B2B", corner_radius=8, border_width=1, border_color="#333333")
        card.grid(row=row, column=0, sticky="ew", padx=20, pady=8)
        card.grid_columnconfigure(0, weight=1)

        # Título com a cor Primária (Teal)
        lbl_tit = ctk.CTkLabel(card, text=titulo, font=ctk.CTkFont(family="Roboto", size=18, weight="bold"), text_color=COLORS["accent"])
        lbl_tit.grid(row=0, column=0, sticky="w", padx=20, pady=(15, 5))

        lbl_desc = ctk.CTkLabel(card, text=descricao, font=("Roboto", 13), text_color="#CCCCCC", justify="left", wraplength=800)
        lbl_desc.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 15))

        # Linha divisória sutil
        linha = ctk.CTkFrame(card, height=1, fg_color="#404040")
        linha.grid(row=2, column=0, sticky="ew", padx=10, pady=0)

        io_frame = ctk.CTkFrame(card, fg_color="transparent")
        io_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=15)
        io_frame.grid_columnconfigure((0, 1), weight=1)

        # Ícones visuais nos textos
        ctk.CTkLabel(io_frame, text="📥 ENTRADAS", font=("Roboto", 11, "bold"), text_color="gray60").grid(row=0, column=0, sticky="w")
        lbl_in = ctk.CTkLabel(io_frame, text=inputs, font=("Roboto", 12), text_color="gray80", justify="left", anchor="w")
        lbl_in.grid(row=1, column=0, sticky="nw", pady=(5, 0))

        ctk.CTkLabel(io_frame, text="📤 SAÍDAS", font=("Roboto", 11, "bold"), text_color="gray60").grid(row=0, column=1, sticky="w")
        lbl_out = ctk.CTkLabel(io_frame, text=outputs, font=("Roboto", 12), text_color="gray80", justify="left", anchor="w")
        lbl_out.grid(row=1, column=1, sticky="nw", pady=(5, 0))

