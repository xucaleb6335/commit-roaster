import pytest

from commit_roaster.knowledge import KnowledgeBase, load_chunks


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase.load()


def test_every_section_becomes_a_chunk_with_unique_id():
    chunks = load_chunks()
    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids)) >= 20
    assert all(c.text and c.title for c in chunks)


@pytest.mark.parametrize("query, expected", [
    ("wip commit", "BP-08"),
    ("vague message fix", "BP-05"),
    ("breaking change api", "CC-07"),
    ("past tense fixed", "BP-03"),
    ("small tweak huge change many files", "BP-06"),
    ("subject line too long", "BP-02"),
    ("feat vs fix version bump", "CC-02"),
    ("typo misspelled udpate", "BP-13"),
    ("venting blame stupid api", "BP-14"),
])
def test_search_ranks_the_right_rule_first(kb, query, expected):
    assert kb.search(query)[0].id == expected


def test_search_with_no_useful_terms_returns_nothing(kb):
    assert kb.search("the and of") == []
    assert "No matching guidelines" in kb.format_results([])


def test_format_results_includes_citation_ids(kb):
    text = kb.format_results(kb.search("wip"))
    assert "[BP-08]" in text and "commit_best_practices.md" in text
