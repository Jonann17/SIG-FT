"""As regras do portal PMIB, conferidas ANTES de abrir o navegador.

R2 de `docs/PMIB_ENGENHARIA_REVERSA.md` §8. Hoje o SIG-FT descobre a recusa do
portal depois de digitar; aqui as regras que o próprio código do portal ensina
(§5 e Apêndice D daquele documento) rodam sobre os dados que JÁ iam para o
robô, e devolvem a lista do que ele vai recusar.

Três regras da casa:

* **Só avisa, nunca corrige.** A conferência valida uma CÓPIA; o robô recebe os
  dados como vieram. Quem decide o que fazer com o aviso é a pessoa, na janela
  "Revisão antes do portal" (`sigft/app_qt/widgets/revisao_portal.py`).
* **Só o que o robô preenche.** Campo que o robô não toca, ou que ele PULA
  (status desligado, PDM "NENHUM", ação diferente de PREENCHER), não gera
  problema. Valor vazio só é problema onde o portal recusa vazio.
* **O portal continua sendo o juiz.** As regras `…_BL` do servidor não são
  visíveis; uma regra local que erre só gera um aviso a mais.

Regra nova do portal entra AQUI: um campo no modelo da tela (pydantic) e o
nome dele em `_CAMPOS`. Sem Qt, sem Selenium e sem pandas no import.
"""
from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from typing import Annotated, Any, Iterable

from pydantic import (
    AfterValidator, BaseModel, BeforeValidator, ConfigDict, StringConstraints, ValidationError,
    ValidationInfo, field_validator,
)
from pydantic_core import PydanticCustomError

# Tamanho máximo do valor mostrado na janela e no console.
MAX_VALOR_MOSTRADO = 60
# `Input_QuantityInstalled` (LMR): o portal limita a 10 dígitos (§5.6).
MAX_DIGITOS_QUANTIDADE = 10

# §5.1: o que o Texto breve aceita depois da 1ª letra. A regex do portal,
# `^[A-Z a-z](?:_?[A-Za-z0-9 .,\-/_()]+)*$`, é exatamente "1º caractere letra
# ou espaço, os outros deste conjunto" (o `_?` some porque `_` já está no
# conjunto). Conferida por conjunto, não pela regex: aquele `(?:…+)*` aninhado
# é retrocesso exponencial no `re` do Python quando o texto falha no fim.
_LETRAS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
_ACEITOS_TEXTO_BREVE = _LETRAS | frozenset("0123456789 .,-/_()")


@dataclass(frozen=True)
class Problema:
    """Uma recusa prevista: o que deu erro e onde.

    `ficha` é como a pessoa a reconhece (PMIB ou descrição); `campo`, o nome na
    tela; `interno`, o nome interno do portal (Apêndice D); `valor`, encurtado;
    `regra`, curta; `mensagem`, em português. `indice` é a posição da ficha na
    entrada da conferência: é por ele que a tela tira as fichas com erro.
    """

    ficha: str
    campo: str
    interno: str
    valor: str
    regra: str
    mensagem: str
    indice: int = -1


# =============================================================================
# Tipos (pydantic)
# =============================================================================
def _como_texto(valor: Any) -> str:
    """Do jeito que o robô vai digitar: `None` e NaN (célula vazia do pandas)
    viram vazio; número vira texto."""
    if valor is None:
        return ""
    if isinstance(valor, float) and math.isnan(valor):
        return ""
    return str(valor)


def _sem_negativo(valor: str) -> str:
    """§5.5: dimensões, pesos e umidade não aceitam negativo."""
    texto = valor.strip().replace(",", ".")
    try:
        negativo = float(texto) < 0
    except ValueError:
        negativo = texto.startswith("-") and texto[1:2].isdigit()
    if negativo:
        raise PydanticCustomError("sem_negativo", "é negativo; o portal não aceita negativo aqui")
    return valor


