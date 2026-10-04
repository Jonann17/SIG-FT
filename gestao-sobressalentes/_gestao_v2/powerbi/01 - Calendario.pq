// Sem tabela de feriados: o calendário dos 15 dias úteis vive no SIG-FT (decisão de 04/10/2026).

// =====================================================================
// CONSULTA: Calendario   (marque como tabela de datas: Ferramentas de tabela >
//                         Marcar como tabela de datas > coluna Data)
// =====================================================================
let
    Inicio = #date(2024, 1, 1),
    Fim = #date(2028, 12, 31),
    Datas = List.Dates(Inicio, Duration.Days(Fim - Inicio) + 1, #duration(1, 0, 0, 0)),
    Tabela = Table.FromList(Datas, Splitter.SplitByNothing(), type table [Data = date]),
    ComAno = Table.AddColumn(Tabela, "Ano", each Date.Year([Data]), Int64.Type),
    ComMes = Table.AddColumn(ComAno, "Mes", each Date.Month([Data]), Int64.Type),
    ComMesNome = Table.AddColumn(ComMes, "Mes Ano", each Text.Proper(Date.ToText([Data], "MMM/yy", "pt-BR")), type text),
    ComMesInicio = Table.AddColumn(ComMesNome, "Inicio do Mes", each Date.StartOfMonth([Data]), type date),
    ComSemana = Table.AddColumn(ComMesInicio, "Inicio da Semana", each Date.StartOfWeek([Data], Day.Monday), type date)
in
    ComSemana
