# FastAPI Graph View Backend Implementation Plan

## 1. Purpose

Build a small, read-only FastAPI backend that generates and serves graph data for a Next.js LLM Wiki Graph View.

The backend must read only from the chatbot service's synchronized copy of `wiki/`. It must never read from, modify, or write to the original local-Agent workspace. The generated graph represents Markdown pages as nodes and resolved page-to-page links as edges.

The initial implementation should remain simple, deterministic, testable, and suitable for Cytoscape.js with the fCoSE layout extension.

---

## 2. Scope

### In scope

- Recursively scan the chatbot backend's local `wiki/` copy.
- Parse Markdown files and YAML frontmatter.
- Extract page metadata, aliases, tags, summaries, and graph-related status fields.
- Extract Obsidian wikilinks and relative Markdown links.
- Resolve links to canonical Wiki pages.
- Build nodes, edges, graph metadata, and unresolved-link diagnostics.
- Expose the graph through FastAPI endpoints.
- Cache the generated graph in memory and optionally as `graph.json`.
- Support explicit graph regeneration after the Wiki copy is synchronized.
- Return data in a stable, versioned schema that the Next.js frontend can consume.

### Out of scope for the first version

- Writing to Wiki Markdown files.
- Updating the original LLM Wiki repository.
- Git push, pull request, or file-back workflows.
- Graph editing from the frontend.
- Full-text chatbot answering.
- Graph database deployment.
- Community detection or machine-learning-based relationship inference.
- Real-time filesystem watching.
- User-specific graph data.

---

## 3. System Boundary

The backend should use the following one-way data flow:

```text
Original LLM Wiki repository
        |
        | separate synchronization process
        v
Chat backend local repository copy
        |
        | read only
        v
wiki/ Markdown parser
        |
        v
WikiGraph builder
        |
        +--> in-memory cache
        +--> optional generated graph.json
        |
        v
FastAPI Graph API
        |
        v
Next.js + Cytoscape.js + cytoscape-fcose
```

The Graph API must not know the path of the original local-Agent workspace. It should receive only the path of the chatbot backend's synchronized repository copy through configuration.

---

## 4. Recommended Project Structure

```text
chat-backend/
├─ app.py
├─ config.py
├─ wiki_store.py
├─ graph/
│  ├─ __init__.py
│  ├─ models.py
│  ├─ markdown_parser.py
│  ├─ link_parser.py
│  ├─ link_resolver.py
│  ├─ graph_builder.py
│  ├─ graph_service.py
│  └─ routes.py
├─ data/
│  ├─ source-repo/
│  │  └─ wiki/
│  └─ generated/
│     └─ graph.json
├─ tests/
│  ├─ fixtures/
│  │  └─ wiki/
│  ├─ test_markdown_parser.py
│  ├─ test_link_parser.py
│  ├─ test_link_resolver.py
│  ├─ test_graph_builder.py
│  └─ test_graph_routes.py
├─ requirements.txt
└─ .env
```

The graph implementation should be separated from the chatbot retrieval implementation. The two features may read the same synchronized `wiki/` directory, but they should have independent services and API routes.

---

## 5. Configuration

Use environment variables for all deployment-specific paths and behavior.

```env
WIKI_REPO_DIR=./data/source-repo
WIKI_DIR=./data/source-repo/wiki
GRAPH_OUTPUT_PATH=./data/generated/graph.json
GRAPH_CACHE_ENABLED=true
GRAPH_INCLUDE_DRAFTS=true
GRAPH_INCLUDE_DEPRECATED=false
GRAPH_EXCERPT_LENGTH=240
```

Configuration requirements:

- Convert configured paths to resolved absolute `Path` objects at application startup.
- Verify that `WIKI_DIR` is located inside the chatbot backend's synchronized repository directory.
- Fail startup with a clear error if `wiki/` does not exist.
- Never accept a Wiki filesystem path from an API request.
- Never expose absolute server paths in API responses.