def _texto_breve(valor: str) -> str:
    """§5.1: 1º caractere letra; os outros só letras sem acento, números,
    espaço e `. , - / _ ( )`. Minúscula não é problema: o portal põe em
    maiúsculas sozinho."""
    texto = valor.strip()
    ruins = sorted({c for c in texto if c not in _ACEITOS_TEXTO_BREVE}, key=texto.index)
    if ruins:
        lista = " ".join(repr(c) for c in ruins)
        raise PydanticCustomError(
            "texto_breve_caracteres",
            "tem caractere que o portal recusa ({ruins}): só letras sem acento nem ç, "
            "números, espaço e . , - / _ ( )", {"ruins": lista})
    if texto and texto[0] not in _LETRAS:
        raise PydanticCustomError("texto_breve_letra", "tem de começar com letra (começa com {primeiro!r})",
                                  {"primeiro": texto[0]})
    return valor


# A ordem do `Annotated` importa: as restrições ficam no `str` (é o que dá os
# erros `string_too_long`/`string_too_short`, já depois do `strip`), e o
# `BeforeValidator` embrulha tudo, convertendo antes.
def _ate(n: int):
    """Opcional, até `n` caracteres (o portal tira os espaços das pontas)."""
    return Annotated[str, StringConstraints(strip_whitespace=True, max_length=n),
                     BeforeValidator(_como_texto)]


def _obrigatorio(n: int):
    """Obrigatório (o portal recusa vazio), até `n` caracteres."""
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=n),
                     BeforeValidator(_como_texto)]


Ate30 = _ate(30)
Ate30SemNegativo = Annotated[Ate30, AfterValidator(_sem_negativo)]
Ate500 = _ate(500)
Ate1000 = _ate(1000)


class _Modelo(BaseModel):
    # Campo ausente não é conferido (o robô não o preenche); o que a tela
    # mandar a mais é ignorado.
    model_config = ConfigDict(extra="ignore", validate_default=False)


def _par_es_pt(pt: str, info: ValidationInfo) -> str:
    """§5.5: cuidados ES/PT e outros cuidados ES/PT, os dois idiomas ou nenhum.
    Roda no PT (declarado depois do ES); a falta é atribuída ao campo vazio."""
    nome_es = info.field_name[:-2] + "es"
    if nome_es not in info.data:
        return pt  # o ES já falhou por outro motivo (ou não foi preenchido)
    tem_es, tem_pt = bool(info.data[nome_es].strip()), bool(pt.strip())
    if tem_es != tem_pt:
        vazio, cheio = ("PT", "ES") if tem_es else ("ES", "PT")
        raise PydanticCustomError(
            "par_es_pt",
            "{vazio} vazio e {cheio} preenchido: o portal exige os dois idiomas ou nenhum",
            {"vazio": vazio, "cheio": cheio, "campo": info.field_name if tem_es else nome_es})
    return pt


class EntradaCriaFichas(_Modelo):
    """§5.1 — o que o robô de Criação de Fichas digita no formulário novo."""

    descricao_curta: Annotated[_obrigatorio(40), AfterValidator(_texto_breve)]
    codigo_projeto: _obrigatorio(1000)


class EntradaCondicoes(_Modelo):
    """§5.5 — as quatro subabas que o robô de Condições preenche. Só chegam
    aqui os campos que o robô de fato vai digitar (ver `_achatar_condicoes`)."""

    comprimento: Ate30SemNegativo = None
    largura: Ate30SemNegativo = None
    altura: Ate30SemNegativo = None
    temp_max: Ate30 = None            # temperatura PODE ser negativa
    temp_min: Ate30 = None
    hr_max: Ate30SemNegativo = None
    hr_min: Ate30SemNegativo = None
    nocivo_es: Ate500 = None
    nocivo_pt: Ate500 = None
    peso_liquido: Ate30SemNegativo = None
    peso_bruto: Ate30SemNegativo = None
    empilhamento: Ate30 = None
    outros_es: Ate500 = None
    outros_pt: Ate500 = None
    embalagem_transp_es: Ate1000 = None
    embalagem_transp_pt: Ate1000 = None
    posicao_icagem_es: Ate1000 = None
    posicao_icagem_pt: Ate1000 = None
    cuidad_preserv_es: Ate1000 = None
    cuidad_preserv_pt: Ate1000 = None
    limpeza_secagem_es: Ate1000 = None
    limpeza_secagem_pt: Ate1000 = None
    ferramentas_es: Ate1000 = None
    ferramentas_pt: Ate1000 = None
    legislacao_es: _obrigatorio(1000) = None
    legislacao_pt: _obrigatorio(1000) = None
    descarte_es: _obrigatorio(1000) = None
    descarte_pt: _obrigatorio(1000) = None
    logistica_es: _obrigatorio(1000) = None
    logistica_pt: _obrigatorio(1000) = None

    _par = field_validator("nocivo_pt", "outros_pt")(_par_es_pt)


