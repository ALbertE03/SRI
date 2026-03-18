import json
import os
from datetime import datetime, timezone
from pathlib import Path

from scrapy.exceptions import DropItem

from .items import MobileItem, PCItem


class DuplicatesPipeline:
    """Drops items with URLs already seen in current and past crawl sessions."""

    def open_spider(self, spider):
        self.urls_seen = set()

        data_dir_setting = spider.settings.get("DATA_DIR")
        if data_dir_setting:
            data_dir = Path(data_dir_setting)
        else:
            data_dir = Path(__file__).resolve().parent.parent.parent / "data"

        self.seen_urls_file = data_dir / "seen_urls.txt"

        if self.seen_urls_file.exists():
            with open(self.seen_urls_file, "r", encoding="utf-8") as f:
                for line in f:
                    url = line.strip()
                    if url:
                        self.urls_seen.add(url)
            spider.logger.info(
                f"[DuplicatesPipeline] Loaded {len(self.urls_seen)} URLs from {self.seen_urls_file}"
            )
        else:
            spider.logger.info(
                f"[DuplicatesPipeline] No seen URLs file found at {self.seen_urls_file}"
            )

        self.file = open(self.seen_urls_file, "a", encoding="utf-8")

    def close_spider(self, spider):

        if hasattr(self, "file"):
            self.file.close()

    def process_item(self, item, spider):
        url = item.get("url")
        if not url:
            return item

        if url in self.urls_seen:
            raise DropItem(f"Duplicate item found: {url}")

        self.urls_seen.add(url)

        self.file.write(url + "\n")
        self.file.flush()

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

    DEFAULT_DATA_DIR = os.path.join(
        os.path.dirname(  # src/extract_data/
            os.path.dirname(  # src/
                os.path.dirname(os.path.abspath(__file__))  # project root
            )
        ),
        "data",
    )

    def open_spider(self, spider):
        data_dir = Path(spider.settings.get("DATA_DIR", self.DEFAULT_DATA_DIR))
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

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
