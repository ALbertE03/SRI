import requests
from bs4 import BeautifulSoup
import scrapy
from ...extract import Extract


class Xataka(Extract):
    """
    Spider for Xataka — mobile technology news.
    Source: https://www.xataka.com/
    Content: Noticias de móviles, lanzamientos, reviews, comparativas,
             software y hardware de todos los fabricantes y SO.
    """

    name = "xataka"
    source = "xataka"
    start_urls = [
        "https://www.xataka.com/tag/moviles",
        "https://www.xataka.com/tag/smartphones",
        "https://www.xataka.com/tag/iphone",
        "https://www.xataka.com/tag/samsung",
        "https://www.xataka.com/tag/xiaomi",
        "https://www.xataka.com/tag/android",
        "https://www.xataka.com/tag/ios",
        "https://www.xataka.com/moviles",
    ]

    async def parse(self, response):
        """
        Parse Xataka mobile article listings.
        """
        article_links = response.css(".abstract-title a::attr(href)").getall()
        for link in article_links:
            yield response.follow(link, self.parse_article)

        # Pagination
        next_page = response.css("a.btn-next::attr(href)").get()
        if next_page:
            yield response.follow(next_page, self.parse)

    async def parse_article(self, response):
        """
        Parse an individual Xataka mobile article.
        """
        title = response.css("h1::text").get()
        subtitle = response.css("h2::text").get()
        author = (
            response.css(".p-a-chip.js-author span::text").get()
            or response.css('meta[name="DC.Creator"]::attr(content)').get()
        )
        date = (
            response.css("time::attr(datetime)").get()
            or response.css(
                'meta[property="article:published_time"]::attr(content)'
            ).get()
        )

        # Extract content
        content_elements = response.css(
            ".article-content p, .article-content h2, .article-content h3"
        ).getall()
        content = " ".join(
            [BeautifulSoup(html, "html.parser").get_text() for html in content_elements]
        )

        # Tags
        tags = response.css(".article-tags a::text, .p-a-list a::text").getall()
        meta_tags = response.css('meta[property="article:tag"]::attr(content)').getall()
        all_tags = list(set([t.strip() for t in tags + meta_tags if t.strip()]))

        # Detect brand and OS from tags and title
        title_lower = (title or "").lower()
        tags_lower = " ".join(all_tags).lower()
        combined = f"{title_lower} {tags_lower}"

        brand = self._detect_brand(combined)
        mobile_os = self._detect_os(combined)
        article_type = self._detect_article_type(combined)

        metadata = {
            "description": response.css(
                'meta[name="description"]::attr(content)'
            ).get(),
            "subtitle": subtitle.strip() if subtitle else None,
            "section": response.css(
                'meta[property="article:section"]::attr(content)'
            ).get(),
            "image": response.css('meta[property="og:image"]::attr(content)').get(),
        }

        yield self.create_mobile_item(
            response,
            title=title.strip() if title else None,
            content=content.strip() if content else None,
            author=author.strip() if author else None,
            date=date,
            tags=all_tags,
            metadata=metadata,
            brand=brand,
            os=mobile_os,
            article_type=article_type,
            category="smartphone",
        )

    def _detect_brand(self, text):
        brands = {
            "samsung": "Samsung",
            "galaxy": "Samsung",
            "apple": "Apple",
            "iphone": "Apple",
            "ipad": "Apple",
            "xiaomi": "Xiaomi",
            "redmi": "Xiaomi",
            "poco": "Xiaomi",
            "oneplus": "OnePlus",
            "oppo": "Oppo",
            "vivo": "vivo",
            "honor": "Honor",
            "huawei": "Huawei",
            "motorola": "Motorola",
            "google pixel": "Google",
            "pixel": "Google",
            "nothing": "Nothing",
            "realme": "Realme",
            "sony xperia": "Sony",
        }
        for keyword, brand in brands.items():
            if keyword in text:
                return brand
        return None

    def _detect_os(self, text):
        os_map = {
            "android": "Android",
            "ios": "iOS",
            "ipados": "iPadOS",
            "harmonyos": "HarmonyOS",
            "one ui": "One UI",
            "miui": "MIUI",
            "hyperos": "HyperOS",
            "coloros": "ColorOS",
        }
        for keyword, os_name in os_map.items():
            if keyword in text:
                return os_name
        return None

    def _detect_article_type(self, text):
        type_map = {
            "review": "review",
            "análisis": "review",
            "analisis": "review",
            "comparativa": "comparativa",
            "vs": "comparativa",
            "lanzamiento": "lanzamiento",
            "presenta": "lanzamiento",
            "anuncia": "lanzamiento",
            "oficial": "lanzamiento",
            "filtración": "rumor",
            "rumor": "rumor",
            "tutorial": "tutorial",
            "cómo": "tutorial",
            "truco": "tutorial",
        }
        for keyword, article_type in type_map.items():
            if keyword in text:
                return article_type
        return "noticia"
