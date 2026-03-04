import re
import requests
from bs4 import BeautifulSoup
import scrapy
from ...extract import Extract


class PhoneArenaNews(Extract):
    """
    Spider for PhoneArena News.
    Source: https://www.phonearena.com/news
    Content: Mobile phone news, reviews, comparisons, and analysis.
             Covers all brands and OSes: Samsung, Apple, Google, Xiaomi,
             OnePlus, Motorola, etc. Includes carrier news and software updates.
    """

    name = "phonearena_news"
    source = "phonearena_news"
    start_urls = [
        "https://www.phonearena.com/news",
    ]

    async def parse(self, response):
        """
        Parse PhoneArena news listing.
        Article URLs follow pattern: /news/slug_idXXXXXX
        """
        article_links = response.css('a[href*="/news/"]::attr(href)').getall()

        # Filter to actual news articles (must have _id pattern)
        article_links = [
            link
            for link in article_links
            if "/news/" in link and "_id" in link and link != response.url
        ]

        seen = set()
        for link in article_links:
            if link not in seen:
                seen.add(link)
                yield response.follow(link, self.parse_article)

        # Pagination
        next_page = response.css(
            'a[rel="next"]::attr(href), '
            "a.next::attr(href), "
            'a[aria-label="Next"]::attr(href), '
            ".pagination a.next::attr(href)"
        ).get()
        if next_page:
            yield response.follow(next_page, self.parse)

    async def parse_article(self, response):
        """
        Parse an individual PhoneArena news article.
        """
        title = (
            response.css("h1::text").get()
            or response.css('meta[property="og:title"]::attr(content)').get()
        )

        # Author
        author = (
            response.css(".article-author-name::text").get()
            or response.css('[class*="author"] a::text').get()
            or response.css('meta[name="author"]::attr(content)').get()
        )

        # Date
        date = (
            response.css("time::attr(datetime)").get()
            or response.css(
                'meta[property="article:published_time"]::attr(content)'
            ).get()
        )

        # Content
        content_elements = response.css(
            ".article-body p, .article-body h2, .article-body h3, "
            ".article-body li, "
            ".content p, .content h2, .content h3, "
            "article p, article h2, article h3"
        ).getall()

        if not content_elements:
            content_elements = response.css("main p, main h2, main h3").getall()

        content = " ".join(
            [BeautifulSoup(html, "html.parser").get_text() for html in content_elements]
        )

        # Tags
        tags = response.css(
            ".article-tags a::text, " 'meta[property="article:tag"]::attr(content)'
        ).getall()

        keywords = response.css('meta[name="keywords"]::attr(content)').get()
        if keywords:
            tags.extend([t.strip() for t in keywords.split(",") if t.strip()])

        tags = list(set([t.strip() for t in tags if t.strip()]))

        # Detect brand, os, device, type
        title_lower = (title or "").lower()
        content_lower = (content or "")[:500].lower()
        combined = f"{title_lower} {content_lower}"

        brand = self._detect_brand(combined)
        mobile_os = self._detect_os(combined)
        device_name = self._extract_device_name(title or "")
        article_type = self._detect_article_type(combined, response.url)

        metadata = {
            "description": response.css('meta[name="description"]::attr(content)').get()
            or response.css('meta[property="og:description"]::attr(content)').get(),
            "image": response.css('meta[property="og:image"]::attr(content)').get(),
            "blog_type": "phonearena",
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
            "razr": "Motorola",
            "google pixel": "Google",
            "pixel": "Google",
            "nothing": "Nothing",
            "realme": "Realme",
            "sony": "Sony",
            "nokia": "Nokia",
            "zte": "ZTE",
            "nubia": "Nubia",
            "asus": "ASUS",
            "rog phone": "ASUS",
            "t-mobile": "T-Mobile",
            "verizon": "Verizon",
            "at&t": "AT&T",
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
            "pixel feature drop": "Android",
            "wear os": "WearOS",
        }
        for keyword, os_name in os_map.items():
            if keyword in text:
                return os_name
        return None

    def _extract_device_name(self, title):
        """Extract device model name from the article title."""
        patterns = [
            r"(Galaxy\s+\w+(?:\s+\w+)?(?:\s+\w+)?)",
            r"(iPhone\s+\d+\w*(?:\s+\w+)?(?:\s+\w+)?)",
            r"(Pixel\s+\d+\w*(?:\s+\w+)?)",
            r"(Xiaomi\s+\d+\w*(?:\s+\w+)?)",
            r"(OnePlus\s+\d+\w*)",
            r"(Razr\s+\w+(?:\s+\w+)?)",
            r"(Moto\s+\w+(?:\s+\w+)?)",
            r"(Nothing\s+Phone\s*\(\w+\))",
            r"(Oppo\s+Find\s+\w+(?:\s+\w+)?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _detect_article_type(self, text, url=""):
        if "/reviews/" in url:
            return "review"
        if any(w in text for w in ["review", "hands-on"]):
            return "review"
        if any(w in text for w in [" vs ", "compared", "comparison"]):
            return "comparativa"
        if any(w in text for w in ["announced", "launches", "unveiled", "debuts"]):
            return "lanzamiento"
        if any(
            w in text for w in ["rumor", "leaked", "leak", "tipster", "may feature"]
        ):
            return "rumor"
        if any(w in text for w in ["deal", "discount", "price drop"]):
            return "precio"
        if any(w in text for w in ["how to", "tip", "trick", "guide"]):
            return "tutorial"
        return "noticia"
