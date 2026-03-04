import requests
from bs4 import BeautifulSoup
import scrapy
from ...extract import Extract


class SamsungNewsroom(Extract):
    """
    Spider for Samsung Global Newsroom.
    Source: https://news.samsung.com/global/
    Content: Official Samsung press releases about Galaxy smartphones,
             tablets, wearables, One UI, Exynos chips, Galaxy AI, etc.
    """

    name = "samsung_newsroom"
    source = "samsung_newsroom"
    start_urls = [
        "https://news.samsung.com/global/",
    ]

    async def parse(self, response):
        """
        Parse the Samsung Newsroom listing page.
        """
        article_links = response.css(
            ".news-list a::attr(href), "
            'a[href*="news.samsung.com/global/"]::attr(href)'
        ).getall()

        # Filter to actual article pages
        article_links = [
            link
            for link in article_links
            if "news.samsung.com/global/" in link
            and link.rstrip("/") != "https://news.samsung.com/global"
            and link != response.url
            and not link.endswith("/global/")
        ]

        seen = set()
        for link in article_links:
            if link not in seen:
                seen.add(link)
                yield response.follow(link, self.parse_article)

        # Pagination
        next_page = response.css(
            "a.btn-more::attr(href), "
            'a[class*="load-more"]::attr(href), '
            "a.next::attr(href), "
            ".pagination a.next::attr(href)"
        ).get()
        if next_page:
            yield response.follow(next_page, self.parse)

    async def parse_article(self, response):
        """
        Parse an individual Samsung Newsroom article.
        """
        title = (
            response.css("h1::text").get()
            or response.css('meta[property="og:title"]::attr(content)').get()
        )

        author = (
            response.css('[class*="author"]::text').get()
            or response.css('meta[name="author"]::attr(content)').get()
            or "Samsung Newsroom"
        )

        date = (
            response.css("time::attr(datetime)").get()
            or response.css(".article-date::text").get()
            or response.css(
                'meta[property="article:published_time"]::attr(content)'
            ).get()
        )

        # Content
        content_elements = response.css(
            ".article-body p, .article-body h2, .article-body h3, "
            ".article-body li, "
            ".post-content p, .post-content h2, .post-content h3, "
            "article p, article h2, article h3"
        ).getall()

        if not content_elements:
            content_elements = response.css("main p, main h2, main h3").getall()

        content = " ".join(
            [BeautifulSoup(html, "html.parser").get_text() for html in content_elements]
        )

        # Tags
        tags = response.css(
            ".tag-list a::text, .article-tag a::text, "
            'meta[property="article:tag"]::attr(content)'
        ).getall()

        category_text = response.css(
            ".article-category::text, .post-category::text"
        ).get()
        if category_text:
            tags.append(category_text.strip())

        tags = list(set([t.strip() for t in tags if t.strip()]))

        # Detect device and type
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
            "blog_type": "samsung_newsroom",
        }

        yield self.create_mobile_item(
            response,
            title=title.strip() if title else None,
            content=content.strip() if content else None,
            author=author.strip() if author else None,
            date=date.strip() if date else None,
            tags=tags,
            metadata=metadata,
            brand="Samsung",
            os="Android",
            device_name=device_name,
            article_type=article_type,
            category=category,
        )

    def _detect_device(self, text):
        devices = [
            "galaxy s26 ultra",
            "galaxy s26+",
            "galaxy s26",
            "galaxy s25 ultra",
            "galaxy s25+",
            "galaxy s25",
            "galaxy z fold",
            "galaxy z flip",
            "galaxy a",
            "galaxy tab",
            "galaxy watch ultra",
            "galaxy watch",
            "galaxy buds",
            "galaxy ring",
        ]
        for device in devices:
            if device in text:
                return device.title()
        return None

    def _detect_article_type(self, text):
        if any(
            w in text
            for w in ["unpacked", "introduces", "announces", "launch", "unveils"]
        ):
            return "lanzamiento"
        if any(w in text for w in ["update", "one ui", "nueva versión"]):
            return "actualizacion"
        if any(w in text for w in ["interview", "entrevista"]):
            return "entrevista"
        return "noticia"

    def _detect_category(self, text):
        if any(w in text for w in ["galaxy s", "galaxy z", "galaxy a", "smartphone"]):
            return "smartphone"
        if "galaxy tab" in text:
            return "tablet"
        if "galaxy watch" in text or "galaxy ring" in text:
            return "wearable"
        if "galaxy buds" in text:
            return "accesorio"
        return "smartphone"
