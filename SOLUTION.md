# Personalization Service --- Solution

## 1. Overview

Este projeto implementa um microserviço de recomendação utilizando
FastAPI e um modelo de machine learning previamente treinado em
scikit-learn.

A solução foi estruturada para separar preparação de dados, serving e
inferência:

-   as features derivadas do histórico são preparadas durante o startup;
-   o modelo e o scaler são carregados uma única vez;
-   durante uma requisição, são selecionadas as features referentes ao
    usuário;
-   o modelo calcula um score para os produtos;
-   os produtos são ordenados pelo score e o Top 10 é retornado;
-   usuários sem histórico utilizam um fallback baseado em popularidade;
-   logs e métricas permitem acompanhar latência, requests, erros e uso
    do fallback.

Os CSVs fornecidos pelo case são tratados como a fonte de entrada da
aplicação. A camada de processamento é separada da camada de inferência,
permitindo que a origem dos dados seja substituída por uma camada de
armazenamento ou serving distribuída sem alterar o contrato da API.

------------------------------------------------------------------------

## 2. Arquitetura

A solução possui duas etapas principais: preparação das features e
serving online.

### Preparação das features

``` text
events.csv + products.csv
            ↓
    Feature Processing
            ↓
      Feature Dataset
```

### Serving online

``` text
request
   ↓
user_id
   ↓
features do usuário
   ↓
scaler
   ↓
modelo
   ↓
ranking
   ↓
Top 10
```

O feature processing é executado durante o startup porque é uma etapa
determinística e independente da requisição. Dessa forma, o custo de
construção das features não faz parte do caminho crítico da API.

O modelo, o scaler e as features processadas ficam disponíveis para as
requisições enquanto a instância está ativa.

A arquitetura mantém uma separação clara entre:

-   processamento de dados;
-   armazenamento/serving das features;
-   inferência;
-   apresentação das recomendações.

Essa separação permite escalar cada responsabilidade de acordo com sua
necessidade.

------------------------------------------------------------------------

## 3. Dados e Feature Processing

O serviço recebe dois datasets:

-   `events.csv`: histórico de interações entre usuários e produtos;
-   `products.csv`: informações dos produtos.

A partir desses dados é construído o dataset utilizado pelo modelo.

### Features

  -----------------------------------------------------------------------
  Feature                             Descrição
  ----------------------------------- -----------------------------------
  `interactions`                      Quantidade de interações do usuário
                                      com o produto

  `price`                             Preço do produto

  `avg_rating`                        Avaliação média do produto

  `popularity_score`                  Score de popularidade do produto

  `user_affinity_match`               Indica se a categoria do produto
                                      corresponde à categoria de maior
                                      afinidade do usuário
  -----------------------------------------------------------------------

### `user_affinity_match`

Essa feature é derivada do histórico do usuário.

Primeiro é identificada a categoria com maior afinidade para o usuário.
Depois essa categoria é comparada com a categoria de cada produto.

``` text
histórico do usuário
        ↓
categoria de maior afinidade
        ↓
categoria do produto
        ↓
match
   ┌────┴────┐
   │         │
  1          0
match     sem match
```

O resultado é:

-   `1`: o produto pertence à categoria de maior afinidade;
-   `0`: o produto não pertence à categoria de maior afinidade.

### Dataset de features

O processamento gera as combinações usuário-produto necessárias para a
inferência.

No dataset fornecido pelo case temos:

-   500 usuários;
-   60 produtos;
-   8.000 eventos;
-   30.000 combinações usuário-produto.

O resultado do processamento é mantido em memória para permitir acesso
rápido às features durante a requisição.

A camada de processamento é independente do contrato da API. Isso
permite que a mesma lógica seja alimentada por diferentes fontes de
dados sem alterar a etapa de inferência.

------------------------------------------------------------------------

## 4. Inferência Online

O modelo já está treinado e armazenado em:

``` text
model/model.pkl
```

A API não realiza treinamento durante o runtime.

Durante o startup são carregados:

-   modelo;
-   scaler;
-   lista de features utilizadas pelo modelo.

Durante uma requisição:

``` text
user_id
   ↓
selecionar features
   ↓
scaler
   ↓
predict_proba()
   ↓
score
   ↓
ordenar
   ↓
Top 10
```

