"""Ponto de entrada do SIG-FT — Checkpoint 7.3 (Fase 7 do plano).

Monta a janela principal (sidebar + área de conteúdo), registra as 12 telas de
`sigft/app/views/` e sobe a splash que carrega os backends pesados.

    python -m sigft.app.main

`frontend.py` continua funcionando: virou um shim que importa daqui.
"""
from __future__ import annotations

import json
import os
import sys

# ⚠️ ANTES de qualquer import pesado, e isto é deliberado.
#
# `--conferir-pacote` existe para dizer O QUE ESTÁ FALTANDO num bundle. Se ela
# rodasse depois do `import tkinter` logo abaixo, um bundle quebrado a
# quebraria junto — e o passo do CI morreria com um traceback em vez do
# relatório. Uma conferência de pacote tem de funcionar justamente quando o
# pacote está incompleto.
#
# `sigft/app/conferencia.py` é só stdlib, de propósito. Ver o docstring de lá.
#
# ⚠️ O `if` aqui vale para `python -m sigft.app.main`, que é uma das formas de
# abrir. A OUTRA — a que o `.exe` usa — é o `frontend.py`, e lá este bloco
# precisa existir também: no bundle quem é `"__main__"` é ele, não este
# arquivo. Em 2026-09-21 faltava, e o Release ficou pendurado. O nome da flag
# mora em `conferencia.despachar_cedo`, para não haver dois donos.
if __name__ == "__main__":
    from sigft.app.conferencia import despachar_cedo as _despachar_cedo

    _despachar_cedo()

import threading
import time
import tkinter as tk

from dotenv import load_dotenv
from PIL import Image

from sigft.app import backends
from sigft import _build_info
from sigft.app.theme import COLORS
from sigft.app.views.analyzer import ModuloAnalyzer
from sigft.app.views.autospec import ModuloAutoSpec
from sigft.app.views.busca_pmib import ModuloBuscaPMIB
from sigft.app.views.copia_fichas import ModuloCopiaFichas
from sigft.app.views.cria_fichas import ModuloCriaFichas
from sigft.app.views.home import HomeView
# [2026-08-28] As duas telas de LMR viraram abas de uma seção só.
from sigft.app.views.aplicacao_lmr import ModuloAplicacaoLMR
from sigft.app.views.pdm import ModuloPDM
from sigft.app.views.pmib_manager import ModuloPMIBManager
from sigft.app.views.translator import ModuloTranslator
from sigft.app.views.upload_conditions import ModuloUploadConditions
from sigft.app.views.upload_tech_specs import ModuloUploadTechSpecs

import customtkinter as ctk

# Configuração Global
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")
# O NOME do arquivo. O CAMINHO vem de `config.caminho_config()`, que o resolve
# em `Documentos\SIG-FT\` — ver `sigft/core/dados_usuario.py`. Era um nome
# relativo, resolvido pelo diretório de trabalho; sob `Program Files` (o padrão
# do instalador) isso é somente-leitura, e as chaves de API sumiriam a cada
# abertura.
CONFIG_FILE = "api_config.json"


def _arquivo_de_chaves() -> str:
    """Caminho completo do `api_config.json` do usuário."""
    from sigft.config import caminho_config

    return caminho_config()

# Raiz do projeto: dois níveis acima de sigft/app/main.py.
#
# [CP 7.3] Isto É a correção, não enfeite. O `resource_path` do `frontend.py`
# fazia `os.path.dirname(os.path.abspath(__file__))`, e lá isso dava a raiz
# porque o arquivo ESTAVA na raiz. Movido para cá sem ajuste, passaria a
# apontar para `sigft/app/` — e o `.env`, o `api_config.json` e a pasta
# `assets/` (ícone e logo) sumiriam, sem erro nenhum na abertura: o app
# subiria sem ícone e sem chave de API, como se nunca tivessem sido
# configurados.
_RAIZ_DO_PROJETO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def resource_path(relative_path):
    """Caminho absoluto de um recurso, no .py e dentro do .exe do PyInstaller."""
    try:
        # PyInstaller cria uma pasta temporária (modo executável)
        base_path = sys._MEIPASS
    except Exception:
        base_path = _RAIZ_DO_PROJETO
    return os.path.join(base_path, relative_path)