---

## 6. Graph Data Contract

Use a versioned response model.

```typescript
export type LinkType =
  | "wikilink"
  | "markdown-link"
  | "embed"
  | "frontmatter-link";

export interface WikiGraph {
  schemaVersion: string;
  generatedAt: string;
  sourceVersion?: string;
  metadata: GraphMetadata;
  nodes: WikiNode[];
  edges: WikiEdge[];
  unresolvedLinks: UnresolvedLink[];
}

export type PageType =
  | "concept"
  | "decision"
  | "experiment"
  | "project"
  | "question"
  | "source"
  | "synthesis";

export interface WikiNode {
  id: string;
  title: string;
  path: string;
  folder: string;
  tags: string[];
  aliases: string[];
  excerpt: string;
  type?: PageType;
  status?: string;
  confidence?: string;
  classification?: string;
  knowledgeStatus?: string;
  reviewNeeded?: boolean;
  owner?: string;
  author?: string;
  sourceKind?: string;
  createdAt?: string;
  updatedAt?: string;
  decisionDate?: string;
  reviewDate?: string;
  completedAt?: string;
  outgoingCount: number;
  incomingCount: number;
  isOrphan: boolean;
}

export interface WikiEdge {
  id: string;
  source: string;
  target: string;
  type: LinkType;
  label?: string;
  occurrences?: number;
  sourceHeadings?: string[];
}

export interface UnresolvedLink {
  source: string;
  rawTarget: string;
  type: LinkType;
  label?: string;
  heading?: string;
  reason?: string;
}

export interface GraphMetadata {
  nodeCount: number;
  edgeCount: number;
  orphanCount: number;
  brokenLinkCount: number;
  folderCount: number;
  tagCount: number;
  reviewNeededCount?: number;
  draftCount?: number;
  typeBreakdown?: Record<PageType, number>;
}
```

Use equivalent Pydantic models in the FastAPI backend. The API response must always conform to this contract.

---

## 7. Stable Identity Rules

### Node ID

Use the normalized Wiki-relative Markdown path as the node ID.

Example:

```text
concepts/llm-wiki.md
```

Requirements:

- Use POSIX `/` separators on every platform.
- Exclude the absolute host path.
- Keep IDs stable across graph regenerations.
- Do not use page titles as IDs because titles may change or be duplicated.

### Edge ID

Generate an edge ID from:

```text
source node ID + target node ID + link type
```

If duplicate links from the same source to the same target are merged, store their total in `occurrences`.

Use a deterministic hash if the combined string is too long for convenient frontend handling.

---

## 8. Markdown Parsing

Create a parser that returns one normalized internal page record per Markdown file.

### Frontmatter fields

The Wiki uses seven page templates (concept, decision, experiment, project, question, source, synthesis), each with a distinct set of YAML frontmatter fields. The parser must read the union of all fields across templates.

#### Common fields (all or most templates)

- `title`
- `type` — one of: `concept`, `decision`, `experiment`, `project`, `question`, `source`, `synthesis`
- `status` — type-specific values (see below)
- `classification` — `public` or `internal`
- `tags` — concept, question, synthesis
- `aliases` — concept, synthesis

#### Knowledge and review fields

- `confidence` — concept, synthesis: `low`, `medium`, or `high`
- `knowledge_status` — concept, synthesis: `current`, `disputed`, `superseded`, or `uncertain`
- `review_needed` — concept, synthesis: boolean

#### Date fields

- `created` — concept, question, synthesis
- `updated` — concept, question, synthesis
- `started` — project, experiment
- `completed` — experiment
- `captured` — source
- `ingested` — source
- `decision_date` — decision
- `review_date` — decision, project

#### People fields

- `owner` — project
- `author` — source

#### Source-specific fields

- `source_kind` — source: `article`, `notes`, `transcript`, or `webpage`
- `source_id` — source: SHA256 hash of the raw file

#### Wikilink-bearing relationship fields

