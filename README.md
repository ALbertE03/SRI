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

## Variables de Entorno

Crea un `.env` solo con los valores que necesites sobreescribir. Estas son las variables usadas por la API/RAG; la mayoria se leen desde `src/config.py`.

### Modelo

| Variable | Descripcion | Por defecto |
|----------|-------------|-------------|
| `MODEL_PATH` | Ruta local a un `.gguf` o repo de HuggingFace. Vacio descarga el modelo por defecto. | `""` |
| `MODEL_TEMPERATURE` | Temperatura de muestreo del LLM. | `0.3` |
| `MODEL_MAX_TOKENS` | Maximo de tokens generados. | `2048` |
| `MODEL_N_CTX` | Tamano de ventana de contexto. | `2048` |
| `MODEL_VERBOSE` | Logs verbose de `llama-cpp`. | `false` |
| `GGML_BACKEND` | Backend para cargar embeddings: `cpu`, `cuda` o `metal`. | `cpu` |

### RAG

| Variable | Descripcion | Por defecto |
|----------|-------------|-------------|
| `RAG_RELEVANCE_THRESHOLD` | Umbral para activar busqueda web si la relevancia local es baja. | `0.6` |
| `RAG_ENABLE_QUERY_EXPANSION` | Habilita expansion de consulta por coocurrencia. | `true` |
| `RAG_QUERY_EXPANSION_TERMS` | Numero de terminos agregados por expansion. | `10` |
| `RAG_COOCCURRENCE_WINDOW` | Ventana para matriz de coocurrencia. | `1` |
| `RAG_LM_RETRIEVER_WEIGHT` | Peso del retriever LM en el ensemble. | `0.5` |
| `RAG_VECTOR_RETRIEVER_WEIGHT` | Peso del retriever vectorial en el ensemble. | `0.5` |
| `RAG_RETRIEVER_K` | Numero de documentos a recuperar por defecto. | `10` |

### Indexacion y Vector DB

| Variable | Descripcion | Por defecto |
|----------|-------------|-------------|
| `VECTOR_DB_COLLECTION_NAME` | Nombre de la coleccion Chroma. | `sri_documents_transformer` |
| `VECTOR_DB_TOP_K` | Numero de resultados en busqueda vectorial directa. | `10` |
| `BATCH_SIZE` | Tamano de lote al poblar Chroma. | `1000` |
| `RESET` | Borra y recrea la coleccion vectorial al indexar. | `false` |
| `FORCE` | Fuerza reconstruccion de componentes al iniciar la API. | `false` |
| `CHUNK_SIZE` | Tamano objetivo de chunk. | `3500` |
| `CHUNK_OVERLAP` | Solapamiento entre chunks. | `100` |
| `STRATEGY` | Estrategia de chunking. | `sliding` |
| `MIN_CHUNK_SIZE` | Tamano minimo de chunk. | `100` |
| `INDEX_LANGUAGE` | Idioma del normalizador. | `spanish` |
| `MU` | Parametro de suavizado del retriever LM. | `2000.0` |
| `MAX_FEATURES` | Maximo de features para fallback TF-IDF. | `15000` |

### Busqueda Web, API y Feedback

| Variable | Descripcion | Por defecto |
|----------|-------------|-------------|
| `WEB_SEARCH_ENGINE` | Motores de busqueda: `all`, `duckduckgo`, `yandex`, `brave`, `google`, `bing` o lista separada por coma/espacio. | `all` |
| `WEB_SEARCH_MAX_RESULTS` | Maximo de resultados por busqueda web. | `3` |
| `WEB_SEARCH_REGION` | Region para DuckDuckGo. | `es-es` |
| `WEB_SEARCH_TIME` | Filtro temporal para DuckDuckGo. | `y` |
| `DEFAULT_TIMEOUT` | Timeout HTTP para extraer contenido web. | `15` |
| `API_HOST` | Host del servidor FastAPI. | `0.0.0.0` |
| `API_PORT` | Puerto del servidor FastAPI. | `8000` |
| `ALPHA` | Peso de la consulta original en Rocchio. | `1.0` |
| `BETA` | Peso de documentos relevantes en Rocchio. | `0.75` |
| `GAMMA` | Peso de documentos no relevantes en Rocchio. | `0.15` |

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
