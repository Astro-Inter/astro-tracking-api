# Astro — API de tracking

Fluxo: React → `dataLayer` → Google Tag Manager → `POST /api/eventos` → PostgreSQL.

A API recebe um evento por requisição, valida o contrato e confirma a gravação com HTTP 201.
As outras rotas são `GET /health` (processo ativo) e `GET /health/db` (conexão e colunas da tabela).
Não há consultas públicas dos eventos. O Swagger está em `/docs`.

## Banco e contrato

Usa a tabela `eventos_astro` existente, com as onze colunas do DDL informado.
Não cria nem altera tabelas automaticamente. O `BIGSERIAL` gera `id_evento`;
o INSERT preenche `criado_em` com `CURRENT_TIMESTAMP AT TIME ZONE 'UTC'`,
porque a tabela não possui DEFAULT para esse campo. A resposta representa esse horário com `Z`.
`criado_em` é o horário de recebimento/gravação, não o instante original do clique.

O JSON aceita `firebase_uid`, `tipo_evento`, `nome_botao`, `nome_tela`, `contexto_tela`,
`nome_dialog`, `dialog_clicado`, `showcase_click` e `nome_showcase`.
`id_evento` e `criado_em` são controlados pela API/banco.

| Tipo | Campos específicos obrigatórios |
| --- | --- |
| `screen_view` | nenhum |
| `button_click` | `nome_botao` |
| `dialog_viewed` | `nome_dialog` |
| `dialog_clicked` | `nome_dialog`, `dialog_clicado` |
| `showcase_viewed` | `nome_showcase` |
| `showcase_clicked` | `nome_showcase`, `showcase_click` |
| `conversation_started` | nenhum |
| `conversation_message_sent` | nenhum |
| `conversation_message_received` | nenhum |

Todos podem informar `nome_tela` e `contexto_tela`. Os campos de componentes não relacionados
ao tipo devem ser omitidos ou `null`. Cliques guardam a ação como texto, não booleanos.
`firebase_uid` é opcional para permitir tracking antes do login; após o login envie o UID atual,
e após logout envie `null`. A API não verifica o UID com Firebase: ele é um atributo de analytics,
não uma prova de autenticação.

Nomes e UID aceitam até 255 caracteres e não aceitam texto vazio. `contexto_tela` aceita até
8.000 caracteres. Não envie mensagens da conversa, senhas ou valores dos campos de login.
Campos extras e combinações inválidas retornam 422. Falhas de banco retornam 503.

Exemplo:

```json
{
  "firebase_uid": null,
  "tipo_evento": "button_click",
  "nome_tela": "login",
  "nome_botao": "entrar"
}
```

O DDL enviado não declara PRIMARY KEY/UNIQUE em `id_evento`. A API funciona sem isso,
mas a sequência BIGSERIAL sozinha não impede IDs duplicados inseridos manualmente.
Uma chave primária é recomendada após conferir os dados existentes.
A tabela também não tem chave de idempotência: enviar o mesmo evento duas vezes grava duas linhas.

## Executar localmente

