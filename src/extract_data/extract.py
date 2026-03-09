import re
import scrapy
from abc import ABC, abstractmethod
from .items import Item


class Extract(scrapy.Spider, ABC):
    """
    Base class for all SRI spiders.
    Ensures consistent data structure and ethical defaults.
    """

    name = None
    source = None

    def __init__(self, *args, **kwargs):
        super(Extract, self).__init__(*args, **kwargs)
        if self.name is None:
            raise ValueError(f"{type(self).__name__} must have a name defined")
        if self.source is None:
            raise ValueError(
                f"{type(self).__name__} must have a source defined (github, xataka, etc.)"
            )

    async def start(self):
        """
        Apply per-spider download delay from settings before starting.
        """
        delays = self.settings.getdict("DOWNLOAD_DELAYS_PER_SPIDER", {})
        if self.name in delays:
            self.download_delay = delays[self.name]
        async for req in super().start():
            yield req

    @abstractmethod
    async def parse(self, response):
        """Standard async parse method to be implemented by children."""
        pass

    def create_item(
        self,
        response,
        title=None,
        content=None,
        author=None,
        date=None,
        tags=None,
        **kwargs,
    ) -> Item:
        """
        Main helper to create an Item.
        Accepts any extra Tech-specific fields via kwargs (brand, model, os, specs, price, etc).
        """
        item = Item()
        item["url"] = response.url
        item["source"] = self.source
        item["title"] = title
        item["content"] = content
        item["author"] = author
        item["date"] = date
        item["tags"] = tags or []
        item["scraped_at"] = None

        # Tech fields
        item["brand"] = kwargs.get("brand")
        item["os"] = kwargs.get("os")
        item["category"] = kwargs.get("category")

        item["metadata"] = kwargs.get("metadata") or {}
        return item

    # --- Data Extraction Helpers ---

    def _detect_brand(self, text):
        """Detect Tech brand (Mobile & PC) from text."""
        if not text:
            return None
        text = text.lower()
        brands = {
            # Mobile
            "samsung": "Samsung",
            "iphone": "Apple",
            "xiaomi": "Xiaomi",
            "redmi": "Xiaomi",
            "poco": "Xiaomi",
            "oneplus": "OnePlus",
            "oppo": "Oppo",
            "vivo": "vivo",
            "honor": "Honor",
            "huawei": "Huawei",
            "pixel": "Google",
            "motorola": "Motorola",
            "realme": "Realme",
            "nothing": "Nothing",
            # PC / Laptops
            "macbook": "Apple",
            "imac": "Apple",
            "thinkpad": "Lenovo",
            "legion": "Lenovo",
            "lenovo": "Lenovo",
            "dell": "Dell",
            "xps": "Dell",
            "alienware": "Dell",
            "hp": "HP",
            "pavilion": "HP",
            "omen": "HP",
            "asus": "ASUS",
            "rog": "ASUS",
            "tuf": "ASUS",
            "msi": "MSI",
            "acer": "Acer",
            "predator": "Acer",
            "razer": "Razer",
            "microsoft surface": "Microsoft",
            "surface": "Microsoft",
            "gigabyte": "Gigabyte",
            "corsair": "Corsair",
        }
        for keyword, brand in brands.items():
            if re.search(rf"\b{keyword}\b", text):
                return brand
        return None

    def _detect_os(self, text):
        """Detect OS (Mobile & PC)."""
        if not text:
            return None
        text = text.lower()
        os_map = {
            "android": "Android",
            "ios": "iOS",
            "ipados": "iPadOS",
            "windows 11": "Windows 11",
            "windows 10": "Windows 10",
            "windows": "Windows",
            "macos": "macOS",
            "mac os": "macOS",
            "linux": "Linux",
            "ubuntu": "Linux",
            "chromeos": "ChromeOS",
            "harmonyos": "HarmonyOS",
        }
        for keyword, os_name in os_map.items():
            if re.search(rf"\b{keyword}\b", text):
                return os_name
        return None
