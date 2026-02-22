import requests
from bs4 import BeautifulSoup
import scrapy
from ..extract import Extract


# api
class GitHub(Extract):
    name = "github"
    source = "github"

    def parse(self, response):
        """
        Logic for parsing GitHub API or pages.
        """
        pass
