from typing import List
from urllib.parse import quote
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from langchain_core.documents import Document

from src.config import WEB_SEARCH_ENGINE, WEB_SEARCH_MAX_RESULTS, WEB_SEARCH_REGION, WEB_SEARCH_TIME
from src.errors.internet_search_error import WebSearchExecutionError
from src.utils.logger import search_logger as logger
from src.search_internet.content_fetcher import ContentFetcher
from src.indexing.indexer import TextNormalizer

DIRECT_ENGINES = {
    "yandex": "https://yandex.com/search/?text={query}",
    "brave": "https://search.brave.com/search?q={query}",
    "google": "https://www.google.com/search?q={query}", 
    "bing": "https://www.bing.com/search?q={query}",
}

class WebSearcher:
    """
    Search the internet across multiple engines and return results as LangChain Documents.
    By default searches duckduckgo + yandex + brave.
    """
    def __init__(self, max_results: int | None = None, normalizer: TextNormalizer | None = None, engine: str | None = None):
        raw = (engine or WEB_SEARCH_ENGINE).lower()
        if raw.lower() == "all":
            self.engines = ["duckduckgo",*list(DIRECT_ENGINES.keys())]
        else:
            self.engines = [e.strip() for e in raw.replace(",", " ").split()]
        actual_max_results = max_results if max_results is not None else WEB_SEARCH_MAX_RESULTS
        self.search_wrapper = DuckDuckGoSearchAPIWrapper(
            region=WEB_SEARCH_REGION, time=WEB_SEARCH_TIME, max_results=actual_max_results
        )
        self.content_fetcher = ContentFetcher()
        self.normalizer = normalizer

    def _search_duckduckgo(self, query: str) -> List[Document]:
        results = self.search_wrapper.results(query, max_results=WEB_SEARCH_MAX_RESULTS)
        documents = []

        filtered = [
            res for res in results
            if res.get("link") and "youtube.com" not in res.get("link", "")
        ]

        urls = list(set([res.get("link", "") for res in filtered]))

        logger.info(f"Fetching full content from {len(urls)} URLs...")
        contents = self.content_fetcher.fetch_all(urls)

        for res, page_content in zip(filtered, contents):
            if not page_content:
                continue
            doc = Document(
                page_content=page_content,
                metadata={
                    "title": res.get("title", "Internet Result"),
                    "url": res.get("link", ""),
                    "source": "Internet",
                },
            )
            documents.append(doc)

        return documents

    def _search_direct(self, engine: str, search_url: str, query: str) -> List[Document]:
        url = search_url.format(query=quote(query))
        logger.info(f"Searching directly via {url}")
        content = self.content_fetcher.fetch(url)
        if not content:
            return []
        doc = Document(
            page_content=content,
            metadata={
                "title": f"{engine.title()} Search: {query}",
                "url": url,
                "source": "Internet",
            },
        )
        return [doc]

    def search(self, query: str) -> List[Document]:
        logger.info(f"Searching the internet for: {query}  [engines={self.engines}]")
        try:
            all_documents = []
            for engine in self.engines:
                if engine == "duckduckgo":
                    all_documents.extend(self._search_duckduckgo(query))
                elif engine in DIRECT_ENGINES:
                    all_documents.extend(self._search_direct(engine, DIRECT_ENGINES[engine], query))
                else:
                    logger.warning(f"Unknown search engine: {engine}, skipping")

            logger.info(f"Got {len(all_documents)} documents with content across {len(self.engines)} engine(s)")
            return all_documents
        except Exception as exc:
            print(exc)
            raise WebSearchExecutionError("Error during web search execution.") from exc
    def __str__(self)->str:
        return f"WebSearcher(engines: {self.engines})"