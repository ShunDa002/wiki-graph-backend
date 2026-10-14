from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

LinkType = Literal['wikilink','markdown-link','embed','frontmatter-link']
PageType = Literal['concept','decision','experiment','project','question','source','synthesis']

class WikiNode(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str; title: str; path: str; folder: str
    tags: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    excerpt: str = ''
    type: PageType | None = None
    status: str | None = None
    confidence: str | None = None
    classification: str | None = None
    knowledgeStatus: str | None = None
    reviewNeeded: bool | None = None
    owner: str | None = None
    author: str | None = None
    sourceKind: str | None = None
    createdAt: str | None = None
    updatedAt: str | None = None
    decisionDate: str | None = None
    reviewDate: str | None = None
    completedAt: str | None = None
    outgoingCount: int = Field(0, ge=0)
    incomingCount: int = Field(0, ge=0)
    isOrphan: bool = True

class WikiEdge(BaseModel):
    id: str; source: str; target: str; type: LinkType
    label: str | None = None
    occurrences: int = Field(1, ge=1)
    sourceHeadings: list[str] = Field(default_factory=list)

class UnresolvedLink(BaseModel):
    source: str; rawTarget: str; type: LinkType
    label: str | None = None; heading: str | None = None; reason: str | None = None

class GraphMetadata(BaseModel):
    nodeCount: int = Field(ge=0); edgeCount: int = Field(ge=0)
    orphanCount: int = Field(ge=0); brokenLinkCount: int = Field(ge=0)
    folderCount: int = Field(ge=0); tagCount: int = Field(ge=0)
    reviewNeededCount: int = Field(0, ge=0); draftCount: int = Field(0, ge=0)
    typeBreakdown: dict[str,int] = Field(default_factory=dict)

class WikiGraph(BaseModel):
    schemaVersion: str = '1.0.0'; generatedAt: str
    sourceVersion: str | None = None; metadata: GraphMetadata
    nodes: list[WikiNode]; edges: list[WikiEdge]
    unresolvedLinks: list[UnresolvedLink]

    @model_validator(mode='after')
    def integrity(self):
        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)): raise ValueError('duplicate node IDs')
        edge_ids = [e.id for e in self.edges]
        if len(edge_ids) != len(set(edge_ids)): raise ValueError('duplicate edge IDs')
        known = set(ids)
        if any(e.source not in known or e.target not in known for e in self.edges):
            raise ValueError('edge references a missing node')
        if self.metadata.nodeCount != len(self.nodes) or self.metadata.edgeCount != len(self.edges):
            raise ValueError('metadata count mismatch')
        if self.metadata.brokenLinkCount != len(self.unresolvedLinks):
            raise ValueError('broken link count mismatch')
        for n in self.nodes:
            if n.isOrphan != (n.incomingCount == 0 and n.outgoingCount == 0):
                raise ValueError(f'orphan mismatch: {n.id}')
        return self
