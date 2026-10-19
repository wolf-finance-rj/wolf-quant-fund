## Objetivo e Issue

Closes #

## Alterações realizadas

## Como testar

```bash
docker compose run --rm checks
```

> Sem Docker: `uv run ruff check . && uv run ruff format --check . && uv run pytest`.

## Risco e impacto quantitativo

- Dados históricos/temporais afetados?
- Sinais, execução, custos, patrimônio ou risco afetados?
- Reprodutibilidade e limitações?

## Checklist

- [ ] Critérios da Issue atendidos
- [ ] Testes relevantes implementados/executados
- [ ] Sem segredos, datasets restritos ou outputs grandes
- [ ] Documentação/contratos atualizados quando necessário
- [ ] Revisão independente solicitada
