# Self-written, plan v2.3 § 13.5 F301
from autosearch.core.models import OutlineNode, parse_markdown_outline


def make_outline_tree() -> OutlineNode:
    return OutlineNode(
        heading="Parent",
        level=1,
        children=[
            OutlineNode(
                heading="Child A",
                level=2,
                children=[
                    OutlineNode(
                        heading="Grandchild A1",
                        level=3,
                    )
                ],
            ),
            OutlineNode(
                heading="Child B",
                level=2,
                children=[
                    OutlineNode(
                        heading="Grandchild B1",
                        level=3,
                    )
                ],
            ),
        ],
    )


def test_outline_node_basic_roundtrip() -> None:
    node = OutlineNode(heading="Overview", level=1)

    payload = node.model_dump_json()
    restored = OutlineNode.model_validate_json(payload)

    assert restored == node
    assert restored.children == []
    assert restored.section_query is None


def test_outline_node_nested_roundtrip() -> None:
    node = OutlineNode(
        heading="Overview",
        level=1,
        children=[
            OutlineNode(
                heading="Background",
                level=2,
                children=[OutlineNode(heading="Timeline", level=3)],
            )
        ],
    )

    payload = node.model_dump_json()
    restored = OutlineNode.model_validate_json(payload)

    assert restored == node
    assert restored.children[0].children[0].heading == "Timeline"


def test_get_subtree_headings_flat() -> None:
    node = OutlineNode(heading="Overview", level=1)

    assert node.get_subtree_headings() == ["Overview"]


def test_get_subtree_headings_nested() -> None:
    node = make_outline_tree()

    assert node.get_subtree_headings() == [
        "Parent",
        "Parent > Child A",
        "Parent > Child A > Grandchild A1",
        "Parent > Child B",
        "Parent > Child B > Grandchild B1",
    ]


def test_get_subtree_headings_with_root_name() -> None:
    node = OutlineNode(
        heading="Overview",
        level=1,
        children=[OutlineNode(heading="History", level=2)],
    )

    assert node.get_subtree_headings(root_name="Topic") == [
        "Topic > Overview",
        "Topic > Overview > History",
    ]


def test_walk_leaves() -> None:
    node = make_outline_tree()

    assert [leaf.heading for leaf in node.walk_leaves()] == [
        "Grandchild A1",
        "Grandchild B1",
    ]


def test_walk_depth_first() -> None:
    node = make_outline_tree()

    assert [current.heading for current in node.walk_depth_first()] == [
        "Parent",
        "Child A",
        "Grandchild A1",
        "Child B",
        "Grandchild B1",
    ]


def test_parse_markdown_outline_single_level() -> None:
    outline = parse_markdown_outline("# A\n# B")

    assert outline.heading == ""
    assert outline.level == 0
    assert [child.heading for child in outline.children] == ["A", "B"]


def test_parse_markdown_outline_nested() -> None:
    outline = parse_markdown_outline("# A\n## A1\n## A2\n# B")

    assert outline.heading == ""
    assert outline.level == 0
    assert [child.heading for child in outline.children] == ["A", "B"]
    assert [child.heading for child in outline.children[0].children] == ["A1", "A2"]
    assert outline.children[1].children == []


def test_parse_markdown_outline_no_hash_fallback() -> None:
    outline = parse_markdown_outline("Alpha\n\nBeta\nGamma")

    assert outline.heading == ""
    assert outline.level == 0
    assert [child.heading for child in outline.children] == ["Alpha", "Beta", "Gamma"]
    assert all(child.level == 1 for child in outline.children)


def test_parse_markdown_outline_empty() -> None:
    outline = parse_markdown_outline("")

    assert outline == OutlineNode(heading="", level=0, children=[])


def test_parse_markdown_outline_handles_mixed_whitespace_and_blank_lines() -> None:
    outline = parse_markdown_outline("   # A   \n\n\n  ## A1  ")

    assert outline.heading == "A"
    assert outline.level == 1
    assert [child.heading for child in outline.children] == ["A1"]


def test_parse_markdown_outline_skips_non_heading_lines() -> None:
    outline = parse_markdown_outline("# A\nparagraph\n## A1")

    assert outline.heading == "A"
    assert [child.heading for child in outline.children] == ["A1"]