# =============================================================================
# O ÍCONE DA JANELA E DA BARRA DE TAREFAS
# =============================================================================
# [2026-09-04] Decisão do usuário: o ícone do app e da barra de tarefas passa
# a ser o do SIG-FT; DENTRO da janela continua o símbolo da GE Vernova.
#
# São dois arquivos com papéis diferentes, e confundi-los é o erro fácil:
#
#   assets/icone-sig-ft.ico   -> ÍCONE: barra de tarefas, barra de título, o
#                                .exe e o instalador. Nunca aparece na tela.
#   assets/icone-sig-ft.png   -> o mesmo desenho, para a SPLASH (e como
#                                fallback do Tk fora do Windows).
#   assets/logo.png           -> IMAGEM: o símbolo da GE Vernova, na BARRA
#                                LATERAL. Continua sendo o de dentro do app.
#
# [2026-09-22] O usuário trocou o ícone e pediu que a splash mostrasse o mesmo
# desenho, mantendo a GE Vernova dentro da janela. O `.ico` versionado passou
# a trazer todos os tamanhos (16 a 256): o anterior tinha só 256, o
# `Gerar-Executavel.bat` remendava isso em `build/`, e o workflow de Release
# não roda o `.bat` -- então o `.exe` publicado saía com o ícone borrado na
# barra de tarefas. Ver `tests/test_icone_do_aplicativo.py`.
#
# `.ico` e não `.png` porque no Windows quem dá o ícone bonito na barra de
# tarefas é o `iconbitmap` com um `.ico` de verdade — o `wm_iconphoto` com PNG
# funciona, mas o Windows redimensiona na hora e a barra de título sai borrada.
ARQUIVO_DO_ICONE = os.path.join("assets", "icone-sig-ft.ico")
ARQUIVO_DO_LOGO_DA_SPLASH = os.path.join("assets", "icone-sig-ft.png")


def definir_icone(janela) -> bool:
    """Põe o ícone do SIG-FT na janela. `True` se conseguiu.

    Nunca levanta: ficar sem ícone é cosmético, e derrubar a abertura do app
    por causa disso seria trocar um arranhão por um buraco. Foi assim que o
    ícone quebrado do CP 7.3 passou despercebido — só avisava no console.
    """
    caminho = resource_path(ARQUIVO_DO_ICONE)
    if not os.path.exists(caminho):
        return False
    try:
        janela.iconbitmap(caminho)
        return True
    except Exception:
        # `iconbitmap` só existe com .ico no Windows. Fora dele (ou com um
        # .ico que o Tk recuse), tenta o PNG, que é melhor que nada.
        try:
            png = resource_path(ARQUIVO_DO_LOGO_DA_SPLASH)
            if os.path.exists(png):
                janela.wm_iconphoto(False, tk.PhotoImage(file=png))
                return True
        except Exception:
            pass
    return False


# =============================================================================
# SEM JANELA PRETA, MAS COM DIAGNOSTICO
# =============================================================================
# [2026-09-04] Pedido do usuário: *"quando executo o executável, não pode
# ficar com o powershell aberto"*. O `.exe` passou a ser compilado com
# `console=False` (ver SIG-FT.spec).
#
# Só que o console não era enfeite: ERA o canal de diagnóstico. É nele que
# apareciam "Erro ao carregar <módulo>" da splash e o
# `CERTIFICATE_VERIFY_FAILED` do Zscaler. Numa primeira execução em máquina
# nova — exatamente o caso da GE Vernova — perder isso troca uma mensagem
# clara por "não funciona".
#
# Então o canal não some: muda de lugar. Sem console, o PyInstaller deixa
# `sys.stdout` e `sys.stderr` como `None`; aqui eles passam a apontar para
# `logs/sigft.log`, AO LADO do .exe. Quem precisar diagnosticar abre o
# arquivo (é o que o `Diagnostico-Erro.bat` mostra).
def _desviar_saida_para_arquivo() -> None:
    """Sem console, manda `print` e traceback para `logs/sigft.log`.

    Só age no executável compilado (`sys.frozen`) e só quando o PyInstaller
    de fato não deu console (`sys.stdout is None`). Rodando do `.py` nada
    muda — o terminal continua sendo o lugar certo.

    Nunca levanta: se não der para abrir o arquivo (pasta somente-leitura,
    disco cheio), o app tem que subir assim mesmo. Perder o log é ruim;
    não abrir é pior.
    """
    if not getattr(sys, "frozen", False):
        return
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        # `Documentos\SIG-FT\logs\`, e não ao lado do `.exe`: sob
        # `Program Files` a pasta do programa é somente-leitura, e este é o
        # pior lugar para falhar em silêncio — é justamente este log que
        # explicaria qualquer outra falha da abertura.
        from sigft.core.dados_usuario import pasta_logs

        destino = open(
            os.path.join(str(pasta_logs()), "sigft.log"),
            "a", encoding="utf-8", buffering=1,
        )
        if sys.stdout is None:
            sys.stdout = destino
        if sys.stderr is None:
            sys.stderr = destino
        destino.write(chr(10))
        print("===== SIG-FT iniciado em %s =====" % time.strftime("%d/%m/%Y %H:%M:%S"))
    except Exception:
        pass


