r"""
`scripts/capturar_portal.py` — a captura que substitui o ping-pong de log.

Por que a ferramenta existe, e por que ela é testada: mapear o portal pelo log
de execução do robô não estava funcionando. O log tem teto de 20 000 caracteres
(senão o arquivo fica ilegível para quem o manda), fotografa só a seção que o
robô conseguiu abrir, e nunca vê a tela que o robô ainda NÃO sabe abrir -- que
é exatamente a que falta mapear. Uma cópia de ficha levou uma semana nesse
laço.

A captura inverte a direção: o usuário navega, o script anota. E anota duas
coisas, não uma:

  - o HTML COMPLETO da página, sem corte e sem escopo escolhido por mim;
  - o RASTRO DOS CLIQUES, que liga a ação ("marquei Horizontal") ao campo
    (`RadioButton7-input`). É esse casamento que nenhum dump estático entrega,
    e é onde eu vinha errando ao deduzir o mapa.

Os testes cobrem o que roda em Python. O espião é JavaScript e só existe dentro
do navegador; dele se testa o CONTRATO -- as três estratégias de rótulo e o
`capture: true` --, porque cada uma delas foi posta para resolver um jeito
específico de o OutSystems desenhar o campo, e perder uma faria o rastro voltar
sem o rótulo, calado.
"""
import importlib.util
import json
import pathlib

import pytest

# `scripts/` não é pacote e não está no `sys.path` da suíte. Carregar pelo
# caminho mantém assim: o script é uma FERRAMENTA de linha de comando, não uma
# dependência do aplicativo, e transformá-lo em módulo importável convidaria o
# código de produção a chamá-lo.
_CAMINHO = (pathlib.Path(__file__).resolve().parent.parent
            / "scripts" / "capturar_portal.py")
_spec = importlib.util.spec_from_file_location("capturar_portal", _CAMINHO)
capturar_portal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(capturar_portal)


# ===========================================================================
# 1. O nome do arquivo
# ===========================================================================

def test_nome_vira_arquivo_previsivel():
    assert capturar_portal._limpar_nome("Condições Armazenamento") == \
        "condicoes-armazenamento" or \
        capturar_portal._limpar_nome("Condições Armazenamento") == \
        "condições-armazenamento"


def test_nome_perde_o_que_quebraria_o_caminho():
    """Barra e dois-pontos no nome criariam pasta ou arquivo inválido no
    Windows -- e a pessoa está digitando depressa, entre uma tela e outra."""
    sujo = capturar_portal._limpar_nome("Condições/Transporte: 2ª aba")
    assert "/" not in sujo and ":" not in sujo


def test_nome_vazio_tem_padrao():
    """Só Enter é o caso comum: a pessoa está capturando rápido e não quer
    nomear cada tela."""
    assert capturar_portal._limpar_nome("") == "tela"
    assert capturar_portal._limpar_nome("   ") == "tela"


def test_espaco_repetido_nao_vira_hifen_duplo():
    assert "--" not in capturar_portal._limpar_nome("condicoes    armazenamento")


# ===========================================================================
# 2. O resumo — conferir a captura sem abrir o HTML
# ===========================================================================
# HTML REAL do portal (ficha 4500063671.1277, seção Condições em
# visualização). Copiado do dump, não escrito de memória: é o mesmo motivo de
# `test_duplicadas_xpath_real` existir -- markup inventado testa a minha ideia
# do portal, não o portal.

HTML_REAL = '''
<div id="b12-b20-b1-b20-Content">
  <span class="text-primary font-size-base">Nocivo</span>
  <div data-container="" class="custom">
    <span><input data-checkbox="" class="radio-button" disabled="" type="checkbox"
                 checked="" id="b12-b20-b1-Checkbox1"></span>
    <label data-label="" class="margin-left-s">Não contém agentes nocivos</label>
  </div>
  <div data-container="" class="custom">
    <span><input data-checkbox="" class="radio-button" disabled="" type="checkbox"
                 id="b12-b20-b1-Checkbox2"></span>
    <label data-label="" class="margin-left-s">Sem necessidade</label>
  </div>
  <input class="form-control" required="" type="text" maxlength="100"
         value="RTC-45" id="b10-b11-b4-Input_TextVar">
</div>
'''


@pytest.fixture
def captura(tmp_path):
    caminho = tmp_path / "001-condicoes.html"
    caminho.write_text(HTML_REAL, encoding="utf-8")
    return caminho