Python 3.13 ou posterior:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install ".[local,test]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Preencha as credenciais em .env; preserve seu .env se ele já existir.
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8080
```

`DB_SSL=prefer` é o padrão local. Para conexão direta de produção, use a política TLS exigida
pelo seu provedor (por exemplo `verify-full`). No Worker, a conexão usa os bindings do Hyperdrive.

Teste o POST:

```powershell
$evento = @{ tipo_evento = 'button_click'; nome_tela = 'login'; nome_botao = 'entrar'; firebase_uid = $null } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://localhost:8080/api/eventos' -ContentType 'application/json' -Body $evento
```

Docker é uma alternativa para rodar a API localmente:

```powershell
docker build -t astro-tracking .
docker run --rm -p 8080:8080 --env-file .env astro-tracking
```

Se PostgreSQL estiver no host, use `DB_HOST=host.docker.internal` para esse container.
O projeto não inclui Docker Compose nem inicializador de banco.

## Google Tag Manager

Em cada interação, o frontend faz um único push com um novo objeto completo do evento:

```javascript
window.dataLayer = window.dataLayer || [];
window.dataLayer.push({
  event: 'button_click',
  astro_event: {
    firebase_uid: usuarioAtual ? usuarioAtual.uid : null,
    tipo_evento: 'button_click',
    nome_tela: 'login',
    nome_botao: 'entrar'
  }
});
```

1. Crie a variável da camada de dados **DLV - astro_event**, nome `astro_event`, **versão 1**.
   Essa versão substitui o objeto em vez de mesclar campos do evento anterior.
2. No container GTM do frontend, configure uma tag que envie o objeto `astro_event`
   como JSON para `POST /api/eventos`, com `Content-Type: application/json`.
   Use a URL da API local ou o domínio HTTPS do Worker. A tag é mantida fora deste repositório.
3. Configure um acionador de evento personalizado com regex:
   `^(screen_view|button_click|dialog_viewed|dialog_clicked|showcase_viewed|showcase_clicked|conversation_started|conversation_message_sent|conversation_message_received)$`.
4. Confira no Preview do GTM e na aba Network que cada interação produz um POST com HTTP 201.
   Evite habilitar simultaneamente outra tag ou chamada direta do frontend para o mesmo evento.

A tag envia somente os campos da tabela, sem `event` e metadados `gtm.*`.
O `keepalive` ajuda a enviar durante navegação, mas não garante entrega; bloqueadores,
rede e limites do navegador ainda podem causar perda. Não há retry automático, pois sem
idempotência ele pode duplicar eventos. Tags de consentimento devem usar as APIs próprias do GTM.

Em `CORS_ALLOWED_ORIGINS`, configure as origens do **frontend** (protocolo, domínio e porta),
não o domínio do GTM. CORS controla acesso pelo navegador e não autentica o remetente.
Se for necessário comprovar identidade, o contrato deverá incluir verificação de token Firebase.

Referência: [dataLayer e eventos do GTM](https://developers.google.com/tag-platform/tag-manager/datalayer).

## Cloudflare Workers + Hyperdrive

Mantém FastAPI em Python Workers e usa `asyncpg` com Hyperdrive para o PostgreSQL existente.
O Dockerfile é para execução convencional; o Worker usa `src/worker.py` e o adaptador ASGI da Cloudflare.
Não é um deploy de Uvicorn no Cloudflare Pages.

1. Instale `uv` e use Node.js compatível com o Wrangler. As dependências do Worker estão no `pyproject.toml`.
   No Windows, execute o pywrangler em um clone/cópia com caminho simples, como
   `C:\dev\astro-tracking`: a versão validada falhou no caminho deste projeto por causa
   do `&` em `Instituto J&F`. O dry-run passou em uma pasta temporária sem esse caractere.
2. No painel da Cloudflare, crie um Hyperdrive apontando para o PostgreSQL, com credenciais
   próprias da API. O banco deve ser acessível pelo Hyperdrive; `localhost` não funciona após deploy.
   Bancos privados exigem configurar a conectividade apropriada antes.
3. Em `wrangler.jsonc`, substitua `SUBSTITUA_PELO_ID_DO_HYPERDRIVE` pelo ID real.
   Troque `CORS_ALLOWED_ORIGINS` pelas origens do frontend de produção.
   As credenciais do banco ficam no Hyperdrive, fora desse arquivo e do GTM.
4. Autentique e publique quando essas configurações estiverem prontas:

```powershell
uv run pywrangler login
uv run pywrangler deploy
```

Para desenvolvimento do Worker com banco de testes:

```powershell
# Use exclusivamente credenciais de um PostgreSQL de testes.
$env:CLOUDFLARE_HYPERDRIVE_LOCAL_CONNECTION_STRING_HYPERDRIVE = 'postgresql://usuario:senha@localhost:5432/astro_test'
uv run pywrangler dev
```

O Worker abre e fecha uma conexão por requisição; Hyperdrive mantém o pool até o PostgreSQL.
Não depende de inicialização de engine pelo lifespan nem compartilha conexões entre requisições.
O código está em `src/` para que o empacotamento não inclua testes, caches ou ambientes locais.
A configuração usa `compatibility_date` de 02/10/2026, posterior ao mínimo de 08/09/2026
documentado para Hyperdrive com Python Workers.

Como o endpoint de tracking é público, configure rate limiting na Cloudflare de acordo com o tráfego
esperado. Uma chave secreta colocada em uma tag GTM não autentica usuários, porque fica visível no navegador.
Após publicar, valide `/health/db`, preflight CORS e um POST pelo frontend real.

Referências oficiais: [FastAPI em Python Workers](https://developers.cloudflare.com/workers/languages/python/packages/fastapi/),
[Hyperdrive em Python Workers](https://developers.cloudflare.com/hyperdrive/examples/python-workers/).

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Os testes HTTP usam conexão simulada: validam contrato, parâmetros SQL, erros e ciclo da conexão.
Para confirmar a persistência em PostgreSQL real, configure explicitamente um banco de testes:

```powershell
$env:TEST_DATABASE_URL = 'postgresql://usuario:senha@localhost:5432/astro_test'
.\.venv\Scripts\python.exe -m pytest tests/test_postgres.py -q
```

Esse teste cria um schema temporário com exatamente o DDL informado, sem PK nem DEFAULT de
`criado_em`, verifica os registros persistidos e remove somente esse schema ao terminar.
Veja [VALIDACAO.md](VALIDACAO.md) para resultados e limites da revisão.
