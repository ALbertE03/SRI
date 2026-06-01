# SRI RAG System

Sistema de Recuperacion de Informacion en espanol con RAG, busqueda hibrida LM + vectorial, busqueda web como fallback y retroalimentacion Rocchio desde la UI.

## Requisitos

- Python >=3.12 y <3.14
- Node.js 18+
- uv
- pnpm
- 4GB+ RAM minimo (8GB+ recomendado)
- 20GB+ libres para modelos, indices y contenedores

## Instalacion

```bash
uv sync
cd ui && pnpm install && cd ..
```

## Ejecucion

### API

```bash
uv run python api.py
```

La API queda disponible en:

- API: <http://localhost:8000>
- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- OpenAPI JSON: <http://localhost:8000/openapi.json>

### UI

```bash
cd ui && pnpm dev
```

La UI de desarrollo queda disponible en <http://localhost:5173>. Vite proxya `/api` hacia `http://localhost:8000`.

### Docker Compose

```bash
docker compose up --build
```

El servicio `api` escucha en el puerto `8000` y el servicio `ui` en el puerto `5173`.

### Crawlers (Scrapy)

Para recolectar datos de noticias tecnológicas, el proyecto incluye dos arañas de Scrapy: `xataka_mobile` y `xataka_pc`.

**(Local):**

```bash
# Para ejecutar los crawlers de forma local necesitas activar tu ambiente y ejecutar:
uv run scrapy crawl xataka_mobile
uv run scrapy crawl xataka_pc
```

**Docker:**
Se ha agregado un servicio de crawler que usa el perfil `tools`. Puedes ejecutarlo así:

```bash
# Extraer datos con el crawler de móviles usando Docker
docker compose run --rm crawler xataka_mobile

# Extraer datos con el crawler de PC usando Docker
docker compose run --rm crawler xataka_pc
```

## Variables de Entorno

Crea un `.env` solo con los valores que necesites sobreescribir.

### Modelo

| Variable | Descripcion | Opciones Validas | Por defecto |
|----------|-------------|------------------|-------------|
| `MODEL_PATH` | Ruta local a un `.gguf` o repo de HuggingFace. Vacio descarga el modelo por defecto. | Texto | `lm-kit/llama-3.1-8b-instruct-gguf` |
| `MODEL_TEMPERATURE` | Temperatura de muestreo del LLM. | Decimal mayor a 0 | `0.3` |
| `MODEL_MAX_TOKENS` | Maximo de tokens generados. | Entero mayor a 0 | `200` |
| `MODEL_N_CTX` | Tamano de ventana de contexto. | Entero mayor a 0 | `2048` |
| `MODEL_VERBOSE` | Logs verbose de `llama-cpp`. | `true`, `false` | `false` |
| `GGML_BACKEND` | Backend para cargar embeddings. | `cpu`, `cuda`, `metal` | `cpu` |
| `N_BATCH` | Tamaño del batch para inferencia LLM. | Entero mayor a 0 | `64` |
| `N_THREADS` | Hilos a usar en CPU. | Entero mayor a 0 | `8` |

### RAG

| Variable | Descripcion | Opciones Validas | Por defecto |
|----------|-------------|------------------|-------------|
| `RAG_RELEVANCE_THRESHOLD` | Umbral para activar busqueda web. | Decimal `0.0` - `1.0` | `0.5` |
| `RAG_ENABLE_QUERY_EXPANSION` | Habilita expansion de consulta por coocurrencia. | `true`, `false` | `true` |
| `RAG_QUERY_EXPANSION_TERMS` | Numero de terminos agregados por expansion. | Entero mayor a 0 | `10` |
| `RAG_COOCCURRENCE_WINDOW` | Ventana para matriz de coocurrencia. | Entero mayor a 0 | `1` |
| `RAG_LM_RETRIEVER_WEIGHT` | Peso del retriever LM en el ensemble. | Decimal `0.0` - `1.0` | `0.5` |
| `RAG_VECTOR_RETRIEVER_WEIGHT` | Peso del retriever vectorial en el ensemble. | Decimal `0.0` - `1.0` | `0.5` |
| `RAG_RETRIEVER_K` | Numero de documentos a recuperar por defecto. | Entero mayor a 0 | `10` |

