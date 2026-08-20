r"""
A ficha ORIGINAL nunca é aberta em edição — decisão do usuário (2026-08-20).

    "Por que você colocou para o robô tentar pegar condições do modo em
     edição? TUDO é para pegar do modo de visualização. Somente a ficha ALVO é
     para entrar no modo de edição."

⚠️ A DECISÃO ERRADA FOI MINHA, e vale registrar como foi tomada. A cópia das
Condições é POR XPATH (`Input_PackingLength` da original -> `Input_
PackingLength` da alvo), e esses campos só existem como `input` no modo de
EDIÇÃO. Em vez de perguntar, eu abri a original para editar e documentei o
trade-off no código -- "nada é salvo nela, só se lê". Documentar não é
combinar: a escolha era do usuário e eu não a levei a ele.

E o custo apareceu na primeira ficha do primeiro lote:

    Ficha 4500063671.1263 encontrada na aba 'Em Análise ITAIPU'.
    [Aviso] Não consegui abrir 4500063671.1263 em edição (TempoEsgotado).

20 segundos perdidos por ficha, e a original em qualquer status que não seja
"Em Elaboração" simplesmente não tem lápis.

O que este arquivo tranca é a regra, não a implementação da leitura: NENHUM
caminho que toca a ficha original pode pedir edição.
"""
import ast
import inspect

from sigft.services import duplicadas_robo as robo


def test_nenhuma_leitura_da_original_abre_edicao():
    """Teste de AST porque o risco não é o código de hoje -- é alguém, daqui a
    dois meses, precisar de um campo que só existe na edição e "só abrir
    rapidinho"."""
    fonte = ast.parse(inspect.cleandoc(
        "".join(inspect.getsource(robo).splitlines(keepends=True))))

    leitores_da_original = {
        "ler_ficha_original", "ler_documentos_da_original",
        "ler_condicoes_da_original", "ler_imagens_da_original",
    }
    infratores = []
    for no in ast.walk(fonte):
        if not isinstance(no, ast.FunctionDef) or no.name not in leitores_da_original:
            continue
        for interno in ast.walk(no):
            if isinstance(interno, ast.Call):
                nome = getattr(interno.func, "id", "") or getattr(interno.func, "attr", "")
                if "edicao" in nome.lower():
                    infratores.append(f"{no.name} -> {nome}")

    assert infratores == [], (
        "a ficha ORIGINAL é só de leitura, e só em modo de visualização: "
        f"{infratores}"
    )


def test_abrir_para_edicao_so_e_chamado_para_a_ficha_ALVO():
    """`abrir_alvo_para_edicao` recebe `ficha.pmib` (a alvo) e nunca
    `ficha.ficha_original`."""
    fonte = inspect.getsource(robo)
    arvore = ast.parse(fonte)

    argumentos = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call) and \
                getattr(no.func, "id", "") == "abrir_alvo_para_edicao":
            argumentos.extend(ast.unparse(a) for a in no.args)

    assert argumentos, "o teste precisa achar as chamadas"
    assert "ficha.ficha_original" not in argumentos
    assert "pmib_original" not in argumentos


# =============================================================================
# 2. A palavra da seção estava no PLURAL e o portal fala no singular
# =============================================================================
def test_o_toast_real_das_caracteristicas_confirma_a_secao():
    """O log de 2026-08-20, 14h32, prova que o salvamento FUNCIONOU:

        [Injetor] SALVAR da seção Características Técnicas (dentro da seção).
        [!] Não vi a confirmação. A última mensagem na tela foi:
            'A característica técnica foi salva com sucesso!. A característica
             técnica não está marcada como breve descrição'

    A seção gravou; quem falhou foi a minha checagem. Eu mapeei a palavra como
    `"caracteristicas"` (plural, de "As características técnicas foram
    salvas") e o portal escreveu **"A característica técnica foi salva"** --
    no singular. Uma letra.

    O radical no singular casa as duas redações; o plural só casava uma.
    """
    from sigft.core.rpa import portal as portal_mod

    real = ("A característica técnica foi salva com sucesso!. A característica "
            "técnica não está marcada como breve descrição")
    assert portal_mod.mensagem_confirma_secao(real, "Características Técnicas") is True

    # a redação que o usuário tinha mandado antes continua valendo
    antiga = "As características técnicas foram salvas com sucesso!"
    assert portal_mod.mensagem_confirma_secao(antiga, "Características Técnicas") is True


def test_a_palavra_da_secao_nao_casa_a_secao_errada():
    from sigft.core.rpa import portal as portal_mod

    de_condicoes = "As condições de armazenamento foram adicionadas com sucesso!"
    assert portal_mod.mensagem_confirma_secao(
        de_condicoes, "Características Técnicas") is False


def test_adicionadas_tambem_e_sucesso():
    """O portal diz "adicionadas" nas Condições, não "modificadas" -- e as
    duas passam, porque o marcador é "sucesso"."""
    from sigft.core.rpa import portal as portal_mod

    assert portal_mod.mensagem_confirma_secao(
        "As condições de descarte foram adicionadas com sucesso!", "Descarte") is True


# =============================================================================
# 3. Um SALVAR que não dá para clicar é PENDÊNCIA, não queda da ficha
# =============================================================================
def test_salvar_que_estoura_o_timeout_nao_derruba_a_ficha():
    """O log terminou assim, DEPOIS de a ficha estar quase pronta:

        [Erro] TempoEsgotado: Locator.click: Timeout 20000ms exceeded.
          - locator resolved to <button tabindex="-1" class="btn btn-primary">
          - element is visible, enabled and stable
          - scrolling into view ... done scrolling

    Resolveu, está visível, rolou -- e o clique nunca completa: algo cobre o
    botão (o `tabindex="-1"` sugere painel inativo). A exceção subiu até
    `processar_ficha` e virou ERRO FATAL, apagando do placar tudo o que já
    tinha dado certo na ficha.

    Salvar é uma etapa; não poder clicar nela é pendência.
    """
    from sigft.core.rpa.portal import PMIBPortal

    class _EngineQueNaoDeixaClicar:
        def contar(self, seletor):
            return 1 if "SALVAR" in seletor else 0

        def scroll_to(self, _s):
            pass

        def click_raw(self, _s):
            raise TimeoutError("Locator.click: Timeout 20000ms exceeded")

    linhas = []
    ok = PMIBPortal(_EngineQueNaoDeixaClicar()).clicar_salvar_do_bloco(
        "//div[contains(@id, 'MultiUploadContainer')]", "Documentos e imagens",
        linhas.append)

    assert ok is False
    assert any("não consegui clicar" in l.lower() for l in linhas)
