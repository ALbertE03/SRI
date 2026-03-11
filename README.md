# SRI — Sistema de Recuperación de Información

Motor de búsqueda sobre noticias tecnológicas de [Xataka](https://www.xataka.com/) (móvil y PC).  
El sistema extrae artículos mediante web scraping, los indexa con un índice invertido + LSI y permite realizar consultas en lenguaje natural.

---

## Requisitos

| Herramienta | Versión mínima |
|-------------|----------------|
| Docker      | 24+            |
| Docker Compose | v2 (`docker compose`) |

No es necesario instalar Python ni ninguna dependencia en el host; todo corre dentro del contenedor.

---

## Estructura del proyecto

```
.
├── data/           # Artículos scrapeados (.jsonl), generados por los spiders
│   ├── mobile/
│   └── pc/
├── indexes/        # Índice invertido y modelo LSI persistidos
├── logs/           # Logs de ejecución de los spiders
├── src/
│   ├── extract_data/   # Spiders de Scrapy + pipelines
│   ├── indexing/       # Construcción del índice invertido
│   └── retrieval/      # Retriever LSI + procesador de consultas
├── main.py             # CLI de consulta interactiva
├── docker-compose.yml
└── dockerfile
```

---

## Paso a paso

### 1. Construir la imagen

```bash
docker compose build
```

Solo es necesario la primera vez, o cuando se modifique el código o las dependencias.  
Para forzar una reconstrucción limpia:

```bash
docker compose build --no-cache
```

---

### 2. Ejecutar los spiders (scraping)

```bash
docker compose run --rm crawl
```

Lanza en paralelo los dos spiders:

- `xataka_mobile` → guarda en `data/mobile/`
- `xataka_pc` → guarda en `data/pc/`

Los logs se escriben en `logs/xataka_mobile.log` y `logs/xataka_pc.log`.  
El proceso puede tardar varios minutos según el volumen de páginas. El timeout máximo es de **1 hora** por spider.

> Los datos y logs se persisten en el host gracias a los volúmenes de Docker.

---

### 3. Construir el índice

```bash
docker compose run --rm index
```

Lee los `.jsonl` de `data/`, construye el índice invertido y el modelo LSI, y los guarda en `indexes/`.

> Este paso requiere que el scraping (paso 2) haya finalizado y existan archivos en `data/`.

---

### 4. Realizar consultas

```bash
docker compose run --rm -it query
```

Abre una sesión interactiva desde la que se pueden introducir consultas en lenguaje natural.  
El sistema devuelve los artículos más relevantes según el modelo LSI.

> El flag `-it` es necesario para que la terminal interactiva funcione correctamente.

---

## Flujo completo (de inicio a fin)

```bash
# 1. Construir imagen
docker compose build

# 2. Scrapear artículos
docker compose run --rm crawl

# 3. Indexar
docker compose run --rm index

# 4. Consultar
docker compose run --rm -it query
```

---

## Notas

- Los datos ya scrapeados en `data/` y los índices en `indexes/` persisten entre ejecuciones. No es necesario volver a scrapear si los datos son recientes.
- El caché HTTP de Scrapy se almacena en `httpcache/` y tiene una validez de **24 horas**, lo que acelera las re-ejecuciones.
- Para correr solo un spider concreto:

```bash
docker compose run --rm crawl /bin/sh -c "uv run scrapy crawl xataka_mobile"
```
