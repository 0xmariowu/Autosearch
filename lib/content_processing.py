from __future__ import annotations

import math
import re

import lxml.html
from rank_bm25 import BM25Okapi
from snowballstemmer import stemmer

LINK_PATTERN = re.compile(
    r'!?\[((?:[^\[\]]|\[(?:[^\[\]]|\[[^\]]*\])*\])*)\]\(((?:[^()\s]|\([^()]*\))*)(?:\s+"([^"]*)")?\)'
)

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "he",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "that",
    "the",
    "to",
    "was",
    "were",
    "will",
    "with",
    "i",
    "you",
    "she",
    "we",
    "they",
    "me",
    "him",
    "her",
    "us",
    "them",
    "my",
    "your",
    "his",
    "our",
    "their",
    "mine",
    "yours",
    "hers",
    "ours",
    "theirs",
    "myself",
    "yourself",
    "himself",
    "herself",
    "itself",
    "ourselves",
    "themselves",
    "am",
    "been",
    "being",
    "have",
    "had",
    "having",
    "do",
    "does",
    "did",
    "doing",
    "about",
    "above",
    "across",
    "after",
    "against",
    "along",
    "among",
    "around",
    "before",
    "behind",
    "below",
    "beneath",
    "beside",
    "between",
    "beyond",
    "down",
    "during",
    "except",
    "inside",
    "into",
    "near",
    "off",
    "out",
    "outside",
    "over",
    "past",
    "through",
    "toward",
    "under",
    "underneath",
    "until",
    "up",
    "upon",
    "within",
    "but",
    "or",
    "nor",
    "yet",
    "so",
    "although",
    "because",
    "since",
    "unless",
    "this",
    "these",
    "those",
    "what",
    "which",
    "who",
    "whom",
    "whose",
    "when",
    "where",
    "why",
    "how",
    "all",
    "any",
    "both",
    "each",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "can",
    "cannot",
    "can't",
    "could",
    "couldn't",
    "may",
    "might",
    "must",
    "mustn't",
    "shall",
    "should",
    "shouldn't",
    "won't",
    "would",
    "wouldn't",
    "not",
    "n't",
    "no",
    "none",
}

_NOISE = {
    "ccp",
    "up",
    "↑",
    "▲",
    "⬆️",
    "a",
    "an",
    "at",
    "by",
    "in",
    "of",
    "on",
    "to",
    "the",
}

_PARAGRAPH_WEIGHTS = {
    "h1": 5.0,
    "h2": 4.0,
    "h3": 3.0,
    "h4": 2.0,
    "blockquote": 2.0,
    "code": 2.0,
    "content": 1.0,
}

_PRUNING_REMOVE_TAGS = {
    "script",
    "style",
    "nav",
    "footer",
    "header",
    "aside",
    "form",
    "iframe",
    "noscript",
}

_PRUNING_TAG_WEIGHTS = {
    "div": 0.5,
    "p": 1.0,
    "article": 1.5,
    "section": 1.0,
    "span": 0.3,
    "li": 0.5,
    "ul": 0.5,
    "ol": 0.5,
    "h1": 1.2,
    "h2": 1.1,
    "h3": 1.0,
    "h4": 0.9,
    "h5": 0.8,
    "h6": 0.7,
}

_NEGATIVE_PATTERNS = re.compile(
    r"nav|footer|header|sidebar|ads|comment|promo|advert|social|share", re.I
)

_TIER1_PATTERNS = [
    (
        re.compile(r"Reference\s*#\s*[\d]+\.[0-9a-f]+\.\d+\.[0-9a-f]+", re.IGNORECASE),
        "Akamai block (Reference #)",
    ),
    (
        re.compile(r"Pardon\s+Our\s+Interruption", re.IGNORECASE),
        "Akamai challenge (Pardon Our Interruption)",
    ),
    (
        re.compile(r"challenge-form.*?__cf_chl_f_tk=", re.IGNORECASE | re.DOTALL),
        "Cloudflare challenge form",
    ),
    (
        re.compile(r'<span\s+class="cf-error-code">\d{4}</span>', re.IGNORECASE),
        "Cloudflare firewall block",
    ),
    (
        re.compile(r"/cdn-cgi/challenge-platform/\S+orchestrate", re.IGNORECASE),
        "Cloudflare JS challenge",
    ),
    (
        re.compile(r"window\._pxAppId\s*=", re.IGNORECASE),
        "PerimeterX block",
    ),
    (
        re.compile(r"captcha\.px-cdn\.net", re.IGNORECASE),
        "PerimeterX captcha",
    ),
    (
        re.compile(r"captcha-delivery\.com", re.IGNORECASE),
        "DataDome captcha",
    ),
    (
        re.compile(r"_Incapsula_Resource", re.IGNORECASE),
        "Imperva/Incapsula block",
    ),
    (
        re.compile(r"Incapsula\s+incident\s+ID", re.IGNORECASE),
        "Imperva/Incapsula incident",
    ),
    (
        re.compile(r"Sucuri\s+WebSite\s+Firewall", re.IGNORECASE),
        "Sucuri firewall block",
    ),
    (
        re.compile(r"KPSDK\.scriptStart\s*=\s*KPSDK\.now\(\)", re.IGNORECASE),
        "Kasada challenge",
    ),
    (
        re.compile(r"blocked\s+by\s+network\s+security", re.IGNORECASE),
        "Network security block",
    ),
]

