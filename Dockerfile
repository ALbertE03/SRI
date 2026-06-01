FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

RUN uv pip install --system torch==2.3.1 

WORKDIR /app

COPY pyproject.toml .

RUN uv pip install --system llama-cpp-python 

RUN uv pip install --system -e .

COPY . .

RUN python -m nltk.downloader punkt_tab stopwords wordnet

EXPOSE 8000

CMD ["python", "api.py"]