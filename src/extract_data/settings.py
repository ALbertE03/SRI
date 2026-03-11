# Scrapy settings

BOT_NAME = "sri"

SPIDER_MODULES = [
    "src.extract_data.spiders.mobile.xataka_mobile",
    "src.extract_data.spiders.pc.xataka_pc",
]
NEWSPIDER_MODULE = "src.extract_data"


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)


# Always respect robots.txt
ROBOTSTXT_OBEY = True


# Hard timeout per spider (seconds). Prevents runaway crawls.
CLOSESPIDER_TIMEOUT = 3600  # 1 hour

# maximum concurrent requests
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 4

# Disable cookies (reduces tracking / server load)
COOKIES_ENABLED = False

DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es,en;q=0.9",
}

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2
AUTOTHROTTLE_MAX_DELAY = 60
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0

HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 86400  # 24 hours
HTTPCACHE_DIR = "httpcache"
HTTPCACHE_IGNORE_HTTP_CODES = [500, 502, 503, 504, 400, 403, 404, 408, 429]
HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"

REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

ITEM_PIPELINES = {
    # Stamp every item with its collection timestamp
    "src.extract_data.pipelines.TimestampPipeline": 100,
    #  Drop URL duplicates within a single spider run
    "src.extract_data.pipelines.DuplicatesPipeline": 300,
    # Persist items to organised JSONL files on disk
    "src.extract_data.pipelines.JsonStoragePipeline": 500,
}

# Root directory where scraped data files are written.
# Sub-directories (mobile/, pc/, general/) are created automatically.
DATA_DIR = "data"


DOWNLOAD_DELAYS_PER_SPIDER = {
    "xataka_mobile": 5.5,
    "xataka_pc": 5.5,
}


EXTENSIONS = {
    "src.extract_data.log.SpiderFileLogger": 500,
}

SPIDER_FILE_LOGGING = True

