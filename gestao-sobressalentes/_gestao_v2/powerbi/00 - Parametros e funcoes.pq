// =====================================================================
// SOBRESSALENTES — MODELO v2 — PARÂMETROS E FUNÇÕES
// Cada bloco abaixo é UMA consulta. No Power Query: Nova Fonte > Consulta
// Nula > Editor Avançado > colar o bloco > renomear a consulta com o nome
// indicado em "CONSULTA:". As regras espelham _scripts/regras_sobressalentes.py.
// =====================================================================


// ---------------------------------------------------------------------
// CONSULTA: PastaPMIB   (parâmetro — troque pelo caminho da SUA máquina)
// ---------------------------------------------------------------------
"C:\Users\560083605\Box\CMI - Consórcio Itaipu\11 - Ger. Engenharia\15 - PDM\SOBRESSALENTES - PMIB" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]


// ---------------------------------------------------------------------
// CONSULTA: DataReferencia   (a "data de hoje" de cada atualização)
// ---------------------------------------------------------------------
let
    Hoje = Date.From(DateTime.LocalNow())
in
    Hoje


// ---------------------------------------------------------------------
// CONSULTA: fxNorm   — maiúsculas, sem acento, espaços colapsados
// ---------------------------------------------------------------------
(valor as any) as text =>
let
    Texto = if valor = null then "" else Text.Upper(Text.Trim(Text.From(valor))),
    Trocas = {
        {"Á","A"},{"À","A"},{"Â","A"},{"Ã","A"},{"Ä","A"},
        {"É","E"},{"È","E"},{"Ê","E"},{"Ë","E"},
        {"Í","I"},{"Ì","I"},{"Î","I"},{"Ï","I"},
        {"Ó","O"},{"Ò","O"},{"Ô","O"},{"Õ","O"},{"Ö","O"},
        {"Ú","U"},{"Ù","U"},{"Û","U"},{"Ü","U"},
        {"Ç","C"},{"Ñ","N"},{"°",""},{"º",""},{"ª",""},
        {"#(lf)"," "},{"#(cr)"," "},{"#(tab)"," "}
    },
    SemAcento = List.Accumulate(Trocas, Texto, (estado, par) => Text.Replace(estado, par{0}, par{1})),
    Colapsado = Text.Combine(List.Select(Text.Split(SemAcento, " "), each _ <> ""), " ")
in
    Colapsado


// ---------------------------------------------------------------------
// CONSULTA: fxPMIB   — '4500063671.0156' | 4500063671.0156 | '45000636710156'
//                      -> '4500063671.0156'; qualquer outra coisa -> null
//                      Sequencial com 3 dígitos perdeu o zero do FIM (ljust).
// ---------------------------------------------------------------------
(valor as any) as nullable text =>
let
    Bruto = if valor = null then ""
            else if Value.Is(valor, type number) then Number.ToText(valor, "F4", "en-US")
            else Text.Remove(Text.From(valor), {" ", "#(lf)", "#(tab)"}),
    TemPonto = Text.StartsWith(Bruto, "4500063671."),
    SemPonto = (not TemPonto) and Text.StartsWith(Bruto, "4500063671"),
    Seq = if TemPonto then Text.AfterDelimiter(Bruto, "4500063671.")
          else if SemPonto then Text.Middle(Bruto, 10)
          else null,
    SoDigitos = Seq <> null and Seq <> "" and Text.Length(Seq) <= 4
                and List.AllTrue(List.Transform(Text.ToList(Seq), each List.Contains({"0".."9"}, _))),
    Valido = SoDigitos and (TemPonto or Text.Length(Seq) = 4),
    Resultado = if Valido then "4500063671." & Text.PadEnd(Seq, 4, "0") else null
in
    Resultado


