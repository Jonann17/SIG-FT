"""O rascunho de e-mail da seção "Sugestões" (2026-10-30): o Outlook pelo COM,
falsificado aqui, e o `mailto:` quando ele não abre."""
from urllib.parse import parse_qs, urlparse

import pytest

from sigft.services import sugestoes


class ItemFalso:
    def __init__(self):
        self.Subject = self.Body = None
        self.To = ""
        self.anexos = []
        self.exibido = None
        self.enviado = False
        item = self

        class Anexos:
            def Add(self, caminho):  # noqa: N802 -- nome do COM
                item.anexos.append(caminho)

        self.Attachments = Anexos()

    def Display(self, modal):  # noqa: N802
        self.exibido = modal

    def Send(self):  # noqa: N802
        self.enviado = True


class ComFalso:
    def __init__(self, recusar=False):
        self.item = ItemFalso()
        self.recusar = recusar
        self.iniciado = self.encerrado = 0
        self.pedidos = []
        com = self

        class Outlook:
            def CreateItem(self, tipo):  # noqa: N802
                com.pedidos.append(tipo)
                return com.item

        class Cliente:
            @staticmethod
            def Dispatch(nome):  # noqa: N802
                if com.recusar:
                    raise OSError("classe nao registrada")
                assert nome == "Outlook.Application"
                return Outlook()

        class PythonCom:
            @staticmethod
            def CoInitialize():  # noqa: N802
                com.iniciado += 1

            @staticmethod
            def CoUninitialize():  # noqa: N802
                com.encerrado += 1

        self.cliente, self.pythoncom = Cliente, PythonCom

    def __call__(self):
        return self.cliente, self.pythoncom


@pytest.fixture
def log(tmp_path):
    arquivo = tmp_path / "logs" / "sigft.log"
    arquivo.parent.mkdir()
    arquivo.write_text("linha do log\n", encoding="utf-8")
    return arquivo


def _abrir(texto="Ideia boa", *, anexar_log=True, com=None, log=None, tmp_path=None, abrir_link=None):
    links = []
    resultado = sugestoes.abrir_rascunho(
        texto, versao="1.3.2", idioma="pt", anexar_log=anexar_log, log_cb=lambda _m: None,
        com=com, abrir_link=abrir_link or (lambda url: links.append(url) or True),
        origem_do_log=log, pasta_temporaria=tmp_path / "tmp" if tmp_path else None)
    return resultado, links


def test_montar_poe_versao_idioma_e_sistema_no_fim_do_corpo():
    r = sugestoes.montar("  Uma ideia.  ", versao="1.3.2", idioma="es", sistema="Windows 11")
    assert r.assunto == "SIG-FT v1.3.2 - sugestão"
    assert r.corpo.startswith("Uma ideia.\n\n")
    assert r.corpo.endswith("SIG-FT v1.3.2 | idioma: es | Windows 11")
    assert r.anexo is None


def test_outlook_abre_rascunho_sem_destinatario_com_a_copia_do_log(log, tmp_path):
    com = ComFalso()
    resultado, links = _abrir(com=com, log=log, tmp_path=tmp_path)
    assert resultado == sugestoes.Resultado(via="outlook")
    assert links == []
    item = com.item
    assert com.pedidos == [sugestoes.OL_MAIL_ITEM]
    assert item.To == "" and not item.enviado and item.exibido is False
    assert item.Subject == "SIG-FT v1.3.2 - sugestão"
    assert item.Body.startswith("Ideia boa")
    # Anexa a CÓPIA, na pasta temporária, e não o log vivo.
    assert len(item.anexos) == 1
    anexo = item.anexos[0]
    assert anexo != str(log) and anexo.startswith(str(tmp_path / "tmp"))
    assert open(anexo, encoding="utf-8").read() == "linha do log\n"
    assert com.iniciado == com.encerrado == 1


def test_sem_a_caixa_marcada_nao_anexa(log, tmp_path):
    com = ComFalso()
    _abrir(com=com, log=log, tmp_path=tmp_path, anexar_log=False)
    assert com.item.anexos == []
    assert not (tmp_path / "tmp").exists()


def test_sem_log_o_rascunho_sai_sem_anexo(tmp_path):
    com = ComFalso()
    resultado, _ = _abrir(com=com, log=tmp_path / "nao_existe.log", tmp_path=tmp_path)
    assert resultado.via == "outlook" and com.item.anexos == []


def test_outlook_recusado_cai_no_mailto_e_devolve_o_log_para_anexar_a_mao(log, tmp_path):
    com = ComFalso(recusar=True)
    resultado, links = _abrir("Ação & teste\nlinha 2", com=com, log=log, tmp_path=tmp_path)
    assert resultado == sugestoes.Resultado(via="mailto", log=log)
    assert com.iniciado == com.encerrado == 1
    (url,) = links
    partes = urlparse(url)
    assert partes.scheme == "mailto" and partes.path == ""
    consulta = parse_qs(partes.query)
    assert consulta["subject"] == ["SIG-FT v1.3.2 - sugestão"]
    assert consulta["body"][0].startswith("Ação & teste\nlinha 2")


def test_sem_pywin32_vai_o_mailto(tmp_path, monkeypatch):
    def sem_com():
        raise sugestoes.SemOutlook("pywin32 indisponivel")

    resultado, links = _abrir(com=sem_com, anexar_log=False, tmp_path=tmp_path)
    assert resultado == sugestoes.Resultado(via="mailto", log=None)
    assert len(links) == 1


def test_mailto_corta_corpo_longo():
    r = sugestoes.montar("x" * 5000, versao="1", idioma="pt", sistema="s")
    url = sugestoes.link_mailto(r)
    corpo = parse_qs(urlparse(url).query)["body"][0]
    assert len(corpo) <= sugestoes.LIMITE_CORPO_MAILTO + len("\n(...)")
    assert corpo.endswith("(...)")


def test_nem_o_mailto_abre_levanta(tmp_path):
    def sem_com():
        raise sugestoes.SemOutlook("x")

    with pytest.raises(RuntimeError):
        _abrir(com=sem_com, anexar_log=False, tmp_path=tmp_path, abrir_link=lambda _u: False)


def test_o_caminho_do_log_e_o_da_pasta_de_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(sugestoes, "pasta_logs", lambda: tmp_path)
    assert sugestoes.caminho_do_log() == tmp_path / "sigft.log"
