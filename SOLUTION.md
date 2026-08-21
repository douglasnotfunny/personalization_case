# Personalization Service --- Solution

## 1. Visão geral

O projeto implementa um microserviço de recomendação utilizando
FastAPI para calculo de um modelo de machine learning 
previamente treinado em scikit-learn.

O serviço é responsável por:

-   preparar as features a partir do histórico de eventos e catálogo;
-   carregar e validar o artefato do modelo;
-   receber um `user_id`;
-   calcular o score dos produtos para esse usuário;
-   retornar os produtos ranqueados;
-   tratar usuários sem histórico através de cold start;
-   registrar logs e métricas de operação.

O modelo não é treinado pela aplicação. O artefato recebido pelo case é
utilizado diretamente no serving.

------------------------------------------------------------------------

## 2. Arquitetura

O fluxo da aplicação é dividido em preparação e serving.

``` text
                     STARTUP
                        │
        ┌───────────────┴────────────────┐
        │                                │
   events.csv                       products.csv
        │                                │
        └───────────────┬────────────────┘
                        ↓
               Feature Processing
                        ↓
                 Feature Dataset
                        │
                        │
                   model.pkl
                        ↓
                   Model Loader
                        │
                        ↓
                 FastAPI app.state
                        │
                ────────┴────────
                        │
                     REQUEST
                        │
                     user_id
                        ↓
                Seleção do usuário
                        │
                  ┌─────┴─────┐
                  │           │
               existe       não existe
                  │           │
                  ↓           ↓
              Modelo      Cold Start
                  │           │
                  └─────┬─────┘
                        ↓
                     Ranking
                        ↓
                      Top 10
```

### Startup

Durante o startup:

1.  `events.csv` e `products.csv` são carregados;
2.  o dataset de features é construído;
3.  o modelo é carregado uma única vez;
4.  as features esperadas pelo modelo são validadas contra o dataset
    produzido;
5.  os objetos necessários são armazenados em `app.state`.

Essa decisão retira o processamento pesado e o carregamento do modelo do
caminho crítico da requisição.

### Request

Durante uma requisição:

1.  o `user_id` é recebido;
2.  as linhas correspondentes ao usuário são selecionadas;
3.  as features esperadas pelo modelo são extraídas;
4.  o scaler é aplicado;
5.  o modelo calcula o score;
6.  os produtos são ordenados;
7.  os 10 maiores scores são retornados.

------------------------------------------------------------------------

## 3. Feature Processing

O processamento utiliza:

-   `events.csv`, contendo o histórico de interações;
-   `products.csv`, contendo os dados do catálogo.

As features utilizadas pelo modelo são:

  Feature                 Origem
  ----------------------- ----------------------------------
  `interactions`          histórico de eventos
  `price`                 catálogo
  `avg_rating`            catálogo
  `popularity_score`      catálogo
  `user_affinity_match`   derivada do histórico + catálogo

### Interactions

A quantidade de interações é calculada agrupando os eventos por:

``` text
user_id + product_id
```

Cada ocorrência representa uma interação no histórico.

### User affinity

Para cada usuário, os eventos são associados às categorias dos produtos.

A categoria com maior quantidade de interações é considerada a categoria
de maior afinidade.

A feature `user_affinity_match` indica se a categoria do produto
corresponde à categoria de maior afinidade do usuário.

Esse critério segue a definição de referência fornecida pelo model card.

### Dataset usuário-produto

Depois das agregações, são geradas as combinações entre usuários
existentes no histórico e produtos do catálogo.

Cada linha representa:

``` text
(user_id, product_id, features)
```

O modelo pode então calcular um score individual para cada produto
candidato.

------------------------------------------------------------------------

## 4. Modelo

O artefato fornecido pelo case contém:

``` text
model/
├── model.pkl
└── model_card.json
```

O `model.pkl` contém:

-   modelo;
-   scaler;
-   ordem das features esperadas.

O modelo é uma `LogisticRegression` e o pré-processamento utiliza
`StandardScaler`.

A aplicação encapsula o carregamento do artefato na função
`load_model()`, evitando que o endpoint precise conhecer o processo de
leitura do arquivo.

O carregamento acontece durante o startup e os objetos são mantidos em
memória através de `app.state`.

### Validação das features

Depois do carregamento do modelo, a aplicação verifica se todas as
features esperadas pelo artefato existem no dataset produzido.

Se alguma feature estiver ausente, o startup falha com erro explícito.

Essa validação evita que uma incompatibilidade entre o processamento e o
modelo seja descoberta somente durante uma requisição.

