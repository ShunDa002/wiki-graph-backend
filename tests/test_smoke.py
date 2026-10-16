from types import SimpleNamespace

from graph.graph_builder import build_graph

SOURCE_FOLDERS = [
    "sources",
    "concepts",
    # "decisions",
    # "questions",
    # "syntheses",
    # "experiments",
    # "projects",
]


def test_build_scans_only_configured_knowledge_folders(tmp_path):
    repo = tmp_path / "repo"
    wiki = repo / "wiki"
    wiki.mkdir(parents=True)

    for folder in SOURCE_FOLDERS:
        (wiki / folder).mkdir()

    # Vault navigation and audit files must not become graph nodes.
    (wiki / "index.md").write_text("# The Wiki Index", encoding="utf-8")
    (wiki / "log.md").write_text("# The Operation Log", encoding="utf-8")

    # Markdown under an unconfigured wiki folder must also be ignored.
    (wiki / "templates").mkdir()
    (wiki / "templates" / "note.md").write_text("# Template", encoding="utf-8")

    (wiki / "concepts" / "alpha.md").write_text(
        "---\ntitle: Alpha\ntype: concept\ntags: [x]\n---\n" "# Alpha\nSee [[Beta]].",
        encoding="utf-8",
    )
    (wiki / "sources" / "beta.md").write_text(
        "# Beta\nBack to [Alpha](../concepts/alpha.md).",
        encoding="utf-8",
    )

    settings = SimpleNamespace(
        wiki_dir=wiki,
        wiki_repo_dir=repo,
        graph_source_folders=SOURCE_FOLDERS,
        graph_max_nodes=100,
        graph_max_file_bytes=10000,
        graph_excerpt_length=240,
        graph_include_drafts=True,
        graph_include_deprecated=True,
    )

    graph = build_graph(settings)

    assert {node.id for node in graph.nodes} == {
        "concepts/alpha.md",
        "sources/beta.md",
    }
    assert graph.metadata.nodeCount == 2
    assert graph.metadata.edgeCount == 2
    assert not graph.unresolvedLinks
    assert all(
        node.incomingCount == 1 and node.outgoingCount == 1 for node in graph.nodes
    )
