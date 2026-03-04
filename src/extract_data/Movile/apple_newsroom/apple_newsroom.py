import requests
from bs4 import BeautifulSoup
import scrapy
from ...extract import Extract


class AppleNewsroom(Extract):
    """
    Spider for Apple Newsroom.
    Source: https://www.apple.com/newsroom/
    Content: Official Apple press releases and articles about
             iPhone, iPad, iOS, watchOS, Apple Watch, AirPods,
             Apple Intelligence, chips (A-series, M-series), etc.
    """

    name = "apple_newsroom"
    source = "apple_newsroom"
    start_urls = [
        "https://www.apple.com/newsroom/",
    ]

    async def parse(self, response):
        """
        Parse the Apple Newsroom listing page.
        Articles follow pattern: /newsroom/YYYY/MM/slug/
        """
        article_links = response.css('a[href*="/newsroom/20"]::attr(href)').getall()

        # Filter to actual article pages (must have year/month/slug pattern)
        article_links = [
            link
            for link in article_links
            if "/newsroom/20" in link and link != response.url
        ]

        seen = set()
        for link in article_links:
            if link not in seen:
                seen.add(link)
                yield response.follow(link, self.parse_article)

        # Pagination — "more stories" or archive links
        next_page = response.css(
            "a.button.more::attr(href), "
            'a[class*="load-more"]::attr(href), '
            "a.results__morelink::attr(href)"
        ).get()
        if next_page:
            yield response.follow(next_page, self.parse)

    async def parse_article(self, response):
        """
        Parse an individual Apple Newsroom article.
        """
        title = (
            response.css("h1::text").get()
            or response.css('meta[property="og:title"]::attr(content)').get()
        )

        # Author — Apple Newsroom rarely has individual authors
        author = (
            response.css('[class*="author"]::text').get()
            or response.css('meta[name="author"]::attr(content)').get()
            or "Apple Newsroom"
        )

        # Date
        date = (
            response.css("time::attr(datetime)").get()
            or response.css(
                'meta[property="article:published_time"]::attr(content)'
            ).get()
            or response.css(".hero-eyebrow__date::text").get()
        )

        # Content
        content_elements = response.css(
            ".article__body p, .article__body h2, .article__body h3, "
            ".article__body li, .pagebody p, .pagebody h2, .pagebody h3, "
            "article p, article h2, article h3"
        ).getall()

        if not content_elements:
            content_elements = response.css("main p, main h2, main h3").getall()

        content = " ".join(
            [BeautifulSoup(html, "html.parser").get_text() for html in content_elements]
        )

        # Tags/topics
        tags = response.css(
            '.article-topic::text, a[class*="topic"]::text, '
            'meta[property="article:tag"]::attr(content)'
        ).getall()

        # Detect category from URL and tags
        category_text = response.css(
            ".hero-eyebrow__category::text, .tile__topic::text"
        ).get()
        if category_text:
            tags.append(category_text.strip())

        tags = list(set([t.strip() for t in tags if t.strip()]))

        # Detect device and article type
        title_lower = (title or "").lower()
        content_lower = (content or "")[:500].lower()
        combined = f"{title_lower} {content_lower}"

        device_name = self._detect_device(combined)
        article_type = self._detect_article_type(combined)
        category = self._detect_category(combined)

        metadata = {
            "description": response.css('meta[name="description"]::attr(content)').get()
            or response.css('meta[property="og:description"]::attr(content)').get(),
            "image": response.css('meta[property="og:image"]::attr(content)').get(),
            "category_label": category_text.strip() if category_text else None,
            "blog_type": "apple_newsroom",
        }

        yield self.create_mobile_item(
            response,
            title=title.strip() if title else None,
            content=content.strip() if content else None,
            author=author.strip() if author else None,
            date=date.strip() if date else None,
            tags=tags,
            metadata=metadata,
            brand="Apple",
            os="iOS",
            device_name=device_name,
            article_type=article_type,
            category=category,
        )

    def _detect_device(self, text):
        devices = [
            "iphone 17",
            "iphone 16",
            "iphone 15",
            "iphone",
            "ipad pro",
            "ipad air",
            "ipad mini",
            "ipad",
            "apple watch ultra",
            "apple watch",
            "airpods pro",
            "airpods max",
            "airpods",
            "macbook pro",
            "macbook air",
        ]
        for device in devices:
            if device in text:
                return device.title()
        return None

    def _detect_article_type(self, text):
        if any(
            w in text
            for w in ["presenta", "introduces", "announces", "lanza", "launch"]
        ):
            return "lanzamiento"
        if any(w in text for w in ["actualiza", "update", "nueva versión"]):
            return "actualizacion"
        if any(w in text for w in ["disponible", "available"]):
            return "disponibilidad"
        return "noticia"

    def _detect_category(self, text):
        if any(w in text for w in ["iphone", "smartphone"]):
            return "smartphone"
        if "ipad" in text:
            return "tablet"
        if "apple watch" in text:
            return "wearable"
        if "airpods" in text:
            return "accesorio"
        if "mac" in text:
            return "laptop"
        return "smartphone"
