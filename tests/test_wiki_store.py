from wiki_store import WikiStore


def test_store_load_search_and_relative_paths(tmp_path):
    wiki = tmp_path / "wiki"
    concepts = wiki / "concepts"
    sources = wiki / "sources"
    concepts.mkdir(parents=True)
    sources.mkdir()
    (wiki / "index.md").write_text("# Index", encoding="utf-8")
    (concepts / "graph.md").write_text(
        "---\ntitle: Knowledge Graph\nconfidence: high\nreviewed: true\n---\n"
        "A graph connects knowledge pages.",
        encoding="utf-8",
    )
    (sources / "notes.md").write_text(
        "# Notes\nRetrieval uses Wiki content.", encoding="utf-8"
    )

    store = WikiStore(wiki, ["sources", "concepts"])
    store.load()
    results = store.search("knowledge graph", top_k=1)

    assert len(store.documents) == 2
    assert results[0]["path"] == "concepts/graph.md"
    assert all(item["path"] != "index.md" for item in store.documents)


def test_random_topic_source_can_have_fewer_than_three(tmp_path):
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "sources").mkdir()
    (wiki / "concepts" / "one.md").write_text("# One", encoding="utf-8")
    store = WikiStore(wiki, ["sources", "concepts"])
    store.load()
    assert len(store.concepts_docs) == 1
