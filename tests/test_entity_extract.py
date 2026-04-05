from lib.entity_extract import extract_entities


def test_extract_subreddits():
    results = [
        {
            "url": "https://reddit.com/1",
            "title": "One",
            "snippet": "Alpha",
            "source": "reddit",
            "query": "agents",
            "metadata": {"subreddit": "Python"},
        },
        {
            "url": "https://reddit.com/2",
            "title": "Two",
            "snippet": "Beta",
            "source": "reddit",
            "query": "agents",
            "metadata": {"subreddit": "Python"},
        },
        {
            "url": "https://reddit.com/3",
            "title": "Three",
            "snippet": "Gamma",
            "source": "reddit",
            "query": "agents",
            "metadata": {"subreddit": "MachineLearning"},
        },
    ]

    entities = extract_entities(results)

    assert entities["subreddits"] == ["python", "machinelearning"]


def test_extract_subreddits_top5():
    results = []
    for index in range(6):
        for repeat in range(index + 1):
            results.append(
                {
                    "url": f"https://reddit.com/{index}/{repeat}",
                    "title": f"Post {index}",
                    "snippet": "Text",
                    "source": "reddit",
                    "query": "agents",
                    "metadata": {"subreddit": f"sub{index}"},
                }
            )

    entities = extract_entities(results)

    assert entities["subreddits"] == ["sub5", "sub4", "sub3", "sub2", "sub1"]


def test_extract_x_handles():
    results = [
        {
            "url": "https://x.com/1",
            "title": "@alice on agents",
            "snippet": "RT @bob and @alice",
            "source": "twitter",
            "query": "agents",
            "metadata": {"author_handle": "@carol"},
        },
        {
            "url": "https://x.com/2",
            "title": "@alice shipping updates",
            "snippet": "Conversation with @bob",
            "source": "twitter",
            "query": "agents",
            "metadata": {},
        },
    ]

    entities = extract_entities(results)

    assert entities["x_handles"] == ["alice", "bob", "carol"]


def test_extract_x_handles_filters_generic():
    results = [
        {
            "url": "https://x.com/1",
            "title": "@openai meets @google",
            "snippet": "@builder shares notes",
            "source": "twitter",
            "query": "agents",
            "metadata": {"author_handle": "@OpenAI"},
        }
    ]

    entities = extract_entities(results)

    assert entities["x_handles"] == ["builder"]


def test_extract_authors():
    results = [
        {
            "url": "https://arxiv.org/abs/1",
            "title": "Paper title",
            "snippet": "Jane Doe, John Smith, Alice Brown. New findings in agents.",
            "source": "arxiv",
            "query": "agents",
            "metadata": {},
        },
        {
            "url": "https://scholar.google.com/2",
            "title": "Another paper",
            "snippet": "by Jane Doe",
            "source": "google-scholar",
            "query": "agents",
            "metadata": {},
        },
    ]

    entities = extract_entities(results)

    assert entities["authors"] == ["Jane Doe", "Alice Brown", "John Smith"]


def test_extract_empty_results():
    assert extract_entities([]) == {
        "subreddits": [],
        "x_handles": [],
        "authors": [],
    }
