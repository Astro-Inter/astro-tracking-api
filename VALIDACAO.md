# Revisão de 02/10/2026

## Problemas encontrados e corrigidos

| Problema | Efeito anterior | Correção |
| --- | --- | --- |
| `firebase_uid` ausente do schema de entrada | UID enviado pelo GTM era rejeitado; sem UID o modelo exigia coluna não nula | UID opcional no contrato e no INSERT, permitindo eventos antes do login |
| `criado_em` dependia de um DEFAULT ausente no DDL | INSERT podia gravar NULL; resposta exigia datetime e podia falhar após a gravação | Horário UTC explícito no INSERT; resposta com `Z` |
| Modelo ORM pressupunha PK e NOT NULL que não constam do DDL | Modelo e tabela divergiam | INSERT parametrizado com asyncpg, sem depender dessas constraints |
| Listagem e busca sem uso no repositório | Código morto e testes de rotas inexistentes | API limitada à ingestão e saúde |
| Testes dependiam de `examples/` ausente | 15 falhas na suíte original | Cenários autocontidos e teste PostgreSQL opt-in |
| Dockerfile copiava `database/` ausente | Build falhava | Dockerfile usa pacote Python real |
| README citava frontend, compose e migrações ausentes | Instruções não executáveis | Guia refeito para os arquivos presentes |
| Inicialização via engine/lifespan não tratava bindings Workers | Deploy convencional não era uma configuração de Worker | Entrypoint ASGI, bindings Hyperdrive e conexão por requisição |
| `requirements.txt` rejeitado pelo pywrangler atual | Empacotamento abortava | Dependências consolidadas em pyproject.toml |
| Empacotamento com entrypoint na raiz incluía caches Python | Bundle carregava arquivos locais desnecessários | Código em src e exclusão de bytecode das dependências |

## Verificações executadas

- Antes das mudanças: 15 testes falharam, 12 passaram.
- Depois: **58 testes Python passaram; 1 teste PostgreSQL foi ignorado por falta de TEST_DATABASE_URL**.
- Contrato dos nove tipos, UID ausente/presente, campos extras, componentes incompatíveis,
  tamanho de contexto e caractere NUL verificados.
- Payload inválido retorna 422 sem abrir conexão com o banco.
- SQL parametrizado, timestamp UTC, tratamento de erro de conexão/INSERT e fechamento
  das conexões verificados com banco simulado.
- CORS de preflight e de respostas de erro verificado.
- Aplicação ASGI do Worker verificada com bindings e SDK simulados, incluindo lifespan sem env.
- A tag GTM e seu teste JavaScript foram removidos do projeto a pedido do usuário;
  a configuração do container GTM é mantida no projeto do frontend.
- Instalação local via pyproject.toml e criação do wheel aprovadas; pip check sem dependências quebradas.
- Compilação Python em src e tests aprovada.
- Dependências resolvidas com uv.lock.
- Empacotamento Cloudflare **dry-run aprovado** com pywrangler 1.17.6 e Wrangler 4.147.0.
  Executado em uma cópia temporária sem .env, devido ao bug com `&` no caminho original.
  Bundle final: 10.581,57 KiB bruto / 2.608,16 KiB gzip (~2,55 MiB compactado).

## Limites e pendências de deploy

- Não houve conexão ou escrita no banco existente nem alteração do DDL.
- O Docker daemon está parado; build Docker e teste de integração em PostgreSQL real não executados.
- O dry-run confirma o empacotamento, não a execução remota nem a conectividade real do Hyperdrive.
- Antes de publicar, preencher o ID real do Hyperdrive, origens CORS de produção e URL da tag GTM.
- Validar rede do banco, /health/db, CORS e POST no ambiente publicado.
- BIGSERIAL não declara PRIMARY KEY/UNIQUE; avaliar chave primária após conferir os dados existentes.
- UID do navegador não é autenticado. O endpoint público precisa de controle de volume na Cloudflare.
- A tabela não permite deduplicação por identidade do evento; reenvios podem duplicar linhas.
- `criado_em` mede gravação no servidor. Entrega via GTM/keepalive é best effort.
- A suíte emite um aviso de depreciação do TestClient/Starlette sobre httpx; os testes passaram.

As instruções de execução, GTM e deploy estão em [README.md](README.md).