class EntradaCaracteristica(_Modelo):
    """§5.3 — uma característica que o robô de Tech Specs vai PREENCHER."""

    char_pt: Ate1000 = None
    char_es: Ate1000 = None
    num: _ate(15) = None
    minimo: _obrigatorio(15) = None
    maximo: _obrigatorio(15) = None


class EntradaAplicacaoLMR(_Modelo):
    """§5.6 — um código LMR com as suas tags."""

    codigo: _ate(200) = None
    tag: _obrigatorio(150) = None


# Nome do campo no modelo -> (nome na tela, nome interno do portal).
_CAMPOS = {
    "descricao_curta": ("Texto breve do material", "Input_ShortText"),
    "codigo_projeto": ("Código do projeto", "TextArea_ProjectCode"),
    # Condições — Armazenamento
    "comprimento": ("Comprimento da embalagem", "Input_PackingLength"),
    "largura": ("Largura da embalagem", "Input_PackagingWidth"),
    "altura": ("Altura da embalagem", "Input_PackagingHeight"),
    "temp_max": ("Temperatura máxima", "Input_MaximumTemperature"),
    "temp_min": ("Temperatura mínima", "Input_MinimumTemperature"),
    "hr_max": ("Umidade relativa máxima", "Input_MaxHR"),
    "hr_min": ("Umidade relativa mínima", "Input_MinHR"),
    "nocivo_es": ("Cuidados de armazenamento (ES)", "TextArea_StorageCareES"),
    "nocivo_pt": ("Cuidados de armazenamento (PT)", "TextArea_StorageCarePT"),
    "peso_liquido": ("Peso líquido", "Input_LiquidWeight"),
    "peso_bruto": ("Peso bruto", "Input_GrossWeight"),
    "empilhamento": ("Empilhamento", "Input_Stacking"),
    "outros_es": ("Outros cuidados (ES)", "TextArea_OtherCareES"),
    "outros_pt": ("Outros cuidados (PT)", "TextArea_OtherCarePT"),
    # Condições — Transporte e Manutenção
    "embalagem_transp_es": ("Embalagem de transporte (ES)", "TextArea_TransportPackagingES"),
    "embalagem_transp_pt": ("Embalagem de transporte (PT)", "TextArea_TransportPackagingPT"),
    "posicao_icagem_es": ("Posição e içamento (ES)", "TextArea_PositionCareES"),
    "posicao_icagem_pt": ("Posição e içamento (PT)", "TextArea_PositionCarePT"),
    "cuidad_preserv_es": ("Cuidados de preservação (ES)", "TextArea_PreservationCareES"),
    "cuidad_preserv_pt": ("Cuidados de preservação (PT)", "TextArea_PreservationCarePT"),
    "limpeza_secagem_es": ("Limpeza e secagem (ES)", "TextArea_CleaningMethodES"),
    "limpeza_secagem_pt": ("Limpeza e secagem (PT)", "TextArea_CleaningMethodPT"),
    "ferramentas_es": ("Ferramentas e equipamentos (ES)", "TextArea_ToolPreservationES"),
    "ferramentas_pt": ("Ferramentas e equipamentos (PT)", "TextArea_ToolPreservationPT"),
    # Condições — Descarte
    "legislacao_es": ("Legislação (ES)", "TextArea_TypeLegislationES"),
    "legislacao_pt": ("Legislação (PT)", "TextArea_TypeLegislationPT"),
    "descarte_es": ("Tipo de descarte (ES)", "TextArea_DiscardTypeES"),
    "descarte_pt": ("Tipo de descarte (PT)", "TextArea_DiscardTypePT"),
    "logistica_es": ("Logística reversa (ES)", "TextArea_ReserveLogisticES"),
    "logistica_pt": ("Logística reversa (PT)", "TextArea_ReserveLogisticPT"),
    # Tech Specs (o nome na tela é o da característica; aqui só o sufixo)
    "char_pt": ("", "TextArea_ValuePT"),
    "char_es": ("", "TextArea_ValueES"),
    "num": ("", "NumberValue_Input"),
    "minimo": (" (Mín)", "MinValue_Input"),
    "maximo": (" (Máx)", "MaxValue_Input"),
    # LMR
    "codigo": ("Código do equipamento", "Input_EquipmentCode"),
    "tag": ("Tag", "Input_Tag"),
}


