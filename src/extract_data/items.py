import scrapy


class Item(scrapy.Item):

    url = scrapy.Field()
    title = scrapy.Field()
    content = scrapy.Field()
    author = scrapy.Field()
    date = scrapy.Field()
    source = scrapy.Field()  # github, xataka, silicon, wired
    scraped_at = scrapy.Field()
    tags = scrapy.Field()
    metadata = scrapy.Field()
