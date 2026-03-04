import re
import requests
from bs4 import BeautifulSoup
import scrapy
from ...extract import Extract


class GSMArenaNews(Extract):
    """
    Spider for GSMArena News.
    Source: https://www.gsmarena.com/news.php3
    Content: THE global reference for mobile phone specs, reviews, and news.
             Covers ALL brands: Samsung, Apple, Xiaomi, OnePlus, Oppo,
             vivo, Honor, Motorola, Huawei, Nothing, Realme, Tecno, etc.
    """

    name = "gsmarena_news"
    source = "gsmarena_news"
    start_urls = [
        "https://www.gsmarena.com/news.php3",
    ]

    async def parse(self, response):
        """
        Parse GSMArena news listing. Articles have links like:
        /slug-news-XXXXX.php
        Pagination: news.php3?sPage=N
        """
        # News article links
        article_links = response.css(
            "#review-body a::attr(href), "
            ".news-item a::attr(href), "
            'a[href*="-news-"]::attr(href)'
        ).getall()

        article_links = [
            link for link in article_links if "-news-" in link and link != response.url
        ]

        seen = set()
        for link in article_links:
            if link not in seen:
                seen.add(link)
                yield response.follow(link, self.parse_article)

        # Pagination — next page
        next_page = response.css(
            "a.pages-next::attr(href), " 'a[title="Next page"]::attr(href)'
        ).get()
        if next_page:
            yield response.follow(next_page, self.parse)

    async def parse_article(self, response):
        """
        Parse an individual GSMArena news article.
        """
        title = (
            response.css("h1::text").get()
            or response.css(".article-hgroup h1::text").get()
            or response.css('meta[property="og:title"]::attr(content)').get()
        )

        # Author and date
        author = response.css(
            ".article-info-name a::text, .article-info-name::text"
        ).get()
        date = (
            response.css(".article-info time::attr(datetime)").get()
            or response.css(
                'meta[property="article:published_time"]::attr(content)'
            ).get()
        )

        # Content
        content_elements = response.css(
            ".article-body p, .article-body h2, .article-body h3, "
            ".article-body li, "
            "#review-body p, #review-body h2, #review-body h3"
        ).getall()

        if not content_elements:
            content_elements = response.css(
                "article p, article h2, article h3"
            ).getall()

        content = " ".join(
            [BeautifulSoup(html, "html.parser").get_text() for html in content_elements]
        )

        # Tags from related links
        tags = response.css(
            ".article-tags a::text, "
            'meta[property="article:tag"]::attr(content), '
            'meta[name="keywords"]::attr(content)'
        ).getall()

        # Split comma-separated keywords
        expanded_tags = []
        for tag in tags:
            if "," in tag:
                expanded_tags.extend([t.strip() for t in tag.split(",") if t.strip()])
            else:
                expanded_tags.append(tag.strip())
        tags = list(set([t for t in expanded_tags if t]))

        # Detect brand and device from title and content
        title_lower = (title or "").lower()
        content_lower = (content or "")[:500].lower()
        combined = f"{title_lower} {content_lower}"

        brand = self._detect_brand(combined)
        mobile_os = self._detect_os(combined)
        device_name = self._extract_device_name(title or "")
        article_type = self._detect_article_type(combined)

        metadata = {
            "description": response.css(
                'meta[name="description"]::attr(content)'
            ).get(),
            "image": response.css('meta[property="og:image"]::attr(content)').get(),
            "blog_type": "gsmarena",
        }

        yield self.create_mobile_item(
            response,
            title=title.strip() if title else None,
            content=content.strip() if content else None,
            author=author.strip() if author else None,
            date=date,
            tags=tags,
            metadata=metadata,
            brand=brand,
            os=mobile_os,
            device_name=device_name,
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
            "moto ": "Motorola",
            "google pixel": "Google",
            "pixel": "Google",
            "nothing": "Nothing",
            "realme": "Realme",
            "sony xperia": "Sony",
            "tecno": "Tecno",
            "infinix": "Infinix",
            "itel": "Itel",
            "asus": "ASUS",
            "rog phone": "ASUS",
            "nokia": "Nokia",
            "zte": "ZTE",
            "nubia": "Nubia",
            "lenovo": "Lenovo",
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
            "one ui": "Android",
            "miui": "Android",
            "hyperos": "Android",
            "coloros": "Android",
            "oxygenos": "Android",
            "funtouch": "Android",
            "magic os": "Android",
        }
        for keyword, os_name in os_map.items():
            if keyword in text:
                return os_name
        return None

    def _extract_device_name(self, title):
        """Try to extract device model from the article title."""
        # Common patterns: "Samsung Galaxy S26 Ultra ..." or "iPhone 17 Pro ..."
        patterns = [
            r"(Galaxy\s+\w+(?:\s+\w+)?)",
            r"(iPhone\s+\d+\w*(?:\s+\w+)?)",
            r"(Pixel\s+\d+\w*(?:\s+\w+)?)",
            r"(Xiaomi\s+\d+\w*(?:\s+\w+)?)",
            r"(OnePlus\s+\d+\w*)",
            r"(Redmi\s+\w+(?:\s+\w+)?)",
            r"(Oppo\s+Find\s+\w+(?:\s+\w+)?)",
            r"(Nothing\s+Phone\s*\(\w+\))",
            r"(Moto\s+\w+(?:\s+\w+)?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _detect_article_type(self, text):
        if any(w in text for w in ["review", "hands-on", "hands on"]):
            return "review"
        if any(w in text for w in ["vs", "compared", "comparison"]):
            return "comparativa"
        if any(
            w in text
            for w in ["announced", "launches", "unveiled", "official", "debuts"]
        ):
            return "lanzamiento"
        if any(w in text for w in ["rumor", "leaked", "leak", "tipster"]):
            return "rumor"
        if any(w in text for w in ["deal", "price", "discount"]):
            return "precio"
        return "noticia"