These fields contain Obsidian `[[wikilinks]]` and must be parsed to produce `frontmatter-link` edges:

- `sources` — concept, question, synthesis: `[[Source - <Name>]]`
- `project` — decision, experiment: `[[<Project>]]`
- `knowledge_basis` — decision: `[[<Synthesis or concept>]]`
- `validated_by` — decision: `[[<Experiment>]]`
- `tests_decision` — experiment: `[[<Decision>]]`
- `informed_by` — project: `[[<Wiki concept or synthesis>]]`
- `based_on` — synthesis: `[[<Concept A>]]`
- `raw_file` — source: `[[raw/articles/<file>]]`

#### Fallback field

- `description` — not in any template, but used as excerpt fallback if present

#### Type-specific `status` values

| Type       | Valid `status` values                |
| ---------- | ------------------------------------ |
| concept    | `active`, `draft`, `superseded`      |
| decision   | `proposed`, `accepted`, `superseded` |
| experiment | `planned`, `running`, `complete`     |
| project    | `active`, `paused`, `done`           |
| question   | `open`, `answered`, `abandoned`      |
| source     | `processed`                          |
| synthesis  | `active`, `draft`, `superseded`      |

### Normalization rules

- `title`: frontmatter title, otherwise first H1, otherwise filename.
- `tags`: convert strings and lists into a normalized string array.
- `aliases`: convert strings and lists into a normalized string array.
- `review_needed`: accept only a real YAML Boolean `true` as `True`.
- `status`, `type`, `confidence`, `classification`, and `knowledge_status`: trim and normalize case.
- `path`: store a Wiki-relative POSIX path.
- `folder`: store the complete Wiki-relative parent folder.
- `excerpt`: use `description`, otherwise the first meaningful prose paragraph.
- Strip Markdown syntax, HTML, image markup, and code fences from excerpts.
- Limit excerpts to the configured maximum length.
- Date fields: normalize `created`, `started`, `captured`, `ingested` into `createdAt`; normalize `updated` into `updatedAt`; preserve `decision_date`, `review_date`, and `completed` as separate fields.

### Error handling

A malformed page should not prevent the complete graph from loading.

For recoverable parsing failures:

- Use safe defaults.
- Add a warning to server logs.
- Continue processing other pages.

For unreadable files:

- Exclude the file from nodes.
- Log the path and reason.
- Optionally expose a build-warning count in a future schema version.

---

## 9. Link Extraction

Extract links from the Markdown body after frontmatter removal.

### Wikilinks

Support:

```markdown
[[Page Name]]
[[folder/Page Name]]
[[Page Name|Display Label]]
[[Page Name#Heading]]
![[Embedded Page]]
```

Preserve:

- Raw target
- Display label
- Link type
- Heading fragment
- Source section heading

### Markdown links

Support relative Markdown links:

```markdown
[LLM Wiki](../concepts/llm-wiki.md)
[LLM Wiki](../concepts/llm-wiki.md#architecture)
```

Ignore external URLs such as:

```text
https://
http://
mailto:
```

Ignore image and asset links unless the target is a Markdown page.

### Frontmatter links

The Wiki templates use structured frontmatter fields that contain Obsidian `[[wikilinks]]`. These must be extracted as `frontmatter-link` edges with a descriptive `label` matching the field name.

The set of wikilink-bearing frontmatter fields should be configurable. The default configuration must include:

```yaml
frontmatter_link_fields:
  - field: sources
    label: "sources"
  - field: project
    label: "project"
  - field: knowledge_basis
    label: "knowledge-basis"
  - field: validated_by
    label: "validated-by"
  - field: tests_decision
    label: "tests-decision"
  - field: informed_by
    label: "informed-by"
  - field: based_on
    label: "based-on"
  - field: raw_file
    label: "raw-file"
```

