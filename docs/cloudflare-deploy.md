# Deploy Cloudflare

O workflow cloudflare.yml valida o Worker em PRs, sem credenciais de produção. Após os checks, publica somente pushes na main ou execução manual na main; mantém os workflows existentes. Deploys de produção são serializados.

Diretório: .. Comando: uv run --locked pywrangler deploy. As validações incluem uv sync --locked --extra test; uv run --locked pytest -q; uv run --locked pywrangler deploy --dry-run. A instalação usa o lockfile existente quando disponível.

CLOUDFLARE_API_TOKEN fica nos secrets do repositório; CLOUDFLARE_ACCOUNT_ID é uma variável pública. O token é restrito à conta Astro, com Workers Scripts: Edit, e expira em 25/10/2027. Os secrets de aplicação, Hyperdrives e demais bindings existentes permanecem no Cloudflare; este workflow não importa arquivos .env nem provisiona conectores.

A configuração entra em vigor após a revisão e o merge desta PR. Nenhum deploy ocorre ao atualizar a branch da PR.

workers-py permanece somente no grupo dev: é ferramenta de empacotamento e não deve entrar nas dependências WebAssembly da aplicação. O lockfile foi atualizado mantendo as versões já fixadas.
