# Self-written, plan v2.3 § 13.5 F103
from __future__ import annotations

import re

from bs4 import BeautifulSoup, Comment, Tag

from autosearch.cleaners.base import Cleaner


class PruningCleaner(Cleaner):
    TEXT_DENSITY_WEIGHT = 0.55
    LINK_DENSITY_WEIGHT = 0.30
    TAG_WEIGHT = 0.18
    CLASS_ID_HINT_WEIGHT = 0.20

    POSITIVE_TAG_WEIGHTS = {
        "article": 1.5,
        "main": 1.3,
        "section": 1.0,
        "p": 0.8,
        "li": 0.4,
        "pre": 1.8,
        "code": 1.8,
        "blockquote": 1.0,
    }
    NEGATIVE_TAG_WEIGHTS = {
        "nav": -1.6,
        "footer": -1.4,
        "aside": -1.2,
        "script": -2.0,
        "style": -2.0,
        "header": -0.8,
        "form": -1.0,
        "button": -0.8,
    }
    ALWAYS_DROP_TAGS = {"script", "style", "noscript", "template"}
    POSITIVE_HINT_KEYWORDS = {"content", "article", "post", "main", "body", "entry"}
    NEGATIVE_HINT_KEYWORDS = {
        "nav",
        "menu",
        "footer",
        "sidebar",
        "ad",
        "advert",
        "banner",
        "social",
        "share",
        "comment",
        "related",
        "popup",
        "modal",
        "cookie",
    }

    def __init__(self, threshold: float = 0.48, min_word_count: int = 2):
        self.threshold = threshold
        self.min_word_count = min_word_count

    def clean(self, html: str) -> str:
        if not html:
            return ""

        soup = BeautifulSoup(html, "html.parser")
        if soup.body is None:
            soup = BeautifulSoup(f"<body>{html}</body>", "html.parser")

        self._remove_comments(soup)
        self._remove_always_drop_tags(soup)

        body = soup.body
        if body is None:
            return ""

        self._prune_node(body, is_root=True)
        return body.decode_contents().strip()

    def _remove_comments(self, soup: BeautifulSoup) -> None:
        for node in soup(string=lambda value: isinstance(value, Comment)):
            node.extract()

    def _remove_always_drop_tags(self, soup: BeautifulSoup) -> None:
        for tag_name in self.ALWAYS_DROP_TAGS:
            for node in soup.find_all(tag_name):
                node.decompose()

    def _prune_node(self, node: Tag, *, is_root: bool = False) -> None:
        children = [child for child in node.children if isinstance(child, Tag)]
        for child in children:
            self._prune_node(child)

        if is_root or node.name in {"html", "body"}:
            return

        text = node.get_text(" ", strip=True)
        if not text:
            node.decompose()
            return

        if node.name not in {"pre", "code"} and self._word_count(text) < self.min_word_count:
            node.decompose()
            return

        score, link_density, class_id_hints = self._score_node(node, text)
        if score >= self.threshold:
            return

        if self._can_unwrap(node, link_density, class_id_hints):
            node.unwrap()
            return

        node.decompose()

    def _score_node(self, node: Tag, text: str) -> tuple[float, float, float]:
        text_length = len(text)
        html_length = max(1, len(str(node)))
        link_text_length = sum(len(link.get_text(" ", strip=True)) for link in node.find_all("a"))

        text_density = min(1.0, text_length / html_length)
        link_density = min(1.0, link_text_length / max(1, text_length))
        tag_weight = self.POSITIVE_TAG_WEIGHTS.get(node.name, 0.0) + self.NEGATIVE_TAG_WEIGHTS.get(
            node.name,
            0.0,
        )
        class_id_hints = self._class_id_hint_score(node)

        score = (
            text_density * self.TEXT_DENSITY_WEIGHT
            - link_density * self.LINK_DENSITY_WEIGHT
            + tag_weight * self.TAG_WEIGHT
            + class_id_hints * self.CLASS_ID_HINT_WEIGHT
        )
        return score, link_density, class_id_hints

    def _class_id_hint_score(self, node: Tag) -> float:
        tokens = set(self._attribute_tokens(node))
        if not tokens:
            return 0.0

        positive_hits = self._count_hint_hits(tokens, self.POSITIVE_HINT_KEYWORDS)
        negative_hits = self._count_hint_hits(tokens, self.NEGATIVE_HINT_KEYWORDS)
        raw_score = positive_hits - negative_hits
        return max(-1.0, min(1.0, raw_score))

    def _attribute_tokens(self, node: Tag) -> list[str]:
        values: list[str] = []

        class_values = node.get("class", [])
        if isinstance(class_values, str):
            values.append(class_values)
        else:
            values.extend(class_values)

        element_id = node.get("id")
        if isinstance(element_id, str):
            values.append(element_id)

        tokens: list[str] = []
        for value in values:
            tokens.extend(token for token in re.split(r"[^a-z0-9]+", value.lower()) if token)
        return tokens

    def _count_hint_hits(self, tokens: set[str], keywords: set[str]) -> int:
        hits = 0
        for token in tokens:
            for keyword in keywords:
                if keyword == "ad":
                    if token == keyword:
                        hits += 1
                        break
                    continue
                if token == keyword or token.startswith(keyword):
                    hits += 1
                    break
        return hits

    def _can_unwrap(self, node: Tag, link_density: float, class_id_hints: float) -> bool:
        if node.name in self.NEGATIVE_TAG_WEIGHTS:
            return False
        if class_id_hints < 0:
            return False
        if link_density > 0.6:
            return False
        return any(isinstance(child, Tag) for child in node.children)

    def _word_count(self, text: str) -> int:
        return len(text.split())