O modelo utilizado é uma `LogisticRegression`, acompanhada de um
`StandardScaler`.

### Por que o score é calculado em tempo de requisição?

As features são preparadas antecipadamente, enquanto o score final é
calculado no momento da requisição.

Essa separação permite manter o dataset de features desacoplado do
resultado final de recomendação e mantém o ranking como parte do serviço
online.

Também evita manter um segundo artefato contendo recomendações finais
pré-calculadas para todos os usuários.

A estratégia de inferência online é adequada quando o custo do modelo
está dentro do SLA da API. Caso o modelo ou o volume de candidatos
cresça, a arquitetura possui espaço para introduzir cache ou pré-cálculo
seletivo sem alterar o contrato externo do serviço.

------------------------------------------------------------------------

## 5. Cold Start

Um usuário é considerado cold start quando não possui histórico
disponível no dataset de eventos.

Nesse cenário, não existem informações comportamentais suficientes para
gerar uma recomendação personalizada pelo modelo.

A estratégia implementada é utilizar a popularidade dos produtos:

``` text
usuário sem histórico
        ↓
fallback
        ↓
ordenar por popularity_score
        ↓
Top 10
```

A resposta indica explicitamente que o fallback foi utilizado:

``` json
{
  "user_id": "u_090909",
  "recommendations": [...],
  "fallback": true
}
```

### Por que popularidade?

A estratégia é:

-   determinística;
-   rápida;
-   simples;
-   disponível mesmo sem histórico do usuário;
-   capaz de garantir uma resposta válida.

A principal limitação é que o resultado não é personalizado.

A estratégia de fallback pode ser enriquecida com sinais contextuais,
como categoria, região, dispositivo ou outros atributos disponíveis no
momento da requisição.

------------------------------------------------------------------------

## 6. API

A aplicação possui três endpoints principais.

### Health

``` http
GET /health
```

Resposta:

``` json
{
  "status": "ok"
}
```

### Recomendações

``` http
GET /recommendations/{user_id}
```

Exemplo para um usuário conhecido:

``` json
{
  "user_id": "u_0242",
  "recommendations": [
    {
      "product_id": "p_012",
      "score": 0.91
    }
  ],
  "fallback": false
}
```

Para um usuário sem histórico:

``` json
{
  "user_id": "u_090909",
  "recommendations": [
    {
      "product_id": "p_000",
      "score": 0.652
    }
  ],
  "fallback": true
}
```

### Métricas

``` http
GET /metrics
```

Exemplo:

``` json
{
  "requests_total": 2,
  "fallback_total": 1,
  "errors_total": 0,
  "average_latency_ms": 12.65
}
```

------------------------------------------------------------------------

## 7. Observabilidade

A aplicação possui logs por requisição e métricas agregadas.

### Logs

Cada requisição de recomendação registra:

-   `user_id`;
-   latência;
-   utilização do fallback.

Exemplo:

``` text
recommendation_request user_id=u_0242 latency_ms=11.02 fallback=False
recommendation_request user_id=u_090909 latency_ms=7.27 fallback=True
```

Isso permite investigar o comportamento de uma requisição individual.

### Métricas

O endpoint `/metrics` disponibiliza:

  Métrica                Descrição
  ---------------------- ----------------------------------------------
  `requests_total`       Total de requisições de recomendação
  `fallback_total`       Total de requisições atendidas pelo fallback
  `errors_total`         Total de erros internos registrados
  `average_latency_ms`   Latência média das requisições

As métricas são mantidas em memória nesta implementação.

A camada de métricas pode ser substituída por um sistema externo e
agregável entre réplicas, como Prometheus, mantendo o mesmo conjunto de
indicadores expostos pela aplicação.

### Indicadores adicionais

A observabilidade pode ser expandida com:

-   p50, p95 e p99 de latência;
-   métricas por endpoint;
-   métricas de erro por tipo;
-   request/correlation ID;
-   tracing distribuído;
-   alertas;
-   métricas centralizadas entre réplicas.

------------------------------------------------------------------------

## 8. Testes

A aplicação possui testes para as principais responsabilidades:

``` text
tests/
├── test_feature_processing.py
├── test_health.py
└── test_recommendations.py
```

São cobertos:

