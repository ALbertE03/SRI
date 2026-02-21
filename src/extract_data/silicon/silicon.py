import requests
from bs4 import BeautifulSoup
import scrapy

class Silicon(scrapy.Spider):
    name = "silicon"
    url = "https://www.silicon.es/"
    pass