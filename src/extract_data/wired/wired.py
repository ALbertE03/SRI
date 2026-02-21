import requests
from bs4 import BeautifulSoup
import scrapy

class Wired(scrapy.Spider):
    name = "wired"
    url = "https://es.wired.com"
    pass