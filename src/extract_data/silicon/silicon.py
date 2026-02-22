import requests
from bs4 import BeautifulSoup
import scrapy
from ..extract import Extract


class Silicon(Extract):
    name = "silicon"
    source = "silicon"
    start_urls = ["https://www.silicon.es/"]

    async def parse(self, response):
        """
        Logic for parsing Silicon articles.
        """
        pass