------------------------------------------------------------------------

## 5. Inferência e Ranking

Para usuários existentes no histórico:

``` text
user_id
   ↓
linhas do usuário
   ↓
feature_cols
   ↓
StandardScaler
   ↓
LogisticRegression.predict_proba
   ↓
score
   ↓
sort descending
   ↓
Top 10
```

O score produzido pelo modelo é a base do ranking, conforme solicitado
pelo case.

A resposta contém:

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

O modelo e o scaler não são carregados durante a requisição. Eles
permanecem disponíveis na instância da aplicação depois do startup.

------------------------------------------------------------------------

## 6. Cold Start

Quando o `user_id` não aparece no histórico, não existem informações
suficientes para calcular as features comportamentais necessárias ao
ranking personalizado.

A aplicação utiliza um fallback baseado em `popularity_score`.

``` text
usuário sem histórico
        ↓
fallback
        ↓
produtos ordenados por popularidade
        ↓
Top 10
```

A resposta indica explicitamente o uso do fallback:

``` json
{
  "user_id": "cold_start_user",
  "recommendations": [
    {
      "product_id": "p_030",
      "score": 0.801
    }
  ],
  "fallback": true
}
```

Essa estratégia garante uma resposta mesmo quando não existe histórico
individual.

A escolha por popularidade também mantém o fallback simples,
determinístico e barato em termos computacionais.

------------------------------------------------------------------------

## 7. API

### Health check

``` http
GET /health
```

Resposta:

``` json
{
  "status": "ok"
}
```

### Recommendation

``` http
GET /recommendations/{user_id}
```

Retorna o Top 10 para usuários conhecidos ou utiliza o fallback para
usuários sem histórico.

### Metrics

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

## 8. Observabilidade

A aplicação registra logs estruturados em formato legível por sistemas
de agregação.

Para cada requisição de recomendação são registrados:

-   `user_id`;
-   `latency_ms`;
-   `fallback`.

Exemplos:

``` text
recommendation_request user_id=u_0242 latency_ms=11.02 fallback=False
recommendation_request user_id=u_090909 latency_ms=7.27 fallback=True
```

Também são registrados eventos importantes do ciclo de vida:

``` text
feature_processing_started
datasets_loaded
feature_processing_completed
model_loaded
```

### Métricas

São mantidas as seguintes métricas:

-   total de requisições;
-   total de fallbacks;
-   total de erros;
-   latência média.

A exposição ocorre pelo endpoint `/metrics`.

### Próximas métricas

A evolução natural da observabilidade é adicionar:

-   p50;
-   p95;
-   p99;
-   latência por etapa;
-   taxa de erro;
-   métricas de negócio;
-   request/correlation ID;
-   tracing distribuído;
-   alertas.

------------------------------------------------------------------------

## 9. Testes

Os testes cobrem as principais partes do serviço.

### Feature processing

Valida:

-   cálculo de `interactions`;
-   cálculo de `user_affinity_match`.

### Health

Valida o endpoint `/health`.

### Metrics

Valida a disponibilidade e a estrutura do endpoint `/metrics`.

### Recommendation

Valida:

-   usuário conhecido;
-   quantidade de recomendações;
-   existência de `product_id` e `score`;
-   scores entre 0 e 1;
-   ordenação decrescente.

### Cold start

Valida que um usuário inexistente recebe os produtos mais populares.

### End-to-end

O teste de integração utiliza `TestClient` e executa o fluxo HTTP
completo:

``` text
HTTP request
     ↓
FastAPI
     ↓
feature dataset
     ↓
modelo
     ↓
ranking
     ↓
HTTP response
```

Sem mockar as camadas internas.

------------------------------------------------------------------------

## 10. Docker

A aplicação possui containerização através de Docker.

### Build

``` bash
docker build -t personalization-api .
```

### Run

``` bash
docker run --rm -p 8000:8000 personalization-api
```

O container executa a mesma aplicação utilizada no ambiente local.

O `Dockerfile` instala as dependências antes de copiar o código da
aplicação, permitindo aproveitar o cache da camada de instalação quando
os arquivos de dependências não mudam.

------------------------------------------------------------------------

## 11. Decisões arquiteturais

### Feature processing no startup

**Motivo:**  
O processamento das features não depende do `user_id` recebido pela 
requisição. Executá-lo durante o startup evita repetir a mesma preparação 
a cada chamada da API.

**Benefício:**  
O caminho da requisição fica concentrado na seleção das features, 
transformação, inferência e ranking, mantendo a latência mais previsível.