def test_resumo_lista_os_campos_com_o_rotulo(captura, capsys):
    """O rótulo vem do `<label>` SEGUINTE, não do `for=` -- o OutSystems quase
    nunca usa `for`, e um resumo sem rótulo não serviria para conferir nada."""
    capturar_portal.resumir(str(captura))
    saida = capsys.readouterr().out

    assert "b12-b20-b1-Checkbox1" in saida
    assert "Não contém agentes nocivos" in saida
    assert "Sem necessidade" in saida


def test_resumo_marca_o_que_esta_MARCADO(captura, capsys):
    """Qual opção do radio está escolhida é a informação que fecha o mapa. Sem
    ela o resumo diria que os campos existem, que é o que eu já sabia."""
    capturar_portal.resumir(str(captura))
    linhas = [l for l in capsys.readouterr().out.splitlines()
              if "Checkbox" in l]

    marcada = [l for l in linhas if "MARCADO" in l]
    assert len(marcada) == 1
    assert "Checkbox1" in marcada[0]


def test_resumo_marca_o_campo_OBRIGATORIO(captura, capsys):
    """É a pergunta que decide se CONDIÇÕES pode fechar sem os campos em
    espanhol -- e ela se responde olhando o `required`, não tentando salvar."""
    capturar_portal.resumir(str(captura))
    saida = capsys.readouterr().out
    assert "OBRIGATÓRIO" in saida


def test_resumo_conta_os_campos(captura, capsys):
    capturar_portal.resumir(str(captura))
    assert "3 campo(s) de formulário" in capsys.readouterr().out


def test_resumo_mostra_o_rastro_de_cliques(tmp_path, capsys):
    """O rastro é a metade que justifica a ferramenta: ele liga o clique da
    pessoa ao id do campo."""
    html = tmp_path / "002-armazenamento.html"
    html.write_text(HTML_REAL, encoding="utf-8")
    (tmp_path / "002-armazenamento.cliques.json").write_text(json.dumps([
        {"quando": "10:31:02", "tag": "INPUT", "id": "b10-RadioButton7-input",
         "classe": "", "tipo": "radio", "valor": "", "marcado": True,
         "texto": "", "rotulo": "Horizontal", "secao": "Armazenamento"},
    ]), encoding="utf-8")

    capturar_portal.resumir(str(html))
    saida = capsys.readouterr().out

    assert "b10-RadioButton7-input" in saida
    assert "Horizontal" in saida


def test_resumo_sem_arquivo_de_cliques_nao_estoura(captura, capsys):
    """Tela que a pessoa só olhou, sem clicar em nada, é caso normal."""
    capturar_portal.resumir(str(captura))
    assert "Rastro de cliques" not in capsys.readouterr().out


def test_texto_visivel_tira_as_etiquetas():
    assert capturar_portal._texto_visivel(
        "<span>  Peso <b>líquido</b>  </span>") == "Peso líquido"


# ===========================================================================
# 3. O contrato do espião (JavaScript)
# ===========================================================================
# Ele roda no navegador e não dá para exercitar aqui. O que se protege é a
# RAZÃO de cada pedaço: perder qualquer um faz o rastro voltar sem o dado, e
# sem erro nenhum -- a falha silenciosa que este projeto inteiro combate.

def test_espiao_escuta_na_fase_de_CAPTURA():
    """Os widgets do OutSystems cancelam a propagação do clique. Um listener
    no bubbling perderia justamente os cliques que mais interessam -- os dos
    radios e checkboxes dentro dos widgets."""
    corpo = capturar_portal.ESPIAO.split("addEventListener")[1]
    assert "}, true);" in corpo, (
        "o terceiro argumento de addEventListener tem de ser `true` "
        "(fase de captura)")


def test_espiao_tem_as_TRES_estrategias_de_rotulo():
    """`label[for]`, `<label>` ancestral e o `<label>` irmão. Cada uma existe
    para um jeito de o portal desenhar o campo; o irmão é o caso dos radios,
    que é o que falta mapear."""
    js = capturar_portal.ESPIAO
    assert "label[for=" in js
    assert "closest('label')" in js
    assert "querySelector('label')" in js


def test_espiao_anota_se_o_campo_ficou_MARCADO():
    """Sem `checked` o rastro diria que a pessoa clicou, não o que ela
    escolheu."""
    assert "checked" in capturar_portal.ESPIAO


def test_espiao_e_idempotente():
    """`add_init_script` e o `evaluate` da página já aberta rodam o mesmo
    código; sem a guarda, a segunda injeção registraria um segundo listener e
    todo clique apareceria em duplicata no rastro."""
    assert "if (window.__sigftEspiao) return;" in capturar_portal.ESPIAO
