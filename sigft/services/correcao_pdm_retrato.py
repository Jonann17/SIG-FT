r"""O retrato das características técnicas de uma ficha, em disco.

POR QUE ELE GRAVA ANTES DE QUALQUER COISA
------------------------------------------------------------------------
Trocar o PDM de uma ficha faz o portal apagar TODAS as características — é o
que o próprio modal avisa ("Todos os dados de Características Técnicas serão
removidos"). Depois do CONFIRMAR, **o dado não existe mais em lugar nenhum**:
nem no portal, nem na planilha, nem na ficha.

Um retrato que estivesse só na memória morreria junto com o processo. Se o
robô cair entre a troca e a reposição — queda de rede, sessão expirada, o
usuário fechando a janela — a ficha fica vazia e o original se perdeu.

Por isso duas regras deste módulo não são zelo:

1. o retrato vai para o **disco** antes da troca;
2. `gravar` **levanta** em vez de engolir o erro. Ao contrário de
   `dados_usuario.pasta_logs()`, que pode falhar quieta, aqui uma gravação
   que falhou em silêncio seria autorização para destruir o original.

Ele também habilita o modo **"só repor"**: se algo der errado depois da troca,
a reposição roda de novo a partir do arquivo, sem refazer nada no portal.

Plano completo em `docs/refatoracao/CORRECAO_PDM.md` (etapa E2).
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from sigft.core import dados_usuario
from sigft.core.rpa.caracteristicas import Caracteristica


# Versão do FORMATO do arquivo, não do módulo. É o que permite ler um retrato
# gravado hoje daqui a seis meses sem adivinhar a estrutura -- e um retrato
# velho é justamente o que se vai abrir quando algo der errado há tempos.
VERSAO_DO_FORMATO = 1

NOME_DA_PASTA = "retratos_pdm"

# Windows recusa estes no nome de arquivo. Um PMIB estranho não pode impedir a
# gravação: é ela que autoriza a troca.
_RE_PROIBIDOS = re.compile(r'[\\/:*?"<>|]+')


@dataclass(frozen=True)
class Retrato:
    """O que a ficha tinha ANTES da troca."""

    pmib: str
    pdm_antigo: str   # o texto completo do portal, COM a revisão
    pdm_novo: str     # o PDM pretendido
    caracteristicas: tuple[Caracteristica, ...] = ()
    momento: str = ""


def pasta_retratos() -> Path:
    """`Documentos\\SIG-FT\\retratos_pdm\\`. Cria se faltar.

    Dentro da pasta de dados do usuário, e nunca no diretório de trabalho:
    sob `Program Files` o app não escreve, e foi isso que derrubou a primeira
    instalação real (2026-09-21, ver `dados_usuario.resolver_config`).
    """
    destino = dados_usuario.pasta_dados() / NOME_DA_PASTA
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def _caminho_livre(pmib: str) -> Path:
    """`<PMIB>_<AAAAMMDD-HHMMSS-mmm>.json`, num caminho que AINDA NÃO EXISTE.

    Duas tentativas seguidas da mesma ficha não podem se sobrescrever: se a
    primeira falhou no meio, é justamente o retrato dela que guarda o
    original.

    ⚠️ O carimbo de tempo sozinho NÃO garante isso, e o teste provou: duas
    gravações seguidas caem no mesmo milissegundo com facilidade. Confiar no
    relógio para unicidade é confiar na velocidade da máquina.

    ⚠️ E o contador é SEMPRE escrito, com dois dígitos, em vez de aparecer só
    a partir do segundo arquivo. Isso também saiu de um teste: com o sufixo
    opcional, `..-123.json` e `..-123-2.json` ordenam ao contrário do
    esperado, porque `-` (0x2D) vem antes de `.` (0x2E) — o PRIMEIRO gravado
    ficava na frente do segundo. E a ordem é justamente o que o modo "só
    repor" usa para achar a tentativa que falhou. Com `-01`, `-02` a
    comparação é uniforme, e o padding mantém `-10` depois de `-02`.
    """
    limpo = _RE_PROIBIDOS.sub("-", str(pmib or "sem-pmib")).strip() or "sem-pmib"
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
    pasta = pasta_retratos()

    sufixo = 1
    caminho = pasta / f"{limpo}_{carimbo}-{sufixo:02d}.json"
    while caminho.exists():
        sufixo += 1
        caminho = pasta / f"{limpo}_{carimbo}-{sufixo:02d}.json"
    return caminho


def gravar(retrato: Retrato) -> Path:
    """Grava o retrato e devolve o caminho. **Levanta** em qualquer falha.

    Não engolir o erro é o ponto: quem chama só pode trocar o PDM depois que
    isto voltar sem exceção.
    """
    momento = retrato.momento or datetime.now().isoformat(timespec="seconds")
    conteudo = {
        "versao": VERSAO_DO_FORMATO,
        "momento": momento,
        "pmib": retrato.pmib,
        "pdm_antigo": retrato.pdm_antigo,
        "pdm_novo": retrato.pdm_novo,
        "caracteristicas": [asdict(c) for c in retrato.caracteristicas],
    }
    caminho = _caminho_livre(retrato.pmib)
    # `ensure_ascii=False`: o arquivo também é para PESSOA ler quando algo
    # der errado, e `ç` no lugar de `ç` esconde justamente o valor que
    # se foi conferir.
    caminho.write_text(
        json.dumps(conteudo, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho


def ler(caminho) -> Retrato:
    """Lê um retrato gravado. Levanta `OSError` se o arquivo não abre e
    `ValueError` (com o caminho na mensagem) se o conteúdo não presta."""
    caminho = Path(caminho)
    texto = caminho.read_text(encoding="utf-8")
    try:
        conteudo = json.loads(texto)
    except json.JSONDecodeError as erro:
        raise ValueError(
            f"O retrato {caminho} nao e um JSON valido: {erro}") from erro

    try:
        return Retrato(
            pmib=conteudo["pmib"],
            pdm_antigo=conteudo.get("pdm_antigo", ""),
            pdm_novo=conteudo.get("pdm_novo", ""),
            momento=conteudo.get("momento", ""),
            caracteristicas=tuple(
                Caracteristica(**c) for c in conteudo.get("caracteristicas", [])
            ),
        )
    except (KeyError, TypeError) as erro:
        raise ValueError(
            f"O retrato {caminho} nao tem a estrutura esperada: {erro}") from erro


def listar(pmib: str) -> list[Path]:
    """Os retratos de uma ficha, **do mais novo para o mais velho**.

    A ordem importa para o modo "só repor": quem vai repor quer o ÚLTIMO, que
    é o da tentativa que falhou.

    Ordena pelo NOME e não pela data do sistema de arquivos: o carimbo está no
    nome, é ordenável como texto, e não muda se o arquivo for copiado para
    outra máquina.
    """
    limpo = _RE_PROIBIDOS.sub("-", str(pmib or "")).strip()
    if not limpo:
        return []
    return sorted(pasta_retratos().glob(f"{limpo}_*.json"), reverse=True)