# =============================================================================
# Tradução das mensagens do pydantic
# =============================================================================
def _encurtar(valor: str) -> str:
    valor = valor.strip()
    if len(valor) <= MAX_VALOR_MOSTRADO:
        return valor
    return valor[:MAX_VALOR_MOSTRADO - 1] + "…"


def traduzir(erro: dict) -> tuple[str, str]:
    """`(regra curta, mensagem em português)` de um erro do pydantic. Os erros
    dele saem em inglês; aqui cada TIPO vira a frase da casa."""
    tipo = erro.get("type", "")
    ctx = erro.get("ctx") or {}
    texto = _como_texto(erro.get("input")).strip()
    if tipo == "string_too_long":
        limite = ctx.get("max_length")
        return (f"até {limite} caracteres",
                f"tem {len(texto)} caracteres; o portal aceita até {limite}")
    if tipo == "string_too_short":
        return "obrigatório", "está vazio; o portal não aceita este campo vazio"
    if tipo == "sem_negativo":
        return "sem negativo", erro["msg"]
    if tipo in ("texto_breve_caracteres", "texto_breve_letra"):
        return "sem acento nem caractere especial", erro["msg"]
    if tipo == "par_es_pt":
        return "ES e PT juntos", erro["msg"]
    # Tipo que ninguém traduziu ainda: melhor a frase dele do que nada.
    return tipo or "regra do portal", f"o portal deve recusar ({erro.get('msg', '')})"


def _validar(modelo: type[BaseModel], dados: dict, *, ficha: str, indice: int,
             campo_tela: str | None = None) -> list[Problema]:
    """Valida `dados` em `modelo` e devolve os problemas na ordem dos campos."""
    try:
        modelo.model_validate(dados)
    except ValidationError as erros:
        problemas = []
        for erro in erros.errors():
            nome = (erro.get("ctx") or {}).get("campo") or erro["loc"][0]
            rotulo, interno = _CAMPOS[nome]
            if campo_tela is not None:
                rotulo = campo_tela + rotulo
            regra, mensagem = traduzir(erro)
            valor = dados.get(nome) if nome != erro["loc"][0] else erro.get("input")
            problemas.append(Problema(ficha=ficha, campo=rotulo, interno=interno,
                                      valor=_encurtar(_como_texto(valor)), regra=regra,
                                      mensagem=mensagem, indice=indice))
        return problemas
    return []


