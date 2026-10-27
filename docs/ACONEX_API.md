# API do Aconex — guia de acesso e integração

15/10/2026 · Luan Carlos Covalski Cozer · trazido para o SIG-FT em 27/10/2026, com o
que o teste de conexão do SIG-FT aprendeu (seção "Achados do SIG-FT", no fim)

## Visão geral

A API do Aconex é uma API REST que devolve **XML** e dá acesso, por projeto, aos mesmos dados que o usuário vê no site: documentos, correspondência, fluxos de revisão, diretório de pessoas, entre outros. O acesso é feito com um token OAuth 2.0 da Oracle, e cada chamada enxerga só o que a conta de usuário vinculada enxerga no projeto.

Este guia junta a documentação oficial da Oracle com o que o nosso app **DocManager** já validou ao vivo contra o projeto Itaipu (extração do register de documentos, download de arquivos, fluxos de trabalho e mail).

Três ideias para guardar desde o início:

- **Toda integração precisa ser registrada na Oracle** e recebe credenciais próprias (Client ID + Client Secret).
- **A API é por projeto**: quase toda URL é `https://<instância>/api/projects/<ID do projeto>/...`.
- **A permissão é a do usuário**: se a pessoa não vê um documento no site, a API também não devolve.

## O que pedir e a quem

Para chamar a API são necessários **cinco dados**. Sem qualquer um deles a autenticação ou a consulta falha.

| Dado | O que é | Quem fornece | Exemplo (projeto Itaipu) |
| --- | --- | --- | --- |
| Client ID | Identifica a integração registrada | Admin do Lobby da organização (cria o OAuth Client) | `SCP_<NOME>_ACONEX_client_APPID` |
| Client Secret | Senha da integração — nunca vai para o código | O mesmo admin, entregue por canal seguro | (sigiloso) |
| User ID | ID numérico da conta Aconex à qual a integração está vinculada | O próprio usuário (perfil no Aconex) ou o admin | `1208560183` |
| Instância | Servidor regional onde o projeto mora | Vem do endereço do site ao fazer login | `https://us1.aconex.com` |
| Project ID | ID numérico do projeto | URL do projeto no site ou `GET /api/projects` | `1207975853` |

### Passo a passo da solicitação

1. **Ter uma conta Aconex ativa no projeto**, com acesso aos módulos que a integração vai ler (Documentos, Mail, Fluxos…). A API herda exatamente essas permissões.
2. **Pedir ao Admin do Lobby da organização** (no nosso caso, quem administra o Aconex do lado CMI) que registre um **OAuth Client** em *Lobby → OAuth Clients*, com:
   - nome único e descrição do uso;
   - aplicação de recurso **Aconex APIs**;
   - tipo **User-Bound Integration** (mais simples: o client fica preso a uma conta). Para robôs agendados de longo prazo, a Oracle recomenda **Non-Interactive Integration** (exige enviar um certificado público).
3. **Receber Client ID e Client Secret** por canal seguro. Guardar o secret em variável de ambiente ou cofre do sistema, nunca no repositório.
4. **Anotar o User ID** da conta vinculada e o **Project ID**.
5. **Testar o token** (seção "Primeiro teste") antes de escrever qualquer código de negócio.

**Modelo de mensagem para o admin:** "Preciso de um OAuth Client do tipo User-Bound para a aplicação Aconex APIs, vinculado à minha conta (User ID \_\_\_\_), para ler \[documentos / mail / fluxos\] do projeto \_\_\_\_ em modo somente leitura. Uso: \_\_\_\_."

Não use **Basic Auth / Integration ID**: a Oracle anunciou a aposentadoria de todos os Integration IDs no início de 2027.

## Autenticação

O fluxo que funciona hoje no DocManager é OAuth 2.0 `client_credentials`: troca-se Client ID + Secret por um token Bearer, que vai em todas as chamadas.

1. `POST https://constructionandengineering.oraclecloud.com/auth/token`
   - Cabeçalho `Authorization: Basic base64(<client_id>:<client_secret>)`
   - Cabeçalho `Content-Type: application/x-www-form-urlencoded;charset=UTF-8`
   - Corpo: `grant_type=client_credentials`, `user_id=<User ID>`, `user_site=<instância>` (ex.: `https://us1.aconex.com`)
