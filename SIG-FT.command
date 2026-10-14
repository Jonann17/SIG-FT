#!/bin/bash
# =============================================================================
#  SIG-FT -- clique duas vezes neste arquivo, no Finder, para abrir o
#  aplicativo no Mac. (E o SIG-FT.bat do Windows.)
#
#  Na PRIMEIRA vez o macOS barra o clique duplo num arquivo baixado da
#  internet: clique com o botao direito -> Abrir -> Abrir.
#
#  Na primeira execucao ele cria o ambiente virtual e instala as dependencias
#  (leva alguns minutos). Nas vezes seguintes ele so abre o aplicativo.
#
#  Nao precisa instalar nada antes, so o Python 3 (3.10 ou mais novo):
#  https://www.python.org/downloads/macos/
#
#  Rede corporativa com Zscaler: veja o README.md, secao
#  "Rede corporativa (Zscaler)".
# =============================================================================

RAIZ="$(cd "$(dirname "$0")" && pwd)"

_sigft_encerrar_com_erro() {
    echo
    echo "[SIG-FT] Encerrado com erro. As mensagens acima dizem o motivo."
    echo "         Para abrir a interface antiga: \"$RAIZ/SIG-FT.command\" --ctk"
    echo
    # O `pause` do .bat: sem isto, o Terminal pode fechar a janela (ou
    # esconder a mensagem) antes de a pessoa conseguir ler.
    read -r -p "Pressione Enter para fechar esta janela." _
    exit 1
}

# O titulo da janela do Terminal (o `title SIG-FT` do .bat).
[ -t 1 ] && printf '\033]0;SIG-FT\007'

# shellcheck source=scripts/_bootstrap_venv.sh
. "$RAIZ/scripts/_bootstrap_venv.sh" || _sigft_encerrar_com_erro
SIGFT_RAIZ="$RAIZ"
sigft_bootstrap || _sigft_encerrar_com_erro

# Roda a partir da raiz do projeto: .env, assets/ e as planilhas de trabalho
# sao resolvidos por caminho relativo.
cd "$RAIZ" || _sigft_encerrar_com_erro

echo "[SIG-FT] Abrindo o aplicativo. Pode fechar esta janela do Terminal so DEPOIS"
echo "         de fechar o SIG-FT -- e nela que aparecem os erros."
echo
# Os argumentos seguem adiante: no Terminal, `./SIG-FT.command --ctk` abre a
# interface antiga.
"$SIGFT_PY" "$RAIZ/frontend.py" "$@" || _sigft_encerrar_com_erro
exit 0