_TIER2_PATTERNS = [
    (
        re.compile(r"Access\s+Denied", re.IGNORECASE),
        "Access Denied on short page",
    ),
    (
        re.compile(r"Checking\s+your\s+browser", re.IGNORECASE),
        "Cloudflare browser check",
    ),
    (
        re.compile(r"<title>\s*Just\s+a\s+moment", re.IGNORECASE),
        "Cloudflare interstitial",
    ),
    (
        re.compile(r'class=["\']g-recaptcha["\']', re.IGNORECASE),
        "reCAPTCHA on block page",
    ),
    (
        re.compile(r'class=["\']h-captcha["\']', re.IGNORECASE),
        "hCaptcha on block page",
    ),
    (
        re.compile(r"Access\s+to\s+This\s+Page\s+Has\s+Been\s+Blocked", re.IGNORECASE),
        "PerimeterX block page",
    ),
    (
        re.compile(r"blocked\s+by\s+security", re.IGNORECASE),
        "Blocked by security",
    ),
    (
        re.compile(r"Request\s+unsuccessful", re.IGNORECASE),
        "Request unsuccessful (Imperva)",
    ),
]

_TIER2_MAX_SIZE = 10000
_STRUCTURAL_MAX_SIZE = 50000
_CONTENT_ELEMENTS_RE = re.compile(
    r"<(?:p|h[1-6]|article|section|li|td|a|pre)\b", re.IGNORECASE
)
_SCRIPT_TAG_RE = re.compile(r"<script\b", re.IGNORECASE)
_STYLE_TAG_RE = re.compile(r"<style\b[\s\S]*?</style>", re.IGNORECASE)
_SCRIPT_BLOCK_RE = re.compile(r"<script\b[\s\S]*?</script>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_BODY_RE = re.compile(r"<body\b", re.IGNORECASE)
_BLOCK_PAGE_MAX_SIZE = 5000
_EMPTY_CONTENT_THRESHOLD = 100


def _classify_markdown_paragraph(paragraph: str) -> str:
    if paragraph.startswith("#### "):
        return "h4"
    if paragraph.startswith("### "):
        return "h3"
    if paragraph.startswith("## "):
        return "h2"
    if paragraph.startswith("# "):
        return "h1"
    if paragraph.startswith("> "):
        return "blockquote"
    if paragraph.startswith("```"):
        return "code"
    return "content"


def _stem_tokens(text: str, stemmer_instance) -> list[str]:
    return [stemmer_instance.stemWord(word) for word in text.lower().split()]


def _remove_node(node) -> None:
    parent = node.getparent()
    if parent is not None:
        parent.remove(node)


def _node_text(node) -> str:
    return "".join(node.itertext()).strip()


def _node_inner_html(node) -> str:
    parts = []
    if node.text:
        parts.append(node.text)
    for child in node:
        parts.append(lxml.html.tostring(child, encoding="unicode"))
    return "".join(parts)


def _direct_link_text_length(node) -> int:
    link_text_len = 0
    for child in node:
        if getattr(child, "tag", None) == "a" and len(child) == 0 and child.text:
            link_text_len += len(child.text.strip())
    return link_text_len


def _compute_class_id_weight(node) -> float:
    class_id_score = 0.0
    classes = node.get("class")
    if classes:
        if _NEGATIVE_PATTERNS.match(classes):
            class_id_score -= 0.5
    element_id = node.get("id")
    if element_id:
        if _NEGATIVE_PATTERNS.match(element_id):
            class_id_score -= 0.5
    return class_id_score


def _compute_pruning_score(node) -> float:
    text_len = len(_node_text(node))
    tag_len = len(_node_inner_html(node))
    link_text_len = _direct_link_text_length(node)

    score = 0.0
    total_weight = 0.0

    density = text_len / tag_len if tag_len > 0 else 0
    score += 0.4 * density
    total_weight += 0.4

    density = 1 - (link_text_len / text_len if text_len > 0 else 0)
    score += 0.2 * density
    total_weight += 0.2

    tag_score = _PRUNING_TAG_WEIGHTS.get(node.tag, 0.5)
    score += 0.2 * tag_score
    total_weight += 0.2

    class_score = _compute_class_id_weight(node)
    score += 0.1 * max(0, class_score)
    total_weight += 0.1

    score += 0.1 * math.log(text_len + 1)
    total_weight += 0.1

    return score / total_weight if total_weight > 0 else 0.0


def _prune_tree(node, threshold: float) -> None:
    if node is None or not isinstance(getattr(node, "tag", None), str):
        return

    if _compute_pruning_score(node) < threshold:
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)
        else:
            node.clear()
            node.text = ""
        return

    children = [child for child in node if isinstance(getattr(child, "tag", None), str)]
    for child in children:
        _prune_tree(child, threshold)