2. A resposta 200 traz `access_token` em JSON.
3. Toda chamada à API leva `Authorization: Bearer <access_token>` e o `Accept` certo do serviço.
4. O token expira (na prática, por volta de meia hora). Ao receber **401**, peça um token novo e repita a chamada.

**O cabeçalho `Accept` escolhe o serviço.** O Aconex roteia por *media type* versionado. Documentos aceitam `application/xml`, mas Workflows exige `application/vnd.aconex.workflow.v1+xml`. Com o `Accept` errado, a resposta é **404 `URL_UNKNOWN`**, idêntica a "esse serviço não existe". Sempre confira no guia de cada API qual media type ela pede.

## Endpoints principais

Os endpoints abaixo foram testados pelo DocManager no projeto Itaipu. Todos partem de `https://<instância>/api/projects/<ID do projeto>`. A Oracle documenta 18 APIs no total; as demais estão nos guias oficiais (ver Fontes).

| Rota | Método | `Accept` | Para que serve | Situação |
| --- | --- | --- | --- | --- |
| `/register` | GET | `application/xml` | Busca de documentos (metadados, revisões, status, campos customizados) | ✅ Em produção |
| `/register/schema` | GET | `application/xml` | Lista os campos disponíveis neste projeto (inclusive os customizados) | ✅ Validado |
| `/register/{DocumentId}/markedup` | GET | (qualquer) | Baixa o arquivo da versão (PDF etc., binário) | ✅ Em produção |
| `/workflows` | GET | `application/vnd.aconex.workflow.v1+xml` | Fluxos de revisão: etapa, responsável, prazo, atraso | ✅ Em produção |
| `/workflows/initiated-by/{us\|others}` e `/workflows/assigned-to/{us\|others}` | GET | idem | Mesmos fluxos, filtrados por quem iniciou ou com quem está | ✅ Validado |
| `/mail` | GET | `application/xml` | Correspondência e transmittals (`mail_box` obrigatório, ex.: caixa de enviados) | 🟡 Sondado |
| `/mail/schema` e `/mail/{MailId}` | GET | `application/xml` | Campos da Mail API e detalhe de um mail (anexos) | 🟡 Sondado |
| `/register/{id}/markups`, `/annotations`, `/comments` | — | — | **Não existem** (404). Anotações do site não saem pela API | ❌ |

### Parâmetros da busca de documentos (`/register`)

| Parâmetro | Uso |
| --- | --- |
| `search_query` | Filtro. Código **entre aspas** (`"6213-60-T0201-P"`) faz busca exata; sem aspas volta zero. Vazio traz tudo |
| `return_fields` | Campos separados por vírgula (`docno,title,revision,statusid,current,...`). Nomes vêm do `/register/schema` |
| `search_type` | `PAGED` para paginar |
| `page_size` / `page_number` | Tamanho só aceita 25, 50, …, 500. Outro valor → 400 |
| `sort_field` / `sort_direction` | Ex.: `docno` / `ASC`. Ordenação fixa evita perder linhas entre páginas |
| `show_document_history` | `true` traz uma linha por versão de cada revisão (histórico completo) |

Nos fluxos (`/workflows`), `page_size` aceita até 1000 e `updated_after` / `updated_before` (RFC 3339) permitem extração incremental.

## Primeiro teste

O script abaixo obtém o token e busca um documento pelo código. Se ele imprimir o título do documento, as credenciais e a rede estão certas. Requer `pip install requests` e as variáveis de ambiente `ACONEX_CLIENT_ID`, `ACONEX_CLIENT_SECRET`, `ACONEX_USER_ID` e `ACONEX_PROJECT_ID`.