Each field value may be a single string or a list of strings. Each string is expected to contain one `[[wikilink]]` that the existing wikilink regex can extract. Frontmatter link fields that resolve to targets outside `wiki/` (such as `raw_file` pointing to `raw/articles/`) should produce unresolved links with `reason: target-outside-wiki` rather than being silently dropped.

Keep this parser configurable so unused or future fields do not create accidental edges.

---

## 10. Link Resolution

Build lookup indexes before resolving relationships.

### Required indexes

```text
normalized path -> node ID
path without .md -> node ID
filename stem -> candidate node IDs
title -> candidate node IDs
alias -> candidate node IDs
```

### Resolution order

1. Exact normalized relative path.
2. Exact path without `.md`.
3. Path relative to the source page directory.
4. Exact title.
5. Exact alias.
6. Unique filename stem.

### Ambiguous links

If a title, alias, or filename matches multiple nodes:

- Do not choose a target arbitrarily.
- Add an `UnresolvedLink` entry.
- Set `reason` to `ambiguous-target`.

### Missing links

If no target is found:

- Do not create a normal edge.
- Add an `UnresolvedLink` entry.
- Set `reason` to `target-not-found`.

### Self-links

Decide explicitly whether self-links should be retained. The recommended initial behavior is to exclude them from rendered edges and graph counts while logging them for diagnostics.

---

## 11. Edge Aggregation

Multiple occurrences of the same page-to-page relationship should normally become one edge.

Use this aggregation key:

```text
source + target + link type
```

For each aggregated edge:

- Increment `occurrences`.
- Collect unique source headings.
- Preserve the best available display label.
- Sort `sourceHeadings` for deterministic output.

This prevents Cytoscape.js from rendering multiple overlapping lines for repeated links.

---

## 12. Graph Metrics

After all edges are resolved, calculate metrics from the final edge set.

### Node metrics

- `outgoingCount`: number of unique target nodes.
- `incomingCount`: number of unique source nodes.
- `isOrphan`: `incomingCount === 0 && outgoingCount === 0`.

Do not calculate counts directly from raw link occurrences.

### Graph metadata

Calculate:

- `nodeCount`
- `edgeCount`
- `orphanCount`
- `brokenLinkCount`
- `folderCount`
- `tagCount`
- `reviewedCount`
- `draftCount`

`brokenLinkCount` should equal the number of unresolved link records, unless a future version adds separate ambiguity and failure counts.

---

## 13. Source Version

When the synchronized Wiki copy is a Git repository, retrieve the checked-out commit SHA:

```text
git rev-parse HEAD
```

Store it in `sourceVersion`.

Requirements:

- Run Git commands only inside the chatbot backend's synchronized repository copy.
- Do not run Git against the original local-Agent workspace.
- If Git metadata is unavailable, return `sourceVersion` as `null` or omit it.
- Graph generation must still work without Git.

This field allows the frontend to show which Wiki version produced the graph and lets chat responses and graph data be compared against the same source revision.

---

## 14. Graph Service

Create a `GraphService` responsible for graph lifecycle management.

Suggested interface:

```python
class GraphService:
    def build_graph(self) -> WikiGraph:
        ...

    def get_graph(self, force_refresh: bool = False) -> WikiGraph:
        ...

    def get_node(self, node_id: str) -> WikiNode | None:
        ...

    def get_neighbors(self, node_id: str, depth: int = 1) -> WikiGraph:
        ...

    def invalidate(self) -> None:
        ...
```

Responsibilities:

- Build the complete graph.
- Hold an in-memory cached graph.
- Optionally write an atomic `graph.json` snapshot.
- Return the current graph without reparsing files on every request.
- Regenerate the graph when explicitly requested.

Use a lock around graph regeneration so simultaneous requests do not trigger duplicate builds.

---

## 15. Cache and `graph.json`

### In-memory cache

Use an application-level in-memory cache for the current graph. This is sufficient for the first deployment if the API runs as a single process.

### Static JSON output

Optionally write the generated graph to:

```text
data/generated/graph.json
```

Write atomically:

