r"""
Log de execução em ARQUIVO — a trilha de auditoria de um lote.

Pedido do usuário em 2026-08-18: *"trabalhar com os logs de saída do que está
acontecendo pra eventual auditoria do processo"*.

O que existia até aqui: `core/relatorio_lote.py` (CP 4.4) padroniza o TEXTO
que vai para o console da tela. É bom para acompanhar, e some quando a janela
fecha. Para auditar — "por que esta ficha saiu INCOMPLETO na terça?" — não
serve: a informação já foi embora quando a pergunta aparece.

Este módulo grava a MESMA coisa num arquivo, sem mudar nada do que a tela
mostra. Envolve o `callback_log` que a UI já passa; quem chama não muda.

    log = LogDeExecucao("duplicadas", contexto={"fichas": 3})
    resultados = processar_lote(fichas, callback_log=log.envolver(self.log))
    log.fechar()

Três decisões que valem registro:

1. **Grava linha a linha, com flush.** Um lote de RPA morre no meio por
   motivos que não controlamos (portal fora, sessão expirada, o usuário
   fechando o navegador). Se o arquivo só fosse escrito no fim, justamente a
   execução que mais interessa auditar seria a que não deixa registro.

2. **Nunca levanta.** Falha ao gravar log não pode derrubar um lote que está
   funcionando — seria trocar um problema pequeno por um grande. Erro de
   escrita desliga a gravação e avisa UMA vez no console.

3. **Blocos grandes (HTML) vão só para o ARQUIVO.** É o que permite o modo de
   auditoria despejar a estrutura da tela sem tornar o console ilegível: quem
   acompanha vê o resumo, quem investiga abre o arquivo.
"""
from __future__ import annotations

import datetime as _dt
import os

from sigft import config


# Quanto de um bloco (HTML de uma seção, por exemplo) vai para o arquivo.
# Uma tela de OutSystems inteira passa de megabyte; sem teto, uma execução de
# auditoria produziria um arquivo que ninguém abre. O corte AVISA quanto
# faltou -- corte silencioso faria quem lê concluir que o elemento acaba ali.
LIMITE_DE_BLOCO = 60_000


def _agora_padrao():
    return _dt.datetime.now()


def recortar(texto, limite=LIMITE_DE_BLOCO):
    """Corta no limite, dizendo quanto sobrou."""
    texto = str(texto or "")
    if limite is None or limite <= 0 or len(texto) <= limite:
        return texto
    return texto[:limite] + (
        f"\n… [RECORTADO: faltam {len(texto) - limite} caracteres deste bloco]")


def nome_de_arquivo(modulo, agora):
    """`duplicadas_2026-08-18_14-32-05.log` — ordenável por nome.

    Data ISO na frente e não `18-08-2026` justamente por isso: a ordem
    alfabética da pasta vira ordem cronológica, que é como se procura "o log
    daquele dia".
    """
    seguro = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(modulo or "log"))
    return f"{seguro}_{agora.strftime('%Y-%m-%d_%H-%M-%S')}.log"


class LogDeExecucao:
    """Espelha o log da tela num arquivo, e aceita blocos que só vão ao arquivo."""

    def __init__(self, modulo, *, pasta=None, contexto=None, agora_fn=None,
                 abrir_fn=None):
        self._agora = agora_fn or _agora_padrao
        self.modulo = modulo
        self.pasta = pasta if pasta is not None else config.PASTA_LOGS
        self.caminho = os.path.join(self.pasta, nome_de_arquivo(modulo, self._agora()))
        self._abrir = abrir_fn or open
        self._arquivo = None
        self._desligado = False
        self._avisou_falha = False
        self._falha_pendente = None
        self._console = None
        self._abrir_arquivo(contexto or {})

    # -- ciclo de vida ----------------------------------------------------
    def _abrir_arquivo(self, contexto):
        try:
            if self.pasta:
                os.makedirs(self.pasta, exist_ok=True)
            self._arquivo = self._abrir(self.caminho, "a", encoding="utf-8")
        except Exception as erro:  # noqa: BLE001 -- ver decisão 2 na docstring
            # Guarda o motivo: quem não conseguiu nem ABRIR o arquivo é o caso
            # que mais precisa avisar, e é o que sai por `_avisar_falha_uma_vez`
            # na primeira linha que passar pela tela.
            self._desligado = True
            self._falha_pendente = erro
            return
        inicio = self._agora().strftime("%Y-%m-%d %H:%M:%S")
        self._escrever(f"===== {self.modulo} - início {inicio} =====")
        for chave, valor in contexto.items():
            self._escrever(f"      {chave}: {valor}")

    def fechar(self):
        if self._arquivo is None:
            return
        fim = self._agora().strftime("%Y-%m-%d %H:%M:%S")
        self._escrever(f"===== {self.modulo} - fim {fim} =====")
        try:
            self._arquivo.close()
        except Exception:  # noqa: BLE001
            pass
        self._arquivo = None

    def __enter__(self):
        return self

    def __exit__(self, _tipo, _valor, _tb):
        self.fechar()
        return False

    # -- escrita ----------------------------------------------------------
    def _escrever(self, texto):
        if self._desligado or self._arquivo is None:
            return
        try:
            self._arquivo.write(str(texto) + "\n")
            # `flush` a cada linha: ver decisão 1 na docstring. O custo é
            # irrelevante perto do RPA (que gasta segundos por campo).
            self._arquivo.flush()
        except Exception as erro:  # noqa: BLE001
            self._desligado = True
            # GUARDA o motivo em vez de avisar aqui. A primeira escrita
            # acontece em `_abrir_arquivo`, ANTES de `envolver()` conhecer o
            # console -- avisar direto perderia justamente o caso pior: um log
            # que morre na abertura e deixa o usuário achando que a auditoria
            # está ligada. O aviso sai na primeira linha que passar pela tela.
            if self._falha_pendente is None:
                self._falha_pendente = erro

    def envolver(self, callback_log=None):
        """Devolve um callback que escreve no arquivo E repassa para a tela.

        Devolver um callback (em vez de exigir que o serviço conheça esta
        classe) é o que mantém os serviços ignorantes de onde o log vai parar
        -- o mesmo princípio do `core/callbacks.py`.
        """
        self._console = callback_log

        def _log(mensagem):
            carimbo = self._agora().strftime("%H:%M:%S")
            self._escrever(f"[{carimbo}] {mensagem}")
            self._avisar_falha_uma_vez()
            if callback_log:
                callback_log(mensagem)

        return _log

    def _avisar_falha_uma_vez(self):
        """Conta ao usuário, UMA vez, que a gravação parou.

        Repetir a cada linha viraria ruído e esconderia o log de verdade; não
        contar deixaria a pessoa auditando um arquivo que não existe.
        """
        if self._falha_pendente is None or self._avisou_falha:
            return
        self._avisou_falha = True
        motivo = self._falha_pendente
        if self._console:
            self._console(f"[!] Parei de gravar o log de auditoria: {motivo}")

    def bloco(self, titulo, texto, limite=LIMITE_DE_BLOCO):
        """Grava um bloco grande SÓ no arquivo (ver decisão 3).

        É por aqui que o modo de auditoria despeja o HTML de uma seção: o
        console continua legível e o arquivo guarda a estrutura real da tela
        -- que é exatamente o que falta para mapear uma seção nova sem o
        usuário copiar caixa por caixa no "inspecionar elemento".
        """
        self._escrever(f"----- {titulo} " + "-" * max(0, 60 - len(str(titulo))))
        self._escrever(recortar(texto, limite))
        self._escrever("-" * 66)