_desviar_saida_para_arquivo()


env_path = resource_path('.env')
load_dotenv(env_path)


# =============================================================================
# TELA DE CARREGAMENTO (SPLASH SCREEN)
# =============================================================================
class SplashScreen(ctk.CTk):
    def __init__(self):
        super().__init__()
        # Configurações da Janela
        self.title("Carregando...")
        width, height = 500, 350

        # Centralizar
        ws = self.winfo_screenwidth()
        hs = self.winfo_screenheight()
        x = (ws/2) - (width/2)
        y = (hs/2) - (height/2)
        self.geometry(f'{width}x{height}+{int(x)}+{int(y)}')

        self.overrideredirect(True)  # Remove a barra de título
        self.configure(fg_color=COLORS["background"])

        # Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure((0, 1, 2, 3), weight=1)

        # 1. Logo
        # [CP 7.3] Passou a usar `resource_path`. Antes montava o caminho com
        # `os.path.dirname(os.path.abspath(__file__))` -- que dava a raiz
        # enquanto este codigo morava no frontend.py, e passou a dar
        # `sigft/app/` quando ele veio para ca. O resultado era o app abrindo
        # SEM logo e SEM icone, avisando so no console (que ninguem le), como
        # se os arquivos nao existissem.
        image_path = resource_path(ARQUIVO_DO_LOGO_DA_SPLASH)

        self.logo_img = None  # Mantém referência para não sumir
        if os.path.exists(image_path):
            try:
                pil_img = Image.open(image_path)
                # Redimensiona mantendo proporção
                w_percent = (300 / float(pil_img.size[0]))
                h_size = int((float(pil_img.size[1]) * float(w_percent)))

                self.logo_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(300, h_size))

                lbl_logo = ctk.CTkLabel(self, text="", image=self.logo_img)
                lbl_logo.pack(pady=(50, 10))
            except Exception as e:
                print(f"Erro ao carregar imagem da Splash: {e}")
                ctk.CTkLabel(self, text="GE Vernova", font=("Roboto", 30, "bold"), text_color="white").pack(pady=(50, 10))
        else:
            print(f"Imagem não encontrada em: {image_path}")
            ctk.CTkLabel(self, text="GE Vernova", font=("Roboto", 30, "bold"), text_color="white").pack(pady=(50, 10))

        # 2. Título
        ctk.CTkLabel(self, text="SIG-FT System", font=("Roboto", 16), text_color="gray").pack(pady=(0, 30))

        # 3. Status
        self.status_label = ctk.CTkLabel(self, text="Iniciando...", font=("Roboto", 12), text_color=COLORS["accent"])
        self.status_label.pack(pady=(0, 5))

        # 4. Barra
        self.progress = ctk.CTkProgressBar(self, width=400, height=12, corner_radius=5,
                                           progress_color=COLORS["accent"], fg_color="#333333")
        self.progress.pack(pady=(0, 20))
        self.progress.set(0)

        # Thread de carregamento
        threading.Thread(target=self.carregar_modulos).start()

    def carregar_modulos(self):
        """Importa os modulos pesados um por um e atualiza a barra.

        [CP 7.3] A LISTA e o mecanismo de import saíram daqui para
        `sigft/app/backends.py`. O splash ficou com o que e dele: mexer na
        barra e no rotulo. O motivo esta no docstring daquele modulo -- em
        resumo, `globals()[nome] = modulo` so alcancava as telas enquanto elas
        moravam neste arquivo.

        A ORDEM e os nomes exibidos sao os mesmos: e o que o usuario ve.
        """
        inicio = time.time()

        def ao_progredir(exibido, fracao):
            self.after(0, lambda d=exibido: self.status_label.configure(text=f"Carregando: {d}..."))
            # Delay minimo para a transicao nao piscar -- estava aqui antes.
            time.sleep(0.1)
            self.after(0, lambda p=fracao: self.progress.set(p))

        def ao_falhar(exibido, erro):
            print(f"Erro ao carregar {exibido}: {erro}")
            self.after(0, lambda d=exibido: self.status_label.configure(
                text=f"Erro em {d}", text_color=COLORS["danger"]))
            time.sleep(1)  # Pausa para ler o erro

        backends.carregar_todos(ao_progredir=ao_progredir, ao_falhar=ao_falhar)

        # Finalização
        elapsed = time.time() - inicio
        self.after(0, lambda: self.status_label.configure(text=f"Concluído em {elapsed:.1f}s"))
        self.after(0, lambda: self.progress.set(1.0))

        # Aguarda um momento breve e inicia o App Principal
        time.sleep(0.8)
        self.after(0, self.iniciar_app_principal)

    def iniciar_app_principal(self):
        self.withdraw()  # Esconde a Splash em vez de destruir imediatamente (evita erros do Tcl)
        self.destroy()   # Destrói
        app = SIG_FT_App()
        app.mainloop()

