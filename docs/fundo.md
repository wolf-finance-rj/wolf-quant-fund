# O fundo — manual resumido

> Esta é a versão Markdown do manual do fundo. O documento oficial é o `Wolf_Quant_Fund_Documento_de_Estruturacao.docx` (interno, não versionado). Para instruções de desenvolvimento, volte ao [`README.md`](../README.md).

## Missão

Aplicar estratégias quantitativas ao mercado brasileiro de forma realista e operacionalizável: o resultado simulado deve ser o mais próximo possível do que seria obtido com capital real. O fundo prioriza estratégias conhecidas, bem executadas e plenamente compreendidas, em vez de modelos sofisticados e frágeis.

## Objetivos

- Operar estratégias sistemáticas com custos de transação, limites de risco e regras de execução realistas.
- Entender e documentar quando cada estratégia funciona e quando falha.
- Manter um pipeline de código reproduzível, versionado e compreendido por toda a equipe.
- Publicar mensalmente os resultados e a análise em uma carta.
- Formar membros em finanças quantitativas por meio da operação do fundo e de projetos de pesquisa.

## Princípios

Em caso de conflito entre uma regra do manual e um princípio, **prevalece o princípio**.

| Princípio | O que significa |
|---|---|
| Simplicidade | Estratégias conhecidas e bem executadas são preferidas a estratégias complexas e pouco compreendidas. |
| Realismo | Custos de transação, liquidez, limites de risco e regras de rebalanceamento estão sempre incluídos nos resultados. |
| Compreensão total | Cada membro deve conseguir explicar qualquer trecho do código que submete, inclusive o gerado com auxílio de IA. |
| Disciplina de decisão | Mudanças de alocação, exposição ou parâmetros são raras, justificadas por escrito e acompanhadas depois. |
| Reprodutibilidade | Todo resultado pode ser reproduzido a partir do repositório, dos dados e dos parâmetros registrados. |
| Continuidade | O conhecimento do fundo está documentado e não depende de nenhuma pessoa específica. |
| Transparência | Resultados, inclusive os negativos, são divulgados e analisados. |

## Fora de escopo

- Operação com capital real e envio automático de ordens.
- Estratégias de alta frequência ou dependentes de infraestrutura profissional de execução.
- Otimização de resultados de backtest sem validação de aplicabilidade real.

## Estratégias

| Estratégia | Ideia central | Papel no portfólio |
|---|---|---|
| **Pairs trading** | Opera a convergência de preços entre pares de ativos historicamente relacionados: compra o que se afastou para baixo e vende o que se afastou para cima. | Diversificador, com baixa dependência da direção do mercado. |
| **Momentum** | Compra ativos com melhor desempenho recente e vende os de pior desempenho. Sujeita a quedas abruptas em crises (*momentum crashes*). | Principal motor de retorno, sujeito a controle de volatilidade. |
| **Complementares** | Estratégias adicionais, como modelos de aprendizado de máquina, que passam pelo ciclo de vida (Seção 11 do manual). | Complementam o portfólio quando validadas. |

Cada estratégia mantém uma **ficha no repositório** (modelo no Anexo 15.1 do manual), atualizada sempre que a estratégia muda. Critérios para entrar no fundo: hipótese econômica/estatística clara, implementável com dados disponíveis e custos realistas, limites de risco definidos, aderente às estratégias ativas e revisada por outro membro.

### Ciclo de vida de uma estratégia

1. **Pesquisa** — replicação de ideia ou paper com dados locais.
2. **Candidata** — indicação ao fundo com ficha preenchida e checklist aprovado.
3. **Incubação** — operação simulada em paralelo, sem capital, por no mínimo 3 meses.
4. **Ativa** — recebe capital e integra o portfólio (decisão estrutural do comitê).
5. **Suspensa** — sem alocação por alerta de Revisão ou perda de validade da hipótese.
6. **Aposentada** — retirada definitiva, com documentação preservada.

## Construção do portfólio