```python
import base64, os, xml.etree.ElementTree as ET
import requests

INSTANCIA = "https://us1.aconex.com"
AUTH_URL = "https://constructionandengineering.oraclecloud.com/auth/token"
PROJETO = os.environ["ACONEX_PROJECT_ID"]

def obter_token():
    cred = f"{os.environ['ACONEX_CLIENT_ID']}:{os.environ['ACONEX_CLIENT_SECRET']}"
    r = requests.post(AUTH_URL, timeout=30,
        headers={"Authorization": "Basic " + base64.b64encode(cred.encode()).decode(),
                 "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        data={"grant_type": "client_credentials",
              "user_id": os.environ["ACONEX_USER_ID"],
              "user_site": INSTANCIA})
    r.raise_for_status()
    return r.json()["access_token"]

token = obter_token()
r = requests.get(f"{INSTANCIA}/api/projects/{PROJETO}/register", timeout=60,
    headers={"Authorization": f"Bearer {token}", "Accept": "application/xml"},
    params={"search_query": '"6213-60-T0201-P"',      # aspas = busca exata
            "return_fields": "docno,title,revision,statusid,current",
            "search_type": "PAGED", "page_size": 25, "page_number": 1})
print(r.status_code)
for doc in ET.fromstring(r.content).iter():
    if doc.tag.split("}")[-1] == "Document":
        print(doc.attrib.get("DocumentId"),
              {c.tag.split("}")[-1]: c.text for c in doc})
```

Se falhar:

- **401 no token**: Client ID, Secret ou User ID errados, ou o client não está vinculado a essa conta.
- **Erro de SSL ou conexão na rede corporativa**: o proxy intercepta HTTPS. O DocManager resolve com `truststore` (usa os certificados do Windows) e com o proxy do sistema.
- **200 sem documentos**: código sem aspas, ou a conta não tem acesso àquele documento.

## Possibilidades para o projeto

O que dá para construir com a API, do mais garantido ao que ainda precisa de validação. "Comprovado" significa que o DocManager já faz isso no projeto real.

| Caso de uso | API usada | Viabilidade | Observação |
| --- | --- | --- | --- |
| Extrair a base completa de documentos (todas as revisões e versões) para Excel | `/register` + `show_document_history` | Comprovado | \~80 mil linhas; precisa paginar com retentativa e checkpoint |
| Consultar o status atual de uma lista de códigos | `/register` com busca exata | Comprovado | Uma chamada por código |
| Baixar o PDF vigente de uma lista de documentos | `/register` + `/markedup` | Comprovado | Usa o `DocumentId` devolvido pela busca |
| Saber com quem está cada documento em revisão, prazo e atraso | `/workflows` | Comprovado | \~96 mil linhas; incremental por data |
| Painel de atrasos por responsável ou organização | `/workflows` | Comprovado | Status vêm em português (`Em Andamento`, `Em Atraso`) |
| Data de transmissão ("Transmitido em") de cada documento | `/mail` | Em estudo | Custo depende de o mail trazer os documentos anexados ou exigir um GET por mail |
| Cruzar o Aconex com planilhas internas, P6 ou outro sistema | `/register` + `/workflows` | Comprovado | Chaves: `TrackingId` (documento) e `WorkflowNumber` (fluxo) |
| Traduzir IDs de usuário em nomes e organizações | Directory API | A validar | `modifiedby` devolve só ID numérico |
| Enviar documentos ou correspondência (escrita) | Documents / Mail API (upload) | A validar | Exige permissão de escrita e cuidado redobrado: altera o projeto real |
| Contar as "Anotações" de uma revisão como o site mostra | — | Impossível | `numberOfMarkups` conta elementos de marcação, não anotações |

**Antes de começar um caso novo**, chame o `/schema` da API correspondente: os campos variam por projeto. No Itaipu, campos citados no guia genérico (`dateReviewed`, `plannedSubmissionDate`, `author`…) **não existem**, e há campos customizados como `Especialidad_singleSelect` e `Disciplina_singleSelect`.

## Limites e cuidados