# =============================================================================
# Um `conferir_<robô>` por robô
# =============================================================================
def conferir_cria_fichas(linhas: Iterable) -> list[Problema]:
    """Criação de Fichas. `linhas`: os itens do `df_processed` (um mapeamento
    por linha: dict, ou a `Series` de `df.iterrows()`). Linha com PDM
    "NENHUM" o robô pula, e não é conferida."""
    problemas: list[Problema] = []
    for indice, linha in enumerate(linhas):
        if linha.get("pdm_escolhido") == "NENHUM":
            continue
        ficha = (_como_texto(linha.get("descricao_original")).strip()
                 or _como_texto(linha.get("descricao_curta")).strip() or f"Item {indice + 1}")
        dados = {"descricao_curta": linha.get("descricao_curta"),
                 "codigo_projeto": linha.get("codigo_projeto")}
        problemas += _validar(EntradaCriaFichas, dados, ficha=_encurtar(ficha), indice=indice)
    return problemas


def _sub(dic: Any, chave: str) -> dict:
    valor = dic.get(chave) if isinstance(dic, dict) else None
    return valor if isinstance(valor, dict) else {}


def _achatar_condicoes(ficha: dict) -> dict:
    """Só o que `UploadAutomation.processar_lista` digita, com a MESMA
    condição de lá (`sigft/services/upload_conditions.py`)."""
    dados: dict = {}
    dimensoes = _sub(ficha, "dimensoes")
    for chave in ("comprimento", "largura", "altura"):
        if chave in dimensoes:
            dados[chave] = dimensoes[chave]
    temperatura = _sub(ficha, "controle_temperatura")
    if temperatura.get("necessidade") == "SIM":
        clima, umidade = _sub(temperatura, "climatizacao"), _sub(temperatura, "umidade")
        if clima.get("ativo"):
            dados.update(temp_max=clima.get("temp_max"), temp_min=clima.get("temp_min"))
        if umidade.get("ativo"):
            dados.update(hr_max=umidade.get("hr_max"), hr_min=umidade.get("hr_min"))
    nocivo = _sub(ficha, "nocivo")
    if nocivo.get("status") == "Nocivo":
        dados.update(nocivo_es=nocivo.get("cuidado_es"), nocivo_pt=nocivo.get("cuidado_pt"))
    peso = _sub(ficha, "peso")
    for chave, nome in (("liquido", "peso_liquido"), ("bruto", "peso_bruto")):
        if chave in peso:
            dados[nome] = peso[chave]
    dados["empilhamento"] = ficha.get("empilhamento", "")
    outros = _sub(ficha, "outros_cuidados")
    if outros.get("status") == "SIM":
        dados.update(outros_es=outros.get("cuidado_es"), outros_pt=outros.get("cuidado_pt"))
    for chave in ("embalagem_transp", "posicao_icagem", "cuidad_preserv", "limpeza_secagem",
                  "ferramentas", "legislacao", "descarte"):
        for idioma in ("es", "pt"):
            nome = f"{chave}_{idioma}"
            dados[nome] = ficha.get(nome, "")  # o robô digita "" quando falta
    logistica = _sub(ficha, "logistica_reversa")
    if logistica.get("status") == "SIM":
        dados.update(logistica_es=logistica.get("logistica_reversa_es", ""),
                     logistica_pt=logistica.get("logistica_reversa_pt", ""))
    return dados


def conferir_condicoes(fichas: list) -> list[Problema]:
    """Upload Condições. `fichas`: a lista de dicts (o JSON da IA) que vai para
    `UploadAutomation.processar_lista`. Ficha = `pmib_codigo`."""
    problemas: list[Problema] = []
    for indice, ficha in enumerate(fichas):
        if not isinstance(ficha, dict):
            continue
        nome = _como_texto(ficha.get("pmib_codigo")).strip() or f"Ficha {indice + 1}"
        problemas += _validar(EntradaCondicoes, _achatar_condicoes(ficha), ficha=nome, indice=indice)
    return problemas


