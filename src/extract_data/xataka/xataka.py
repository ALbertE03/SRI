import requests
from bs4 import BeautifulSoup
import scrapy
from ..extract import Extract


class Xataka(Extract):
    name = "xataka"
    source = "xataka"
    start_urls = ["https://www.xataka.com/"]

    def parse(self, response):
        """
        Logic for parsing Xataka articles.
        """
        pass