1. Serialize to a temporary file.
2. Validate the serialized data.
3. Rename the temporary file over `graph.json`.

Do not write `graph.json` into the synchronized source repository. Generated artifacts belong to the chatbot backend.

### Multi-worker consideration

An in-memory cache is not shared between Uvicorn workers. For the first version, use one worker or regenerate per worker. If multiple workers are later required, use the generated JSON file or an external cache as the shared artifact.

---

## 16. API Endpoints

### Health check

```http
GET /health
```

Response:

```json
{
  "status": "ok",
  "wikiPages": 120,
  "graphReady": true,
  "sourceVersion": "a3fd218"
}
```

### Get complete graph

```http
GET /graph
```

Returns the complete `WikiGraph` object.

Recommended headers:

```text
Cache-Control: private, max-age=60
ETag: <hash of sourceVersion and schemaVersion>
```

Support conditional requests with `If-None-Match` when practical.

### Get graph metadata

```http
GET /graph/metadata
```

Returns generation time, source version, and graph counts without transferring all nodes and edges.

### Get one node

```http
GET /graph/nodes/{node_id}
```

Because node IDs can contain slashes, either:

- URL-encode the ID, or
- Use a stable hash as the API-facing identifier, or
- Accept the path as a query parameter.

A query parameter is simplest for path-based IDs:

```http
GET /graph/node?id=concepts%2Fllm-wiki.md
```

### Get a node neighborhood

```http
GET /graph/neighborhood?id=concepts%2Fllm-wiki.md&depth=1
```

Return a smaller `WikiGraph` containing the selected node and its neighbors. Limit depth to a safe maximum such as `2` or `3`.

This endpoint is optional for the first frontend release but useful when the complete graph becomes large.

### Regenerate graph

```http
POST /graph/rebuild
```

This endpoint rebuilds the graph from the chatbot backend's current synchronized `wiki/` copy.

Protect it with one of the following:

- Internal network access only
- API key
- Admin authentication
- Invocation only from the repository synchronization process

It must not perform `git pull` and must not modify Wiki files.

---

## 17. FastAPI Response Models

Implement Pydantic models matching the TypeScript types. Use them as FastAPI response models so invalid graph data is detected before it reaches the frontend.

Key validation rules:

- Dates must be ISO 8601 strings or typed datetimes serialized as ISO 8601.
- Node IDs must be unique.
- Edge IDs must be unique.
- Every resolved edge source and target must exist in `nodes`.
- Counts must be non-negative.
- `isOrphan` must agree with incoming and outgoing counts.
- `metadata` counts must match the arrays in the response.

Perform full graph integrity validation during graph generation, not on every `GET /graph` request.

---

## 18. Frontend Integration Contract

The Next.js frontend should request graph data only from the FastAPI backend:

```text
Next.js -> FastAPI /graph -> chatbot backend Wiki copy
```

It should not request Markdown files or repository contents directly from the original GitHub repository.

Benefits:

- The chatbot and graph use the same synchronized Wiki revision.
- The browser does not require GitHub credentials.
- Repository structure and parsing rules remain server-side.
- GitHub API limits do not affect graph rendering.
- The frontend receives a stable, normalized contract.
- The original repository remains isolated from the website.

### Cytoscape.js mapping

The frontend can map nodes and edges as follows:

```typescript
const elements = [
  ...graph.nodes.map((node) => ({
    data: {
      ...node,
      id: node.id,
    },
  })),
  ...graph.edges.map((edge) => ({
    data: {
      ...edge,
      id: edge.id,
      source: edge.source,
      target: edge.target,
    },
  })),
];
```

The backend should not emit Cytoscape-specific style rules. Keep the API data framework-neutral and let the Next.js feature layer define colors, sizing, filtering, fCoSE layout settings, and Motion animations.

---

## 19. CORS

Allow only the configured Next.js frontend origin in normal deployments.

Example:

```env
FRONTEND_ORIGIN=http://localhost:3000
```

