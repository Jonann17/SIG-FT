#!/bin/bash
# =============================================================================
#  SIG-FT -- bootstrap do ambiente virtual no Mac (script interno)
#
#  Nao rode este arquivo direto. O SIG-FT.command faz `source` dele e chama
#  `sigft_bootstrap`. O `source` so DEFINE funcoes -- nao faz nada sozinho, e
#  e isso que deixa os testes (tests/test_lancador_mac.py) chamarem cada uma.
#
#  E o scripts/_bootstrap_venv.bat do Windows, no que vale no Mac:
#     1. escolhe/cria o ambiente virtual (venv);
#     2. instala o requirements.txt (e o requirements-dev.txt com SIGFT_DEV=1)
#        so quando o arquivo mudou desde a ultima instalacao;
#     3. baixa o navegador do Playwright uma vez, sem derrubar nada se falhar;
#     4. devolve o python do venv em $SIGFT_PY (e a pasta em $SIGFT_VENV_DIR).
#
#  Escrito para o bash 3.2, que e o que o macOS traz: nada de ${x,,},
#  `mapfile` ou vetor associativo.
# =============================================================================

sigft_bootstrap() {
    # A raiz do projeto: este arquivo vive em <raiz>/scripts/.
    if [ -z "${SIGFT_RAIZ:-}" ]; then
        SIGFT_RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    fi

    # --- 1. onde fica o venv, e cria se ainda nao existe ---------------------
    _sigft_escolher_venv
    if [ ! -x "$SIGFT_VENV_DIR/bin/python" ]; then
        _sigft_criar_venv || return 1
    fi
    SIGFT_PY="$SIGFT_VENV_DIR/bin/python"

    # --- 2. dependencias -----------------------------------------------------
    _sigft_resolver_pip_args
    _sigft_instalar "$SIGFT_RAIZ/requirements.txt" requirements || return 1
    if [ -n "${SIGFT_DEV:-}" ]; then
        _sigft_instalar "$SIGFT_RAIZ/requirements-dev.txt" requirements-dev || return 1
    fi

    # --- 3. navegador do Playwright ------------------------------------------
    # Nunca derruba a abertura: ver _sigft_instalar_navegador.
    _sigft_instalar_navegador
    return 0
}


# =============================================================================
#  Onde fica o venv
# =============================================================================

_sigft_escolher_venv() {
    # Ordem: variavel SIGFT_VENV > .venv do projeto > Application Support >
    # criar novo (na raiz, ou em Application Support se a pasta sincroniza).
    local suporte="$HOME/Library/Application Support/SIG-FT/venv"
    if [ -n "${SIGFT_VENV:-}" ]; then
        SIGFT_VENV_DIR="$SIGFT_VENV"
    elif [ -x "$SIGFT_RAIZ/.venv/bin/python" ]; then
        SIGFT_VENV_DIR="$SIGFT_RAIZ/.venv"
    elif [ -x "$suporte/bin/python" ]; then
        SIGFT_VENV_DIR="$suporte"
    elif _sigft_pasta_sincronizada "$SIGFT_RAIZ"; then
        # O servico tentaria sincronizar as dezenas de milhares de arquivos do
        # venv -- entao ele vai para fora da pasta sincronizada.
        SIGFT_VENV_DIR="$suporte"
        echo "[SIG-FT] A pasta do projeto esta (ou pode estar) sincronizada com a"
        echo "         nuvem (Mesa ou Documentos no iCloud, iCloud Drive, OneDrive,"
        echo "         Dropbox, Google Drive ou Box). Para nao sincronizar milhares de"
        echo "         arquivos, o ambiente virtual vai ficar fora dela: $suporte"
        echo
    else
        SIGFT_VENV_DIR="$SIGFT_RAIZ/.venv"
    fi
}

