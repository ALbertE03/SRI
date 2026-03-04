
import logging
import os
from datetime import datetime, timezone

from scrapy import signals
from scrapy.exceptions import NotConfigured


LOG_DIR = os.path.join(
    os.path.dirname(  # src/extract_data/
        os.path.dirname(  # src/
            os.path.dirname(  # project root
                os.path.abspath(__file__)
            )
        )
    ),
    "logs",
)

_LOG_FMT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


class SpiderFileLogger:
    """
    Scrapy extension that writes per-spider log files.

    Activated automatically when ``SPIDER_FILE_LOGGING = True`` is set in
    *settings.py* (enabled by default through the EXTENSIONS mapping).
    Set ``SPIDER_FILE_LOGGING = False`` to disable without removing the
    extension entry.
    """

    def __init__(self, log_dir: str):
        self._log_dir = log_dir
        self._handlers: dict[str, logging.FileHandler] = {}

    # ------------------------------------------------------------------ #
    #  Scrapy extension protocol                                           #
    # ------------------------------------------------------------------ #

    @classmethod
    def from_crawler(cls, crawler):
        if not crawler.settings.getbool("SPIDER_FILE_LOGGING", True):
            raise NotConfigured("SPIDER_FILE_LOGGING is False")

        log_dir = crawler.settings.get("SPIDER_LOG_DIR", LOG_DIR)
        os.makedirs(log_dir, exist_ok=True)

        ext = cls(log_dir)
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        return ext

    # ------------------------------------------------------------------ #
    #  Signal handlers                                                     #
    # ------------------------------------------------------------------ #

    def spider_opened(self, spider):
        log_path = os.path.join(self._log_dir, f"{spider.name}.log")

        handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        handler.setFormatter(logging.Formatter(_LOG_FMT, datefmt=_DATE_FMT))
        handler.setLevel(logging.DEBUG)

        # Session separator so multiple runs in the same file are easy to scan
        session_start = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        separator = f"\n{'=' * 72}\n  Spider run started: {session_start}\n{'=' * 72}\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(separator)

        # Attach to Scrapy's spider logger (root logger also captures it)
        spider.logger.logger.addHandler(handler)
        self._handlers[spider.name] = handler

        spider.logger.info("File logging active → %s", log_path)

    def spider_closed(self, spider, reason):
        handler = self._handlers.pop(spider.name, None)
        if handler:
            spider.logger.info(
                "Spider closed (reason=%s) — closing log file handler.", reason
            )
            handler.flush()
            handler.close()
            spider.logger.logger.removeHandler(handler)
