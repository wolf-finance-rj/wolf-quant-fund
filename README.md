# Wolf Quant Fund

Fundo quantitativo **simulado** da **Wolf Finance**, com capital fictício aplicado ao mercado de ações brasileiro. Este repositório contém o código que baixa dados, testa estratégias e calcula os resultados do fundo — **nenhum dinheiro real é movimentado**.

> [!TIP]
> **Primeira vez aqui?** O caminho principal usa Docker Compose: siga os [Primeiros passos](#primeiros-passos) e depois leia [Como contribuir](#como-contribuir). Você não precisa saber finanças nem dominar Git para pegar sua primeira tarefa.

## Índice

- [O que é este projeto](#o-que-é-este-projeto)
- [Primeiros passos](#primeiros-passos)
- [Comandos do dia a dia](#comandos-do-dia-a-dia)
- [Como o projeto está organizado](#como-o-projeto-está-organizado)
- [Como contribuir](#como-contribuir)
- [Convenções do projeto](#convenções-do-projeto)
- [Problemas comuns](#problemas-comuns)
- [Sobre o fundo](#sobre-o-fundo)
- [Glossário](#glossário)
- [Onde aprender mais](#onde-aprender-mais)

---

## O que é este projeto

Em palavras simples: **este repositório é o código do fundo**. Ele pega dados do mercado brasileiro, aplica estratégias de investimento e mostra como o fundo teria se saído.

O código é um pipeline de 4 etapas:

| Etapa | O que faz |
|---|---|
| 1. Limpeza | Organiza os dados brutos de mercado: preços, volumes, proventos e CDI. |
| 2. Estratégias | Transforma os dados em sinais de compra e venda (momentum, pairs trading). |
| 3. Consolidação | Monta o portfólio do fundo, aplicando alocação, caixa e regras de risco. |
| 4. Métricas | Calcula retorno, volatilidade, Sharpe, drawdown, gráficos e a carta mensal. |

Cada etapa é um módulo independente. A execução é **manual e supervisionada** por alguém da equipe — nada roda sozinho em produção.

---

## Primeiros passos

### 1. Instale as ferramentas

| Ferramenta | Para quê | Onde baixar |
|---|---|---|
| **Docker + Compose** (v2.24 ou mais novo) | rodar o projeto inteiro em container — jeito principal | <https://docs.docker.com/get-docker/> |
| **Git** | baixar e versionar o código | <https://git-scm.com/downloads> |
| **VS Code** (recomendado) | editar o código dentro do container | <https://code.visualstudio.com/> |

> [!NOTE]
> Com Docker você **não precisa instalar Python nem uv** na máquina: a imagem já traz tudo na versão correta.

> [!TIP]
> No Windows, use o **WSL 2** com Docker Desktop — o desempenho e os comandos ficam bem melhores do que no Git Bash.

### 2. Baixe o projeto e suba o ambiente

```bash
# baixa o repositório para a sua máquina
git clone https://github.com/wolf-finance-rj/wolf-quant-fund.git

# entra na pasta do projeto
cd wolf-quant-fund

# constrói a imagem e sobe o sandbox de desenvolvimento
docker compose up -d app

# roda todos os checks (lint, formatação e testes)
docker compose run --rm checks
```

Saída esperada no final: `All checks passed!` e `1 passed`.

Se quiser criar seu arquivo de variáveis de ambiente (opcional):

```bash
cp .env.example .env
```

### 3. Abra o projeto dentro do container (recomendado)

1. Instale a extensão **Dev Containers** no VS Code.
2. Abra a pasta do projeto e rode o comando **Dev Containers: Reopen in Container** (`Ctrl+Shift+P`).
3. O VS Code entra no serviço `app` com Python, dependências e Ruff já configurados — o terminal integrado já está dentro do container.

A configuração fica em [`.devcontainer/devcontainer.json`](.devcontainer/devcontainer.json).

### 4. Alternativa sem Docker (uv)

Se não puder usar Docker, instale o [uv](https://docs.astral.sh/uv/getting-started/installation/) e rode:

```bash
uv sync --group dev
uv run pytest -q
```

> [!NOTE]
> Você não precisa instalar Python: o `uv` baixa a versão 3.12 automaticamente. E não precisa ativar a `.venv` — `uv run <comando>` já usa o ambiente certo.

---

## Comandos do dia a dia

| Quero... | Com Docker (principal) | Sem Docker (uv) |
|---|---|---|
| Rodar todos os testes | `docker compose run --rm test` | `uv run pytest -q` |
| Rodar os testes de uma pasta | `docker compose run --rm app uv run pytest tests/unit -q` | `uv run pytest tests/unit -q` |
| Rodar **todos os checks** | `docker compose run --rm checks` | `uv run ruff check . && uv run ruff format --check . && uv run pytest` |
| Ver problemas de estilo | `docker compose run --rm lint` | `uv run ruff check .` |
| Corrigir a formatação | `docker compose run --rm app uv run ruff format .` | `uv run ruff format .` |
| Abrir um terminal no container | `docker compose exec app bash` | — |
| Adicionar uma biblioteca | `docker compose run --rm app uv add nome-da-biblioteca` e depois `docker compose build` | `uv add nome-da-biblioteca` |
| Parar o ambiente | `docker compose down` | — |

> [!NOTE]
> O serviço `checks` roda exatamente o que o CI roda. `docker compose run --rm checks` antes de abrir a PR é o caminho mais rápido.

### Notebooks

```bash
docker compose --profile research up notebook
```

Acesse <http://localhost:8888> e use o token definido em `WQF_JUPYTER_TOKEN` (padrão: `wqf`). A porta pode ser trocada em `WQF_JUPYTER_PORT`.

---

## Como o projeto está organizado

```text
.
├── .devcontainer/    # VS Code: abrir o projeto dentro do container
├── src/wqf/          # código do fundo — é aqui que você vai programar
├── tests/            # testes automáticos (acompanham o código)
├── config/           # parâmetros: custos, datas, limites (nunca fixos no código)
├── docs/             # manual, arquitetura, decisões, atas e cartas
├── experiments/      # experimentos pontuais de pesquisa
├── notebooks/        # notebooks de exploração
├── compose.yaml      # ambiente Docker (opcional)
├── Dockerfile
├── pyproject.toml    # dependências, configuração do Ruff e do Pytest
└── uv.lock           # versões exatas das dependências (não edite à mão)
```

Cada etapa do pipeline vira um **módulo dentro de `src/wqf/`**. O fluxo técnico completo está em [`docs/architecture/overview.md`](docs/architecture/overview.md), e os contratos entre as partes do sistema estão em [`docs/architecture/contracts.md`](docs/architecture/contracts.md).

### Onde escrever os testes

| Pasta | Quando usar |
|---|---|
| `tests/unit/` | Funções e módulos isolados, sem depender do resto. |
| `tests/integration/` | Vários módulos funcionando juntos. |
| `tests/contracts/` | Contratos compartilhados (ver `docs/architecture/contracts.md`), com dados sintéticos. |
| `tests/financial/` | Regras financeiras: custos, caixa, proventos e temporalidade dos dados. |
| `tests/fixtures/` | Dados e utilitários reaproveitados por vários testes. |

### Onde colocar código novo

1. **Etapa ou estratégia nova** → um módulo em `src/wqf/`.
2. **Testes correspondentes** → na pasta de teste mais adequada da tabela acima.
3. **Parâmetros** (datas, custos, limites) → `config/parametros.toml`, nunca no código.
4. **Decisão importante** → um registro em `docs/decisions/` (veja o README de lá).

---

## Como contribuir

> [!IMPORTANT]
> A `main` é protegida: **nunca envie código direto para ela**. Toda mudança passa por uma branch e uma Pull Request revisada por outra pessoa.

O fluxo é: **Issue → branch → código + testes → checks → PR → revisão → merge**.

### Passo 1: escolha uma tarefa

As tarefas ficam nas [Issues do repositório](https://github.com/wolf-finance-rj/wolf-quant-fund/issues) e no GitHub Project da organização (peça o link no grupo se não encontrar). Leia a Issue inteira, incluindo os critérios de aceite. Em dúvida, pergunte antes de começar.

### Passo 2: crie uma branch

```bash
git switch main        # vai para a branch principal
git pull               # atualiza com o que já foi mesclado
git switch -c feat/12-descricao-curta
```

O número (`12`) é o número da Issue. Use um prefixo conforme o tipo de trabalho:

| Prefixo | Uso |
|---|---|
| `feat/` | nova funcionalidade |
| `fix/` | correção de bug |
| `docs/` | documentação |
| `test/` | testes |
| `chore/` | manutenção (dependências, configuração) |

### Passo 3: escreva o código

- Coloque o código de produção em `src/wqf/` e os testes na pasta correspondente.
- Trabalhe em passos pequenos: é melhor uma PR pequena e fácil de revisar do que uma gigante.
- Se precisar de uma biblioteca nova, instale com `uv add nome-da-biblioteca` e versione `pyproject.toml` e `uv.lock`.

### Passo 4: rode os checks

```bash
docker compose run --rm checks
```

Sem Docker, o equivalente é `uv run ruff check . && uv run ruff format --check . && uv run pytest`. Corrija o que falhar antes de seguir. Para formatação automática: `docker compose run --rm app uv run ruff format .`.

### Passo 5: salve e envie

```bash
git status                    # confira o que mudou
git add .
git commit -m "feat: adiciona provider csv de exemplo"
git push -u origin feat/12-descricao-curta
```

Mensagens de commit seguem o mesmo prefixo da branch: `feat:`, `fix:`, `docs:`, `test:`, `chore:`.

### Passo 6: abra a Pull Request

1. O GitHub mostra um botão **Compare & pull request** — clique nele.
2. Preencha o template da PR e, no campo de descrição, referencie a Issue: `Closes #12`.
3. Peça revisão para outra pessoa do time (ou avise no grupo).
4. O **CI roda automaticamente** os três checks. Se ficar vermelho, clique em *Details*, corrija e envie de novo.

### Passo 7: revisão e merge

- Responda aos comentários da revisão e envie os ajustes na mesma branch.
- Quem revisa faz o merge — **não faça merge da sua própria PR**.
- Depois do merge, atualize sua `main`:

```bash
git switch main
git pull
```

<details>
<summary><strong>Nunca usou Git? Cola rápida</strong></summary>

| Comando | O que faz |
|---|---|
| `git status` | mostra arquivos alterados |
| `git diff` | mostra exatamente o que mudou |
| `git add .` | marca todas as mudanças para o commit |
| `git commit -m "mensagem"` | salva as mudanças marcadas |
| `git log --oneline` | lista os últimos commits |
| `git switch main` | vai para a branch principal |
| `git switch -c nome` | cria e entra em uma branch nova |
| `git pull` | baixa e aplica as mudanças do GitHub |
| `git push` | envia seus commits para o GitHub |
| `git restore arquivo` | descarta as mudanças de um arquivo (cuidado: não dá para desfazer) |

</details>

### Regras de ouro

- Uma Issue por PR; PR pequena e focada.
- Nunca versione `.env`, dados ou resultados pesados (veja [Convenções](#convenções-do-projeto)).
- Você precisa conseguir explicar todo código que envia, inclusive o gerado com IA.
- Pediu ajuda e continua travado? Avise no grupo e marque a Issue com a label `blocked`.
- Decisões táticas ou estruturais do fundo viram registro em `docs/decisions/`.

---

## Convenções do projeto

- **Parâmetros nunca no código.** Datas, custos, limites e pesos ficam em `config/parametros.toml`.
- **Python 3.12, linhas de até 100 caracteres**, formatação e lint pelo Ruff (configurado no `pyproject.toml`).
- **Todo código novo chega com testes** na categoria correspondente.
- **Dependências novas** entram por `uv add` (no Docker: `docker compose run --rm app uv add ...`, seguido de `docker compose build`) e vão versionadas em `pyproject.toml` e `uv.lock`.
- **Nada de dados, segredos ou outputs pesados no Git.** `data/`, `.env` e artefatos de execução ficam fora do repositório.
- **Uso de IA é permitido e incentivado**, mas quem envia precisa entender e explicar o código; toda alteração passa por revisão de outra pessoa.

---

## Problemas comuns

| Sintoma | Como resolver |
|---|---|
| Docker: `cannot connect to the Docker daemon` | Abra o Docker Desktop (ou inicie o serviço do Docker) e tente de novo. |
| Docker: `permission denied` no Linux | Adicione seu usuário ao grupo `docker` e reinicie a sessão (veja a documentação do Docker). |
| Porta 8888 já está em uso | Troque a porta no `.env`: `WQF_JUPYTER_PORT=8890`. |
| `checks` falha | Rode `docker compose run --rm lint` para separar lint/formatação dos testes. Para corrigir formatação: `docker compose run --rm app uv run ruff format .`. |
| `uv: command not found` (só no caminho sem Docker) | Feche e reabra o terminal depois de instalar. Se persistir, confira se o uv está no `PATH` (instruções na página de instalação). |
| `No interpreter found for Python 3.12` (sem Docker) | Rode `uv python install 3.12` e depois `uv sync --group dev`. |
| `ModuleNotFoundError: No module named 'wqf'` | Rode `docker compose build` (ou, sem Docker, `uv sync --group dev`) e execute tudo com `docker compose run`/`uv run`. |
| A `.venv` local parece quebrada (sem Docker) | Apague a pasta (`rm -rf .venv`) e rode `uv sync --group dev` de novo. |

---

## Sobre o fundo

O fundo é **simulado**, com R$ 100 milhões fictícios. A ideia é operar estratégias quantitativas no mercado brasileiro com o máximo de realismo: custos de transação, aluguel de ações vendidas, liquidez e limites de risco entram na conta. Os benchmarks são o **CDI** e o **Ibovespa**.

| Estratégia | Em uma frase |
|---|---|
| **Momentum** | Compra as ações que subiram mais e vende as que caíram mais. |
| **Pairs trading** | Encontra dois ativos parecidos e aposta na convergência quando os preços se afastam. |
| **Complementares** | Novas ideias (inclusive machine learning) que passam por um ciclo de validação antes de entrar. |

Regras que afetam diretamente o código:

- Capital dividido em partes iguais entre as estratégias; o que não está alocado rende 100% do CDI.
- Pesos iguais (1/N) dentro de cada perna, long e short.
- Rebalanceamento mensal, no 1º dia útil — configurável, nunca fixo no código.
- Custo de 0,15% por operação e aluguel de 2% ao ano sobre posições vendidas.
- Alertas de risco: drawdown acima de **8%** (Atenção) e acima de **15%** (Revisão).

> Todos os detalhes — governança, ciclos, parâmetros completos, equipe e referências — estão em [`docs/fundo.md`](docs/fundo.md).

---

## Glossário

**Git e ferramentas**

| Termo | O que é |
|---|---|
| Repositório | Pasta do projeto versionada pelo Git (este repositório). |
| Branch | Linha paralela de desenvolvimento que isola o seu trabalho. |
| `main` | Branch principal, que deve estar sempre estável. |
| Commit | "Foto" das suas mudanças, com uma mensagem explicando. |
| Push / Pull | Enviar commits para o GitHub / trazer mudanças do GitHub. |
| Issue | Tarefa ou ideia registrada no GitHub. |
| Pull Request (PR) | Pedido para juntar sua branch à `main`, com revisão de outra pessoa. |
| CI | Robô que roda os checks automaticamente em cada PR. |
| uv | Ferramenta que instala Python e dependências e roda comandos no ambiente certo. |
| `.venv` | Ambiente isolado com as dependências do projeto. |
| pytest | Ferramenta que roda os testes automáticos. |
| Ruff | Ferramenta que confere estilo e formata o código. |

**Finanças e do fundo**

| Termo | O que é |
|---|---|
| Backtest | Simulação de uma estratégia usando dados do passado. |
| ETL | Extração, transformação e carga de dados. |
| Long / short | Posição comprada / posição vendida. |
| 1/N | Dividir o capital igualmente entre os ativos. |
| Drawdown | Queda percentual a partir do pico do patrimônio. |
| Sharpe | Retorno acima do CDI dividido pela volatilidade. |
| CDI | Taxa de referência da renda fixa brasileira. |
| Ibovespa | Principal índice da bolsa brasileira. |
| Momentum | Estratégia de comprar o que subiu e vender o que caiu. |
| Pairs trading | Operar a convergência de dois ativos historicamente relacionados. |
| Incubação | Período de operação simulada antes de a estratégia receber capital. |

---

## Onde aprender mais

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — regras completas de contribuição e definição de pronto.
- [`docs/fundo.md`](docs/fundo.md) — manual resumido do fundo: estratégias, risco, parâmetros, processos e governança.
- [`docs/architecture/overview.md`](docs/architecture/overview.md) — fluxo técnico e stack.
- [`docs/architecture/contracts.md`](docs/architecture/contracts.md) — contratos compartilhados entre as partes do sistema.
- [`docs/project-management/README.md`](docs/project-management/README.md) — como o trabalho é organizado no GitHub.
- [`docs/decisions/README.md`](docs/decisions/README.md) — como registrar decisões técnicas.
- **Manual completo:** `Wolf_Quant_Fund_Documento_de_Estruturacao.docx` — documento interno, não versionado; peça à liderança.

*Documento de uso interno — Equipe Wolf Quant.*
