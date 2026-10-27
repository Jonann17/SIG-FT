r"""
Testes da 1ª metade do Checkpoint 1.5 — `sigft/core/prefs.py` (ver
docs/refatoracao/PLANO_REFATORACAO.md, Fase 1 -> CP 1.5, e decisão de produto
nº 7 na seção 0).

Cobre: as 4 camadas de resolução de `get_initial_dir` (chave > categoria >
pasta padrão da chave > `None`) com validação `os.path.isdir` real em cada
camada (pastas criadas/removidas de verdade em `tmp_path`); `remember_dir`
gravando em `ultimos` E `categorias`; `get_default_dir`/`set_default_dir`
(override do usuário > pasta semeada > `None`); tolerância a
ausência/corrupção do `user_prefs.json` (sem exceção); persistência real
(escreve, relê, confirma); e os valores/estrutura de `PASTAS_PADRAO_SEED` /
`PASTAS_PADRAO_POR_CHAVE`.

Todos os testes usam `config_path=<tmp_path>/user_prefs.json` — nunca tocam
no `user_prefs.json` real do repositório. Camadas que dependem de
`PASTAS_PADRAO_SEED`/`PASTAS_PADRAO_POR_CHAVE` "de mentira" usam
`monkeypatch.setitem` (revertido automaticamente ao fim do teste) para não
depender da pasta real do Box existir na máquina que roda os testes.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from sigft.core import prefs


@pytest.fixture()
def config_path(tmp_path) -> Path:
    """`user_prefs.json` de teste — nunca criado automaticamente (os testes
    de "arquivo ausente" dependem disso); só o CAMINHO, dentro de `tmp_path`
    (que sempre existe, então `_salvar_estado` nunca falha por pasta-mãe
    ausente)."""
    return tmp_path / "user_prefs.json"


# =============================================================================
# A. PASTAS_PADRAO_SEED / PASTAS_PADRAO_POR_CHAVE (decisão de produto nº 7)
# =============================================================================

def test_pastas_padrao_seed_tem_exatamente_as_chaves_da_decisao_7():
    # [2026-10-21] "pdms_modificados" saiu com a pasta de PDMs Modificados.
    assert set(prefs.PASTAS_PADRAO_SEED) == {
        "sobressalentes_pmib",
        "templates_ficha",
    }


def test_pastas_padrao_seed_valores_sao_path_relativos_ao_home():
    for caminho in prefs.PASTAS_PADRAO_SEED.values():
        assert isinstance(caminho, Path)
        assert caminho.is_relative_to(Path.home())


def test_pastas_padrao_seed_base_box_e_a_estrutura_da_decisao_7():
    # "<home>/Box/CMI - Consórcio Itaipu/11 - Ger. Engenharia/15 - PDM/..."
    assert prefs.BASE_BOX == (
        Path.home() / "Box" / "CMI - Consórcio Itaipu" / "11 - Ger. Engenharia" / "15 - PDM"
    )


def test_pastas_padrao_seed_subpastas_literais_da_decisao_7():
    # Nomes copiados literalmente do texto da decisão nº 7 / CP 1.5.
    assert prefs.PASTAS_PADRAO_SEED["sobressalentes_pmib"] == prefs.BASE_BOX / "SOBRESSALENTES - PMIB"
    assert prefs.PASTAS_PADRAO_SEED["templates_ficha"] == prefs.BASE_BOX / "Templates"


def test_pastas_padrao_por_chave_tem_as_chaves_do_modulo_pdm():
    assert set(prefs.PASTAS_PADRAO_POR_CHAVE) == {
        "pdm.template",
        "pdm.status_pmib",
    }


def test_pastas_padrao_por_chave_aponta_so_para_nomes_existentes_no_seed():
    for nome_logico in prefs.PASTAS_PADRAO_POR_CHAVE.values():
        assert nome_logico in prefs.PASTAS_PADRAO_SEED


def test_pastas_padrao_por_chave_mapeamento_exato():
    assert prefs.PASTAS_PADRAO_POR_CHAVE == {
        "pdm.template": "templates_ficha",
        "pdm.status_pmib": "sobressalentes_pmib",
    }


def test_pastas_padrao_seed_reais_atravessam_get_default_dir_sem_quebrar(config_path):
    # Os nomes REAIS do seed (sem monkeypatch nenhum) devem atravessar
    # `get_default_dir` sem levantar exceção, EM QUALQUER MÁQUINA.
    #
    # A asserção é de CONTRATO, não de ambiente: o resultado é `None` (Box não
    # sincronizado aqui) ou o caminho de uma pasta que existe DE FATO no disco
    # (Box sincronizado) -- nunca um caminho inventado. Ver o comportamento
    # "só usa se existir no disco" em `prefs.get_default_dir`.
    #
    # ⚠️ Não afirme aqui que "o Box não existe nesta máquina": foi o que esta
    # asserção dizia até 2026-08-27, e ela falhava na máquina de quem TEM o
    # Box do consórcio sincronizado -- que é o caso do usuário e o da máquina
    # da empresa. As duas metades do contrato (seed presente -> devolve; seed
    # ausente -> None) já são testadas na seção D com `monkeypatch`, sem
    # depender de pasta real nenhuma.
    for nome_logico in prefs.PASTAS_PADRAO_SEED:
        resultado = prefs.get_default_dir(nome_logico, config_path=config_path)
        assert resultado is None or os.path.isdir(resultado)


# =============================================================================
# B. get_initial_dir — as 4 camadas de resolução
# =============================================================================

def test_get_initial_dir_sem_nada_salvo_e_sem_pasta_padrao_retorna_none(config_path):
    assert prefs.get_initial_dir("chave.nunca.usada", "excel", config_path=config_path) is None


def test_get_initial_dir_usa_ultimo_da_chave_especifica(tmp_path, config_path):
    pasta = tmp_path / "pasta_excel"
    pasta.mkdir()

    prefs.remember_dir("autospec.ficha", "excel", str(pasta), config_path=config_path)

    assert prefs.get_initial_dir("autospec.ficha", "excel", config_path=config_path) == str(pasta)


def test_get_initial_dir_prioriza_chave_especifica_sobre_categoria(tmp_path, config_path):
    pasta_a = tmp_path / "pasta_a"
    pasta_a.mkdir()
    pasta_b = tmp_path / "pasta_b"
    pasta_b.mkdir()

    # 1ª chamada: chave "autospec.ficha" e categoria "excel" -> pasta_a.
    prefs.remember_dir("autospec.ficha", "excel", str(pasta_a), config_path=config_path)
    # 2ª chamada: OUTRA chave, MESMA categoria "excel" -> sobrescreve
    # categorias["excel"] para pasta_b, mas NÃO mexe em ultimos["autospec.ficha"].
    prefs.remember_dir("cria_fichas.status", "excel", str(pasta_b), config_path=config_path)

    # A chave original continua vendo a PRÓPRIA última pasta (pasta_a),
    # mesmo com a categoria "excel" agora apontando para pasta_b.
    assert prefs.get_initial_dir("autospec.ficha", "excel", config_path=config_path) == str(pasta_a)
    assert prefs.get_initial_dir("cria_fichas.status", "excel", config_path=config_path) == str(pasta_b)


def test_get_initial_dir_cai_para_categoria_quando_chave_nunca_foi_usada(tmp_path, config_path):
    pasta = tmp_path / "pasta_pdf"
    pasta.mkdir()

    prefs.remember_dir("autospec.manuais", "pdf", str(pasta), config_path=config_path)

    # Uma chave DIFERENTE, nunca usada, mas da MESMA categoria "pdf", herda
    # a última pasta da categoria.
    assert prefs.get_initial_dir("outro_modulo.pdf_qualquer", "pdf", config_path=config_path) == str(pasta)


def test_get_initial_dir_pula_ultimo_da_chave_se_pasta_foi_removida_cai_para_categoria(
    tmp_path, config_path
):
    pasta_morta = tmp_path / "pasta_removida"
    pasta_morta.mkdir()
    pasta_viva = tmp_path / "pasta_viva"
    pasta_viva.mkdir()

    # Grava ultimos["k"] = categorias["cat"] = pasta_morta.
    prefs.remember_dir("k", "cat", str(pasta_morta), config_path=config_path)
    # Remove a pasta de fato do disco -- ultimos["k"] fica "morto" (aponta
    # para algo que não existe mais), mas o VALOR continua salvo no JSON.
    shutil.rmtree(pasta_morta)
    # Atualiza categorias["cat"] (via outra chave) para uma pasta que EXISTE.
    prefs.remember_dir("k2", "cat", str(pasta_viva), config_path=config_path)

    # ultimos["k"] é candidato mas isdir falha -> PULA para categorias["cat"].
    assert prefs.get_initial_dir("k", "cat", config_path=config_path) == str(pasta_viva)


def test_get_initial_dir_pula_categoria_morta_cai_para_pasta_padrao_da_chave(
    tmp_path, config_path, monkeypatch
):
    pasta_padrao = tmp_path / "pasta_padrao_seed"
    pasta_padrao.mkdir()
    pasta_morta = tmp_path / "categoria_removida"
    pasta_morta.mkdir()

    monkeypatch.setitem(prefs.PASTAS_PADRAO_POR_CHAVE, "modulo.campo_teste", "nome_logico_teste")
    monkeypatch.setitem(prefs.PASTAS_PADRAO_SEED, "nome_logico_teste", pasta_padrao)

    # categorias["cat_teste"] aponta para uma pasta que existia mas foi
    # removida -- nenhuma chave própria para "modulo.campo_teste" ainda.
    prefs.remember_dir("outra.chave", "cat_teste", str(pasta_morta), config_path=config_path)
    shutil.rmtree(pasta_morta)

    assert prefs.get_initial_dir("modulo.campo_teste", "cat_teste", config_path=config_path) == str(
        pasta_padrao
    )


def test_get_initial_dir_usa_pasta_padrao_quando_nada_foi_usado_ainda(tmp_path, config_path, monkeypatch):
    pasta_padrao = tmp_path / "pasta_padrao_seed"
    pasta_padrao.mkdir()

    monkeypatch.setitem(prefs.PASTAS_PADRAO_POR_CHAVE, "modulo.campo_teste", "nome_logico_teste")
    monkeypatch.setitem(prefs.PASTAS_PADRAO_SEED, "nome_logico_teste", pasta_padrao)

    assert prefs.get_initial_dir("modulo.campo_teste", "cat_nunca_usada", config_path=config_path) == str(
        pasta_padrao
    )


def test_get_initial_dir_pasta_padrao_da_chave_nao_existe_no_disco_cai_para_none(
    tmp_path, config_path, monkeypatch
):
    pasta_padrao_inexistente = tmp_path / "nao_criada"  # nunca criada

    monkeypatch.setitem(prefs.PASTAS_PADRAO_POR_CHAVE, "modulo.campo_teste", "nome_logico_teste")
    monkeypatch.setitem(prefs.PASTAS_PADRAO_SEED, "nome_logico_teste", pasta_padrao_inexistente)

    assert prefs.get_initial_dir("modulo.campo_teste", "cat_qualquer", config_path=config_path) is None


def test_get_initial_dir_chave_sem_mapeamento_de_pasta_padrao_vai_direto_para_none(config_path):
    # "chave.totalmente.desconhecida" não está em PASTAS_PADRAO_POR_CHAVE.
    assert "chave.totalmente.desconhecida" not in prefs.PASTAS_PADRAO_POR_CHAVE
    assert prefs.get_initial_dir("chave.totalmente.desconhecida", "cat_qualquer", config_path=config_path) is None


def test_get_initial_dir_camada_3_usa_override_do_usuario_sobre_seed(tmp_path, config_path, monkeypatch):
    pasta_seed = tmp_path / "seed"
    pasta_seed.mkdir()
    pasta_override = tmp_path / "override_do_usuario"
    pasta_override.mkdir()

    monkeypatch.setitem(prefs.PASTAS_PADRAO_POR_CHAVE, "modulo.campo_teste", "nome_logico_teste")
    monkeypatch.setitem(prefs.PASTAS_PADRAO_SEED, "nome_logico_teste", pasta_seed)
    prefs.set_default_dir("nome_logico_teste", str(pasta_override), config_path=config_path)

    assert prefs.get_initial_dir("modulo.campo_teste", "cat_qualquer", config_path=config_path) == str(
        pasta_override
    )


# =============================================================================
# C. remember_dir
# =============================================================================

def test_remember_dir_grava_em_ultimos_e_categorias(tmp_path, config_path):
    pasta = tmp_path / "pasta"
    pasta.mkdir()

    prefs.remember_dir("chave.x", "categoria.y", str(pasta), config_path=config_path)

    bruto = json.loads(config_path.read_text(encoding="utf-8"))
    assert bruto["ultimos"]["chave.x"] == str(pasta)
    assert bruto["categorias"]["categoria.y"] == str(pasta)


def test_remember_dir_nao_exige_que_a_pasta_exista_no_momento_da_gravacao(tmp_path, config_path):
    # remember_dir não valida isdir -- só get_initial_dir/get_default_dir
    # validam, na LEITURA (ver docstring do módulo).
    pasta_que_nao_existe = str(tmp_path / "pasta_fantasma")

    prefs.remember_dir("chave.x", "categoria.y", pasta_que_nao_existe, config_path=config_path)

    bruto = json.loads(config_path.read_text(encoding="utf-8"))
    assert bruto["ultimos"]["chave.x"] == pasta_que_nao_existe


def test_remember_dir_sobrescreve_valor_anterior_da_mesma_chave(tmp_path, config_path):
    pasta_1 = tmp_path / "pasta_1"
    pasta_1.mkdir()
    pasta_2 = tmp_path / "pasta_2"
    pasta_2.mkdir()

    prefs.remember_dir("chave.x", "categoria.y", str(pasta_1), config_path=config_path)
    prefs.remember_dir("chave.x", "categoria.y", str(pasta_2), config_path=config_path)

    assert prefs.get_initial_dir("chave.x", "categoria.y", config_path=config_path) == str(pasta_2)


def test_remember_dir_funciona_de_primeira_sem_arquivo_previo(tmp_path, config_path):
    assert not config_path.exists()
    pasta = tmp_path / "pasta"
    pasta.mkdir()

    prefs.remember_dir("chave.x", "categoria.y", str(pasta), config_path=config_path)

    assert config_path.exists()
    assert prefs.get_initial_dir("chave.x", "categoria.y", config_path=config_path) == str(pasta)


def test_remember_dir_aceita_objeto_path_alem_de_string(tmp_path, config_path):
    pasta = tmp_path / "pasta_path_obj"
    pasta.mkdir()

    prefs.remember_dir("chave.x", "categoria.y", pasta, config_path=config_path)  # Path, não str

    # Persistido como string (JSON não serializa Path diretamente).
    bruto = json.loads(config_path.read_text(encoding="utf-8"))
    assert bruto["ultimos"]["chave.x"] == str(pasta)
    assert isinstance(bruto["ultimos"]["chave.x"], str)


def test_remember_dir_nao_afeta_outras_chaves_categorias_ja_salvas(tmp_path, config_path):
    pasta_1 = tmp_path / "pasta_1"
    pasta_1.mkdir()
    pasta_2 = tmp_path / "pasta_2"
    pasta_2.mkdir()

    prefs.remember_dir("chave.a", "categoria.a", str(pasta_1), config_path=config_path)
    prefs.remember_dir("chave.b", "categoria.b", str(pasta_2), config_path=config_path)

    assert prefs.get_initial_dir("chave.a", "categoria.a", config_path=config_path) == str(pasta_1)
    assert prefs.get_initial_dir("chave.b", "categoria.b", config_path=config_path) == str(pasta_2)


# =============================================================================
# D. get_default_dir / set_default_dir
# =============================================================================

def test_get_default_dir_nome_totalmente_desconhecido_retorna_none(config_path):
    assert prefs.get_default_dir("nome_que_nao_existe_em_lugar_nenhum", config_path=config_path) is None


def test_get_default_dir_usa_seed_quando_existe_no_disco(tmp_path, config_path, monkeypatch):
    pasta_seed = tmp_path / "seed_existente"
    pasta_seed.mkdir()
    monkeypatch.setitem(prefs.PASTAS_PADRAO_SEED, "nome_logico_teste", pasta_seed)

    assert prefs.get_default_dir("nome_logico_teste", config_path=config_path) == str(pasta_seed)


def test_get_default_dir_seed_nao_existe_no_disco_retorna_none(tmp_path, config_path, monkeypatch):
    pasta_seed_inexistente = tmp_path / "seed_nunca_criada"
    monkeypatch.setitem(prefs.PASTAS_PADRAO_SEED, "nome_logico_teste", pasta_seed_inexistente)

    assert prefs.get_default_dir("nome_logico_teste", config_path=config_path) is None


def test_set_default_dir_grava_override_que_get_default_dir_passa_a_devolver(
    tmp_path, config_path, monkeypatch
):
    pasta_override = tmp_path / "override"
    pasta_override.mkdir()
    monkeypatch.setitem(prefs.PASTAS_PADRAO_SEED, "nome_logico_teste", tmp_path / "seed_nao_criada")

    assert prefs.get_default_dir("nome_logico_teste", config_path=config_path) is None

    prefs.set_default_dir("nome_logico_teste", str(pasta_override), config_path=config_path)

    assert prefs.get_default_dir("nome_logico_teste", config_path=config_path) == str(pasta_override)


def test_override_do_usuario_tem_prioridade_sobre_seed_quando_ambos_existem(
    tmp_path, config_path, monkeypatch
):
    pasta_seed = tmp_path / "seed_valida"
    pasta_seed.mkdir()
    pasta_override = tmp_path / "override_valida"
    pasta_override.mkdir()
    monkeypatch.setitem(prefs.PASTAS_PADRAO_SEED, "nome_logico_teste", pasta_seed)

    prefs.set_default_dir("nome_logico_teste", str(pasta_override), config_path=config_path)

    # Override vence, mesmo com a pasta semeada também existindo de fato.
    assert prefs.get_default_dir("nome_logico_teste", config_path=config_path) == str(pasta_override)


def test_set_default_dir_nao_valida_isdir_na_escrita_mas_get_valida_na_leitura(
    tmp_path, config_path, monkeypatch
):
    pasta_ainda_nao_criada = tmp_path / "sera_criada_depois"
    monkeypatch.setitem(prefs.PASTAS_PADRAO_SEED, "nome_logico_teste", tmp_path / "seed_nao_criada")

    # Grava o override ANTES da pasta existir -- não levanta exceção.
    prefs.set_default_dir("nome_logico_teste", str(pasta_ainda_nao_criada), config_path=config_path)
    # Como a pasta ainda não existe, get_default_dir não a usa (nem o seed,
    # também inexistente) -> None.
    assert prefs.get_default_dir("nome_logico_teste", config_path=config_path) is None

    # Cria a pasta agora -- get_default_dir passa a enxergá-la, sem precisar
    # chamar set_default_dir de novo.
    pasta_ainda_nao_criada.mkdir()
    assert prefs.get_default_dir("nome_logico_teste", config_path=config_path) == str(
        pasta_ainda_nao_criada
    )


def test_set_default_dir_persiste_estrutura_pastas_padrao_no_json(tmp_path, config_path):
    pasta = tmp_path / "pasta"
    pasta.mkdir()

    prefs.set_default_dir("meu_nome", str(pasta), config_path=config_path)

    bruto = json.loads(config_path.read_text(encoding="utf-8"))
    assert bruto["pastas_padrao"]["meu_nome"] == str(pasta)


# =============================================================================
# E. Tolerância a ausência/corrupção do arquivo (mesmo espírito de
#    sigft.config.carregar_chaves)
# =============================================================================

def test_arquivo_ausente_get_initial_dir_nao_levanta_excecao(config_path):
    assert not config_path.exists()
    assert prefs.get_initial_dir("qualquer.chave", "qualquer.cat", config_path=config_path) is None


def test_arquivo_ausente_get_default_dir_nao_levanta_excecao(config_path):
    assert not config_path.exists()
    assert prefs.get_default_dir("qualquer_nome", config_path=config_path) is None


def test_json_corrompido_nao_levanta_excecao_e_cai_para_estado_vazio(tmp_path, config_path):
    config_path.write_text("{isso nao é json valido!!!", encoding="utf-8")

    assert prefs.get_initial_dir("qualquer.chave", "qualquer.cat", config_path=config_path) is None
    assert prefs.get_default_dir("qualquer_nome", config_path=config_path) is None


def test_json_vazio_tambem_e_tratado_como_corrompido(config_path):
    config_path.write_text("", encoding="utf-8")

    assert prefs.get_initial_dir("qualquer.chave", "qualquer.cat", config_path=config_path) is None


def test_json_valido_mas_nao_e_objeto_cai_para_estado_vazio(config_path):
    config_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    assert prefs.get_initial_dir("qualquer.chave", "qualquer.cat", config_path=config_path) is None


def test_secao_com_tipo_inesperado_e_ignorada_sem_derrubar_as_outras(tmp_path, config_path):
    pasta = tmp_path / "pasta_valida"
    pasta.mkdir()

    # "ultimos" corrompido (string em vez de dict); "categorias" continua
    # válido -- get_initial_dir não pode quebrar, e a camada "categorias"
    # continua funcionando normalmente.
    config_path.write_text(
        json.dumps({"ultimos": "isto deveria ser um dict", "categorias": {"cat": str(pasta)}}),
        encoding="utf-8",
    )

    assert prefs.get_initial_dir("chave.qualquer", "cat", config_path=config_path) == str(pasta)


def test_remember_dir_apos_arquivo_corrompido_reescreve_com_estrutura_valida(tmp_path, config_path):
    config_path.write_text("{ json quebrado", encoding="utf-8")
    pasta = tmp_path / "pasta"
    pasta.mkdir()

    prefs.remember_dir("chave.x", "categoria.y", str(pasta), config_path=config_path)

    bruto = json.loads(config_path.read_text(encoding="utf-8"))
    assert bruto["ultimos"]["chave.x"] == str(pasta)


# =============================================================================
# F. Persistência real através de "sessões" (nenhuma função de prefs.py
#    mantém estado em memória entre chamadas -- cada chamada relê o disco,
#    o que já simula naturalmente "reiniciar o app").
# =============================================================================

def test_persistencia_sobrevive_a_nova_leitura_simulando_reinicio_do_app(tmp_path, config_path):
    pasta = tmp_path / "pasta_persistente"
    pasta.mkdir()

    # "Sessão 1": salva.
    prefs.remember_dir("autospec.ficha", "excel", str(pasta), config_path=config_path)

    # "Sessão 2" (chamada independente, nenhum estado compartilhado em
    # memória além do arquivo em disco -- equivalente a reiniciar o app):
    resultado = prefs.get_initial_dir("autospec.ficha", "excel", config_path=config_path)
    assert resultado == str(pasta)


def test_persistencia_estrutura_completa_do_json_apos_uso_combinado(tmp_path, config_path):
    pasta_ultimo = tmp_path / "pasta_ultimo"
    pasta_ultimo.mkdir()
    pasta_padrao = tmp_path / "pasta_padrao_custom"
    pasta_padrao.mkdir()

    prefs.remember_dir("autospec.ficha", "excel", str(pasta_ultimo), config_path=config_path)
    prefs.set_default_dir("templates_ficha", str(pasta_padrao), config_path=config_path)

    bruto = json.loads(config_path.read_text(encoding="utf-8"))
    # [2026-09-03] Eram 3 seções; "arquivos" entrou com `remember_file`, que o
    # mural de atividades precisa (ele lê a planilha sem passar por diálogo, e
    # a memória de PASTA não serve para isso). [2026-10-05] "opcoes" entrou
    # com `set_opcao` -- o "Gerar painel ao terminar" do Gestão PMIB.
    # [2026-10-19] "novidades" entrou com `set_ultima_versao_vista` -- a janela
    # de novidades. [2026-10-20] "preferencias" entrou com `gravar_preferencia`
    # -- o tema da interface (escuro/claro/sistema).
    # [2026-10-21] "recentes" entrou com `lembrar_recente` -- os últimos arquivos de cada diálogo.
    # [2026-10-26] "colunas" entrou com `gravar_colunas` -- as colunas lembradas das tabelas.
    assert set(bruto.keys()) == {"ultimos", "categorias", "pastas_padrao", "arquivos", "opcoes",
                                 "novidades", "preferencias", "recentes", "colunas"}
    assert bruto == {
        "ultimos": {"autospec.ficha": str(pasta_ultimo)},
        "categorias": {"excel": str(pasta_ultimo)},
        "pastas_padrao": {"templates_ficha": str(pasta_padrao)},
        # Vazias porque este teste não chamou `remember_file` nem `set_opcao`
        # -- as seções existem sempre, como as outras três.
        "arquivos": {},
        "opcoes": {},
        "novidades": {},
        "preferencias": {},
        "recentes": {},
        "colunas": {},
    }


# =============================================================================
# Lembrar um ARQUIVO  [2026-09-03]
# =============================================================================
# `remember_dir` guarda a PASTA — é o que o CP 1.5 precisava, porque o objetivo
# era abrir o diálogo no lugar certo. O mural de atividades precisa do ARQUIVO:
# ele lê a planilha sem passar por diálogo nenhum.
#
# Sem isto, o mural dizia "não encontrei o mapeamento" mesmo com o usuário
# tendo acabado de rodar o PMIB Manager sobre ele — aconteceu em 2026-09-03.

def test_remember_file_guarda_o_caminho_completo(tmp_path, config_path):
    arquivo = tmp_path / "Mapeamento.xlsx"
    arquivo.write_text("x", encoding="utf-8")

    prefs.remember_file("pmib.mapa", str(arquivo), config_path=config_path)

    assert prefs.get_last_file("pmib.mapa", config_path=config_path) == str(arquivo)


def test_get_last_file_sem_registro_devolve_none(config_path):
    assert prefs.get_last_file("nunca.usada", config_path=config_path) is None


def test_arquivo_que_sumiu_do_disco_devolve_none(tmp_path, config_path):
    """Registro e realidade divergem quando alguém move ou apaga o arquivo.
    Quem chama trata igual a 'nunca escolhido' — nos dois não há o que ler."""
    arquivo = tmp_path / "some.xlsx"
    arquivo.write_text("x", encoding="utf-8")
    prefs.remember_file("pmib.mapa", str(arquivo), config_path=config_path)

    arquivo.unlink()

    assert prefs.get_last_file("pmib.mapa", config_path=config_path) is None


def test_remember_file_com_caminho_vazio_nao_grava(config_path):
    prefs.remember_file("pmib.mapa", "", config_path=config_path)

    assert prefs.get_last_file("pmib.mapa", config_path=config_path) is None


def test_arquivo_e_pasta_convivem_sem_se_atrapalhar(tmp_path, config_path):
    """As duas memórias são independentes: uma guarda onde ABRIR o diálogo, a
    outra QUAL arquivo foi escolhido."""
    pasta = tmp_path / "planilhas"
    pasta.mkdir()
    arquivo = pasta / "Mapeamento.xlsx"
    arquivo.write_text("x", encoding="utf-8")

    prefs.remember_dir("pmib.mapa", "excel", str(pasta), config_path=config_path)
    prefs.remember_file("pmib.mapa", str(arquivo), config_path=config_path)

    assert prefs.get_initial_dir("pmib.mapa", "excel", config_path=config_path) == str(pasta)
    assert prefs.get_last_file("pmib.mapa", config_path=config_path) == str(arquivo)


def test_a_chave_do_mapeamento_existe():
    """A Home lê por ela; o PMIB Manager grava nela. Se o nome divergir, o
    mural volta a não achar nada — em silêncio."""
    assert prefs.CHAVE_MAPEAMENTO == "pmib_manager.mapeamento"


# ===========================================================================
# Opções liga/desliga (2026-10-05): "Gerar painel ao terminar" do Gestão PMIB
# ===========================================================================
def test_opcao_nunca_gravada_devolve_o_padrao(tmp_path):
    config_path = tmp_path / "user_prefs.json"

    assert prefs.get_opcao("pmib_manager.gerar_painel", True, config_path=config_path) is True
    assert prefs.get_opcao("pmib_manager.gerar_painel", False, config_path=config_path) is False


def test_opcao_gravada_e_lida_de_volta(tmp_path):
    config_path = tmp_path / "user_prefs.json"

    prefs.set_opcao("pmib_manager.gerar_painel", False, config_path=config_path)

    assert prefs.get_opcao("pmib_manager.gerar_painel", True, config_path=config_path) is False


def test_opcao_sobrevive_ao_recarregar_junto_com_as_outras_secoes(tmp_path):
    # A armadilha de 2026-09-03: seção que não está em `_SECOES_ESTADO` é
    # DESCARTADA ao carregar -- gravar e ler de volta pegaria o padrão.
    config_path = tmp_path / "user_prefs.json"
    pasta = tmp_path / "pasta"
    pasta.mkdir()

    prefs.set_opcao("pmib_manager.gerar_painel", False, config_path=config_path)
    prefs.remember_dir("autospec.ficha", "excel", str(pasta), config_path=config_path)

    assert prefs.get_opcao("pmib_manager.gerar_painel", True, config_path=config_path) is False
    assert prefs.get_initial_dir("autospec.ficha", "excel", config_path=config_path) == str(pasta)


def test_opcao_corrompida_no_arquivo_cai_no_padrao(tmp_path):
    config_path = tmp_path / "user_prefs.json"
    config_path.write_text('{"opcoes": {"pmib_manager.gerar_painel": "talvez"}}', encoding="utf-8")

    assert prefs.get_opcao("pmib_manager.gerar_painel", True, config_path=config_path) is True


# =============================================================================
# Preferências de texto  [2026-10-20]
# =============================================================================
# O tema da interface (escuro/claro/sistema) é a primeira: `get_opcao` só guarda
# booleano, e o tema tem três valores.

def test_preferencia_nunca_gravada_e_o_padrao(config_path):
    assert prefs.ler_preferencia("tema", "escuro", config_path=config_path) == "escuro"


def test_preferencia_gravada_volta(config_path):
    prefs.gravar_preferencia("tema", "claro", config_path=config_path)
    assert prefs.ler_preferencia("tema", "escuro", config_path=config_path) == "claro"
    dados = json.loads(config_path.read_text(encoding="utf-8"))
    assert dados["preferencias"] == {"tema": "claro"}


def test_preferencia_nao_apaga_as_outras_secoes(config_path):
    prefs.set_opcao("x", True, config_path=config_path)
    prefs.gravar_preferencia("tema", "claro", config_path=config_path)
    assert prefs.get_opcao("x", False, config_path=config_path) is True


@pytest.mark.parametrize("bruto", ['{"preferencias": {"tema": 3}}', '{"preferencias": []}',
                                   '{"preferencias": {"tema": ""}}', "nao e json"])
def test_preferencia_ilegivel_e_o_padrao(config_path, bruto):
    config_path.write_text(bruto, encoding="utf-8")
    assert prefs.ler_preferencia("tema", "escuro", config_path=config_path) == "escuro"


# =============================================================================
# ultima_pasta: só a camada da chave
# =============================================================================

def test_ultima_pasta_e_a_da_chave_sem_cair_na_categoria(tmp_path, config_path):
    raiz = tmp_path / "raiz"
    raiz.mkdir()
    outra = tmp_path / "outra"
    outra.mkdir()
    prefs.remember_dir("pmib_manager.pasta_raiz", "pasta", str(raiz), config_path=config_path)
    assert prefs.ultima_pasta("pmib_manager.pasta_raiz", config_path=config_path) == str(raiz)
    prefs.remember_dir("outra.tela", "pasta", str(outra), config_path=config_path)
    assert prefs.ultima_pasta("nunca.usada", config_path=config_path) is None


def test_ultima_pasta_que_sumiu_e_none(tmp_path, config_path):
    prefs.remember_dir("pmib_manager.pasta_raiz", "pasta", str(tmp_path / "sumiu"), config_path=config_path)
    assert prefs.ultima_pasta("pmib_manager.pasta_raiz", config_path=config_path) is None
