import requests
from bs4 import BeautifulSoup
import scrapy
from ...extract import Extract


class AndroidMagazine(Extract):
    """
    Spider for Android Magazine (android.com/articles/).
    Source: https://www.android.com/articles/
    Content: Consumer-facing articles about Android features, tutorials,
             tips, device guides, security, and productivity.
    """

    name = "android_magazine"
    source = "android_magazine"
    start_urls = [
        "https://www.android.com/articles/",
    ]

    async def parse(self, response):
        """
        Parse the articles listing page.
        """
        article_links = response.css('a[href*="/articles/"]::attr(href)').getall()

        article_links = [
            link
            for link in article_links
            if "/articles/" in link
            and link.rstrip("/") != "/articles"
            and link.rstrip("/") != "https://www.android.com/articles"
            and link != response.url
        ]

        seen = set()
        for link in article_links:
            if link not in seen:
                seen.add(link)
                yield response.follow(link, self.parse_article)

        next_page = response.css(
            'a.load-more::attr(href), a[aria-label="Next"]::attr(href)'
        ).get()
        if next_page:
            yield response.follow(next_page, self.parse)

    async def parse_article(self, response):
        """
        Parse an individual article from android.com/articles/.
        """
        title = (
            response.css("h1::text").get()
            or response.css('meta[property="og:title"]::attr(content)').get()
        )

        author = (
            response.css('[class*="author"]::text').get()
            or response.css('meta[name="author"]::attr(content)').get()
        )

        date = (
            response.css("time::attr(datetime)").get()
            or response.css(
                'meta[property="article:published_time"]::attr(content)'
            ).get()
        )

        content_elements = response.css(
            "article p, article h2, article h3, article li, "
            '[class*="article-body"] p, [class*="article-body"] h2, '
            '[class*="article-content"] p, [class*="article-content"] h2, '
            "main p, main h2, main h3"
        ).getall()

        content = " ".join(
            [BeautifulSoup(html, "html.parser").get_text() for html in content_elements]
        )

        tags = response.css('meta[property="article:tag"]::attr(content)').getall()
        tags = list(set([t.strip() for t in tags if t.strip()]))

        metadata = {
            "description": response.css('meta[name="description"]::attr(content)').get()
            or response.css('meta[property="og:description"]::attr(content)').get(),
            "image": response.css('meta[property="og:image"]::attr(content)').get(),
            "section": response.css(
                'meta[property="article:section"]::attr(content)'
            ).get(),
            "blog_type": "android_magazine",
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
            article_type="tutorial",
        )
