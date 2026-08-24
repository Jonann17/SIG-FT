# Como eu passo a OLHAR o portal, em vez de adivinhá-lo

> Criado em 2026-08-24, depois de uma semana em que o módulo de ficha duplicada
> não fechava. A causa não era o módulo.

## O problema, em uma linha

A sessão do Claude Code **na web** roda num contêiner na nuvem que **não alcança
o portal**:

```
$ curl https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList
curl: (56) CONNECT tunnel failed, response 403
```

E mesmo que alcançasse, o portal exige login corporativo. Consequência: naquela
sessão, tudo que eu sei do portal chega por recorte — um HTML colado, um log de
execução, um print. Eu formulo uma hipótese, você roda, o log mostra um pedaço,
a hipótese cai, eu formulo outra. **Uma rodada sua por pergunta minha.** Foi
isso que consumiu a semana, não a dificuldade da tarefa.

O sintoma que disfarçava o problema: 2700 testes verdes. Eles rodam contra
dublês escritos por mim, então o que passava era a minha ideia do portal. O
único oráculo é o portal.

## A solução: sessão LOCAL com o navegador na mão

Rodando o Claude Code **na sua máquina**, com um servidor MCP de navegador
ligado ao Chrome onde **você já fez login**, eu deixo de pedir log: eu navego,
leio o DOM, clico, confiro, conserto — no mesmo minuto.

### 1. Chrome com depuração remota

O `--remote-debugging-port` é ignorado no perfil padrão do Chrome; **a pasta de
perfil separada é obrigatória**, não é preferência.

```bat
"C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --remote-debugging-port=9222 ^
  --user-data-dir="C:\temp\chrome-pmib"
```

Faça o login no PMIB nessa janela. O perfil fica em `C:\temp\chrome-pmib`, então
o login **sobrevive** entre sessões — só é preciso repetir quando ele expirar.

### 2. Ligar o MCP ao Chrome que já está aberto

Na pasta do projeto:

```bat
claude mcp add playwright -- npx @playwright/mcp@latest --cdp-endpoint http://localhost:9222
```

Alternativa, se a TI não deixar subir o Chrome com flag: a **extensão do
Playwright** no Chrome que você já usa, e aí `--extension` no lugar do
`--cdp-endpoint`. Mesma coisa do ponto de vista do trabalho.

### 3. Abrir o Claude Code local

```bat
claude
```

E dizer o que atacar. A partir daí eu tenho `browser_snapshot`,
`browser_evaluate`, `browser_click`, `browser_hover`, `browser_fill_form` e
`browser_generate_locator` — este último resolve sozinho o casamento
RÓTULO → CAMPO que virou o gargalo das Condições.

## O que muda na prática

| Antes (sessão na web) | Depois (sessão local) |
|---|---|
| Eu peço um HTML; você cola | Eu leio o DOM |
| Eu suponho o seletor; testo num dublê | Eu gero o seletor do elemento real |
| Uma rodada sua por hipótese minha | Eu testo a hipótese na hora |
| Erro aparece na sua próxima rodada | Erro aparece em segundos |
| Teste verde = minha ideia do portal | Teste verde + prova no portal |

## As cinco perguntas abertas do módulo

Todas se respondem numa sessão local, em minutos, sem você fazer nada além do
login:

1. **Quais radios correspondem a "Horizontal", "Sem necessidade", etc.** São 19
   campos e é o que impede CONDIÇÕES de salvar (`Por favor, verifique os
   campos`). Fonte: a ficha alvo em edição.
2. **Os campos `..._ES` são `required`?** Decide se a seção fecha sem eles.
   Mesma tela.
3. **Por que o `+` não confirma a referência?** O campo está limpo
   (`value="RTC-45'D1"`, sem `not-valid`) e o botão habilitado — a hipótese da
   validação já caiu. Fonte: a seção de fabricantes logo após o clique.
4. **`PDM.9900.000` está no catálogo deste usuário?** Fonte: o combo aberto e
   filtrado.
5. **Como reler a tabela de documentos** sem depender de um id gerado pelo
   OutSystems.

## Regra que fica

Enquanto o trabalho for de **portal**, é sessão local. Sessão na web serve para
o que não depende do portal: planilha, prompts de IA, refatoração, testes.
Misturar as duas foi o erro que custou a semana.
