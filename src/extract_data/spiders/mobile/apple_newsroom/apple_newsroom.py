import re
import json
from bs4 import BeautifulSoup
from ....extract import Extract


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

        # Filter to actual article pages
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

        # Pagination
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

        # Author
        author = (
            response.css('[class*="author"]::text').get()
            or response.css('meta[name="author"]::attr(content)').get()
            or "Apple Newsroom"
        )

        # Date
        date = None
        for ld_text in response.css(
            'script[type="application/ld+json"]::text'
        ).getall():
            try:
                ld = json.loads(ld_text)
                dp = ld.get("datePublished")
                if dp:
                    date = dp.rstrip("Z") if dp.endswith("Z") else dp
                    break
            except (json.JSONDecodeError, AttributeError):
                pass
        if not date:
            date = (
                response.css("time::attr(datetime)").get()
                or response.css(
                    'meta[property="article:published_time"]::attr(content)'
                ).get()
                or response.css(".category-eyebrow__date::text").get()
            )

        # Body Content
        content_elements = response.css(
            "[class*='article'] p, [class*='pagebody-copy'] p, " ".body-copy-wide p"
        ).getall()

        if not content_elements:
            content_elements = response.css("main p").getall()

        content = " ".join(
            [BeautifulSoup(html, "html.parser").get_text() for html in content_elements]
        )

        # Pricing and Availability Section
        availability_text = ""
        availability_header = response.xpath(
            '//h2[contains(text(), "Pricing and Availability")] | '
            '//h3[contains(text(), "Pricing and Availability")]'
        )
        if availability_header:
            availability_elements = availability_header.xpath(
                "following-sibling::p | following-sibling::ul"
            ).getall()
            availability_text = " ".join(
                [
                    BeautifulSoup(html, "html.parser").get_text()
                    for html in availability_elements
                ]
            )

        # Tags/topics
        tags = response.css(
            "span.category-eyebrow__category::text, "
            'a[class*="topic"]::text, '
            'meta[property="article:tag"]::attr(content)'
        ).getall()

        # Detect category label
        category_label = response.css("span.category-eyebrow__category::text").get()
        if category_label:
            tags.append(category_label.strip())

        tags = list(set([t.strip() for t in tags if t.strip()]))

        # Enhanced detection using base class helpers
        title_text = title.strip() if title else ""
        content_text = content.strip() if content else ""
        combined_text = f"{title_text} {content_text[:2000]}"

        category = self._detect_category(combined_text)

        metadata = {
            "category_label": category_label.strip() if category_label else None,
            "blog_type": "apple_newsroom",
        }

        self.logger.info(f"Successfully extracted Apple Newsroom article: {title_text}")

        yield self.create_item(
            response,
            title=title_text if title_text else None,
            content=content_text if content_text else None,
            author=author.strip() if author else "Apple Newsroom",
            date=date.strip() if date else None,
            tags=tags,
            metadata=metadata,
            brand="Apple",
            os="iOS",
            category=category,
        )

    def _detect_category(self, text):
        """Determine device category from text."""
        text = text.lower()
        if any(w in text for w in ["iphone", "smartphone"]):
            return "smartphone"
        if "ipad" in text:
            return "tablet"
        if "apple watch" in text or "watch ultra" in text or "watch series" in text:
            return "wearable"
        if any(w in text for w in ["airpods", "beats", "homepod"]):
            return "accesorio"
        if any(
            w in text for w in ["macbook", "imac", "mac pro", "mac mini", "mac studio"]
        ):
            return "laptop"
        if "apple tv" in text:
            return "entretenimiento"
        return "noticia"