### Indexacion y Vector DB

| Variable | Descripcion | Opciones Validas | Por defecto |
|----------|-------------|------------------|-------------|
| `VECTOR_DB_COLLECTION_NAME` | Nombre de la coleccion Chroma. | Texto | `sri_documents_transformer` |
| `VECTOR_DB_TOP_K` | Numero de resultados en busqueda vectorial. | Entero mayor a 0 | `10` |
| `BATCH_SIZE` | Tamano de lote al poblar Chroma. | Entero mayor a 0 | `1000` |
| `RESET` | Borra y recrea la coleccion vectorial al indexar. | `true`, `false` | `false` |
| `FORCE` | Fuerza reconstruccion de componentes al iniciar la API. | `true`, `false` | `false` |
| `CHUNK_SIZE` | Tamano objetivo de chunk. | Entero mayor a 0 | `500` |
| `CHUNK_OVERLAP` | Solapamiento entre chunks. | Entero mayor a 0 | `100` |
| `STRATEGY` | Estrategia de chunking. | `sliding` | `sliding` |
| `MIN_CHUNK_SIZE` | Tamano minimo de chunk. | Entero mayor a 0 | `100` |
| `INDEX_LANGUAGE` | Idioma del normalizador. | `spanish`, `english` | `spanish` |
| `MU` | Parametro de suavizado del retriever LM. | Decimal mayor a 0 | `500.0` |
| `MAX_FEATURES` | Maximo de features para fallback TF-IDF. | Entero mayor a 0 | `384` |

### Busqueda Web, API y Feedback

| Variable | Descripcion | Opciones Validas | Por defecto |
|----------|-------------|------------------|-------------|
| `WEB_SEARCH_ENGINE` | Motores de busqueda. | `all`, `duckduckgo`, `yandex`, `brave`, `google`, `bing` | `all` |
| `WEB_SEARCH_MAX_RESULTS` | Maximo de resultados por busqueda web. | Entero mayor a 0 | `3` |
| `WEB_SEARCH_REGION` | Region para DuckDuckGo. | `es-es`, `en-us` | `es-es` |
| `WEB_SEARCH_TIME` | Filtro temporal para DuckDuckGo. | `y`, `m`, `w` | `y` |
| `DEFAULT_TIMEOUT` | Timeout HTTP para extraer contenido web. | Entero mayor a 0 | `15` |
| `API_HOST` | Host del servidor FastAPI. | IP | `0.0.0.0` |
| `API_PORT` | Puerto del servidor FastAPI. | Puerto | `8000` |
| `ALPHA` | Peso de la consulta original en Rocchio. | Decimal mayor a 0 | `1.0` |
| `BETA` | Peso de documentos relevantes en Rocchio. | Decimal mayor a 0 | `0.75` |
| `GAMMA` | Peso de documentos no relevantes en Rocchio. | Decimal mayor a 0 | `0.15` |

### UI

Estas variables se leen desde `ui/vite.config.js` durante desarrollo.

| Variable | Descripcion | Por defecto |
|----------|-------------|-------------|
| `VITE_API_PROXY_TARGET` | Backend destino para el proxy `/api` de Vite. | `http://localhost:8000` |
| `CHOKIDAR_USEPOLLING` | Activa polling para file watching. | `false` |

### Scraping

Estas variables las lee Scrapy desde `src/extract_data/settings.py`.

| Variable | Descripcion | Por defecto |
|----------|-------------|-------------|
| `USER_AGENT` | User-Agent para los spiders. | Chrome/macOS |
| `ROBOTSTXT_OBEY` | Respeta `robots.txt`. | `true` |
| `CLOSESPIDER_TIMEOUT` | Timeout maximo por spider en segundos. | `3500` |
| `DEPTH_LIMIT` | Profundidad maxima de crawling. | `3` |
| `CONCURRENT_REQUESTS` | Requests concurrentes globales. | `8` |
| `CONCURRENT_REQUESTS_PER_DOMAIN` | Requests concurrentes por dominio. | `4` |
| `COOKIES_ENABLED` | Habilita cookies en Scrapy. | `false` |
| `AUTOTHROTTLE_ENABLED` | Habilita AutoThrottle. | `true` |
| `AUTOTHROTTLE_START_DELAY` | Delay inicial de AutoThrottle. | `2` |
| `AUTOTHROTTLE_MAX_DELAY` | Delay maximo de AutoThrottle. | `60` |
| `AUTOTHROTTLE_TARGET_CONCURRENCY` | Concurrencia objetivo de AutoThrottle. | `1.0` |
| `HTTPCACHE_ENABLED` | Habilita cache HTTP de Scrapy. | `true` |
| `HTTPCACHE_EXPIRATION_SECS` | Expiracion de cache HTTP en segundos. | `86400` |

