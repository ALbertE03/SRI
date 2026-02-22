import requests
from bs4 import BeautifulSoup
import scrapy
from ..extract import Extract


class Wired(Extract):
    name = "wired"
    source = "wired"
    start_urls = ["https://es.wired.com"]

    async def parse(self, response):
        """
        Logic for parsing Wired articles.
        """
        pass