Development may allow multiple explicit origins. Avoid combining wildcard origins with credentialed browser requests.

---

## 20. Security Requirements

- Treat Markdown content as untrusted data.
- Never execute code blocks, HTML, scripts, or embedded commands from Wiki files.
- Do not return local absolute paths.
- Do not accept arbitrary filesystem paths from request parameters.
- Do not expose `.git`, `.env`, `raw/`, `dev/`, or non-Wiki files.
- Restrict parsing to files under the configured `WIKI_DIR`.
- Resolve and validate paths before reading files.
- Apply a maximum Markdown file size to prevent excessive memory usage.
- Limit graph rebuild access.
- Escape or sanitize excerpts before rendering them as HTML in the frontend.
- Return plain data, not pre-rendered Wiki HTML, in the first version.

---

## 21. Performance Strategy

For the initial version:

- Parse all Markdown files during application startup or the first graph request.
- Cache the complete graph in memory.
- Serve cached JSON for normal requests.
- Rebuild only on explicit reload after Wiki synchronization.

Recommended initial limits:

- Maximum page size: 2 MB
- Maximum total nodes: configurable
- Maximum neighborhood depth: 2
- Maximum excerpt length: 240 characters

If the graph grows substantially:

- Add gzip or Brotli compression at the reverse proxy.
- Add ETag handling.
- Add neighborhood endpoints.
- Add precomputed search indexes.
- Move expensive rebuilds to a background task.
- Store the generated graph in an object store or shared cache for multiple API workers.

Do not introduce a graph database until actual graph size or query requirements justify it.

---

## 22. Logging and Observability

Log graph builds with:

- Start and completion time
- Source version
- Number of Markdown files scanned
- Number of nodes
- Number of edges
- Number of unresolved links
- Number of malformed files
- Build duration

Do not log complete Markdown content.

Expose basic graph status through `/health` and `/graph/metadata`.

---

## 23. Testing Plan

### Unit tests

Test Markdown parsing for:

- Valid frontmatter
- Missing frontmatter
- Malformed YAML
- String and array tags
- String and array aliases
- Boolean `review_needed`
- Title fallback behavior
- Excerpt generation
- All seven page types (concept, decision, experiment, project, question, source, synthesis)
- Type-specific fields (`classification`, `knowledge_status`, `owner`, `author`, `source_kind`)
- Date field normalization (`created`, `started`, `captured`, `ingested` → `createdAt`)
- Type-specific `status` values

Test link extraction for:

- Basic wikilinks
- Aliased wikilinks
- Heading links
- Embedded links
- Relative Markdown links
- External links
- Image links
- Duplicate links
- Frontmatter wikilink fields (`sources`, `project`, `knowledge_basis`, `validated_by`, `tests_decision`, `informed_by`, `based_on`, `raw_file`)
- Single-value vs list-value frontmatter link fields
- Frontmatter link edge labels match field names

Test link resolution for:

- Exact paths
- Relative paths
- Titles
- Aliases
- Duplicate titles
- Ambiguous aliases
- Missing targets
- Self-links

Test graph building for:

- Stable node and edge IDs
- Aggregated occurrences
- Correct incoming and outgoing counts
- Correct orphan detection
- Correct metadata totals
- Unresolved-link collection
- Deterministic output ordering

### API tests

Test:

- `GET /health`
- `GET /graph`
- `GET /graph/metadata`
- Node lookup
- Neighborhood lookup
- Rebuild authorization
- Empty Wiki behavior
- Invalid Wiki path configuration
- ETag behavior if implemented

### Frontend contract test

Validate a generated response against the TypeScript `WikiGraph` schema or a shared JSON Schema.

---

## 24. Deterministic Output

Graph generation must produce stable JSON when Wiki content has not changed.

Sort:

- Nodes by `id`
- Edges by `source`, `target`, and `type`
- Tags alphabetically
- Aliases alphabetically
- Source headings alphabetically
- Unresolved links by source and raw target

