FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml .
COPY scrapy.cfg .

RUN uv sync --no-dev

COPY src/ src/

RUN mkdir -p data/mobile data/pc logs indexes/index indexes/lsi

RUN python -c "\
    import urllib.request, zipfile, io, os; \
    base = 'https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages'; \
    dest_root = '/usr/local/share/nltk_data'; \
    resources = [ \
    ('corpora/wordnet.zip',        'corpora'), \
    ('tokenizers/punkt_tab.zip',   'tokenizers'), \
    ('corpora/stopwords.zip',      'corpora'), \
    ]; \
    [( \
    os.makedirs(dest_root + '/' + d, exist_ok=True), \
    zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(base + '/' + p).read())).extractall(dest_root + '/' + d) \
    ) for p, d in resources] \
    "


CMD ["/bin/sh", "-c", \
    "uv run scrapy crawl xataka_mobile > logs/xataka_mobile.log 2>&1 & \
    uv run scrapy crawl xataka_pc     > logs/xataka_pc.log 2>&1 & \
    wait && echo 'All spiders finished.'"]
