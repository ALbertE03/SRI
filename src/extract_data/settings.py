# Scrapy settings

BOT_NAME = "sri"

SPIDER_MODULES = [
    "src.extract_data.spiders.mobile.xataka_mobile",
    "src.extract_data.spiders.mobile.apple_newsroom",
    "src.extract_data.spiders.pc.xataka_pc",
]
NEWSPIDER_MODULE = "src.extract_data"


USER_AGENT = "SRI-Bot (+https://github.com/ALbertE03/SRI)"

# robots.txt rules
ROBOTSTXT_OBEY = True

# maximum concurrent requests
CONCURRENT_REQUESTS = 8

CONCURRENT_REQUESTS_PER_DOMAIN = 8
# CONCURRENT_REQUESTS_PER_IP = 8

# Disable cookies
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
    "src.extract_data.pipelines.DuplicatesPipeline": 300,
}


DOWNLOAD_DELAYS_PER_SPIDER = {
    "apple_newsroom": 2.5,
    "samsung_newsroom": 2.0,
    "gsmarena_news": 2.0,
    "xataka": 1.5,
}


# Logging

EXTENSIONS = {
    "src.extract_data.log.SpiderFileLogger": 500,
}


SPIDER_FILE_LOGGING = True
