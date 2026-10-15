"""Pacote `sigft.app` — as peças da interface que não dependem de biblioteca gráfica.

A interface do SIG-FT é a Qt, em `sigft/app_qt/`. Aqui ficam o que ela usa e
não desenha nada: a paleta (`theme`), os textos dos diálogos e da atualização
(`textos_dialogos`, `atualizacao_textos`), o registro dos backends que a
splash carrega (`backends`), a memória de pastas dos diálogos de arquivo
(`file_dialogs`) e a `--conferir-pacote` (`conferencia`). Tudo só biblioteca
padrão (mais o resto do `sigft`).

Até 2026-10-15 este pacote também tinha a interface antiga (`main.py`,
`views/`, `widgets/`); ela saiu do SIG-FT, e o histórico está no repositório.
Nenhum serviço importa nada daqui (princípio nº 2 da arquitetura: "UI nunca
contém regra de negócio; serviço nunca importa interface").
"""
