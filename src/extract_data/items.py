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


class MobileItem(Item):
    """
    Extended item for mobile-specific content.
    Inherits all fields from Item and adds mobile-specific fields.
    """

    device_name = scrapy.Field()    # "iPhone 16 Pro", "Galaxy S25 Ultra", etc.
    article_type = scrapy.Field()   # "review", "news", "comparison", "tutorial"
    specs = scrapy.Field()          # dict with parsed specifications
    price = scrapy.Field()          # price if mentioned
    release_date = scrapy.Field()   # device release date if mentioned


class PCItem(Item):
    """
    Extended item for PC-specific content.
    Inherits all fields from Item and adds PC/hardware-specific fields.
    """

    device_name = scrapy.Field()    # "MacBook Pro M4", "Dell XPS 15", etc.
    article_type = scrapy.Field()   # "review", "news", "comparison", "tutorial"
    specs = scrapy.Field()          # dict with parsed specifications
    price = scrapy.Field()          # price if mentioned
    release_date = scrapy.Field()   # device release date if mentioned
