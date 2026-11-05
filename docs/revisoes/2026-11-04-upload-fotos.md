# Revisão do Upload de Fotos (PR #38) — 2026-11-04

Revisão adversarial do módulo **4.5 Upload de Fotos** (Jpcostenar0), depois do merge
na branch oficial (`9ca0c7d`). Arquivos lidos: `sigft/services/upload_fotos.py`,
`sigft/app_qt/views/upload_fotos.py`, as mudanças do PR em `core/excel/status_sheet.py`,
`core/excel/cirurgico.py`, `core/rpa/portal.py`, `core/rpa/engine.py`/`playwright_engine.py`,
`core/rpa/seletores_duplicada.py`, `services/duplicadas_imagens.py`, `services/duplicadas_extrator.py`
e os testes.

Nada aqui foi exercido contra o portal: a sessão é na web (CLAUDE.md, "Trabalho de PORTAL
exige sessão LOCAL"). Seletores e fluxos do portal **não** foram mudados.

## Corrigido nesta revisão

| # | Achado | Caminho realista | Correção |
|---|---|---|---|
| 1 | **Modo "substituir" subia por cima das fotos antigas quando o portal era mais lento que a espera.** `fotos_ao_abrir` desiste depois de `Esperas.tabela` leituras vazias e devolve 0; a ficha passa por "sem fotos"; as linhas antigas chegam logo depois; `antes = fotos_na_ficha()` já as conta, e a conferência final (`>= antes + len(caminhos)`) passa. Resultado: ✅ e `COMPLETO`/`INCOMPLETO` no `_STATUS_PMIB` com as fotos antigas ainda na ficha. | Lote no PMIB lento (o de 2026-11-03 já mostrou o portal estourando os tempos) com "Velocidade do portal" em Normal ou Lento. | `processar_ficha`: quando a ficha devia estar vazia (pareceu sem fotos, ou as antigas foram excluídas) e a tabela mostra fotos antes do envio, a ficha para com o motivo, **sem enviar nada**. "Adicionar" não é afetado. Teste: `test_substituir_nao_sobe_por_cima_de_fotos_que_chegaram_depois_da_espera` (falhava antes). |
| 2 | A tela não estava na guarda de ciclos de referência. | Uma tela com ciclo morre pelo coletor, que pode passar no meio de um `paintEvent` (a queda da Busca PMIB). Hoje ela **não** tem ciclo (medido). | `UploadFotos` entrou em `SEM_CICLO` (`tests/test_qt_tela_morre_sem_coletor.py`), para não voltar. |
| 3 | O módulo não tinha linha no `CHANGELOG.md`. | As notas da próxima versão não diriam que o módulo existe. | Linha "Upload de Fotos" no bloco 1.3.3. |

## Não corrigido (para o JP decidir; precisa de sessão local ou é escolha de produto)

| # | Achado | Por que ficou |
|---|---|---|
| 4 | `excluir_todas` para em `MAX_EXCLUSOES = 30`. Ficha com mais de 30 fotos: exclui 30, devolve `False` e a ficha fica **sem parte das fotos antigas e sem as novas**. | Ficha com mais de 30 fotos parece improvável; o teto existe para lixeira que não exclui. Se for possível, contar antes e recusar a ficha sem excluir nada quando passar do teto. |
| 5 | `PALAVRA_DA_SECAO["Documentos e imagens"]` passou de `"imagem"` para `"image"` (para casar o plural "imagens"). Vale também para as **Fichas Duplicadas**. | Seguro em si (`mensagem_confirma_secao` ainda exige o marcador de sucesso), mas é mudança de comportamento de outro módulo, feita junto: vale conferir num lote real das Duplicadas. |
| 6 | Os seletores da tabela de imagens (`Pré-visualização`, `Arquivos anexados`, `fa-trash`) e o `XPATH_IMAGENS_CANCELAR` saíram de capturas, não do DOM (aviso no próprio módulo). | Portal: só numa sessão local com o navegador ligado (`docs/OLHAR_O_PORTAL.md`). |
| 7 | PARAR enquanto a janela de escolha das fichas ou o "Começar?" estão abertos não faz nada (`self.automacao` ainda é `None`); só vale depois do login. | Inofensivo (nada foi tocado ainda, e a pessoa pode fechar a janela); fica anotado. |
| 8 | No modo "adicionar", uma foto nova com o MESMO nome de uma antiga sai como "foto(s) repetida(s)" (❌), embora o envio tenha entrado. | Comportamento defensável (a ficha fica com duas linhas iguais e a pessoa precisa olhar); só o texto poderia dizer que pode ser a antiga. |

## Conferido e sem problema

- Ligação foto → ficha pelos 4 últimos dígitos: `normalize_pmib` dá 4 casas; código com 5 casas (`.10071`) também termina em `0071` e cai como **ambíguo** com `.0071`, nunca adivinhado.
- Exceção depois de subir: `processar` a captura por ficha e a ficha não é marcada no `_STATUS_PMIB`; rodar de novo no modo "substituir" exclui e sobe de novo, sem duplicar.
- `_STATUS_PMIB`: grava pelo editor cirúrgico (`StatusPMIB.salvar` → `cirurgico.gravar_celulas`), nunca `wb.save`; Excel aberto → `PermissionError` tratado, a marcação não é dada como salva.
- Threads: a escolha das fichas e a pergunta por ficha abrem na thread da interface (`_na_interface_e_esperar`); o worker não toca widget.
- Textos: `t()` com es/en (o `test_textos_da_interface` cobre); cabe em 1366×768 (rolável, `test_qt_tela_1366`).
