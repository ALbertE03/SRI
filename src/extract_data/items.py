import scrapy


class Item(scrapy.Item):
    """
    Unified item for all scraped content (News, Reviews, Products).
    """

    # Basic fields
    url = scrapy.Field()
    title = scrapy.Field()
    content = scrapy.Field()
    author = scrapy.Field()
    date = scrapy.Field()
    source = scrapy.Field()  # xataka, applesfera, etc.
    scraped_at = scrapy.Field()
    tags = scrapy.Field()

    # Tech-specific fields
    brand = scrapy.Field()  # "Samsung", "Apple", "Dell", "HP",...
    os = scrapy.Field()  # "Android", "iOS", "Windows", "macOS", "Linux"
    category = scrapy.Field()  # "smartphone", "laptop", "desktop", "component"

    metadata = scrapy.Field()
