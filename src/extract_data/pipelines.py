# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

from itemadapter import ItemAdapter
from datetime import datetime


class SriPipeline:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # Ensure scraped_at is set
        if not adapter.get("scraped_at"):
            adapter["scraped_at"] = datetime.now().isoformat()

        # Clean whitespace from title and content
        if adapter.get("title"):
            adapter["title"] = adapter["title"].strip()

        if adapter.get("content"):
            # Simple content cleaning
            adapter["content"] = " ".join(adapter["content"].split())

        return item
