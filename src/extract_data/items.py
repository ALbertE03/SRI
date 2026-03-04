import scrapy


class Item(scrapy.Item):
    """
    Base item for all scraped content.
    """

    url = scrapy.Field()
    title = scrapy.Field()
    content = scrapy.Field()
    author = scrapy.Field()
    date = scrapy.Field()
    source = scrapy.Field()  # xataka,..
    scraped_at = scrapy.Field()
    tags = scrapy.Field()
    metadata = scrapy.Field()


class MobileItem(Item):
    """
    Item for mobile technology articles. Extends Item with
    mobile-specific fields for devices, specs, and categorization.
    """

    # Device identification
    device_name = scrapy.Field()  # "Galaxy S26 Ultra", "iPhone 17 Pro"
    brand = scrapy.Field()  # "Samsung", "Apple", "Xiaomi"
    os = scrapy.Field()  #  "Android", "iOS", "HarmonyOS"

    # Classification
    category = scrapy.Field()  # "smartphone", "tablet", "wearable", "accesorio"
    article_type = (
        scrapy.Field()
    )  # "lanzamiento", "review", "noticia", "tutorial", "comparativa"

    specs = scrapy.Field()
    # specs dict:
    # {
    #     "display": "6.9 pulgadas AMOLED 120Hz",
    #     "processor": "Snapdragon 8 Elite",
    #     "ram": "12GB",
    #     "storage": "256GB/512GB/1TB",
    #     "camera_main": "200MP",
    #     "camera_front": "12MP",
    #     "battery": "5000mAh",
    #     "charging": "45W",
    #     "5g": True,
    #     "nfc": True,
    #     "weight": "218g",
    #     "dimensions": "162.8 x 77.6 x 8.2 mm",
    # }

    # Price info
    price = scrapy.Field()  # "desde $1,299 USD"
    release_date = scrapy.Field()  # "2026-02-26"
