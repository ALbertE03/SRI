import re
from bs4 import BeautifulSoup
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
        Parse GSMArena news listing.
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

        # Body Content
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

        # Quick Specs Section
        specs = self._extract_specs(content)  # Get from text first

        # Tags from related links and keywords
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

        # Enhanced detection using base class helpers
        title_text = title.strip() if title else ""
        content_text = content.strip() if content else ""
        combined_text = f"{title_text} {content_text[:2000]}"

        brand = self._detect_brand(combined_text + " " + " ".join(tags).lower())
        mobile_os = self._detect_os(combined_text)
        device_name = self._detect_device_name(title_text, content_text)
        article_type = self._detect_article_type(combined_text)

        # Extract Price from text
        price = self._extract_price(content_text)

        metadata = {
            "description": response.css(
                'meta[name="description"]::attr(content)'
            ).get(),
            "image": response.css('meta[property="og:image"]::attr(content)').get(),
            "blog_type": "gsmarena",
        }

        yield self.create_mobile_item(
            response,
            title=title_text if title_text else None,
            content=content_text if content_text else None,
            author=author.strip() if author else "GSMArena",
            date=date,
            tags=tags,
            metadata=metadata,
            brand=brand,
            os=mobile_os,
            device_name=device_name,
            article_type=article_type,
            category="smartphone",
            specs=specs,
            price=price,
        )

    def _detect_article_type(self, text):
        """Classify the article type based on content keywords."""
        text = text.lower()
        if any(w in text for w in ["review", "hands-on", "hands on"]):
            return "review"
        if any(w in text for w in ["vs", "compared", "comparison"]):
            return "comparativa"
        if any(w in text for w in ["announced", "launches", "official", "debuts"]):
            return "lanzamiento"
        if any(w in text for w in ["rumor", "leaked", "leak", "tipster"]):
            return "rumor"
        if any(w in text for w in ["deal", "price", "discount", "sale"]):
            return "precio"
        return "noticia"
