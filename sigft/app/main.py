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
import threading
import time
import tkinter as tk

from dotenv import load_dotenv
from PIL import Image

from sigft.app import backends
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
CONFIG_FILE = "api_config.json"

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
#   assets/SIG-FT-logo-2.ico  -> ÍCONE: barra de tarefas, barra de título, o
#                                arquivo .exe. Nunca aparece dentro da tela.
#   assets/logo.png           -> IMAGEM: o logo da GE Vernova desenhado no
#                                splash e na barra lateral. Não mexer.
#
# `.ico` e não `.png` porque no Windows quem dá o ícone bonito na barra de
# tarefas é o `iconbitmap` com um `.ico` de verdade — o `wm_iconphoto` com PNG
# funciona, mas o Windows redimensiona na hora e a barra de título sai borrada.
ARQUIVO_DO_ICONE = os.path.join("assets", "SIG-FT-logo-2.ico")


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
            png = resource_path(os.path.join("assets", "logo.png"))
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
        pasta = os.path.join(os.path.dirname(sys.executable), "logs")
        os.makedirs(pasta, exist_ok=True)
        destino = open(
            os.path.join(pasta, "sigft.log"), "a", encoding="utf-8", buffering=1
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
        image_path = resource_path(os.path.join("assets", "logo.png"))

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
        self.title("SIG-FT - GE Vernova")
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
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    saved = json.load(f)
                    self.api_keys = {**defaults, **saved}
            except:
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
        dados_no_arquivo = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    carregado = json.load(f)
                if isinstance(carregado, dict):
                    dados_no_arquivo = carregado
            except Exception:
                dados_no_arquivo = {}

        dados_no_arquivo.update(new_keys)
        self.api_keys = new_keys

        with open(CONFIG_FILE, 'w') as f:
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
    # CP 5.5: aqui se imprimia qual motor cada módulo estava usando. Fazia
    # sentido enquanto havia DOIS e o usuário não tinha como saber em qual
    # estava. Agora só há o Playwright, e um texto que diz sempre a mesma coisa
    # é ruído que ninguém lê.
    splash = SplashScreen()
    splash.mainloop()


if __name__ == "__main__":
    main()
