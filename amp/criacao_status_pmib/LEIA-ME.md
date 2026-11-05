# Criação do _STATUS_PMIB pelo AMP (n8n)

Para a lista de sobressalentes que ainda não tem `_STATUS_PMIB`. O workflow leva ao agente
*Spare Parts Control Sheet Builder*, criado no AMP, dois arquivos:
- o PDF da revisão atual da lista;
- o template do `_STATUS_PMIB` em branco.

O agente devolve um HTML com:
- um resumo, que inclui o que ficou "a conferir";
- a linha de revisão;
- a tabela de materiais no formato exato do template, para colar no Excel a partir da linha do
  cabeçalho.

Nada é gravado no Excel.

É o mesmo desenho da revisão das listas (`amp/revisao_de_listas/`), testado na GE em 2026-11-03.
Ele tem webhook, chave e agente próprios.

**A tela do SIG-FT que chama este workflow é a Etapa 2 do DocPack** (2026-11-04,
`sigft/services/docpack_etapa2.py`, `docs/base-conhecimento/15b-docpack-etapa2.md`). Ela manda o
PDF vigente e o `_STATUS_PMIB` em branco do dossiê e lê a tabela do HTML para gravar o
`_STATUS_PMIB` (a lista com preço saiu dela em 2026-11-05: é o módulo Lista de Preços, que a
preenche a partir do `_STATUS_PMIB`). O webhook dela fica no botão
Webhook… da aba (`AMP_CRIACAO_STATUS_PMIB_*`). O teste pelo PowerShell (abaixo) continua valendo.

| Arquivo | O quê |
|---|---|
| `agente.md` | o agente para criar no AMP: nome, descrição, goal e system prompt. **O agente se melhora no AMP**, e a cópia é atualizada depois |
| `gerar_workflow.py` | gera o `.json`: `python amp/criacao_status_pmib/gerar_workflow.py` |
| `workflow_criacao_status_pmib.json` | o workflow para importar ou colar no n8n. Não edite à mão: rode o gerador |

## Ligar (uma vez)

1. **O agente, no AMP.** Crie com o texto do `agente.md`:
   - **Agent Name**, **Description** e **Customized Goal**;
   - **Tone:** professional;
   - **System Prompt**;
   - **Data sources:** nenhum.

   Não use o **Add Optimized Query**.
2. **O workflow, no n8n.**
   1. Importe o `workflow_criacao_status_pmib.json`, ou cole o conteúdo dele no canvas.
   2. **Webhook do SIG-FT** → *Credential for Header Auth* → **Create new**:
      - Name: `X-SIGFT-Chave`;
      - Value: um valor **novo**, diferente do da revisão das listas.
   3. **AMP Agent**:
      - escolha o *Spare Parts Control Sheet Builder* na lista;
      - confira a credencial do AMP;
      - em **Add option** → **Timeout**, ponha o máximo.
   4. Salve e publique.
   5. Copie a **Production URL**. Ela termina em `/webhook/sigft-criacao-status-pmib`.

## Testar (PowerShell)

Copie para `C:\temp\amp` o PDF da revisão atual da lista e o template em branco. Troque o `XXXXXX`
e os nomes e cole no PowerShell:

```powershell
$url   = "https://ampworkflow.gevernova.net/webhook/sigft-criacao-status-pmib"
$chave = "XXXXXX"
$teste = "C:\temp\amp"
$lista = "$teste\<código>[<revisão>].pdf"
$tpl   = "$teste\<template>_STATUS_PMIB.xlsx"
$msg   = "Lista: <código>. Revisão: <revisão> (arquivo <nome do PDF>). Template: <nome do template>. Data de hoje: <dd/mm/aaaa>. Crie o controle."
curl.exe -sS -w "`nHTTP %{http_code} em %{time_total} s`n" -H "X-SIGFT-Chave: $chave" --form-string "modo=ping" $url
curl.exe -sS --max-time 900 -o "$teste\criacao_amp.json" -w "HTTP %{http_code} em %{time_total} s`n" -H "X-SIGFT-Chave: $chave" --form-string "modo=criar" --form-string "mensagem=$msg" -F "lista=@$lista" -F "template=@$tpl" $url
(Get-Content "$teste\criacao_amp.json" -Raw -Encoding UTF8 | ConvertFrom-Json).html | Set-Content "$teste\criacao_amp.html" -Encoding UTF8
Start-Process "$teste\criacao_amp.html"
```

O ping responde em cerca de 1 s. A criação leva alguns minutos. As respostas e os sintomas são os
da revisão das listas, com a tabela no `amp/revisao_de_listas/LEIA-ME.md`:
- 403: chave errada;
- 404: workflow não publicado ou Test URL;
- 400, etapa `arquivos`: chegou menos de 2 arquivos;
- 502, etapa `agente`: o agente falhou.

## Melhorar o agente

As instruções moram no AMP. Corrija o system prompt lá e copie o texto novo para o `agente.md`.
Não precisa reimportar o workflow.
