import requests
from bs4 import BeautifulSoup
import scrapy
from abc import ABC, abstractmethod
from .items import Item, MobileItem


class Extract(scrapy.Spider, ABC):
    """
    Base class for all SRI spiders.
    Ensures consistent data structure and ethical defaults.
    Reads per-spider download delay from settings.py.
    """

    name = None
    source = None

    def __init__(self, *args, **kwargs):
        super(Extract, self).__init__(*args, **kwargs)
        if self.name is None:
            raise ValueError(f"{type(self).__name__} must have a name defined")
        if self.source is None:
            raise ValueError(
                f"{type(self).__name__} must have a source defined (github, xataka, etc.)"
            )

        # Apply per-spider download delay from settings
        delays = self.settings.getdict("DOWNLOAD_DELAYS_PER_SPIDER", {})
        if self.name in delays:
            self.download_delay = delays[self.name]

    @abstractmethod
    async def parse(self, response):
        """
        Standard async parse method to be implemented by children.
        """
        pass

    def create_item(
        self,
        response,
        title=None,
        content=None,
        author=None,
        date=None,
        tags=None,
        metadata=None,
    ) -> Item:
        """
        Helper method to create a Item with common fields pre-filled.
        """
        item = Item()
        item["url"] = response.url
        item["source"] = self.source
        item["title"] = title
        item["content"] = content
        item["author"] = author
        item["date"] = date
        item["tags"] = tags or []
        item["metadata"] = metadata or {}
        return item

    def create_mobile_item(
        self,
        response,
        title=None,
        content=None,
        author=None,
        date=None,
        tags=None,
        metadata=None,
        device_name=None,
        brand=None,
        os=None,
        category=None,
        article_type=None,
        specs=None,
        price=None,
        release_date=None,
    ) -> MobileItem:
        """
        Helper method to create a MobileItem with all fields pre-filled.
        Used by mobile-focused spiders.
        """
        item = MobileItem()
        item["url"] = response.url
        item["source"] = self.source
        item["title"] = title
        item["content"] = content
        item["author"] = author
        item["date"] = date
        item["tags"] = tags or []
        item["metadata"] = metadata or {}
        item["device_name"] = device_name
        item["brand"] = brand
        item["os"] = os
        item["category"] = category
        item["article_type"] = article_type
        item["specs"] = specs or {}
        item["price"] = price
        item["release_date"] = release_date
        return item