Use stable ID generation and ISO 8601 timestamps. Note that `generatedAt` will naturally change on every rebuild, but all content arrays should otherwise remain deterministic.

---

## 25. Implementation Phases

### Phase 1: Data models and configuration

- Add Pydantic graph models.
- Add environment-based path configuration.
- Validate the synchronized Wiki directory.
- Define schema version `1.0.0`.

### Phase 2: Markdown parser

- Parse frontmatter and body.
- Normalize page metadata.
- Generate title and excerpt fallbacks.
- Produce internal page records.

### Phase 3: Link extraction and resolution

- Parse wikilinks and Markdown links from body text.
- Parse wikilinks from frontmatter relationship fields (`sources`, `project`, `knowledge_basis`, `validated_by`, `tests_decision`, `informed_by`, `based_on`, `raw_file`).
- Build path, title, stem, and alias indexes.
- Resolve valid targets.
- Record ambiguous and missing links.
- Produce labeled `frontmatter-link` edges for each relationship field.

### Phase 4: Graph builder

- Generate stable nodes.
- Aggregate edges.
- Calculate counts and metadata.
- Retrieve the synchronized repository commit SHA.
- Validate graph integrity.

### Phase 5: Graph service and cache

- Add in-memory caching.
- Add rebuild locking.
- Optionally write `data/generated/graph.json` atomically.

### Phase 6: FastAPI routes

- Add health, graph, metadata, node, and rebuild endpoints.
- Add explicit CORS configuration.
- Add response models and error handling.

### Phase 7: Frontend integration

- Fetch `/graph` from Next.js.
- Map `nodes` and `edges` to Cytoscape elements.
- Add folder, tag, type, status, confidence, classification, knowledge status, review needed, and orphan filters.
- Color or shape nodes by `type` (concept, decision, experiment, project, question, source, synthesis).
- Distinguish edge types visually (body wikilinks vs typed frontmatter-link edges like `knowledge-basis`, `validated-by`).
- Use fCoSE for layout.
- Use Motion only for surrounding interface transitions and detail panels, not for direct graph physics.

### Phase 8: Tests and deployment hardening

- Add parser, resolver, graph, and endpoint tests.
- Protect rebuild endpoint.
- Add cache headers and optional ETag.
- Confirm that no endpoint can access the original LLM Wiki workspace.

---

## 26. Acceptance Criteria

The implementation is complete when:

1. The backend reads only from the chatbot backend's synchronized `wiki/` copy.
2. `GET /graph` returns a valid `WikiGraph` object.
3. Every Markdown page produces one stable node unless it is explicitly excluded.
4. Every resolved internal page link produces or contributes to one stable edge.
5. Missing and ambiguous links appear in `unresolvedLinks`.
6. Incoming, outgoing, orphan, and metadata counts are correct.
7. The response includes `schemaVersion`, `generatedAt`, and, when available, `sourceVersion`.
8. No response exposes an absolute filesystem path.
9. The Next.js frontend can map the response directly into Cytoscape.js elements.
10. Rebuilding the graph does not modify any Wiki Markdown file.
11. The graph can be regenerated after the separate repository synchronization process completes.
12. Unit and API tests cover the core parsing and graph integrity rules.

---

## 27. Recommended First Release

For the first usable release, implement only:

- Complete graph generation
- Pydantic data models
- Wikilinks and relative Markdown links
- Stable path-based node IDs
- Aggregated edges
- Incoming, outgoing, and orphan metrics
- Unresolved links
- In-memory caching
- `GET /graph`
- `GET /graph/metadata`
- Protected `POST /graph/rebuild`
- Explicit Next.js CORS origin

Defer neighborhood queries, ETags, background tasks, and advanced graph analytics until the graph size or frontend behavior demonstrates a concrete need.

This release keeps the architecture minimal while preserving the key boundary: the website reads a synchronized Wiki copy and never touches the original local-Agent-managed repository.