def _looks_like_data(html: str) -> bool:
    stripped = html.strip()
    if not stripped:
        return False
    if stripped[0] in ("{", "["):
        return True
    if stripped[:10].lower().startswith(("<html", "<!")):
        if re.search(
            r"<body[^>]*>\s*<pre[^>]*>\s*[{\[]", stripped[:500], re.IGNORECASE
        ):
            return True
        return False
    return stripped[0] == "<"


def _structural_integrity_check(html: str) -> tuple[bool, str]:
    html_len = len(html)
    if html_len > _STRUCTURAL_MAX_SIZE or _looks_like_data(html):
        return False, ""

    signals = []

    if not _BODY_RE.search(html):
        return True, f"Structural: no <body> tag ({html_len} bytes)"

    body_match = re.search(r"<body\b[^>]*>([\s\S]*)</body>", html, re.IGNORECASE)
    body_content = body_match.group(1) if body_match else html
    stripped = _SCRIPT_BLOCK_RE.sub("", body_content)
    stripped = _STYLE_TAG_RE.sub("", stripped)
    visible_text = _TAG_RE.sub("", stripped).strip()
    visible_len = len(visible_text)
    if visible_len < 50:
        signals.append("minimal_text")

    content_elements = len(_CONTENT_ELEMENTS_RE.findall(html))
    if content_elements == 0:
        signals.append("no_content_elements")

    script_count = len(_SCRIPT_TAG_RE.findall(html))
    if script_count > 0 and content_elements == 0 and visible_len < 100:
        signals.append("script_heavy_shell")

    signal_count = len(signals)
    if signal_count >= 2:
        return (
            True,
            f"Structural: {', '.join(signals)} ({html_len} bytes, {visible_len} chars visible)",
        )

    if signal_count == 1 and html_len < 5000:
        return (
            True,
            f"Structural: {signals[0]} on small page ({html_len} bytes, {visible_len} chars visible)",
        )

    return False, ""


def filter_relevant_paragraphs(
    markdown: str,
    query: str,
    threshold: float = 1.0,
    language: str = "english",
) -> str:
    if not markdown or not isinstance(markdown, str):
        return ""
    if not query or not isinstance(query, str):
        return ""

    paragraphs = [
        paragraph for paragraph in markdown.split("\n\n") if paragraph.strip()
    ]
    if not paragraphs:
        return ""

    paragraph_types = [
        _classify_markdown_paragraph(paragraph) for paragraph in paragraphs
    ]
    stemmer_instance = stemmer(language)

    tokenized_corpus = [
        _clean_tokens(_stem_tokens(paragraph, stemmer_instance))
        for paragraph in paragraphs
    ]
    tokenized_query = _clean_tokens(_stem_tokens(query, stemmer_instance))

    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(tokenized_query)

    adjusted_candidates = []
    for index, (paragraph, paragraph_type, score) in enumerate(
        zip(paragraphs, paragraph_types, scores, strict=True)
    ):
        adjusted_score = score * _PARAGRAPH_WEIGHTS.get(paragraph_type, 1.0)
        adjusted_candidates.append((adjusted_score, index, paragraph))

    selected_indices = {
        index
        for adjusted_score, index, _paragraph in adjusted_candidates
        if adjusted_score >= threshold
    }
    minimum_keep = min(3, len(adjusted_candidates))
    if len(selected_indices) < minimum_keep:
        for _score, index, _paragraph in sorted(
            adjusted_candidates, key=lambda item: item[0], reverse=True
        )[:minimum_keep]:
            selected_indices.add(index)

    return "\n\n".join(
        paragraph
        for index, paragraph in enumerate(paragraphs)
        if index in selected_indices
    )


