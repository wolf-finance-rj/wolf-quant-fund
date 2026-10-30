# Deploy manual — Server4You VPS

Este projeto ainda não é uma API ou um serviço com healthcheck. O deploy disponibiliza
o contêiner Python para comandos supervisionados; **não** executa estratégias,
backtests ou fechamento mensal automaticamente.

## Preparação do servidor (uma vez)

Acesse a VPS por SSH com uma conta administrativa existente. Instale Git e Docker
Engine com o plugin Compose de acordo com a documentação oficial do Debian e do Docker.
Configure um usuário de deploy com acesso mínimo necessário ao diretório da aplicação
e ao Docker. **Atenção:** acesso ao daemon do Docker equivale a privilégios elevados
no host; prefira um usuário isolado e não reutilize essa chave para outras aplicações.

Crie e configure o diretório do projeto no servidor:

```bash
sudo mkdir -p /opt/wolf-quant-fund
sudo chown "$USER":"$USER" /opt/wolf-quant-fund
git clone https://github.com/wolf-finance-rj/wolf-quant-fund.git /opt/wolf-quant-fund
cd /opt/wolf-quant-fund
mkdir -p data
cp .env.example .env
chmod 600 .env
# Edite .env e defina WQF_ENV=production, além de outras variáveis necessárias.
docker compose -f compose.yaml -f compose.prod.yaml config --quiet
```

**Não** apague o diretório `data/` em um deploy. Ele reside no host e é
montado no contêiner. Faça backup antes de alterações estruturais.

## Chave SSH de deploy

Na sua máquina, gere uma chave **dedicada** ao workflow:

```bash
ssh-keygen -t ed25519 -f ./wolf_quant_deploy -C wolf-quant-fund-deploy
```

Adicione a chave **pública** (`wolf_quant_deploy.pub`) ao
`~/.ssh/authorized_keys` do usuário de deploy **no servidor**.
Guarde a chave privada fora do repositório. Não reutilize a chave administrativa.

Confira a identidade do host SSH com o console/painel do provedor ou outro canal
confiável e só então registre a linha de chave pública de host apropriada em
`VPS_KNOWN_HOSTS`. Não confie cegamente em uma saída de `ssh-keyscan`.

## Configuração GitHub

Em **Settings → Environments**, crie `production` e, se disponível, habilite
revisores obrigatórios e limite de branch para `main`.

Em **Settings → Secrets and variables → Actions**, configure:

| Tipo | Nome | Valor |
|---|---|---|
| Secret | `VPS_HOST` | IP ou hostname da VPS |
| Secret | `VPS_USER` | Usuário SSH de deploy |
| Secret | `VPS_SSH_KEY` | Conteúdo integral da chave privada dedicada |
| Secret | `VPS_KNOWN_HOSTS` | Linha(s) de chave pública do servidor SSH verificadas |
| Variable | `VPS_PORT` | Porta SSH (opcional; padrão 22) |

Defina os segredos no ambiente `production` ou no repositório.
Nunca use as credenciais do painel Server4You em um workflow.

## Execução

1. Faça merge da PR na `main` depois do CI.
2. Abra **Actions → Deploy VPS (manual) → Run workflow**, usando `main`.
3. Acompanhe a execução e confira o contêiner pela SSH.

O workflow exige que `origin/main` no momento do deploy seja o commit da
execução. Se outros commits entrarem na `main`, rode o workflow novamente.
Ele realiza `git fetch`, checkout do SHA exato, build e `up -d` apenas do
serviço `app`. Não remove volumes e não executa comandos financeiros.

O deployment inicial não inclui rollback automático nem healthcheck de aplicação.
Se o container falhar, verifique `docker compose ... ps` e logs no servidor
antes de tentar novamente. Para funcionamento produtivo posterior, adicione um
entrypoint real, healthcheck e uma estratégia de rollback com releases imutáveis.

## Teste de operação supervisionada

```bash
cd /opt/wolf-quant-fund
docker compose -f compose.yaml -f compose.prod.yaml ps app
docker compose -f compose.yaml -f compose.prod.yaml exec app python --version
```

### Notas de segurança e capacidade

- A VPS possui CPU e RAM limitadas: builds e análises grandes podem exigir otimização.
- O arquivo `compose.yaml` original faz bind mount do código e dos dados;
  o deploy preserva esse comportamento por enquanto.
- O arquivo `.env` permanece somente no servidor, nunca em GitHub.
- Proteja SSH por firewall, utilize uma conta separada e monitore espaço em disco.
- Como o serviço só mantém um ambiente Python pronto, `ps` não comprova
  saúde funcional de uma API ou de um pipeline.