def conferir_tech_specs(fichas: list) -> list[Problema]:
    """Upload Tech Specs. `fichas`: `[{"METADATA": {"PMIB"...}, "DADOS_TRATADOS": [...]}]`.
    Só item com `ACAO` PREENCHER; o campo é o da `TIPO` (CHAR, NUM, INT).
    O INT se divide em mínimo/máximo como o robô divide (`split('/')`)."""
    problemas: list[Problema] = []
    for indice, ficha in enumerate(fichas):
        if not isinstance(ficha, dict):
            continue
        nome = (_como_texto(_sub(ficha, "METADATA").get("PMIB")).strip() or f"Ficha {indice + 1}")
        for item in ficha.get("DADOS_TRATADOS") or []:
            if not isinstance(item, dict):
                continue
            if _como_texto(item.get("ACAO")).strip().upper() != "PREENCHER":
                continue
            tipo = _como_texto(item.get("TIPO")).strip().upper()
            pt = _como_texto(item.get("RESPOSTA_PT_FINAL"))
            if tipo == "CHAR":
                dados = {"char_pt": pt, "char_es": item.get("RESPOSTA_ES_FINAL", "")}
            elif tipo == "NUM":
                dados = {"num": pt}
            elif tipo == "INT":
                partes = pt.split("/")
                dados = {"minimo": partes[0].strip(),
                         "maximo": partes[1].strip() if len(partes) > 1 else ""}
            else:
                continue
            caracteristica = _como_texto(item.get("CARACTERISTICA_CHAVE")).strip() or "Característica"
            problemas += _validar(EntradaCaracteristica, dados, ficha=nome, indice=indice,
                                  campo_tela=caracteristica)
    return problemas


def conferir_lmr(fichas: list) -> list[Problema]:
    """Upload LMR. `fichas`: `[(PMIB, [(código, [tags])])]`, os grupos de
    `sigft.services.lmr.agrupar_por_codigo` (quem agrupa é a tela, com a
    função do serviço: aqui não se duplica o agrupamento).

    A tag "nan" é a célula vazia da planilha (o pandas lê NaN e o
    agrupamento a transforma em texto): o robô digitaria "nan" no portal."""
    problemas: list[Problema] = []
    for indice, (pmib, grupos) in enumerate(fichas):
        nome = _como_texto(pmib).strip() or f"Ficha {indice + 1}"
        for codigo, tags in grupos:
            problemas += _validar(EntradaAplicacaoLMR, {"codigo": codigo}, ficha=nome, indice=indice)
            campo_tag = f"Tag (código {_encurtar(_como_texto(codigo))})"
            for tag in tags:
                texto = _como_texto(tag)
                if texto.strip().lower() == "nan":
                    problemas.append(Problema(
                        ficha=nome, campo=campo_tag,
                        interno="Input_Tag", valor="nan", regra="obrigatório",
                        mensagem="a célula da tag está vazia na planilha; o robô digitaria 'nan'",
                        indice=indice))
                    continue
                for p in _validar(EntradaAplicacaoLMR, {"tag": texto}, ficha=nome, indice=indice):
                    problemas.append(dataclasses.replace(p, campo=campo_tag))
            quantidade = str(len(tags))
            if len(quantidade) > MAX_DIGITOS_QUANTIDADE:
                problemas.append(Problema(
                    ficha=nome, campo="Quantidade instalada", interno="Input_QuantityInstalled",
                    valor=quantidade, regra=f"até {MAX_DIGITOS_QUANTIDADE} dígitos",
                    mensagem=f"tem {len(quantidade)} dígitos; o portal aceita até {MAX_DIGITOS_QUANTIDADE}",
                    indice=indice))
    return problemas


# =============================================================================
# Para a tela
# =============================================================================
def fichas_com_erro(problemas: Iterable[Problema]) -> set[int]:
    """Os `indice` das fichas que têm pelo menos um problema."""
    return {p.indice for p in problemas}


def resumo(problemas: list[Problema], total: int) -> str:
    """"N problema(s) em M ficha(s) de T"."""
    return f"{len(problemas)} problema(s) em {len(fichas_com_erro(problemas))} ficha(s) de {total}"


def linha_do_console(p: Problema) -> str:
    """Uma linha por problema, para o console da tela: ficha · campo (interno) · valor · mensagem."""
    return f"[!] {p.ficha} · {p.campo} ({p.interno}) · {p.valor!r} · {p.mensagem}"
