# Source: storm/knowledge_storm/utils.py:L685-L711 (adapted)
import trafilatura


class TrafilaturaCleaner:
    def clean(self, html: str, min_chars: int = 200) -> str | None:
        article_text = trafilatura.extract(
            html,
            include_tables=False,
            include_comments=False,
            output_format="txt",
        )
        if article_text is None:
            return None

        cleaned = article_text.strip()
        if len(cleaned) < min_chars:
            return None
        return cleaned