# =============================================================================
# APP PRINCIPAL (Gerenciador com Layout Novo, Estilizado e com IMAGENS)
# =============================================================================
class SIG_FT_App(ctk.CTk):
    def __init__(self):
        super().__init__()
        # Configuração da Janela
        # A versão no título é o único lugar onde a pessoa a vê sem procurar.
        # Sem ela: ninguém sabe em que build está ao relatar um problema, e não
        # há como confirmar que a atualização pegou. Vem do `_build_info`, que
        # o CI carimba a partir da tag -- nunca de arquivo do usuário.
        self.title(f"SIG-FT v{_build_info.VERSAO} - GE Vernova")
        self.geometry("1280x850")

        # --- CARREGAMENTO DE IMAGENS (Ícone e Logo) ---
        # [CP 7.3] Mesmo caso do splash: `resource_path` e quem sabe achar a
        # raiz do projeto, tanto rodando do .py quanto de dentro do .exe do
        # PyInstaller (`sys._MEIPASS`).
        image_path = resource_path(os.path.join("assets", "logo.png"))

        # 1. Ícone da janela e da barra de tarefas -- o do SIG-FT.
        #    NÃO é o `image_path` acima: aquele é o logo da GE Vernova, que
        #    continua sendo o desenhado DENTRO da tela (barra lateral).
        if not definir_icone(self):
            print(f"AVISO: icone nao encontrado em: {resource_path(ARQUIVO_DO_ICONE)}")

        # 2. Carregar Imagem para o Menu (Sidebar)
        self.logo_image = None
        try:
            if os.path.exists(image_path):
                # Altura CALCULADA a partir da proporção real do arquivo, não
                # fixada: `size=(180, 60)` impunha 3:1 a uma imagem que não é
                # 3:1, e o logo aparecia esticado na horizontal. A splash já
                # fazia a conta certa (`w_percent`); a sidebar não.
                pil_logo = Image.open(image_path)
                largura_alvo = 180
                proporcao = largura_alvo / float(pil_logo.size[0])
                altura_alvo = max(1, int(pil_logo.size[1] * proporcao))
                self.logo_image = ctk.CTkImage(
                    light_image=pil_logo,
                    dark_image=pil_logo,
                    size=(largura_alvo, altura_alvo)
                )
        except Exception as e:
            print(f"Aviso: Não foi possível carregar a logo do menu. Detalhe: {e}")

        # --- GESTÃO DE CHAVES API ---
        self.api_keys = {}
        self.load_keys()

        # Layout Principal (2 Colunas: Sidebar fixa, Conteúdo dinâmico)
        self.grid_columnconfigure(0, weight=0)  # Sidebar fixa
        self.grid_columnconfigure(1, weight=1)  # Conteúdo expande
        self.grid_rowconfigure(0, weight=1)

        # === 1. CRIANDO O MENU LATERAL (SIDEBAR) ===
        # Substituição do CTkFrame pelo CTkScrollableFrame
        self.sidebar = ctk.CTkScrollableFrame(self, width=260, corner_radius=0, fg_color=COLORS["sidebar"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        # O frame rolável empilha os itens automaticamente; configuração de peso
        # em linha vazia pode bugar a rolagem, por isso não usamos grid_rowconfigure aqui.
        #
        # A COLUNA, sim, precisa de peso. Sem isto ela fica só com a largura do
        # widget mais largo, e os botões (que usam `sticky="ew"`) param antes
        # da borda: sobrava uma faixa vazia entre o texto e a barra de
        # rolagem, com cara de menu mal alinhado. `grid_columnconfigure` não
        # mexe na rolagem, que é vertical.
        self.sidebar.grid_columnconfigure(0, weight=1)

        # --- LOGO E TÍTULO ---
        # Alteração: Texto removido, apenas a imagem é exibida
        self.logo_label = ctk.CTkLabel(
            self.sidebar,
            text="",  # Texto vazio
            image=self.logo_image  # A imagem já contém o texto "GE Vernova"
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 10), sticky="ew")

        self.lbl_app = ctk.CTkLabel(self.sidebar, text="SIG-FT System", font=ctk.CTkFont(family="Roboto", size=13), text_color="gray60")
        self.lbl_app.grid(row=1, column=0, padx=20, pady=(0, 20))

        # Botão Home
        self.btn_home = ctk.CTkButton(self.sidebar, text="  🏠  Home", command=lambda: self.show_frame("Home"),
                                      fg_color="transparent", border_width=1, border_color="gray30",
                                      text_color=COLORS["text_light"], anchor="w", font=("Roboto", 13, "bold"),
                                      hover_color=COLORS["primary"])
        self.btn_home.grid(row=2, column=0, padx=15, pady=10, sticky="ew")

        # --- BOTÕES DO MENU ---
        # Seção 1: Início
        self._criar_label_secao(self.sidebar, "Início da Ficha", row=3)
        self.btn_pmib = self._criar_botao_menu(self.sidebar, "1. Cria Fichas PMIB", "CriaFichas", row=4)
        self.btn_pdm = self._criar_botao_menu(self.sidebar, "2. Planilhas PMIB", "PDM", row=5)
        self.btn_analise = self._criar_botao_menu(self.sidebar, "3. Analyzer (IA)", "Analyzer", row=6)

        # Seção 2: Dados Técnicos
        self._criar_label_secao(self.sidebar, "Dados Técnicos & Upload", row=7)
        self.btn_cond = self._criar_botao_menu(self.sidebar, "4.1. Upload Condições", "UploadConditions", row=8)
        self.btn_trad = self._criar_botao_menu(self.sidebar, "4.2. Tradutor", "Translator", row=9)
        self.btn_specs = self._criar_botao_menu(self.sidebar, "4.3. Upload Specs", "UploadSpecs", row=10)
        self.btn_copia = self._criar_botao_menu(self.sidebar, "5. Upload duplicadas", "CopiaFichas", row=11)
        self.btn_auto = self._criar_botao_menu(self.sidebar, "6. AutoSpec AI (RAG)", "AutoSpec", row=12)

        # Seção 3: Gestão
        self._criar_label_secao(self.sidebar, "Gestão & LMR", row=13)
        # [2026-08-28] Um botão só: as duas operações sobre a MESMA aba do
        # portal ficavam em entradas separadas, e uma delas é destrutiva.
        self.btn_lmr = self._criar_botao_menu(self.sidebar, "7. Aplicação LMR", "LMR", row=14)
        self.btn_manager = self._criar_botao_menu(self.sidebar, "8. PMIB Manager", "PMIBManager", row=16)
        self.btn_search = self._criar_botao_menu(self.sidebar, "9. Search", "SearchPMIB", row=17)

        # === 2. INICIALIZANDO OS FRAMES (MÓDULOS) ===
        self.container = ctk.CTkFrame(self, fg_color=COLORS["background"])
        self.container.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.frames = {}

        # Instanciação dos Módulos
        self.frames["Home"] = HomeView(parent=self.container, controller=self)
        self.frames["CriaFichas"] = ModuloCriaFichas(parent=self.container, controller=self)
        self.frames["PDM"] = ModuloPDM(parent=self.container, controller=self)
        self.frames["Analyzer"] = ModuloAnalyzer(parent=self.container, controller=self)
        self.frames["Translator"] = ModuloTranslator(parent=self.container, controller=self)
        self.frames["UploadConditions"] = ModuloUploadConditions(parent=self.container, controller=self)
        self.frames["UploadSpecs"] = ModuloUploadTechSpecs(parent=self.container, controller=self)
        self.frames["CopiaFichas"] = ModuloCopiaFichas(parent=self.container, controller=self)
        self.frames["AutoSpec"] = ModuloAutoSpec(parent=self.container, controller=self)
        self.frames["LMR"] = ModuloAplicacaoLMR(parent=self.container, controller=self)
        self.frames["PMIBManager"] = ModuloPMIBManager(parent=self.container, controller=self)
        self.frames["SearchPMIB"] = ModuloBuscaPMIB(parent=self.container, controller=self)

        for f in self.frames.values():
            f.configure(fg_color=COLORS["background"])

        self.show_frame("Home")

    # --- Métodos Auxiliares de Estilo ---
    def _criar_botao_menu(self, parent, text, frame_name, row):
        # Botões mais limpos, sem cor de fundo sólida, apenas no hover
        btn = ctk.CTkButton(parent, text=f"  {text}", command=lambda: self.show_frame(frame_name),
                            fg_color="transparent",
                            text_color=COLORS["text_light"],
                            anchor="w",
                            font=("Roboto", 12),
                            hover_color=COLORS["primary"],  # Hover na cor da marca
                            height=35)
        btn.grid(row=row, column=0, padx=10, pady=2, sticky="ew")
        return btn

    def _criar_label_secao(self, parent, text, row):
        # Label de seção mais discreto
        label = ctk.CTkLabel(parent, text=text.upper(), font=("Roboto", 11, "bold"), text_color="gray50", anchor="w")
        label.grid(row=row, column=0, padx=20, pady=(20, 5), sticky="w")

    # --- Gerenciamento de Chaves e Navegação ---
    def load_keys(self):
        gemini_api_key = os.getenv('API_GEMINI_LUAN_GMAIL')
        google_search_api = os.getenv('GOOGLE_SEARCH_API')
        google_cse_api = os.getenv('GOOGLE_CSE_API')
        llama_api = os.getenv('LLAMA_CLOUD_API')
        # [CP 3.2] Gateway OpenRouter (padrão) + endpoint OpenAI-compatível
        # genérico da futura IA interna da empresa — nomes de env var
        # idênticos aos de `sigft.config.ENV_VAR_POR_CHAVE`.
        openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
        empresa_llm_base_url = os.getenv('EMPRESA_LLM_BASE_URL')
        empresa_llm_api_key = os.getenv('EMPRESA_LLM_API_KEY')

        defaults = {
            "GEMINI": gemini_api_key,
            "GOOGLE_SEARCH": google_search_api,
            "GOOGLE_CSE": google_cse_api,
            "LLAMA": llama_api,
            "OPENROUTER": openrouter_api_key,
            "EMPRESA_LLM_BASE_URL": empresa_llm_base_url,
            "EMPRESA_LLM_API_KEY": empresa_llm_api_key
        }
        arquivo = _arquivo_de_chaves()
        if os.path.exists(arquivo):
            try:
                with open(arquivo, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    self.api_keys = {**defaults, **saved}
            except Exception:
                self.api_keys = defaults
        else:
            self.api_keys = defaults

    def save_keys(self, new_keys):
        # [CP 3.3] read-modify-write do JSON INTEIRO: antes, este método
        # sobrescrevia CONFIG_FILE só com `new_keys` (as chaves de API do
        # painel "Configuração de Chaves API"), o que APAGARIA a sub-árvore
        # reservada "_modelos_ia" gravada por `sigft.core.llm.selecao`
        # (seleção de modelo de IA do painel "Modelos de IA" da Home) toda
        # vez que o usuário salvasse as chaves de API depois de escolher um
        # modelo. Mesma disciplina de
        # `sigft.core.llm.selecao._salvar_secao`: lê o que já está no
        # arquivo, atualiza só as chaves de API recebidas, regrava tudo.
        arquivo = _arquivo_de_chaves()
        dados_no_arquivo = {}
        if os.path.exists(arquivo):
            try:
                with open(arquivo, 'r', encoding='utf-8') as f:
                    carregado = json.load(f)
                if isinstance(carregado, dict):
                    dados_no_arquivo = carregado
            except Exception:
                dados_no_arquivo = {}

        dados_no_arquivo.update(new_keys)
        self.api_keys = new_keys

        with open(arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados_no_arquivo, f, indent=4)

    def get_key(self, key_id):
        return self.api_keys.get(key_id, "")

    def show_frame(self, name):
        for frame in self.frames.values():
            frame.grid_forget()
        frame = self.frames.get(name)
        if frame:
            frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

    def show_modulo(self, nome_modulo):
        self.show_frame(nome_modulo)

    def show_home(self):
        self.show_frame("Home")



def main():
    """Sobe o aplicativo pela splash, que carrega os backends e abre a janela."""
    # ANTES de qualquer janela existir, e nesta ordem:
    #
    #   - o `AppUserModelID`, senao o Windows agrupa a janela sob o
    #     identificador que ele deduz sozinho (o do `python.exe`) e mostra DOIS
    #     botoes na barra de tarefas para o mesmo programa;
    #   - o mutex nomeado, que e como o instalador descobre que o SIG-FT esta
    #     aberto e o fecha antes de trocar os arquivos. Sem ele a atualizacao
    #     falha com "arquivo em uso".
    #
    # Ver `sigft/core/instancia.py`; os nomes tem de bater com o
    # `installer/sigft.iss`, e ha teste travando os dois.
    from sigft.core import instancia

    instancia.preparar()

    # CP 5.5: aqui se imprimia qual motor cada módulo estava usando. Fazia
    # sentido enquanto havia DOIS e o usuário não tinha como saber em qual
    # estava. Agora só há o Playwright, e um texto que diz sempre a mesma coisa
    # é ruído que ninguém lê.
    # Traz `api_config.json`, `user_prefs.json` e o `.env` da pasta do
    # programa para `Documentos\SIG-FT\`, uma vez. Quem já usava o SIG-FT
    # atualiza e abre sem recadastrar chave nenhuma.
    #
    # Silenciosa quando não há o que migrar, que é o caso da segunda abertura
    # em diante -- e nunca levanta: perder a importação é ruim, não abrir é
    # pior. Ver `sigft/core/dados_usuario.py`.
    from sigft.core.dados_usuario import migrar_se_preciso

    if (trazidos := migrar_se_preciso()):
        print(f"[SIG-FT] Configuracao importada para a pasta de dados: "
              f"{', '.join(trazidos)}")

    # Acha o Chrome/Edge da máquina para o RPA e repassa o certificado da
    # empresa ao processo Node do Playwright.
    #
    # Isto era feito pelo `SIG-FT Itaipu.bat`, que some com o instalador. Sem
    # esta chamada, `SIGFT_PLAYWRIGHT_EXECUTABLE` não é definida por ninguém e
    # o RPA fica sem navegador EM TODA MÁQUINA -- com o app abrindo normalmente
    # e a falha só aparecendo quando a pessoa aciona um módulo de portal.
    #
    # `None` é resultado válido: o app abre igual, e só o robô reclama quando
    # for usado. Ver `sigft/core/rpa/navegador.py`.
    from sigft.core.rpa.navegador import preparar_ambiente_do_rpa

    if (navegador_do_rpa := preparar_ambiente_do_rpa()):
        print(f"[SIG-FT] Navegador do RPA: {navegador_do_rpa}")
    else:
        print("[SIG-FT] Nenhum Chrome/Edge encontrado. O app abre normalmente; "
              "so o robo do portal vai reclamar de navegador quando for usado.")

    splash = SplashScreen()
    splash.mainloop()


# =============================================================================
# As duas conferencias que o proprio .exe faz de si mesmo, no CI do Windows
# =============================================================================
#
# Vieram do dossie do Corella Suite, e resolvem um problema que o CLAUDE.md
# deste projeto ja nomeava sem ter solucao: "editou o frontend? ABRA O APP
# antes de dizer que esta pronto".
#
# Em 2026-08-25 o CP 5.5 removeu um frame e deixou um widget filho para tras.
# `compileall` passou, 2625 testes passaram, e o app morria na abertura com
# `NameError: name 'f_novo' is not defined`. So abrir a janela teria pego -- e
# nenhum CI em Linux pode fazer isso. O workflow de Release roda no WINDOWS, e
# la o .exe recem-compilado responde estas duas perguntas sozinho.

def _smoke() -> int:
    """Monta a janela principal e sai. Nao entra no `mainloop`.

    E a checagem que pega o widget orfao, o import que sumiu no bundle e o tema
    que nao carrega -- tudo o que so aparece quando a janela e CONSTRUIDA.
    """
    import traceback

    from sigft.app.conferencia import ARQUIVO_JANELA, gravar_relatorio

    avisos: list[str] = []

    try:
        # PRIMEIRO os backends, DEPOIS a janela -- nesta ordem, porque e a do
        # aplicativo de verdade: `main()` sobe a splash, a splash chama
        # `backends.carregar_todos()`, e so entao a janela existe.
        #
        # Montar a janela antes foi o que reprovou o run #3 de 2026-09-21:
        #
        #     backends.translator_backend.TechnicalTranslator()
        #     AttributeError: 'NoneType' object has no attribute ...
        #
        # As views leem o backend no proprio `__init__`, entao com o registro
        # ainda em `None` a primeira delas estoura. O defeito estava no
        # CHECADOR, nao no app -- e um checador que nao reproduz a ordem de
        # abertura reprova o que funciona, que e pior do que nao checar.
        from sigft.app import backends

        backends.carregar_todos(
            ao_falhar=lambda nome, erro: avisos.append(
                f"[smoke] AVISO: o backend '{nome}' nao carregou: "
                f"{type(erro).__name__}: {erro}"))

        app = SIG_FT_App()
        app.update_idletasks()   # forca o layout a ser calculado de verdade
        app.destroy()
    except Exception as e:  # noqa: BLE001 - e exatamente o que se quer relatar
        relatorio = "\n".join(avisos + [
            f"[smoke] FALHOU: {type(e).__name__}: {e}", "",
            traceback.format_exc()])
        # GRAVAR, e nao so imprimir: com `console=False` a saida do .exe nao
        # chega ao PowerShell, e o passo do CI reprova com "codigo 1" e mais
        # nada. Foi o que aconteceu no run #3 de 2026-09-21. Ver
        # `conferencia.gravar_relatorio`.
        gravar_relatorio(ARQUIVO_JANELA, relatorio)
        print(relatorio)
        return 1

    # Os avisos vao para o relatorio mesmo no caminho feliz: um backend que
    # nao importou nao derruba a abertura (`carregar_todos` segue em frente de
    # proposito), mas deixa UMA tela sem funcionar -- e isso tem de estar
    # escrito em algum lugar antes de chegar ao usuario.
    relatorio = "\n".join(
        avisos + ["[smoke] a janela principal montou e fechou sem erro."])
    gravar_relatorio(ARQUIVO_JANELA, relatorio)
    print(relatorio)
    return 0


def executar_da_linha_de_comando() -> None:
    """O que um ponto de entrada deve chamar. Trata `--smoke` e abre o app.

    Existe como função, e não como corpo de um `if __name__ == "__main__"`,
    pela razão que custou um Release: o bundle empacota o `frontend.py`, então
    o `__main__` do bundle é ELE, e um `--smoke` tratado só aqui embaixo seria
    ignorado — o `.exe` abriria a janela e o passo do CI ficaria pendurado
    esperando para sempre. Sendo função, os dois pontos de entrada chamam a
    mesma coisa e não há o que sair de sincronia.

    `--conferir-pacote` não entra aqui de propósito: ele tem de ser tratado
    ANTES dos imports pesados, lá no topo do arquivo. `--smoke` é o oposto —
    ele PRECISA deles, porque o que prova é que a janela monta.
    """
    if "--smoke" in sys.argv:
        sys.exit(_smoke())
    main()


if __name__ == "__main__":
    executar_da_linha_de_comando()