// ---------------------------------------------------------------------
// CONSULTA: fxLerTabela  — abre a aba e começa na linha cujo cabeçalho
//                          contém a palavra-chave (o cabeçalho do _STATUS_PMIB
//                          não está numa linha fixa). Cabeçalhos normalizados.
// ---------------------------------------------------------------------
(conteudo as binary, aba as text, chave as text) as table =>
let
    Livro = Excel.Workbook(conteudo, null, true),
    Planilha = try Livro{[Item = aba, Kind = "Sheet"]}[Data]
               otherwise Table.SelectRows(Livro, each [Kind] = "Sheet"){0}[Data],
    Topo = Table.ToRows(Table.FirstN(Planilha, 30)),
    Posicao = List.PositionOf(List.Transform(Topo, each List.Contains(List.Transform(_, fxNorm), chave)), true),
    Resultado =
        if Posicao < 0 then #table({}, {})
        else
            let
                Corpo = Table.Skip(Planilha, Posicao),
                Promovida = Table.PromoteHeaders(Corpo, [PromoteAllScalars = true]),
                Antigos = Table.ColumnNames(Promovida),
                Novos = List.Accumulate(Antigos, {}, (acc, nome) =>
                    let
                        n = fxNorm(nome),
                        base = if n = "" then "_COL" & Text.From(List.Count(acc)) else n,
                        unico = if List.Contains(acc, base) then base & "_" & Text.From(List.Count(acc)) else base
                    in acc & {unico}),
                Renomeada = Table.RenameColumns(Promovida, List.Zip({Antigos, Novos}))
            in
                Renomeada
in
    Resultado


// ---------------------------------------------------------------------
// CONSULTA: fxData  — data do Excel (data, data/hora, número serial ou texto
//                     dd/mm/aaaa) -> date; o resto ("-", "Atualizar data") -> null
// ---------------------------------------------------------------------
(valor as any) as nullable date =>
    if valor = null then null
    else if Value.Is(valor, type date) then valor
    else if Value.Is(valor, type datetime) then Date.From(valor)
    else if Value.Is(valor, type number) then (if valor > 40000 and valor < 60000 then Date.From(valor) else null)
    else try Date.FromText(Text.Trim(Text.From(valor)), [Culture = "pt-BR"]) otherwise null


// ---------------------------------------------------------------------
// CONSULTA: fxStatus  — vocabulário único da coluna STATUS
// ---------------------------------------------------------------------
(valor as any) as text =>
let
    n = fxNorm(valor),
    Mapa = [
        #"INICIAR" = "INICIAR",
        #"FICHA CRIADA" = "FICHA CRIADA",
        #"FICHAS CRIADAS" = "FICHA CRIADA",
        #"COM O FORNECEDOR" = "COM O FORNECEDOR",
        #"EM ELABORACAO" = "EM ELABORAÇÃO",
        #"EM ANALISE IB" = "EM ANÁLISE IB",
        #"EM ANALISE ITAIPU" = "EM ANÁLISE IB",
        #"EM CORRECAO" = "EM CORREÇÃO",
        #"APROVADO" = "APROVADO",
        #"DUPLICADO" = "DUPLICADO",
        #"N/A" = "N/A"
    ]
in
    if n = "" then "SEM STATUS" else Record.FieldOrDefault(Mapa, n, n)


// ---------------------------------------------------------------------
// CONSULTA: fxTipoEntrega  — FÍSICA E DOCUMENTAL | DOCUMENTAL | TÍTULO | null
// ---------------------------------------------------------------------
(valor as any) as nullable text =>
let
    n = fxNorm(valor)
in
    if n = "FISICA E DOCUMENTAL" or n = "FISICO E DOCUMENTAL" then "FÍSICA E DOCUMENTAL"
    else if n = "DOCUMENTAL" or n = "APENAS DOCUMENTAL" then "DOCUMENTAL"
    else if n = "TITULO" or n = "CONJUNTO" or n = "CONJUNTO (TITULO)" then "TÍTULO"
    else null


// (Sem funções de dias úteis: prazo, situação e atraso da autorização
//  são calculados pelo SIG-FT e lidos do _STATUS_PMIB. Decisão de 04/10/2026.)
