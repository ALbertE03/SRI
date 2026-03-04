import requests
from bs4 import BeautifulSoup
import scrapy
from ...extract import Extract


class AndroidDevelopersBlog(Extract):
    """
    Spider for the official Android Developers Blog.
    Source: https://android-developers.googleblog.com/
    Content: Technical articles about APIs, Android Studio, Jetpack, Kotlin,
             platform releases, Google Play, best practices, etc.
    """

    name = "android_developers_blog"
    source = "android_developers_blog"
    start_urls = [
        "https://android-developers.googleblog.com/",
    ]

    async def parse(self, response):
        """
        Parse the blog listing page.
        """
        article_links = response.css(
            ".post h2 a::attr(href), .post-title a::attr(href)"
        ).getall()

        if not article_links:
            article_links = response.css(".post a::attr(href)").getall()
            article_links = [
                link
                for link in article_links
                if "android-developers.googleblog.com" in link
                and "/search" not in link
                and link != response.url
            ]

        seen = set()
        for link in article_links:
            if link not in seen:
                seen.add(link)
                yield response.follow(link, self.parse_article)

        next_page = response.css(
            'a.blog-pager-older-link::attr(href), a[id="Blog1_blog-pager-older-link"]::attr(href)'
        ).get()
        if next_page:
            yield response.follow(next_page, self.parse)

    async def parse_article(self, response):
        """
        Parse an individual blog post.
        """
        title = (
            response.css(".post-title::text").get()
            or response.css("h3.post-title::text").get()
            or response.css("title::text").get()
        )

        author = (
            response.css(".post-author-name::text").get()
            or response.css('span[itemprop="author"] span[itemprop="name"]::text').get()
        )

        date = (
            response.css("abbr.published::attr(title)").get()
            or response.css("time::attr(datetime)").get()
            or response.css(".post-timestamp::text").get()
        )

        content_elements = response.css(
            ".post-body p, .post-body h2, .post-body h3, "
            ".post-body li, .post-body pre, .post-body blockquote"
        ).getall()

        if not content_elements:
            content_elements = response.css(
                "#post-body p, #post-body h2, #post-body h3"
            ).getall()

        content = " ".join(
            [BeautifulSoup(html, "html.parser").get_text() for html in content_elements]
        )

        tags = response.css(".post-labels a::text, span.post-labels a::text").getall()
        tags = list(set([t.strip() for t in tags if t.strip()]))

        metadata = {
            "description": response.css(
                'meta[name="description"]::attr(content)'
            ).get(),
            "image": response.css('meta[property="og:image"]::attr(content)').get(),
            "blog_type": "developer",
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
