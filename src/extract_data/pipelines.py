from scrapy.exceptions import DropItem


class DuplicatesPipeline:
    def __init__(self):
        self.urls_seen = set()

    def process_item(self, item, spider):
        if item.get("url") in self.urls_seen:
            raise DropItem(f"Duplicate item found: {item['url']}")
        else:
            self.urls_seen.add(item["url"])
            return item
