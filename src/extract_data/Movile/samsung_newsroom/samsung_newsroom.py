import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup
from ...extract import Extract

# XML namespace URIs used in Samsung's WordPress RSS feed
_NS = {
    "dc":      "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "media":   "http://search.yahoo.com/mrss/",
    "atom":    "http://www.w3.org/2005/Atom",
}


class SamsungNewsroom(Extract):
    """
    Spider for Samsung Global Newsroom via RSS feed.

    Samsung's main listing page (news.samsung.com/global/) is behind
    Cloudflare bot-protection and cannot be scraped directly.
    The RSS feed at /global/feed is publicly accessible and returns
    full article content inside <content:encoded>, so all fields are
    extracted without following article links.

    Source: https://news.samsung.com/global/feed
    Content: Official Samsung press releases — Galaxy smartphones,
             tablets, wearables, One UI, Exynos, Galaxy AI, etc.
    """

    name = "samsung_newsroom"
    source = "samsung_newsroom"
    start_urls = ["https://news.samsung.com/global/feed"]

    # ------------------------------------------------------------------ #
    #  Feed parsing                                                        #
    # ------------------------------------------------------------------ #

    async def parse(self, response):
        """Parse the Samsung Global Newsroom RSS 2.0 feed."""
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            self.logger.error("RSS XML parse error: %s", exc)
            return

        for item_el in root.findall(".//item"):
            parsed = self._parse_rss_item(item_el)
            if parsed:
                yield parsed

    def _parse_rss_item(self, item_el):
        """Extract a MobileItem from a single RSS <item> element."""
        ns = _NS

        title_el = item_el.find("title")
        title_text = (title_el.text or "").strip() if title_el is not None else ""

        url_el = item_el.find("link")
        url = (url_el.text or "").strip() if url_el is not None else ""

        # Date — RSS pubDate in RFC-2822 format
        date = None
        pubdate_el = item_el.find("pubDate")
        if pubdate_el is not None and pubdate_el.text:
            try:
                date = parsedate_to_datetime(pubdate_el.text).isoformat()
            except Exception:
                date = pubdate_el.text.strip()

        # Author — dc:creator
        author_el = item_el.find("dc:creator", ns)
        author = (author_el.text or "Samsung Newsroom").strip() if author_el is not None else "Samsung Newsroom"

        # Full HTML content from content:encoded; fall back to <description>
        content_el = item_el.find("content:encoded", ns)
        raw_html = (content_el.text or "") if content_el is not None else ""
        if not raw_html:
            desc_el = item_el.find("description")
            raw_html = (desc_el.text or "") if desc_el is not None else ""
        content_text = BeautifulSoup(raw_html, "html.parser").get_text(" ", strip=True)

        # Tags — <category> elements
        tags = list({
            el.text.strip()
            for el in item_el.findall("category")
            if el.text and el.text.strip()
        })

        # Image — media:thumbnail or media:content
        image = None
        for media_tag in ("media:thumbnail", "media:content"):
            media_el = item_el.find(media_tag, ns)
            if media_el is not None:
                image = media_el.attrib.get("url")
                break

        combined = f"{title_text} {content_text[:2000]}"

        device_name   = self._detect_device_name(title_text, content_text)
        article_type  = self._detect_article_type(combined)
        category      = self._detect_category(combined)
        specs         = self._extract_specs(content_text)
        price         = self._extract_price(content_text)

        # Build a minimal fake response-like object to satisfy create_mobile_item
        class _FakeResponse:
            pass
        fake = _FakeResponse()
        fake.url = url

        item = self.create_mobile_item(
            fake,
            title=title_text or None,
            content=content_text or None,
            author=author,
            date=date,
            tags=tags,
            metadata={
                "description": "",
                "image": image,
                "blog_type": "samsung_newsroom",
            },
            brand="Samsung",
            os="Android",
            device_name=device_name,
            article_type=article_type,
            category=category,
            specs=specs,
            price=price,
        )
        return item

    def _detect_article_type(self, text):
        """Classify the article type."""
        text = text.lower()
        if any(
            w in text
            for w in [
                "unpacked",
                "introduces",
                "announces",
                "launch",
                "unveils",
                "presents",
            ]
        ):
            return "lanzamiento"
        if any(w in text for w in ["update", "one ui", "version"]):
            return "actualizacion"
        if any(w in text for w in ["interview", "entrevista"]):
            return "entrevista"
        if any(w in text for w in ["available", "order", "pre-order"]):
            return "disponibilidad"
        return "noticia"

    def _detect_category(self, text):
        """Determine device category."""
        text = text.lower()
        if any(
            w in text
            for w in ["galaxy s", "galaxy z", "galaxy a", "smartphone", "fold", "flip"]
        ):
            return "smartphone"
        if "galaxy tab" in text:
            return "tablet"
        if any(w in text for w in ["galaxy watch", "galaxy ring", "wearable"]):
            return "wearable"
        if "galaxy buds" in text:
            return "accesorio"
        return "smartphone"