## Endpoints

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| `GET` | `/` | Informacion basica de la API. |
| `GET` | `/docs` | Documentacion Swagger UI. |
| `GET` | `/redoc` | Documentacion ReDoc. |
| `GET` | `/openapi.json` | Esquema OpenAPI. |
| `POST` | `/api/query` | Recupera documentos locales/web y devuelve una `session_id` para feedback. |
| `POST` | `/api/query/feedback` | Aplica feedback Rocchio, re-recupera documentos y genera la respuesta final. |

### POST `/api/query`

```json
{
  "query": "Que movil tiene mejor bateria?",
  "use_rag": true,
  "top_k": 10,
  "relevance_threshold": 0.6,
  "use_query_expansion": true,
  "use_internet_search": true
}
```

Respuesta principal:

```json
{
  "query": "...",
  "expanded_query": "...",
  "top_local_score": 0.0,
  "documents_retrieved": [],
  "session_id": "..."
}
```

### POST `/api/query/feedback`

```json
{
  "session_id": "...",
  "relevant_docs": ["doc_id_1"],
  "non_relevant_docs": ["doc_id_2"],
  "original_query": "Que movil tiene mejor bateria?",
  "top_k": 3
}
```

Respuesta principal:

```json
{
  "answer": "...",
  "retrieved_docs": [],
  "reformulated_query": {},
  "session_id": "..."
}
```

## Estructura del Proyecto

```text
SRI/
├── api.py                         # Entrada para iniciar FastAPI
├── src/
│   ├── config.py                  # Configuracion central de la API/RAG
│   ├── api/                       # App FastAPI, modelos y rutas
│   │   ├── app.py
│   │   ├── server.py
│   │   ├── models.py
│   │   └── routes/
│   ├── errors/                    # Excepciones por modulo
│   ├── extract_data/              # Scrapy: items, pipelines, settings y spiders
│   │   └── spiders/
│   │       ├── mobile/xataka_mobile/
│   │       └── pc/xataka_pc/
│   ├── feedback/                  # Rocchio feedback
│   ├── generator/                 # Generacion de respuestas con LLM
│   ├── indexing/                  # Carga, chunking e indice invertido
│   ├── positioning/               # Ranking de resultados
│   ├── rag/                       # Pipeline RAG
│   ├── retrieval/                 # Retriever LM y wrappers LangChain
│   ├── search_internet/           # Busqueda web y fetch de contenido
│   ├── stats/                     # Estadisticas de consultas
│   ├── utils/                     # Logger y descarga de modelos
│   └── vector_db/                 # Chroma, embeddings y retriever vectorial
├── ui/                            # UI React/Vite y config Nginx
├── data/
│   ├── mobile/                    # JSONL scrapeados de Xataka Mobile
│   ├── pc/                        # JSONL scrapeados de Xataka PC
│   └── stats/                     # Metricas persistidas
├── indexes/                       # Indices LM, invertido y Chroma
├── models/                        # Modelos GGUF y cache HuggingFace
├── papers/                        # PDFs de referencia
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── scrapy.cfg
└── README.md
```

## Agregar Documentos

Los documentos se almacenan en `data/`. El sistema los carga e indexa al iniciar.

Formatos soportados: JSON/JSONL y texto plano.

Ejemplo de documento JSON:

```json
{
  "title": "Titulo del articulo",
  "url": "https://ejemplo.com",
  "content": "Contenido del articulo...",
  "source": "xataka"
}
```

## Licencia

MIT
