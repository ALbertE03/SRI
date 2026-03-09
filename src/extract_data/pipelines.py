import json
import os
from datetime import datetime, timezone
from pathlib import Path

from scrapy.exceptions import DropItem

from .items import MobileItem, PCItem


class DuplicatesPipeline:
    """Drops items with URLs already seen in the current crawl session."""

    def __init__(self):
        self.urls_seen = set()

    def process_item(self, item, spider):
        if item.get("url") in self.urls_seen:
            raise DropItem(f"Duplicate item found: {item['url']}")
        self.urls_seen.add(item["url"])
        return item


class TimestampPipeline:
    """Adds a scraped_at ISO timestamp to every item."""

    def process_item(self, item, spider):
        item["scraped_at"] = datetime.now(timezone.utc).isoformat()
        return item


class JsonStoragePipeline:
    """
    Persists scraped items as newline-delimited JSON files organized by
    content type under  <DATA_DIR>/{mobile,pc,general}/.

    Each spider session writes to a file named:
        <spider_name>_<YYYY-MM-DD>.jsonl

    If the file already exists (e.g. multiple daily runs) items are
    appended rather than overwriting the entire file.
    """

    # Relative path from project root; overridden by DATA_DIR setting
    DEFAULT_DATA_DIR = os.path.join(
        os.path.dirname(          # src/extract_data/
            os.path.dirname(      # src/
                os.path.dirname(  # project root
                    os.path.abspath(__file__)
                )
            )
        ),
        "data",
    )

    def open_spider(self, spider):
        data_dir = Path(
            spider.settings.get("DATA_DIR", self.DEFAULT_DATA_DIR)
        )
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Resolve sub-directory by spider name convention
        if "mobile" in spider.name or spider.name in (
            "apple_newsroom",
            "xataka_mobile",
        ):
            sub = "mobile"
        elif "pc" in spider.name or spider.name in ("xataka_pc",):
            sub = "pc"
        else:
            sub = "general"

        output_dir = data_dir / sub
        output_dir.mkdir(parents=True, exist_ok=True)

        filepath = output_dir / f"{spider.name}_{date_str}.jsonl"
        self._file = open(filepath, "a", encoding="utf-8")
        spider.logger.info(f"[JsonStoragePipeline] Writing to {filepath}")

    def close_spider(self, spider):
        self._file.close()

    def process_item(self, item, spider):
        line = json.dumps(dict(item), ensure_ascii=False)
        self._file.write(line + "\n")
        return item

