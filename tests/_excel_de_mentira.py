"""O Windows com planilhas abertas no Excel, para os testes de gravação.

No Windows, o Excel segura a planilha aberta: abrir para ESCRITA, renomear ou
apagar levanta `PermissionError`; LER funciona (o `pd.read_excel` e o
`load_workbook` de um arquivo aberto no Excel dão certo). E ele cria, ao lado,
o `~$nome.xlsx` com o nome de quem abriu.

No Linux da suíte (e como root, no contêiner) nada disso existe. Este dublê
troca, só durante o teste, os pontos por onde TODO código grava --
`open`/`io.open` (o editor cirúrgico, o `zipfile` do openpyxl, a conferência
de antes), `os.rename`, `os.unlink`/`os.remove` -- e recusa a escrita nos
arquivos "abertos", como o Windows faria. O resto passa direto.

Uso:
    excel = ExcelDeMentira(monkeypatch)
    excel.abrir(caminho, usuario="Luan")   # a pessoa abre no Excel
    ...
    excel.fechar(caminho)                  # e fecha

`TelaDeMentira` é o outro lado: o `callback_travados` da tela, que anota cada
pergunta e responde pelo roteiro do teste. `resumo_do_log` acha o bloco "Não
gravados nesta rodada" no log.
"""
from __future__ import annotations

import builtins
import io
import os


class ExcelDeMentira:
    def __init__(self, monkeypatch):
        self.abertos: set[str] = set()
        self._open = builtins.open
        self._rename = os.rename
        self._unlink = os.unlink
        monkeypatch.setattr(builtins, "open", self._abrir_arquivo)
        monkeypatch.setattr(io, "open", self._abrir_arquivo)
        monkeypatch.setattr(os, "rename", self._renomear)
        monkeypatch.setattr(os, "unlink", self._apagar)
        monkeypatch.setattr(os, "remove", self._apagar)

    @staticmethod
    def _chave(caminho) -> str:
        return os.path.normcase(os.path.abspath(os.fspath(caminho)))

    @staticmethod
    def _dono(caminho) -> str:
        caminho = os.fspath(caminho)
        return os.path.join(os.path.dirname(caminho), "~$" + os.path.basename(caminho))

    # -- o que a pessoa faz ----------------------------------------------------
    def abrir(self, caminho, usuario: str | None = "Luan") -> None:
        """A pessoa abre a planilha no Excel (com o `~$` de quem abriu)."""
        self.abertos.add(self._chave(caminho))
        if usuario is not None:
            ansi = usuario.encode("cp1252")
            dados = bytes([len(ansi)]) + ansi.ljust(53, b" ")
            dados += len(usuario).to_bytes(2, "little") + usuario.encode("utf-16-le")
            with self._open(self._dono(caminho), "wb") as fh:
                fh.write(dados.ljust(165, b" "))

    def fechar(self, caminho) -> None:
        """A pessoa fecha a planilha (o Excel apaga o `~$`)."""
        self.abertos.discard(self._chave(caminho))
        if os.path.exists(self._dono(caminho)):
            self._unlink(self._dono(caminho))

    def aberto(self, caminho) -> bool:
        return self._chave(caminho) in self.abertos

    # -- o que o Windows recusa ----------------------------------------------
    def _travado(self, caminho) -> bool:
        return isinstance(caminho, (str, bytes, os.PathLike)) and self._chave(caminho) in self.abertos

    def _abrir_arquivo(self, file, mode="r", *args, **kwargs):
        if any(c in mode for c in "wax+") and self._travado(file):
            raise PermissionError(13, "Permission denied", os.fspath(file))
        return self._open(file, mode, *args, **kwargs)

    def _renomear(self, origem, destino, *args, **kwargs):
        if self._travado(origem):
            raise PermissionError(13, "The process cannot access the file because it is being used "
                                      "by another process", os.fspath(origem))
        return self._rename(origem, destino, *args, **kwargs)

    def _apagar(self, caminho, *args, **kwargs):
        if self._travado(caminho):
            raise PermissionError(13, "The process cannot access the file because it is being used "
                                      "by another process", os.fspath(caminho))
        return self._unlink(caminho, *args, **kwargs)


class TelaDeMentira:
    """A tela: anota cada pergunta e responde pelo roteiro. `ao_perguntar(momento,
    falhas)` é o que a pessoa faz antes de clicar (fechar o arquivo, salvar
    algo)."""

    def __init__(self, *respostas, ao_perguntar=None):
        self.perguntas = []
        self.respostas = list(respostas)
        self.ao_perguntar = ao_perguntar

    def __call__(self, falhas, momento):
        self.perguntas.append((momento, [(f.nome, f.diagnostico.motivo) for f in falhas]))
        if self.ao_perguntar is not None:
            self.ao_perguntar(momento, falhas)
        return self.respostas.pop(0)


def resumo_do_log(log):
    """As linhas do bloco "Não gravados nesta rodada" (vazio se não houver)."""
    from sigft.core.excel import travas

    for i, linha in enumerate(log):
        if travas.TITULO_RESUMO in linha:
            fim = i + 1
            while fim < len(log) and log[fim].startswith("   - "):
                fim += 1
            return log[i:fim]
    return []


def depois_da_conferencia(linha):
    """A linha que diz que a conferência de antes passou: a pessoa abrir o
    arquivo DEPOIS dela é a trava que aparece durante o processo."""
    return "antes de gravar: nenhum travado" in linha
