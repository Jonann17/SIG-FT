r"""Motor de tradução LOCAL PT -> ES: roda na CPU desta máquina, sem rede.

O modelo é o OPUS-MT `tc-big-itc-itc` (Helsinki-NLP, licença CC-BY 4.0),
convertido para CTranslate2 em int8 por `tools/preparar_tradutor.py`. Ele vem
DENTRO do instalador (`modelos\tradutor_pt_es`), então a tradução funciona sem
chave, sem internet e sem VPN, e nenhuma resposta de ficha sai do computador.

Por que este modelo (experimento de 2026-09-25, spec
`docs/superpowers/specs/2026-09-25-tradutor-local-design.md`): foi o único
dos testados que traduziu o texto técnico sem deixar palavra em português
(o Argos pt->es deixou "Porca sextavada", "Graxa"...), e traduz 88 respostas
em ~2 s num Windows de 2 núcleos. O vocabulário da casa que ele erra fica com
o glossário (`services/traducao_respostas.py`).

Só `ctranslate2` e `sentencepiece` em tempo de execução -- nada de `torch` ou
`transformers`, que só a conversão precisa. E os dois só são importados na
primeira tradução: o resto do app não paga o custo.
"""
from __future__ import annotations

import importlib
import os
import sys
import threading
from pathlib import Path

NOME_DA_PASTA = "tradutor_pt_es"
VARIAVEL_AMBIENTE = "SIGFT_MODELO_TRADUTOR"

# O modelo é MULTILÍNGUE (línguas itálicas): o idioma de destino vai como
# primeiro token da frase de origem. Sem ele, a saída sai em qualquer uma.
PREFIXO_ES = ">>spa<<"
FIM = "</s>"

# Beam 4: no experimento o beam 1 era 2x mais rápido e errava mais
# ("NUEZ HEXAGONAL", "Portabrochas"). O lote inteiro de uma ficha leva menos de
# um segundo com 4 -- a velocidade que falta está no Excel, não aqui.
BEAM = 4
LOTE_MAXIMO = 32

# O que não pode faltar na pasta. O vocabulário (`shared_vocabulary.*`) muda de
# extensão conforme a versão do CTranslate2 e fica a cargo dele reclamar.
ARQUIVOS_DO_MODELO = ("model.bin", "config.json", "source.spm", "target.spm")

_RAIZ_DO_PROJETO = Path(__file__).resolve().parents[2]


class TradutorIndisponivel(RuntimeError):
    """O tradutor local não tem como rodar nesta máquina."""


class ModeloAusente(TradutorIndisponivel):
    """A pasta do modelo não está em nenhum dos lugares conhecidos."""


def _pastas_padrao() -> list[Path]:
    """Onde o modelo pode estar, na ordem de preferência."""
    pastas = []
    base_do_pacote = getattr(sys, "_MEIPASS", None)
    if base_do_pacote:
        pastas.append(Path(base_do_pacote) / "modelos" / NOME_DA_PASTA)
    # Rodando pelo código-fonte: onde `tools/preparar_tradutor.py` grava.
    pastas.append(_RAIZ_DO_PROJETO / "recursos" / NOME_DA_PASTA)
    try:
        from sigft.core import dados_usuario

        pastas.append(Path(dados_usuario.pasta_dados()) / "modelos" / NOME_DA_PASTA)
    except Exception:  # noqa: BLE001 -- sem pasta de dados, sobram as outras
        pass
    return pastas


def modelo_completo(pasta) -> bool:
    pasta = Path(pasta)
    return pasta.is_dir() and all((pasta / nome).is_file() for nome in ARQUIVOS_DO_MODELO)


def localizar_modelo() -> Path:
    """A pasta do modelo. Levanta `ModeloAusente` dizendo onde procurou."""
    candidatas = []
    escolhida = os.environ.get(VARIAVEL_AMBIENTE, "").strip()
    if escolhida:
        candidatas.append(Path(escolhida))
    candidatas += _pastas_padrao()
    for pasta in candidatas:
        if modelo_completo(pasta):
            return pasta
    lugares = "\n".join(f"  - {p}" for p in candidatas)
    raise ModeloAusente(
        "Nao achei o modelo do tradutor local. Procurei em:\n"
        f"{lugares}\n"
        "No programa instalado ele vem junto: instale a versao mais nova. "
        "Rodando pelo codigo-fonte: rode `python tools/preparar_tradutor.py`, ou "
        "copie a pasta `_internal\\modelos\\tradutor_pt_es` de uma instalacao "
        "para `Documentos\\SIG-FT\\modelos\\`."
    )


class TradutorLocal:
    """`TradutorLocal()(textos) -> traducoes`, na mesma ordem.

    Carrega o modelo na primeira chamada (0,2 s no experimento) e o mantém
    para as seguintes. `ctranslate2`/`sentencepiece` podem ser injetados: é
    como os testes rodam sem o pacote nem o modelo.
    """

    def __init__(self, pasta=None, *, ctranslate2=None, sentencepiece=None, threads=0):
        self._pasta = pasta
        self._ct2 = ctranslate2
        self._spm = sentencepiece
        self._threads = threads
        self._modelo = None
        self._trava = threading.Lock()

    def _importar(self, nome, injetado):
        if injetado is not None:
            return injetado
        try:
            return importlib.import_module(nome)
        except ImportError as erro:
            raise TradutorIndisponivel(
                f"O pacote `{nome}` do tradutor local nao esta instalado ({erro}). "
                "Rode `pip install -r requirements.txt`."
            ) from erro

    def _carregar(self):
        with self._trava:
            if self._modelo is None:
                pasta = Path(self._pasta) if self._pasta else localizar_modelo()
                ct2 = self._importar("ctranslate2", self._ct2)
                spm = self._importar("sentencepiece", self._spm)
                tradutor = ct2.Translator(str(pasta), device="cpu",
                                          intra_threads=self._threads)
                origem = spm.SentencePieceProcessor(model_file=str(pasta / "source.spm"))
                destino = spm.SentencePieceProcessor(model_file=str(pasta / "target.spm"))
                self._modelo = (tradutor, origem, destino)
            return self._modelo

    def traduzir(self, textos) -> list[str]:
        textos = [str(t) for t in textos]
        if not textos:
            return []
        tradutor, origem, destino = self._carregar()
        lote = [[PREFIXO_ES, *origem.encode(texto, out_type=str), FIM] for texto in textos]
        # `replace_unknowns`: o que o vocabulário não conhece (o `Ø`, medido)
        # é copiado da origem em vez de virar `⁇`.
        resultados = tradutor.translate_batch(
            lote, beam_size=BEAM, max_batch_size=LOTE_MAXIMO, replace_unknowns=True)
        return [destino.decode(r.hypotheses[0]).strip() for r in resultados]

    __call__ = traduzir


_instancia: TradutorLocal | None = None
_trava_da_instancia = threading.Lock()


def obter() -> TradutorLocal:
    """O tradutor do processo: o modelo carrega uma vez por sessão do app."""
    global _instancia
    with _trava_da_instancia:
        if _instancia is None:
            _instancia = TradutorLocal()
        return _instancia