_sigft_minusculo() {
    printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

_sigft_pasta_sincronizada() {
    # 0 = parece pasta de servico de sincronizacao. Confere o caminho como veio
    # e o fisico (`pwd -P`), porque a pasta pode chegar por um link.
    local dado fisico c
    dado="$(_sigft_minusculo "$1")"
    fisico="$(_sigft_minusculo "$(cd "$1" 2>/dev/null && pwd -P)")"
    for c in "$dado" "$fisico"; do
        case "$c" in
            # iCloud Drive; e Library/CloudStorage e onde o macOS 12.3+ poe
            # OneDrive, Dropbox, Google Drive e Box.
            *"/library/mobile documents/"*|*"/library/cloudstorage/"*) return 0 ;;
            *onedrive*|*/dropbox|*/dropbox/*|*"google drive"*|*googledrive*) return 0 ;;
            */box/*|*"/box sync"*) return 0 ;;
        esac
    done
    _sigft_mesa_ou_documentos "$1"
}

_sigft_mesa_ou_documentos() {
    # ~/Desktop e ~/Documents contam SEMPRE como sincronizadas. O iCloud ("Mesa e
    # Documentos", que o macOS oferece ja na configuracao do Mac) as sincroniza
    # NO LUGAR -- o caminho nao muda -- e nao ha pista confiavel de que esta
    # ligado. Os dois erros nao custam o mesmo: tomar por sincronizada uma pasta
    # que nao e so poe o venv em Application Support, que funciona igual; o
    # contrario poe dezenas de milhares de arquivos do venv no iCloud, que ainda
    # pode tira-los do disco ("Otimizar Armazenamento") e quebrar imports de vez
    # em quando. Sem distinguir maiusculas: o disco do Mac nao distingue.
    local caminho casa pasta
    caminho="$(_sigft_minusculo "$1/")"
    casa="$(_sigft_minusculo "${HOME%/}")"
    for pasta in desktop documents; do
        case "$caminho" in
            "$casa/$pasta/"*) return 0 ;;
        esac
    done
    return 1
}


# =============================================================================
#  O Python e o venv
# =============================================================================

_sigft_python_serve() {
    # 0 = este comando e um Python 3.10 ou mais novo.
    "$1" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)' >/dev/null 2>&1
}

_sigft_achar_python() {
    # O primeiro Python 3.10+ entre os candidatos (os argumentos, ou a lista
    # padrao). Mesma preferencia do .bat: 3.12 primeiro.
    SIGFT_PY_BASE=""
    if [ "$#" -eq 0 ]; then
        set -- python3.12 python3.13 python3.11 python3.10 python3 \
               /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
               /opt/homebrew/bin/python3 /usr/local/bin/python3
    fi
    local candidato caminho
    for candidato in "$@"; do
        caminho="$(command -v "$candidato" 2>/dev/null)" || continue
        [ -n "$caminho" ] || continue
        # O /usr/bin/python3 do macOS e um atalho: sem as "Command Line Tools"
        # ele abre uma janela oferecendo instala-las, em vez de rodar. (E com
        # elas costuma ser o 3.9, que a conferencia abaixo recusa.)
        if [ "$caminho" = "/usr/bin/python3" ] && [ "$(uname -s)" = "Darwin" ] \
                && ! xcode-select -p >/dev/null 2>&1; then
            continue
        fi
        if _sigft_python_serve "$caminho"; then
            SIGFT_PY_BASE="$caminho"
            return 0
        fi
    done
    return 1
}

_sigft_criar_venv() {
    echo "[SIG-FT] Primeira execucao: criando o ambiente virtual em"
    echo "         $SIGFT_VENV_DIR"
    echo "         Isso baixa as dependencias e leva alguns minutos. Nas proximas"
    echo "         vezes o aplicativo abre direto."
    echo
    _sigft_achar_python
    if [ -z "$SIGFT_PY_BASE" ]; then
        echo "[ERRO] Nao achei o Python 3.10 (ou mais novo) neste Mac."
        echo "       Instale o Python 3.12 de https://www.python.org/downloads/macos/"
        echo "       e abra o SIG-FT.command de novo."
        return 1
    fi
    echo "[SIG-FT] Usando o interpretador: $SIGFT_PY_BASE"
    mkdir -p "$(dirname "$SIGFT_VENV_DIR")"
    "$SIGFT_PY_BASE" -m venv "$SIGFT_VENV_DIR"
    if [ ! -x "$SIGFT_VENV_DIR/bin/python" ]; then
        echo
        echo "[ERRO] Nao consegui criar o ambiente virtual em:"
        echo "       $SIGFT_VENV_DIR"
        echo "       Verifique se voce tem permissao de escrita nessa pasta."
        return 1
    fi
    return 0
}


# =============================================================================
#  Dependencias
# =============================================================================

_sigft_resolver_pip_args() {
    # Rede corporativa com inspecao SSL (Zscaler e afins) costuma quebrar o pip.
    # Mesmos argumentos e mesma ordem de prioridade do .bat:
    #    1. variavel de ambiente SIGFT_PIP_ARGS
    #    2. arquivo pip_corporativo.txt na raiz (1a linha que nao e comentario)
    SIGFT_PIP_ARGS_EFETIVO="--isolated --index-url https://pypi.org/simple --trusted-host pypi.org --trusted-host files.pythonhosted.org"
    local linha
    if [ -f "$SIGFT_RAIZ/pip_corporativo.txt" ]; then
        while IFS= read -r linha || [ -n "$linha" ]; do
            linha="${linha%$'\r'}"
            case "$linha" in ''|'#'*) continue ;; esac
            SIGFT_PIP_ARGS_EFETIVO="$linha"
            echo "[SIG-FT] Argumentos de pip vindos de pip_corporativo.txt."
            break
        done < "$SIGFT_RAIZ/pip_corporativo.txt"
    fi
    if [ -n "${SIGFT_PIP_ARGS:-}" ]; then
        SIGFT_PIP_ARGS_EFETIVO="$SIGFT_PIP_ARGS"
    fi
}

_sigft_hash_arquivo() {
    # shasum vem em todo macOS; sha256sum e o do Linux; cksum (POSIX) e o
    # ultimo recurso -- tambem muda quando o arquivo muda.
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    elif command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        cksum "$1" | awk '{print $1 "-" $2}'
    fi
}

_sigft_precisa_instalar() {
    # 0 = precisa instalar: sem carimbo, ou o arquivo mudou desde a ultima
    # instalacao que deu certo (o carimbo guarda o hash dela).
    local atual anterior=""
    atual="$(_sigft_hash_arquivo "$1")"
    if [ -f "$2" ]; then
        read -r anterior < "$2"
    fi
    [ "$atual" != "$anterior" ]
}

_sigft_instalar() {
    # $1 = arquivo de requirements   $2 = nome curto do carimbo
    local arquivo="$1" carimbo="$SIGFT_VENV_DIR/.sigft-$2.stamp" nome
    [ -f "$arquivo" ] || return 0
    _sigft_precisa_instalar "$arquivo" "$carimbo" || return 0
    nome="$(basename "$arquivo")"
    echo
    echo "[SIG-FT] Instalando as dependencias de $nome ..."
    # Atualizar o pip e so uma cortesia: se falhar, segue com o pip do venv --
    # por isso nao ha checagem nesta linha, so na de baixo. Os argumentos vao
    # sem aspas de proposito: sao varios.
    # shellcheck disable=SC2086
    "$SIGFT_PY" -m pip install --upgrade pip $SIGFT_PIP_ARGS_EFETIVO
    # shellcheck disable=SC2086
    if ! "$SIGFT_PY" -m pip install $SIGFT_PIP_ARGS_EFETIVO -r "$arquivo"; then
        echo
        echo "[ERRO] Falha ao instalar as dependencias de $nome."
        _sigft_dica_rede
        if [ -f "$carimbo" ]; then
            # Ja houve uma instalacao que deu certo: o pip baixa tudo antes de
            # instalar, entao o ambiente anterior continua inteiro e o app abre
            # com ele. O carimbo antigo fica, e a proxima
            # abertura tenta de novo. Sem carimbo (nunca instalou), falha.
            echo
            echo "[SIG-FT] SEGUINDO com as dependencias da instalacao anterior."
            echo "         Na proxima abertura o SIG-FT tenta instalar de novo."
            echo
            return 0
        fi
        return 1
    fi
    _sigft_hash_arquivo "$arquivo" > "$carimbo"
    echo "[SIG-FT] Dependencias de $nome instaladas."
    echo
    return 0
}

_sigft_instalar_navegador() {
    # O pacote `playwright` traz so a biblioteca; o navegador (Chromium, ~150
    # MB) e baixado a parte. UMA vez (carimbo no venv), e NUNCA derruba a
    # abertura: em rede corporativa e o download que mais falha, e o
    # aplicativo abre sem ele.
    [ -n "${SIGFT_SEM_NAVEGADOR:-}" ] && return 0
    local carimbo="$SIGFT_VENV_DIR/.sigft-playwright.stamp"
    [ -f "$carimbo" ] && return 0
    "$SIGFT_PY" -c "import playwright" >/dev/null 2>&1 || return 0

    # Ja instalado por fora (outro projeto, ou a mao)? So carimba.
    if "$SIGFT_PY" -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(); b.close(); p.stop()" >/dev/null 2>&1; then
        echo ok > "$carimbo"
        return 0
    fi

    echo
    echo "[SIG-FT] Baixando o navegador Chromium (~150 MB, so na primeira vez)."
    echo "         Ele serve aos recursos que usam navegador (o robo do portal e a"
    echo "         leitura de paginas que so montam com JavaScript). Se falhar, o"
    echo "         aplicativo abre do mesmo jeito."
    echo
    # Rede com inspecao SSL: o download nao passa pelo pip, e sim pelo processo
    # Node do Playwright, que so obedece a NODE_EXTRA_CA_CERTS.
    if [ -z "${NODE_EXTRA_CA_CERTS:-}" ] && [ -n "${SSL_CERT_FILE:-}" ]; then
        export NODE_EXTRA_CA_CERTS="$SSL_CERT_FILE"
    fi
    if ! "$SIGFT_PY" -m playwright install chromium; then
        echo
        echo "[SIG-FT] Nao consegui baixar o navegador -- SEGUINDO ASSIM MESMO."
        echo "         Os recursos que dependem dele ficam indisponiveis; todo o"
        echo "         resto funciona. Para tentar de novo:"
        echo "         \"$SIGFT_PY\" -m playwright install chromium"
        echo
        return 0
    fi
    echo ok > "$carimbo"
    echo "[SIG-FT] Navegador instalado."
    echo
    return 0
}

_sigft_dica_rede() {
    echo
    echo "       Se voce esta em rede corporativa com inspecao SSL (Zscaler), o pip"
    echo "       costuma falhar com \"SSLError\" ou \"CERTIFICATE_VERIFY_FAILED\"."
    echo "       Copie pip_corporativo.txt.exemplo para pip_corporativo.txt e ajuste"
    echo "       os argumentos (indice interno, proxy, --trusted-host) conforme o"
    echo "       que o time de TI indicar. Detalhes no README.md, secao"
    echo "       \"Rede corporativa (Zscaler)\"."
    echo "       No Mac, o PySide6 (a interface) exige o macOS 12 ou mais novo."
}