- **Limite de requisições:** no máximo 5 por segundo e 10 simultâneas, contadas **por organização** (todas as integrações da CMI dividem a cota). Excedeu, volta **503** com `MAX_FREQUENCY_THROTTLE_LIMIT_REACHED` ou `CONCURRENCY_THROTTLE_LIMIT_REACHED`. A Oracle pede pausa mínima de 200 ms entre chamadas.
- **Retentativa:** use espera crescente (o DocManager usa 5, 15, 30 e 60 s, até 5 tentativas por página). Renovar o token num 401 não conta como tentativa.
- **Fim da paginação no register:** pedir uma página além da última devolve **400**, não lista vazia. Trate como fim normal. O total vem no atributo `TotalResults` da resposta.
- **Extrações longas:** salve um checkpoint por página para retomar depois de queda de rede, em vez de recomeçar do zero.
- **XML com namespace:** as tags vêm com prefixo `{...}`. Compare só o nome local (`tag.split("}")[-1]`).
- **Nomes de campo mudam na volta:** `registered` volta como `DateModified`; `docno` como `DocumentNumber`. Mapeie pela tag da resposta.
- **Leia tudo como texto:** datas, revisões (`0A`, `01`) e versões viram lixo se o pandas inferir tipo. Converta versão para número só na hora de ordenar.
- **Credenciais:** cada pessoa usa o próprio client. O secret fica em `.env` (fora do git) ou no cofre do sistema.
- **Somente leitura por padrão:** comece sem nenhuma chamada de escrita. Um POST errado altera o projeto real do cliente.

## Achados do SIG-FT

O "Testar conexão com o Aconex" da Conferência de Revisões
(`sigft/core/aconex/diagnostico.py`) rodou na GE em 27/10/2026, com a 1.3.1-rc.2
(perfil Luan Cozer, lista `#ST00=B01BMU10&EPB020`). O que ele ensinou, e que vale
para qualquer código novo que fale com o register:

- **`docno:` com coringa não existe.** `docno:*PB020*` voltou **HTTP 500** em 5 de 5
  tentativas, enquanto as outras buscas da mesma rodada passavam pelo mesmo proxy.
  É o servidor recusando a consulta: o limite de frequência volta 503, não 500. Para
  achar documentos por pedaço do código, busque por outro campo que filtre
  (`title:SOBRESSALENTES` trouxe 96 de 9819) e confira o código no SIG-FT.
- **`title:<palavra>` e `trackingid:<id>` filtram**, com ou sem aspas no id.
- **A busca exata não traz o histórico inteiro de uma lista.** Ela trouxe 7 versões;
  o `trackingid` do mesmo documento trouxe 15. As outras 8 são a mesma lista com
  outro código (o RDS-PP mudou). Quem quer o histórico segue o `TrackingId`.
- **Um 500 de sintaxe não passa esperando.** Com 5 tentativas e as esperas de 5, 15,
  30 e 60 s, uma sonda parada levou quase 2 minutos. O diagnóstico tenta 2 vezes; a
  extração continua com 5, porque lá o 500 pode ser passageiro.

## Fontes

- [Getting started with APIs](https://help.aconex.com/apis/getting-started-with-apis/) — Oracle
- [Create, edit, or delete an OAuth Client](https://help.aconex.com/apis/create-an-oauth-client/) — Oracle
- [What type of OAuth Integration should I register?](https://help.aconex.com/apis/what-type-of-oauth-integration-should-i-register/) — Oracle
- [Implement OAuth](https://help.aconex.com/apis/implement-smart-construction-platform-oauth/) — Oracle
- [Implement Basic Authentication](https://help.aconex.com/apis/implement-basic-authentication/) — Oracle (aposentadoria em 2027)
- [Aconex Web Services Performance Throttling](https://help.aconex.com/apis/aconex-web-services-performance-throttling/) — Oracle
- [Guias das 18 APIs (PDF)](https://help.aconex.com/aconex/aconex-apis/) — Oracle
- Repositório DocManager: `docmanager/aconex_backend.py`, `docmanager/workflows_backend.py`, `tools/probe_mail_aconex.py` e `knowledge_base_docmanager.md` §24 (testes no projeto real, jul–set/2026)

Observação: as páginas da Oracle foram localizadas por busca, mas não puderam ser abertas a partir deste ambiente. Confira-as antes de citar números exatos externamente.
