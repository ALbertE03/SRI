# SRI — Sistema de Recuperación de Información de Noticias

Motor de búsqueda sobre noticias tecnológicas de [Xataka](https://www.xataka.com/) (categorías móvil y PC).  
El sistema utiliza el modelo **Modelo Probabilístico de Lenguaje (Query Likelihood)** con **Suavizado de Dirichlet**, incorporando además **Pseudo-Relevance Feedback (RM3)** para expansión de consultas y **Chroma DB** como base de datos de vectores.

---

## Requisitos

| Herramienta | Versión mínima |
|-------------|----------------|
| Docker      | 24+            |
| Docker Compose | v2 (`docker compose`) |

No es necesario instalar Python ni ninguna dependencia en el host; el entorno está completamente contenedorizado, utilizando `uv` para la gestión de paquetes.

---

## Estructura del proyecto

```
.
├── data/               # Artículos scrapeados (.jsonl), generados por los spiders
├── indexes/            # Índice invertido, modelo LM y persistencia de Chroma
│   ├── index/          # Inverted Index (pickle)
│   ├── lm/             # Modelo LM + estadísticas de colección
│   └── chroma/         # Datos persistentes de Chroma DB
├── logs/               # Logs de ejecución de los spiders
├── src/
│   ├── extract_data/   # Spiders de Scrapy + pipelines
│   ├── indexing/       # Construcción del índice invertido y almacenamiento
│   ├── retrieval/      # LM Retriever (Dirichlet) + RM3 (Query Processor)
│   └── vector_db/      # Integración con Chroma DB + Embeddings (TF-IDF)
├── main.py             # CLI principal (build & query)
├── docker-compose.yml
└── dockerfile
```

---

## Paso a paso

### 1. Construir la imagen

```bash
docker compose build
```

---

### 2. Ejecutar los spiders (scraping)

```bash
docker compose run --rm crawl
```

Extrae artículos de *Xataka Móvil* y *Xataka PC* en paralelo, guardándolos en `data/`. Los logs se escriben en `logs/`.

---

### 3. Construir el índice invertido

```bash
docker compose run --rm index
```

Lee los `.jsonl` de `data/`, construye el índice invertido (TF, metadata, vocabulario) y lo guarda en `indexes/index/`.

---

### 4. Construir el Modelo de Lenguaje y Vector Store

```bash
docker compose run --rm vector-index
```

Este comando realiza dos acciones clave:
1.  **Entrenar el LM**: Ajusta un modelo de lenguaje con **Suavizado de Dirichlet** (μ=2000) a partir del índice.
2.  **Inicializar Chroma**: Popula la base de datos **Chroma DB** con vectores TF-IDF generados a partir del contenido de los documentos.

---

### 5. Realizar consultas interactivas

```bash
docker compose run --rm -it query
```

Inicia la interfaz de búsqueda interactiva. El proceso de recuperación incluye:
1.  **Procesamiento de Consulta**: Normalización y extracción de tokens.
2.  **RM3 (Pseudo-Relevance Feedback)**: Expansión automática de la consulta basada en los 5 documentos principales (α=0.5).
3.  **Ranking Probabilístico**: Clasificación de documentos según la probabilidad de que el documento haya generado la consulta expandida.

---

## Flujo completo (One-linear)

Puedes ejecutar todo el pipeline de inicio a fin con:

```bash
docker compose build && \
docker compose run --rm crawl && \
docker compose run --rm index && \
docker compose run --rm vector-index && \
docker compose run --rm -it query
```

---

## Detalles Técnicos

- **Suavizado de Dirichlet**: Se utiliza para manejar términos ausentes en documentos individuales pero presentes en la colección total. Parámetro por defecto **μ=2000**.
- **RM3 (RM1 Interpolado)**: Mejora la relevancia al expandir la consulta original con términos provenientes de los documentos recuperados inicialmente. Combina la consulta original (α=0.5) con el modelo de relevancia (1-α=0.5).
- **Chroma DB**: Utilizado para almacenamiento eficiente y búsqueda por similitud de coseno sobre representaciones vectoriales.
- **Normalización**: Uso de NLTK para tokenización en español, eliminación de stop-words y limpieza de caracteres no alfanuméricos.