- Capital dividido em **partes iguais** entre as estratégias ativas; a parcela não alocada fica em **caixa remunerado a 100% do CDI**.
- Em estratégias long/short, cada ativo da mesma perna recebe o **mesmo capital (pesos 1/N)**.
- **Rebalanceamento mensal, no 1º dia útil** — data e frequência são parâmetros de configuração, nunca valores fixos no código.
- Universo: ações listadas na B3 com liquidez mínima de **R$ 5 milhões de volume médio diário (3 meses)**; ativos em situação especial são excluídos.
- Todo resultado do fundo é **líquido de custos** (corretagem, emolumentos, impacto de mercado e aluguel das posições vendidas).
- Alterações de pesos são decisões táticas do comitê, nunca reações automáticas a um único mês.

## Gestão de risco

O risco é parte central do código e do processo, atuando em três níveis: **ativo, estratégia e portfólio**.

| Nível | Controle | Descrição |
|---|---|---|
| Ativo | Liquidez e universo | Somente ativos com liquidez mínima e sem situação especial. |
| Estratégia | Controle de volatilidade | Exposição ajustada para manter volatilidade próxima ao alvo (15% a.a. no momentum); excedente vai para o caixa. |
| Estratégia | Exposição máxima | Limite de exposição long e short por estratégia. |
| Portfólio | Diversificação | Pesos iguais entre estratégias e acompanhamento da correlação. |
| Portfólio | Drawdown | Limites de queda a partir do pico disparam os níveis de alerta. |

### Níveis de alerta

| Nível | Condição | Ação |
|---|---|---|
| **Normal** | Todas as métricas dentro dos limites. | Operação regular. |
| **Atenção** | Drawdown acima de 8% ou 2 meses negativos consecutivos, ou volatilidade acima do alvo. | Risco notifica o comitê; análise entra na pauta da reunião semanal. |
| **Revisão** | Drawdown acima de 15% ou 3 meses negativos consecutivos. | Comitê se reúne e decide: manter, reduzir exposição, alterar alocação ou suspender a estratégia. |

Toda redução ou aumento de exposição é decidida pelo comitê e registrada com motivo. O efeito de cada mudança é acompanhado e analisado, funcione ou não.

## Dados

| Tipo | Fonte | Uso |
|---|---|---|
| Preços, volumes e proventos | Provedor institucional de dados de mercado (ex.: Economatica) | Base de todas as estratégias. |
| Juros e CDI | Banco Central do Brasil (SGS) | Caixa e benchmark. |
| Fatores de risco | NEFIN-USP | Análises de fatores e comparações. |

Mudanças de fonte exigem verificação de consistência com a série histórica anterior.

## Parâmetros vigentes

> Qualquer alteração segue o processo de governança (Seção 10 do manual) e é registrada em ata e no controle de versões. Estes são os valores iniciais da versão 1.0.

| Parâmetro | Valor vigente | Tipo de decisão | Revisão |
|---|---|---|---|
| Capital fictício | R$ 100.000.000 | Estrutural | Anual |
| Alocação entre estratégias | Partes iguais; caixa a 100% do CDI | Tática | Semestral |
| Exposição inicial por estratégia long/short | 100% long e 50% short | Tática | Semestral |
| Exposição máxima por estratégia | 150% long e 100% short | Estrutural | Anual |
| Pesos dentro de cada perna | 1/N (iguais) | Estrutural | Anual |
| Rebalanceamento | Mensal, no 1º dia útil | Tática | Semestral |
| Liquidez mínima de ativos | R$ 5 mi de volume médio diário (3 meses) | Estrutural | Semestral |
| Volatilidade-alvo (momentum) | 15% ao ano | Estrutural | Semestral |
| Alerta de Atenção | Drawdown > 8% ou 2 meses negativos consecutivos | Estrutural | Anual |
| Alerta de Revisão | Drawdown > 15% ou 3 meses negativos consecutivos | Estrutural | Anual |
| Custo de transação | 0,15% por operação | Tática | Semestral |
| Aluguel de ações (posição vendida) | 2% ao ano sobre o valor vendido | Tática | Semestral |
| Período mínimo de incubação | 3 meses | Estrutural | Anual |
| Tamanho da equipe | 5 a 7 pessoas | Estrutural | Semestral |
| Benchmarks | CDI e Ibovespa | Estrutural | Anual |

## Processos operacionais

### Ciclo semanal

Reunião do fundo com pauta fixa e ata curta: status do pipeline, nível de alerta de risco, andamento de estratégias e projetos, andamento da carta mensal e decisões a levar ao comitê.

