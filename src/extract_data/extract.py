import re
import scrapy
from abc import ABC, abstractmethod
from .items import Item, MobileItem


class Extract(scrapy.Spider, ABC):
    """
    Base class for all SRI spiders.
    Ensures consistent data structure and ethical defaults.
    Reads per-spider download delay from settings.py.
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

    def start_requests(self):
        """
        Apply per-spider download delay from settings before starting.
        """
        delays = self.settings.getdict("DOWNLOAD_DELAYS_PER_SPIDER", {})
        if self.name in delays:
            self.download_delay = delays[self.name]
        return super().start_requests()

    @abstractmethod
    async def parse(self, response):
        """
        Standard async parse method to be implemented by children.
        """
        pass

    def create_item(
        self,
        response,
        title=None,
        content=None,
        author=None,
        date=None,
        tags=None,
        metadata=None,
    ) -> Item:
        """
        Helper method to create a Item with common fields pre-filled.
        """
        item = Item()
        item["url"] = response.url
        item["source"] = self.source
        item["title"] = title
        item["content"] = content
        item["author"] = author
        item["date"] = date
        item["tags"] = tags or []
        item["metadata"] = metadata or {}
        return item

    def create_mobile_item(
        self,
        response,
        title=None,
        content=None,
        author=None,
        date=None,
        tags=None,
        metadata=None,
        device_name=None,
        brand=None,
        os=None,
        category=None,
        article_type=None,
        specs=None,
        price=None,
        release_date=None,
    ) -> MobileItem:
        """
        Helper method to create a MobileItem with all fields pre-filled.
        Used by mobile-focused spiders.
        """
        item = MobileItem()
        item["url"] = response.url
        item["source"] = self.source
        item["title"] = title
        item["content"] = content
        item["author"] = author
        item["date"] = date
        item["tags"] = tags or []
        item["metadata"] = metadata or {}
        item["device_name"] = device_name
        item["brand"] = brand
        item["os"] = os
        item["category"] = category
        item["article_type"] = article_type
        item["specs"] = specs or {}
        item["price"] = price
        item["release_date"] = release_date
        return item
    

    # start movile specific helpers
    def _extract_price(self, text):
        """Regex for detecting prices in Euros or Dollars.
        Handles European formats: 1.469 € (thousands dot) and 1.299,00 € (decimal comma).
        """
        if not text:
            return None
        #  999€, 999,00 €, 999.00€, 1.469€, $999, 999 dollars, etc.
        patterns = [
            r"(\d[\d\.]*\d|\d)\s?(?:€|euros?|USD|\$|dollars?)",
            r"(?:€|USD|\$)\s?(\d[\d\.]*\d|\d)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                price_str = match.group(1)
                # European thousands separator: remove dot before 3-digit group
                # e.g. "1.469" → "1469", "1.299,00" → "1299,00"
                price_str = re.sub(r"\.(\d{3})(?=[,.]|$)", r"\1", price_str)
                # European decimal comma → dot
                price_str = price_str.replace(",", ".")
                try:
                    return f"{float(price_str):.2f}"
                except ValueError:
                    return price_str
        return None

    def _extract_specs(self, text):
        """Extract basic specs using regex patterns."""
        if not text:
            return {}
        specs = {}
        patterns = {
            "ram": r"(\d+)\s?(?:GB|Gb)\s?(?:de\s?)?RAM",
            "storage": r"(\d+)\s?(?:GB|TB)\s+de\s+(?:almacenamiento|memoria interna|ROM)",

            "battery": r"(\d[\d\.]*\d|\d+)\s?mAh",
            "camera": r"(\d+)\s?MP",
            "screen_size": r'(\d+[\.,]\d+)\s?[""]|(\d+[\.,]\d+)\s?(?:pulgadas|inches)',
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                val = match.group(1) or match.group(2)
                if key == "battery":
                    val = re.sub(r"\.(\d{3})$", r"\1", val)
                specs[key] = val.replace(",", ".")
        return specs

    def _detect_brand(self, text):
        """Detect mobile brand from text. Shared across all mobile spiders."""
        text = text.lower()
        brands = {
            "rog phone": "ASUS",
            "galaxy": "Samsung",
            "samsung": "Samsung",
            "iphone": "Apple",
            "ipad": "Apple",
            "apple": "Apple",
            "redmi": "Xiaomi",
            "poco": "Xiaomi",
            "xiaomi": "Xiaomi",
            "oneplus": "OnePlus",
            "oppo": "Oppo",
            "vivo": "vivo",
            "honor": "Honor",
            "huawei": "Huawei",
            "moto ": "Motorola",
            "motorola": "Motorola",
            "google pixel": "Google",
            "pixel": "Google",
            "nothing phone": "Nothing",
            "nothing": "Nothing",
            "realme": "Realme",
            "xperia": "Sony",
            "sony": "Sony",
            "asus": "ASUS",
            "nokia": "Nokia",
            "zte": "ZTE",
            "nubia": "Nubia",
            "lenovo": "Lenovo",
            "tecno": "Tecno",
            "infinix": "Infinix",
            "fairphone": "Fairphone",
        }
        for keyword, brand in brands.items():
            if keyword in text:
                return brand
        return None

    def _detect_os(self, text):
        """Detect mobile operating system from text. Shared across all mobile spiders."""
        text = text.lower()
        os_map = {
            "watchos": "watchOS",
            "ipados": "iPadOS",
            "harmonyos": "HarmonyOS",
            "one ui": "Android",
            "miui": "Android",
            "hyperos": "Android",
            "coloros": "Android",
            "oxygenos": "Android",
            "android": "Android",
            "ios": "iOS",
        }
        for keyword, os_name in os_map.items():
            if keyword in text:
                return os_name
        return None

    def _detect_device_name(self, title, text=""):
        """regex for detecting mobile devices."""
        combined = f"{title} {text[:500]}".lower()
        patterns = [
            r"(iphone\s+\d+\s*(?:pro\s*max|pro|plus|mini|pm)?)",
            r"(galaxy\s+(?:s|z|a|m|f|note)\d+\s*(?:ultra|\+|\s*plus|fold\s*\d+|flip\s*\d+)?)",
            r"(pixel\s+\d+\s*(?:pro|a|xl)?)",
            r"(xiaomi\s+\d+[a-z]?\s*(?:pro|ultra|lite|t)?)",
            r"(redmi\s+\w+\s+\d+(?:s|pro|plus|ultra)?)",
            r"(oneplus\s+\d+(?:r|t|pro)?)",
            r"(moto\s+\w+\s+(?:\d+|plus|pro|pure)?)",
            r"(razr\s*(?:40|50|2023|2024|ultra)?)",
            r"(nothing\s+phone\s*\(\d+\)?)",
            r"(poco\s+[fmx]\d+\s*(?:pro|gt|nfc)?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, combined, re.IGNORECASE)
            if match:
                return match.group(0).title().strip()
        return None
    # end movile specific helpers