**Evolução:**  
A etapa de feature processing pode ser desacoplada da API e executada
por um processo de atualização de dados, disponibilizando as features
já processadas para o serviço de recomendação.

---

### Dataset de features em memória

**Motivo:**  
O serviço precisa consultar rapidamente as features associadas ao 
usuário e aos produtos candidatos durante a inferência.

**Benefício:**  
O acesso em memória reduz o custo de leitura durante a requisição 
e simplifica o fluxo de serving.

**Evolução:**  
O dataset pode ser substituído por uma camada de armazenamento de 
features, como um feature store ou outro mecanismo de armazenamento 
distribuído, sem alterar o contrato da API.

---

### Modelo carregado no startup

**Motivo:**  
O artefato do modelo e seus componentes de pré-processamento são os
mesmos para as requisições atendidas pela instância.

**Benefício:**  
O modelo permanece carregado em memória e não é necessário realizar
`pickle.load()` durante cada requisição, reduzindo o trabalho 
no caminho crítico.

**Evolução:**  
O carregamento pode evoluir para um mecanismo de gerenciamento e 
versionamento de modelos, permitindo atualizações controladas, 
validação de compatibilidade e rollback.

---

### Inferência online

**Motivo:**  
O score precisa ser calculado para os produtos candidatos do 
usuário no momento da requisição.

**Benefício:**  
A API consegue produzir recomendações utilizando o modelo atual sem 
precisar armazenar previamente todas as recomendações finais dos usuários.

**Evolução:**  
O fluxo pode ser dividido em duas etapas: geração de candidatos e 
ranking. Dessa forma, o modelo de ranking trabalha somente sobre 
um conjunto reduzido de produtos candidatos.

---

### Cold start por popularidade

**Motivo:**  
Usuários sem histórico não possuem informações comportamentais suficientes
 para gerar uma recomendação personalizada.

**Benefício:**  
O fallback garante uma resposta válida para qualquer `user_id`, utilizando
uma informação disponível independentemente do histórico individual.

**Evolução:**  
O fallback pode incorporar outras estratégias, como recomendações por 
categoria, contexto da requisição, tendências recentes ou modelos 
específicos para usuários novos.

------------------------------------------------------------------------

## 12. O que eu faria diferente com mais tempo

### Dados

-   Separar a atualização das features do ciclo de vida da API;
-   validação automática da qualidade dos dados;

### Modelo

-   versionamento dos artefatos;
-   validação mais completa do `model_card.json`;
-   controle de compatibilidade entre versão do modelo e dependências;

### Serving

-   candidate generation;
-   cache de resultados quando apropriado;

### Observabilidade

-   p50/p95/p99;
-   tracing distribuído;
-   dashboards;
-   alertas;
-   logs detalhados a partir do usuário requisitado.

------------------------------------------------------------------------

## 13. Limitações conhecidas

As principais limitações da implementação atual são:

1.  Os dados de entrada são fornecidos em CSV.
2.  O dataset de features é mantido em memória.
3.  As métricas são mantidas em memória.
4.  O fallback utiliza somente popularidade.
5.  O ranking considera o conjunto de produtos gerado pelo feature
    processing.
6.  A atualização de dados e do modelo ocorre por ciclo de inicialização
    da aplicação.

Essas decisões mantêm o serviço simples e coerente com o escopo do case,
enquanto deixam pontos claros de evolução.

------------------------------------------------------------------------

## 14. Como executar

### Ambiente local

``` bash
pip install -r requirements.txt
python -m pytest -v
uvicorn app.main:app --reload
```

Acessar:

``` text
http://localhost:8000/docs
http://localhost:8000/health
http://localhost:8000/metrics
http://localhost:8000/recommendations/{user_id}
```

### Docker

``` bash
docker build -t personalization-api .
docker run --rm -p 8000:8000 personalization-api
```

------------------------------------------------------------------------

## 15. Resumo

A solução mantém o processamento de dados separado da inferência e
carrega o modelo uma única vez no ciclo de vida da aplicação.

``` text
events + products
       ↓
feature processing
       ↓
feature dataset
       ↓
FastAPI
       ↓
user_id
       ↓
features
       ↓
scaler + model
       ↓
score
       ↓
ranking
       ↓
Top 10
```

Para usuários sem histórico:

``` text
user_id
   ↓
sem histórico
   ↓
popularity_score
   ↓
Top 10
```

A arquitetura prioriza baixa latência no caminho da requisição,
separação de responsabilidades, tratamento explícito de cold start,
observabilidade e testes do fluxo completo.
