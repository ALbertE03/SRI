import re
from bs4 import BeautifulSoup
from ...extract import Extract


class Xataka(Extract):
    """
    Spider for Xataka — mobile technology news.
    Source: https://www.xataka.com/
    Content: Mobile news, launches, reviews, comparisons,
             software and hardware from all manufacturers and OS.
    """

    name = "xataka"
    source = "xataka"
    start_urls = [
        "https://www.xataka.com/tag/moviles",
        "https://www.xataka.com/tag/smartphones",
        "https://www.xataka.com/tag/iphone",
        "https://www.xataka.com/tag/samsung",
        "https://www.xataka.com/tag/xiaomi",
        "https://www.xataka.com/tag/android",
        "https://www.xataka.com/tag/ios",
        "https://www.xataka.com/moviles",
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
        combined_text = f"{title_text} {content_text[:2000]}"
        tags_text = " ".join(all_tags).lower()

        # Specific detections
        brand = self._detect_brand(combined_text + " " + tags_text)
        mobile_os = self._detect_os(combined_text + " " + tags_text)
        article_type = self._detect_article_type(combined_text)
        device_name = self._detect_device_name(title_text, content_text)

        # Extract Price from text
        price = self._extract_price(content_text)

        # Extract Specs from table if it's a review/technical sheet
        specs = self._extract_specs(content_text)
        table_specs = self._extract_table_specs(response)
        specs.update(table_specs)

        metadata = {
            "description": response.css(
                'meta[name="description"]::attr(content)'
            ).get(),
            "subtitle": subtitle.strip() if subtitle else None,
            "section": response.css(
                'meta[property="article:section"]::attr(content)'
            ).get(),
            "image": response.css('meta[property="og:image"]::attr(content)').get(),
            "blog_type": "magazine",
        }

        yield self.create_mobile_item(
            response,
            title=title_text if title_text else None,
            content=content_text if content_text else None,
            author=author.strip() if author else None,
            date=date,
            tags=all_tags,
            metadata=metadata,
            device_name=device_name,
            brand=brand,
            os=mobile_os,
            article_type=article_type,
            category="smartphone",
            specs=specs,
            price=price,
        )

    def _extract_table_specs(self, response):
        """
        Extract key-value pairs from Xataka's characteristic tables.
        These are usually inside a .blob-js div or just a <table>.
        """
        specs = {}
        # Find tables that look like specification tables
        tables = response.css("table")
        for table in tables:
            # Check if it has rows with two columns (typical for specs)
            rows = table.css("tr")
            for row in rows:
                cols = row.css("td")
                if len(cols) == 2:
                    key = "".join(cols[0].css("*::text").getall()).strip().lower()
                    value = "".join(cols[1].css("*::text").getall()).strip()

                    # Normalize common keys
                    if "pantalla" in key:
                        specs["screen"] = value
                    elif "procesador" in key:
                        specs["processor"] = value
                    elif "ram" in key:
                        specs["ram"] = value
                    elif "almacenamiento" in key:
                        specs["storage"] = value
                    elif "batería" in key or "bateria" in key:
                        specs["battery"] = value
                    elif "cámara" in key or "camara" in key:
                        if "trasera" in key or "principal" in key:
                            specs["rear_camera"] = value
                        elif "frontal" in key:
                            specs["front_camera"] = value
                    elif "precio" in key:
                        specs["price_tag"] = value
        return specs

    def _detect_article_type(self, text):
        """Classify the article type (Spanish and English keywords)."""
        text = text.lower()
        type_map = {
            # Reviews
            "review": "review",
            "análisis": "review",
            "analisis": "review",
            "hands-on": "review",
            "primeras impresiones": "review",
            # Comparativas
            "comparativa": "comparativa",
            " vs ": "comparativa",
            # Lanzamientos
            "lanzamiento": "lanzamiento",
            "presenta": "lanzamiento",
            "anuncia": "lanzamiento",
            "introduces": "lanzamiento",
            "announces": "lanzamiento",
            "launches": "lanzamiento",
            "unveils": "lanzamiento",
            # Rumores
            "filtración": "rumor",
            "rumor": "rumor",
            "filtrado": "rumor",
            "filtran": "rumor",
            "leak": "rumor",
            # Tutoriales
            "tutorial": "tutorial",
            "cómo": "tutorial",
            "truco": "tutorial",
            "guía": "tutorial",
            # Precios
            "oferta": "precio",
            "descuento": "precio",
            "rebaja": "precio",
        }
        for keyword, article_type in type_map.items():
            if keyword in text:
                return article_type
        return "noticia"