def prune_html(html: str, threshold: float = 0.48) -> str:
    if not html or not isinstance(html, str):
        return ""

    try:
        root = lxml.html.fromstring(html)
    except Exception:
        try:
            root = lxml.html.fromstring(f"<body>{html}</body>")
        except Exception:
            return ""

    if not isinstance(getattr(root, "tag", None), str):
        return ""

    if root.tag.lower() == "html":
        body = root.find(".//body")
        if body is None:
            return ""
        tree_root = body
    elif root.tag.lower() == "body":
        tree_root = root
    else:
        try:
            tree_root = lxml.html.fromstring(f"<body>{html}</body>")
        except Exception:
            return ""

    for comment in tree_root.xpath(".//comment()"):
        _remove_node(comment)

    for tag in _PRUNING_REMOVE_TAGS:
        for node in tree_root.findall(f".//{tag}"):
            _remove_node(node)

    _prune_tree(tree_root, threshold)
    return lxml.html.tostring(tree_root, encoding="unicode", method="text")


def chunk_with_overlap(
    text: str, window_size: int = 2000, step: int = 1800
) -> list[str]:
    words = text.split()
    chunks = []

    if len(words) <= window_size:
        return [text]

    for i in range(0, len(words) - window_size + 1, step):
        chunk = " ".join(words[i : i + window_size])
        chunks.append(chunk)

    if i + window_size < len(words):
        chunks.append(" ".join(words[-window_size:]))

    return chunks


def convert_to_citations(markdown: str) -> tuple[str, str]:
    """Convert [text](url) to text⟨N⟩ with reference section."""
    link_map = {}
    parts = []
    last_end = 0
    counter = 1

    for match in LINK_PATTERN.finditer(markdown):
        parts.append(markdown[last_end : match.start()])
        text, url, title = match.groups()

        if url not in link_map:
            desc = []
            if title:
                desc.append(title)
            if text and text != title:
                desc.append(text)
            link_map[url] = (counter, ": " + " - ".join(desc) if desc else "")
            counter += 1

        num = link_map[url][0]
        parts.append(
            f"{text}⟨{num}⟩"
            if not match.group(0).startswith("!")
            else f"![{text}⟨{num}⟩]"
        )
        last_end = match.end()

    parts.append(markdown[last_end:])
    converted_text = "".join(parts)

    references = ["\n\n## References\n\n"]
    references.extend(
        f"⟨{num}⟩ {url}{desc}\n"
        for url, (num, desc) in sorted(link_map.items(), key=lambda item: item[1][0])
    )

    return converted_text, "".join(references)


def is_blocked(status_code: int | None, html: str) -> tuple[bool, str]:
    html = html or ""
    html_len = len(html)

    if status_code == 429:
        return True, "HTTP 429 Too Many Requests"

    snippet = html[:15000]
    if snippet:
        for pattern, reason in _TIER1_PATTERNS:
            if pattern.search(snippet):
                return True, reason

    if html_len > 15000:
        stripped_for_t1 = _SCRIPT_BLOCK_RE.sub("", html[:500000])
        stripped_for_t1 = _STYLE_TAG_RE.sub("", stripped_for_t1)
        deep_snippet = stripped_for_t1[:30000]
        for pattern, reason in _TIER1_PATTERNS:
            if pattern.search(deep_snippet):
                return True, reason

    if status_code in (403, 503) and not _looks_like_data(html):
        if html_len < _EMPTY_CONTENT_THRESHOLD:
            return (
                True,
                f"HTTP {status_code} with near-empty response ({html_len} bytes)",
            )
        if html_len > _TIER2_MAX_SIZE:
            stripped = _SCRIPT_BLOCK_RE.sub("", html[:500000])
            stripped = _STYLE_TAG_RE.sub("", stripped)
            check_snippet = stripped[:30000]
        else:
            check_snippet = snippet
        for pattern, reason in _TIER2_PATTERNS:
            if pattern.search(check_snippet):
                return True, f"{reason} (HTTP {status_code}, {html_len} bytes)"
        return True, f"HTTP {status_code} with HTML content ({html_len} bytes)"

    if status_code and status_code >= 400 and html_len < _TIER2_MAX_SIZE:
        for pattern, reason in _TIER2_PATTERNS:
            if pattern.search(snippet):
                return True, f"{reason} (HTTP {status_code}, {html_len} bytes)"

    if status_code == 200:
        stripped = html.strip()
        if len(stripped) < _EMPTY_CONTENT_THRESHOLD and not _looks_like_data(html):
            return True, f"Near-empty content ({len(stripped)} bytes) with HTTP 200"

    blocked, reason = _structural_integrity_check(html)
    if blocked:
        return True, reason

    return False, ""


def _clean_tokens(tokens: list[str]) -> list[str]:
    return [
        token
        for token in tokens
        if len(token) > 2
        and token not in _NOISE
        and token not in STOP_WORDS
        and not token.startswith("↑")
        and not token.startswith("▲")
        and not token.startswith("⬆")
    ]
