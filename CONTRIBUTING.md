# Como contribuir

> A `main` é protegida: devs trabalham em branch + PR e **não fazem merge**. O merge é feito por um admin/mantenedor. Fluxo completo no [README](README.md#como-contribuir).

1. Escolha uma Issue refinada no GitHub Project. Confirme critérios de aceite, responsável, revisor, área e sprint.
2. Na primeira configuração, suba o ambiente com `docker compose up -d app` (ou, sem Docker, `uv sync --group dev`) e mantenha o `uv.lock` versionado para garantir instalações futuras reproduzíveis. Atualize `main` e abra uma branch curta: `feat/12-csv-provider`, `fix/31-temporal-leakage`, `docs/18-momentum-hypothesis`.
3. Desenvolva apenas a tarefa proposta e inclua testes e documentação quando aplicável.
4. Rode os checks com `docker compose run --rm checks` (ou, sem Docker, `uv run ruff check .`, `uv run ruff format --check .` e `uv run pytest`).
5. Envie a branch e abra uma Pull Request vinculada à Issue com `Closes #NUMERO`.
6. Solicite revisão independente e responda aos comentários. **O merge é feito por um admin/mantenedor** — não faça merge da sua própria PR.
7. Depois do merge, atualize sua `main` com `git switch main && git pull`.

## Definição de pronto

- Requisitos e critérios de aceite atendidos.
- Testes automatizados adequados ao escopo, com CI verde.
- Revisão independente de outro membro.
- Configurações, contratos e documentação atualizados quando necessários.
- Sem senhas, tokens, datasets licenciados ou outputs pesados no Git.
- Resultado quantitativo identificado com código, dados, parâmetros, período e limitações quando aplicável.

**PR aprovada tecnicamente não equivale à aprovação de uma estratégia para operação simulada.** Essa decisão exige o processo de governança do fundo.

## Administradores e mantenedores

- Revisar e aprovar (**Approve**) somente com CI verde e critérios de aceite conferidos.
- Fazer o merge com **Squash and merge**, excluir a branch e manter a `main` protegida (PR + checks + 1 revisão independente).
- Não commitar direto na `main` no dia a dia. Em emergência, registrar o motivo, usar o bypass apenas se necessário e abrir PR de revisão retroativa.
- Manter `CODEOWNERS` e permissões do time atualizadas.
- Admin que abre PR também precisa de revisão independente.

## Fluxo no Project

`Backlog → Todo → In Progress → In Review → Done`. Use a label `blocked` para sinalizar impedimentos, sem criar status adicional.

## Segurança e dados

Não versionar `.env`, chaves, dados reais não redistribuíveis, snapshots grandes ou relatórios com informação restrita. Repositório público: somente use dados cujo compartilhamento é autorizado.
