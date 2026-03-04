import requests
from bs4 import BeautifulSoup
import scrapy
from ...extract import Extract


class AndroidDevNews(Extract):
    """
    Spider for Android Developers News.
    Source: https://developer.android.com/news
    Content: News and updates about the Android platform, new releases,
             API changes, tooling updates, and developer resources.
    """

    name = "android_dev_news"
    source = "android_dev_news"
    start_urls = [
        "https://developer.android.com/news",
    ]

    async def parse(self, response):
        """
        Parse the news listing at developer.android.com/news.
        """
        article_links = response.css(
            'a[href*="developer.android.com"]::attr(href), '
            'a[href*="/about/versions/"]::attr(href), '
            'a[href*="/studio/"]::attr(href), '
            'a[href*="/jetpack/"]::attr(href), '
            'a[href*="/kotlin/"]::attr(href)'
        ).getall()

        article_links += response.css(
            ".devsite-card a::attr(href), " ".devsite-landing-row a::attr(href)"
        ).getall()

        article_links = [
            link
            for link in article_links
            if link != response.url
            and "/news" != link.rstrip("/")
            and not link.endswith("#")
            and ("developer.android.com" in link or link.startswith("/"))
        ]

        seen = set()
        for link in article_links:
            if link not in seen:
                seen.add(link)
                if link.startswith("/") or "developer.android.com" in link:
                    yield response.follow(link, self.parse_article)

        next_page = response.css(
            'a[aria-label="Next"]::attr(href), a.next::attr(href)'
        ).get()
        if next_page:
            yield response.follow(next_page, self.parse)

    async def parse_article(self, response):
        """
        Parse an individual article/page from developer.android.com.
        """
        title = (
            response.css("h1::text").get()
            or response.css('meta[property="og:title"]::attr(content)').get()
            or response.css("title::text").get()
        )

        author = (
            response.css('meta[name="author"]::attr(content)').get()
            or response.css('[class*="author"]::text').get()
        )

        date = (
            response.css("time::attr(datetime)").get()
            or response.css(
                'meta[property="article:published_time"]::attr(content)'
            ).get()
        )

        content_elements = response.css(
            ".devsite-article-body p, .devsite-article-body h2, "
            ".devsite-article-body h3, .devsite-article-body li, "
            ".devsite-article-body pre, .devsite-article-body code"
        ).getall()

        if not content_elements:
            content_elements = response.css(
                "article p, article h2, article h3, " "main p, main h2, main h3"
            ).getall()

        content = " ".join(
            [BeautifulSoup(html, "html.parser").get_text() for html in content_elements]
        )

        tags_raw = response.css('meta[name="keywords"]::attr(content)').get()
        if tags_raw:
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        else:
            tags = []

        breadcrumbs = response.css(
            ".devsite-breadcrumb-link::text, .devsite-breadcrumb-item::text"
        ).getall()
        breadcrumbs = [b.strip() for b in breadcrumbs if b.strip()]

        metadata = {
            "description": response.css('meta[name="description"]::attr(content)').get()
            or response.css('meta[property="og:description"]::attr(content)').get(),
            "image": response.css('meta[property="og:image"]::attr(content)').get(),
            "breadcrumbs": breadcrumbs,
            "blog_type": "android_developer_news",
        }

        yield self.create_mobile_item(
            response,
            title=title.strip() if title else None,
            content=content.strip() if content else None,
            author=author.strip() if author else None,
            date=date,
            tags=tags,
            metadata=metadata,
            os="Android",
            article_type="noticia",
        )
