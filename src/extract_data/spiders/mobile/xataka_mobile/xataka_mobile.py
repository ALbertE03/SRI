import re
from bs4 import BeautifulSoup
from ....extract import Extract


class XatakaMobile(Extract):
    """
    Spider for Xataka — mobile technology news.
    Source: https://www.xataka.com/
    Content: Mobile news, launches, reviews, comparisons,
             software and hardware from all manufacturers and OS.
    """

    name = "xataka_mobile"
    source = "xataka_mobile"
    start_urls = [
        # Mobile
        "https://www.xataka.com/tag/moviles",
        "https://www.xataka.com/tag/smartphones",
        "https://www.xataka.com/tag/iphone",
        "https://www.xataka.com/tag/samsung",
        "https://www.xataka.com/tag/xiaomi",
        "https://www.xataka.com/tag/android",
        "https://www.xataka.com/tag/ios",
        "https://www.xataka.com/tag/huawei",
        "https://www.xataka.com/tag/oppo",
        "https://www.xataka.com/tag/vivo",
        "https://www.xataka.com/tag/realme",
        "https://www.xataka.com/tag/oneplus",
        "https://www.xataka.com/tag/google-pixel",
        "https://www.xataka.com/tag/sony-xperia",
        "https://www.xataka.com/tag/motorola",
        "https://www.xataka.com/tag/nokia",
        "https://www.xataka.com/tag/asus-rog-phone",
        "https://www.xataka.com/tag/blackberry",
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
        author = (
            response.css(".p-a-chip.js-author span::text").get()
            or response.css('meta[name="DC.Creator"]::attr(content)').get()
        )
        date = (
            response.css("time::attr(datetime)").get()
            or response.css(
                'meta[property="article:published_time"]::attr(content)'
            ).get()
            or response.css('meta[name="DC.date.issued"]::attr(content)').get()
        )
        if not date:
            self.logger.warning(
                f"Failed to extract date for: {response.url}. Using current timestamp as fallback."
            )
            from datetime import datetime

            date = datetime.utcnow().isoformat() + "Z"

        # Extract content more comprehensively
        content_elements = response.css(
            ".article-content p, .article-content h2, .article-content h3, .article-content li"
        ).getall()
        content = " ".join(
            [BeautifulSoup(html, "html.parser").get_text() for html in content_elements]
        )

        # Tags
        tags = response.css(".article-tags a::text, .p-a-list a::text").getall()
        meta_tags = response.css('meta[property="article:tag"]::attr(content)').getall()
        all_tags = list(set([t.strip() for t in tags + meta_tags if t.strip()]))

        # Enhanced detection using base class helpers
        title_text = title.strip() if title else ""
        content_text = content.strip() if content else ""
        combined_text = f"{title_text} {content_text}"
        tags_text = " ".join(all_tags).lower()

        # Specific detections
        brand = self._detect_brand(combined_text + " " + tags_text)
        mobile_os = self._detect_os(combined_text + " " + tags_text)

        metadata = {
            "section": response.css(
                'meta[property="article:section"]::attr(content)'
            ).get(),
            "image": response.css('meta[property="og:image"]::attr(content)').get(),
            "blog_type": "magazine",
        }

        self.logger.info(f"Successfully extracted Xataka Mobile article: {title_text}")

        yield self.create_mobile_item(
            response,
            title=title_text if title_text else None,
            content=content_text if content_text else None,
            author=author.strip() if author else None,
            date=date,
            tags=all_tags,
            metadata=metadata,
            brand=brand,
            os=mobile_os,
            category="smartphone",
        )