### Ciclo mensal

| Etapa | Prazo | Responsável | Saída |
|---|---|---|---|
| Atualização dos dados | D+1 útil | Dados e Infra | Base atualizada e verificada. |
| Execução do pipeline | D+2 útil | Dados e Infra | Retornos das estratégias. |
| Consolidação e rebalanceamento | D+3 útil | Risco e Métricas | Portfólio e novas posições. |
| Conferência de resultados | D+4 útil | Resp. de Estratégia e Risco | Resultados validados. |
| Fechamento aprovado | D+5 útil | Diretor(a) Quant | Mês fechado e registrado. |
| Redação e revisão da carta | D+6 a D+9 útil | Resp. pela Carta | Carta revisada. |
| Publicação | D+10 útil | Resp. pela Carta | Carta publicada. |

### Ciclo semestral

Reunião zero no início do semestre (Seção 13.3 do manual), plano do semestre com projetos e metas, revisão intermediária, revisão geral (desempenho, parâmetros, custos, manual) e passagem de bastão com documentação atualizada e substitutos designados.

## Métricas e relatórios

- **Métricas:** retorno acumulado e anualizado, volatilidade anualizada, Sharpe, drawdown (e máximo), retorno por estratégia, exposição long/short/caixa e comparação com o fundo multimercado e benchmarks.
- **Carta mensal:** publicada todo mês no prazo do ciclo mensal, com resultado do mês e acumulado vs. benchmarks, contribuição por estratégia, alterações e motivos, nível de alerta e análise de cenário, e aprendizados. Toda carta passa por revisão de uma segunda pessoa antes da publicação.

## Governança

- **Comitê do fundo:** Diretor(a) Quant, responsáveis de Estratégia, de Dados e Infraestrutura e de Risco e Métricas. Maioria decide, com voto de desempate do(a) Diretor(a) Quant.
- **Tipos de decisão:**
  - *Operacional* — correções e ajustes do dia a dia (Diretor(a) Quant ou responsável da área).
  - *Tática* — alocação, exposição, resposta a alerta de Revisão (Comitê).
  - *Estrutural* — inclusão/retirada de estratégia, limites, universo, custos, fontes de dados, emendas ao manual (Comitê, com ciência da diretoria da liga).
- **Registro:** toda decisão tática ou estrutural gera uma **ata no repositório** (modelo no Anexo 15.2). Decisões sem registro não têm validade.
- Qualquer membro pode propor emenda ao manual via solicitação de mudança no repositório; cada alteração incrementa a versão e é registrada no controle de versões.
- O uso de IA no desenvolvimento é permitido e incentivado, mas quem submete deve explicar todo o código e toda alteração passa por revisão de outra pessoa. Resultados muito bons ou muito ruins são verificados manualmente antes do fechamento.

## Equipe e papéis

| Papel | Qtd. | Responsabilidades |
|---|---|---|
| Diretor(a) Quant | 1 | Lidera a frente quant, preside o comitê, conduz a reunião zero e a semanal, responde pelo fundo perante a liga. |
| Responsável de Estratégia | 1 por estratégia | Mantém código, ficha e desempenho; propõe melhorias. |
| Responsável de Dados e Infraestrutura | 1 | Etapa de limpeza, qualidade dos dados, repositório e ambiente. |
| Responsável de Risco e Métricas | 1 | Etapa de métricas, camada de risco e níveis de alerta. |
| Responsável pela Carta | 1 | Redação, revisão e publicação da carta mensal. |
| Membros | Demais | Apoiam as frentes, executam projetos e rotacionam entre funções. |

Todo papel crítico tem um **substituto designado**, e a equipe tem entre 5 e 7 pessoas.

## Referências

- **Manual do fundo:** `Wolf_Quant_Fund_Documento_de_Estruturacao.docx` (documento interno, fora do repositório) — versão 1.0, Out/2026.
  - Anexo 15.1 — Modelo de ficha de estratégia
  - Anexo 15.2 — Modelo de ata de decisão
  - Anexo 15.3 — Checklist de fechamento mensal
  - Anexo 15.4 — Glossário
  - Anexo 15.5 — Controle de versões
