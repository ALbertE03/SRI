import requests
from bs4 import BeautifulSoup
import scrapy
from ..extract import Extract


class Xataka(Extract):
    name = "xataka"
    source = "xataka"
    start_urls = [
        "https://www.xataka.com/tag/tecnologia",
        "https://www.xataka.com/tag/software",
    ]

    async def parse(self, response):
        """
        Logic for parsing Xataka article listings.
        """
        # Follow article links
        article_links = response.css(".abstract-title a::attr(href)").getall()
        for link in article_links:
            yield response.follow(link, self.parse_article)

        # Pagination
        next_page = response.css("a.btn-next::attr(href)").get()
        if next_page:
            yield response.follow(next_page, self.parse)

    async def parse_article(self, response):
        """
        Logic for parsing an individual Xataka article.
        """
        title = response.css("h1::text").get()
        subtitle = response.css("h2::text").get()
        author = (
            response.css(".p-a-chip.js-author span::text").get()
            or response.css('meta[name="DC.Creator"]::attr(content)').get()
        )
        date = (
            response.css("time::attr(datetime)").get()
            or response.css(
                'meta[property="article:published_time"]::attr(content)'
            ).get()
        )

        # Extract content
        content_elements = response.css(
            ".article-content p, .article-content h2, .article-content h3"
        ).getall()
        content = " ".join(
            [BeautifulSoup(html, "html.parser").get_text() for html in content_elements]
        )

        # Tags
        tags = response.css(".article-tags a::text, .p-a-list a::text").getall()
        meta_tags = response.css('meta[property="article:tag"]::attr(content)').getall()
        all_tags = list(set([t.strip() for t in tags + meta_tags if t.strip()]))

        metadata = {
            "description": response.css(
                'meta[name="description"]::attr(content)'
            ).get(),
            "subtitle": subtitle.strip() if subtitle else None,
            "section": response.css(
                'meta[property="article:section"]::attr(content)'
            ).get(),
            "image": response.css('meta[property="og:image"]::attr(content)').get(),
        }

        yield self.create_item(
            response,
            title=title.strip() if title else None,
            content=content.strip() if content else None,
            author=author.strip() if author else None,
            date=date,
            tags=all_tags,
            metadata=metadata,
        )
