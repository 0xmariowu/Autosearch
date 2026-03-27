"""Cluster search results by topic similarity."""

name = "cluster_results"
description = "Group search results into topic clusters using semantic similarity. Helps identify themes and reduce noise by seeing which results are about the same subtopic."
when = "After collecting many search results (20+), to understand the landscape and identify clusters of related findings."
input_type = "hits"
output_type = "any"
input_schema = {
    "type": "object",
    "properties": {
        "input": {
            "type": "array",
            "items": {"type": "object"},
            "description": "List of hit dicts to cluster",
        },
        "context": {
            "type": "object",
            "properties": {
                "max_clusters": {"type": "integer", "default": 5},
                "similarity_threshold": {"type": "number", "default": 0.6},
            },
        },
    },
    "required": ["input"],
}


def run(hits, **context):
    if not hits or not isinstance(hits, list):
        return {"clusters": []}

    hits = [h for h in hits if isinstance(h, dict)]
    if not hits:
        return {"clusters": []}

    max_clusters = context.get("max_clusters", 5)
    threshold = context.get("similarity_threshold", 0.6)

    from embeddings import semantic_similarity

    # Simple greedy clustering
    clusters = []
    assigned = set()

    for i, hit in enumerate(hits):
        if i in assigned:
            continue

        text_i = f"{hit.get('title', '')} {hit.get('snippet', hit.get('body', ''))}"
        cluster = [hit]
        assigned.add(i)

        for j, other in enumerate(hits):
            if j in assigned or j <= i:
                continue
            text_j = f"{other.get('title', '')} {other.get('snippet', other.get('body', ''))}"
            try:
                sim = semantic_similarity(text_i, text_j)
                if sim >= threshold:
                    cluster.append(other)
                    assigned.add(j)
            except Exception:
                continue

        if len(clusters) < max_clusters:
            # Label from most common words in titles
            titles = " ".join(h.get("title", "") for h in cluster).lower().split()
            from collections import Counter

            common = [w for w, _ in Counter(titles).most_common(3) if len(w) > 3]
            label = " ".join(common) if common else f"cluster_{len(clusters) + 1}"
            clusters.append({"label": label, "count": len(cluster), "hits": cluster})

    # Add unclustered as "other"
    unclustered = [h for i, h in enumerate(hits) if i not in assigned]
    if unclustered:
        clusters.append(
            {"label": "other", "count": len(unclustered), "hits": unclustered}
        )

    return {"clusters": clusters, "total": len(hits), "cluster_count": len(clusters)}


def test():
    hits = [
        {
            "title": "Python web framework Flask",
            "snippet": "Flask is a micro web framework",
        },
        {
            "title": "Django web framework",
            "snippet": "Django is a full-stack web framework",
        },
        {
            "title": "Machine learning with PyTorch",
            "snippet": "Deep learning framework",
        },
        {"title": "TensorFlow ML framework", "snippet": "Machine learning platform"},
    ]
    result = run(hits, max_clusters=3, similarity_threshold=0.3)
    assert "clusters" in result
    assert result["total"] == 4
    return "ok"
