import requests
from bs4 import BeautifulSoup
import scrapy
from abc import ABC, abstractmethod
from .items import SriItem


class Extract(scrapy.Spider, ABC):
    """
    Base class for all SRI spiders.
    Ensures consistent data structure and ethical defaults.
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

    @abstractmethod
    def parse(self, response):
        """
        Standard parse method to be implemented by children.
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
    ):
        """
        Helper method to create a SriItem with common fields pre-filled.
        """
        item = SriItem()
        item["url"] = response.url
        item["source"] = self.source
        item["title"] = title
        item["content"] = content
        item["author"] = author
        item["date"] = date
        item["tags"] = tags or []
        item["metadata"] = metadata or {}
        return item
