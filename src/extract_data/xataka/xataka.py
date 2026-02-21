import requests
from bs4 import BeautifulSoup
import scrapy

class Xataka(scrapy.Spider):
    name = "xataka"
    url = "https://www.xataka.com/"
    pass