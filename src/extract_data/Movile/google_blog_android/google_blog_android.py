import requests
from bs4 import BeautifulSoup
import scrapy
from ...extract import Extract


class GoogleBlogAndroid(Extract):
    """
    Spider for the official Google Blog — Android section.
    Source: https://blog.google/products/android/
    Content: News about Android features, device launches,
             system updates, AI integrations, ecosystem announcements.
    """

    name = "google_blog_android"
    source = "google_blog_android"
    start_urls = [
        "https://blog.google/products/android/",
    ]

    async def parse(self, response):
        """
        Parse the blog listing page at blog.google/products/android/.
        """
        article_links = response.css(
            'a[href*="/products/android/"]::attr(href)'
        ).getall()

        article_links = [
            link
            for link in article_links
            if link != "/products/android/"
            and link != response.url
            and "/products/android/" in link
            and link.count("/") > 3
        ]

        seen = set()
        for link in article_links:
            if link not in seen:
                seen.add(link)
                yield response.follow(link, self.parse_article)

        next_page = response.css(
            "a.load-more::attr(href), a[data-next-page]::attr(href)"
        ).get()
        if next_page:
            yield response.follow(next_page, self.parse)

    async def parse_article(self, response):
        """
        Parse an individual blog post from blog.google.
        """
        title = (
            response.css("h1::text").get()
            or response.css('meta[property="og:title"]::attr(content)').get()
        )

        author = (
            response.css(".article-header__author-name::text").get()
            or response.css('[rel="author"]::text').get()
            or response.css('meta[name="author"]::attr(content)').get()
        )

        date = (
            response.css("time::attr(datetime)").get()
            or response.css(
                'meta[property="article:published_time"]::attr(content)'
            ).get()
        )

        content_elements = response.css(
            "article p, article h2, article h3, "
            ".article-body p, .article-body h2, .article-body h3, "
            ".article-content p, .article-content h2, .article-content h3"
        ).getall()

        if not content_elements:
            content_elements = response.css(
                '[class*="article"] p, [class*="post"] p'
            ).getall()

        content = " ".join(
            [BeautifulSoup(html, "html.parser").get_text() for html in content_elements]
        )

        tags = response.css('meta[property="article:tag"]::attr(content)').getall()
        category = response.css('meta[property="article:section"]::attr(content)').get()
        if category and category.strip():
            tags.append(category.strip())
        tags = list(set([t.strip() for t in tags if t.strip()]))

        metadata = {
            "description": response.css(
                'meta[name="description"]::attr(content)'
            ).get(),
            "image": response.css('meta[property="og:image"]::attr(content)').get(),
            "section": category,
            "blog_type": "official_google",
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
            brand="Google",
            article_type="noticia",
        )
