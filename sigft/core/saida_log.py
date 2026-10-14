"""Sem console, o `print` vai para `Documentos\\SIG-FT\\logs\\sigft.log`.

Esta é a cópia COMPARTILHADA de `_desviar_saida_para_arquivo` de
`sigft/app/main.py`, para a interface Qt (`sigft/app_qt/main.py`) fazer o mesmo
sem importar a interface CustomTkinter. A cópia de `sigft/app/main.py` continua
onde está porque `tests/test_distribuicao_box.py` a trava lá; as duas se juntam
no corte (Etapa 6), quando `sigft/app/` sair.

Só biblioteca padrão: nenhum import de interface aqui.
"""
from __future__ import annotations

import os
import sys
import time


def desviar_saida_para_arquivo() -> None:
    """Sem console, manda `print` e traceback para `logs/sigft.log`.

    Só age no executável compilado (`sys.frozen`) e só quando o PyInstaller
    de fato não deu console (`sys.stdout is None`). Rodando do `.py` nada
    muda -- o terminal continua sendo o lugar certo.

    Nunca levanta: se não der para abrir o arquivo (pasta somente-leitura,
    disco cheio), o app tem que subir assim mesmo. Perder o log é ruim;
    não abrir é pior.
    """
    if not getattr(sys, "frozen", False):
        return
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        # `Documentos\SIG-FT\logs\`, e não ao lado do `.exe`: sob `Program
        # Files` a pasta do programa é somente-leitura, e este é o pior lugar
        # para falhar em silêncio -- é justamente este log que explicaria
        # qualquer outra falha da abertura.
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
    except Exception:  # noqa: BLE001 -- perder o log é ruim, não abrir é pior
        pass