-   feature processing;
-   health check;
-   métricas;
-   endpoint de recomendação;
-   ordenação por score;
-   cold start/fallback;
-   fluxo end-to-end.

O teste end-to-end utiliza `TestClient` e executa o fluxo real da
aplicação sem mockar o modelo, scaler ou feature processing.

Resultado atual:

``` text
7 passed
```

Isso valida tanto os componentes individuais quanto o fluxo principal da
aplicação.

------------------------------------------------------------------------

## 9. Docker

A aplicação pode ser executada em um container.

### Build

``` bash
docker build -t personalization-api .
```

### Run

``` bash
docker run --rm -p 8000:8000 personalization-api
```

O container contém os artefatos necessários:

``` text
app/
data/
model/
requirements.txt
```

O container foi validado com:

-   `/health`;
-   `/recommendations/{user_id}`;
-   usuário conhecido;
-   usuário em cold start;
-   `/metrics`.

O startup do container executa o feature processing e carrega o modelo
antes de a aplicação começar a atender requisições.

------------------------------------------------------------------------

## 10. Trade-offs e Decisões

### Feature processing no startup

**Decisão**

Executar o processamento das features antes de atender requisições.

**Motivação**

O processamento é determinístico e não depende do `user_id` recebido
pela API. Mantê-lo fora do caminho crítico evita repetir esse trabalho
em cada requisição.

**Benefício**

A requisição fica concentrada em seleção de features, transformação,
inferência e ranking.

**Trade-off**

O resultado do processamento fica associado ao ciclo de vida da
instância. Alterações nos dados exigem uma nova execução do
processamento.

**Melhoria**

A separação entre processamento e serving permite mover a geração das
features para um pipeline independente e disponibilizar os resultados
por uma camada de armazenamento/serving distribuída.

------------------------------------------------------------------------

### Dataset de features em memória

**Decisão**

Manter o dataset processado em memória nesta implementação.

**Motivação**

Permite acesso rápido às features e mantém a execução do serviço
simples.

**Trade-off**

Em um ambiente com múltiplas réplicas, o dataset seria replicado na
memória de cada instância.

**Melhoria**

A camada de serving pode utilizar armazenamento compartilhado ou
distribuído, permitindo a API consultar apenas os dados
necessários para a requisição.

------------------------------------------------------------------------

### Inferência online

**Decisão**

Calcular o score durante a requisição.

**Motivação**

O modelo já está carregado e o custo da inferência pode ser mantido
dentro do caminho de serving.

**Benefício**

Não é necessário manter um segundo artefato contendo recomendações
finais para todos os usuários.

**Trade-off**

O custo computacional do modelo passa a fazer parte da latência da API.

**Melhoria**

O fluxo permite introduzir cache ou pré-cálculo seletivo quando
necessário, sem alterar o contrato da API.

------------------------------------------------------------------------

### Fallback por popularidade

**Decisão**

Utilizar `popularity_score` para usuários sem histórico.

**Motivação**

É uma estratégia simples, rápida e disponível para qualquer usuário.

**Benefício**

Garante uma resposta válida mesmo sem dados comportamentais.

**Trade-off**

O resultado não é personalizado.

**Melhoria**

O fallback pode incorporar sinais contextuais e segmentação conforme
novos dados estejam disponíveis.

------------------------------------------------------------------------

## 11. Arquitetura de Produção

A arquitetura separa o pipeline de dados da camada de serving.

``` text
                 PIPELINE OFFLINE
                        │
        ┌───────────────┴───────────────┐
        │                               │
  Eventos históricos             Catálogo de produtos
        │                               │
        └───────────────┬───────────────┘
                        ↓
                Feature Processing
                        ↓
              Feature Storage/Serving
                        │
                        │
                 ───────┴───────
                        │
                   ONLINE API
                        │
                     user_id
                        ↓
                Buscar features
                        ↓
              Candidate Generation
                        ↓
                    Ranking
                        ↓
                    Top 10
```

### Pipeline offline

Responsável por:

-   ingestão dos eventos;
-   agregações;
-   cálculo das features;
-   atualização das features;
-   versionamento dos artefatos.

### Feature serving

Responsável por disponibilizar rapidamente as features necessárias para
uma requisição.

A API não precisa conhecer a origem dos dados. Ela recebe os dados
necessários para executar a recomendação.

### Recommendation API

Responsável por:

-   receber a requisição;
-   obter as features necessárias;
-   gerar ou receber os candidatos;
-   executar o ranking;
-   aplicar o fallback;
-   retornar a resposta.

Essa separação permite que o pipeline de dados e a API sejam escalados e
atualizados de forma independente.

------------------------------------------------------------------------

## 12. Escalabilidade do Ranking

A implementação trabalha com as combinações usuário-produto disponíveis
no dataset.

Para controlar o custo do ranking conforme o catálogo cresce, o fluxo é
dividido em duas etapas:

``` text
Candidate Generation
        ↓
conjunto reduzido de candidatos
        ↓
Ranking Model
        ↓
Top K
```

O candidate generation pode utilizar diferentes estratégias, como:

-   popularidade;
-   histórico do usuário;
-   similaridade;
-   modelos de retrieval;
-   regras de negócio.

O modelo de ranking avalia somente um conjunto reduzido de candidatos.

Essa separação evita avaliar todos os produtos disponíveis para cada
usuário e permite escalar o sistema de recomendação de forma
independente do tamanho total do catálogo.

------------------------------------------------------------------------

## 13. Evoluções

### Dados e features

-   pipeline offline agendado;
-   feature serving;
-   versionamento de features;
-   atualização incremental;
-   tratamento de dados atrasados;
-   validação de qualidade dos dados.

### Modelo

-   versionamento explícito;
-   validação de compatibilidade entre modelo e runtime;
-   monitoramento de drift;
-   avaliação offline;
-   estratégia de rollback;
-   atualização sem downtime.

### Serving

-   candidate generation;
-   cache quando fizer sentido;
-   múltiplas réplicas;
-   autoscaling;
-   atualização sem downtime.

### Observabilidade

-   métricas Prometheus;
-   dashboards;
-   p95/p99;
-   tracing;
-   alertas;
-   correlação entre request, modelo e versão das features.

### Qualidade da recomendação

Além de latência e disponibilidade, podem ser monitoradas métricas como:

-   CTR;
-   conversion rate;
-   coverage;
-   diversity;
-   novelty;
-   NDCG;
-   MAP;
-   Recall@K.

As métricas exatas dependem do objetivo do produto e do comportamento
esperado do sistema.

------------------------------------------------------------------------

## 14. Limitações Conhecidas

A implementação possui algumas simplificações decorrentes do formato dos
dados fornecidos pelo exercício:

1.  A fonte de dados utilizada é composta por arquivos CSV.
2.  As features processadas são mantidas em memória.
3.  As métricas são mantidas em memória.
4.  O fallback é baseado em popularidade.
5.  O ranking considera as combinações disponíveis no dataset.
6.  A coleta de métricas ainda não é compartilhada entre réplicas.
7.  A atualização das features e do modelo não faz parte do ciclo de
    execução da API.

Esses pontos são tratados como componentes desacoplados da lógica de
recomendação. A evolução natural é substituir as implementações locais
por serviços distribuídos de dados, métricas e atualização de modelos,
preservando o contrato da API.

------------------------------------------------------------------------

## 15. Como Executar

### Ambiente local

Instalar dependências:

``` bash
pip install -r requirements.txt
```

Executar os testes:

``` bash
python -m pytest -v
```

Iniciar a API:

``` bash
uvicorn app.main:app --reload
```

Acessar:

``` text
http://localhost:8000/docs
http://localhost:8000/health
http://localhost:8000/metrics
```

Recomendações:

``` text
http://localhost:8000/recommendations/{user_id}
```

### Docker

Build:

``` bash
docker build -t personalization-api .
```

Run:

``` bash
docker run --rm -p 8000:8000 personalization-api
```

------------------------------------------------------------------------

## 16. Resumo

A solução separa preparação de dados e inferência online.

``` text
dados
  ↓
feature processing
  ↓
feature dataset
  ↓
API
  ↓
scaler
  ↓
modelo
  ↓
ranking
  ↓
Top 10
```

A arquitetura de serving mantém o caminho da requisição pequeno e
previsível, enquanto o processamento de dados, o armazenamento das
features, a geração de candidatos e o ranking possuem responsabilidades
independentes.

Essa separação permite evoluir cada componente de acordo com seu volume,
SLA e frequência de atualização sem alterar o contrato externo da API.
