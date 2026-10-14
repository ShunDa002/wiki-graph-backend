from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import logging, subprocess
from .markdown_parser import parse_page,node_kwargs
from .link_parser import extract_body_links,extract_frontmatter_links
from .link_resolver import Resolver
from .models import WikiNode,WikiEdge,UnresolvedLink,GraphMetadata,WikiGraph
log=logging.getLogger(__name__)

def source_version(repo):
    try:return subprocess.run(['git','rev-parse','HEAD'],cwd=repo,capture_output=True,text=True,timeout=3,check=True).stdout.strip()
    except Exception:return None

def build_graph(settings):
    pages=[]; malformed=0
    paths = sorted(
        (
            path
            for folder in settings.graph_source_folders
            for path in (settings.wiki_dir / folder).rglob("*.md")
        ),
        key=lambda path: path.relative_to(settings.wiki_dir).as_posix().casefold(),
    )
    if len(paths)>settings.graph_max_nodes: raise RuntimeError('Wiki exceeds GRAPH_MAX_NODES')
    for path in paths:
        try:
            resolved=path.resolve()
            if not resolved.is_relative_to(settings.wiki_dir) or path.stat().st_size>settings.graph_max_file_bytes: continue
            p=parse_page(path,settings.wiki_dir,settings.graph_excerpt_length)
            status=str(p.frontmatter.get('status','')).strip().lower()
            if not settings.graph_include_drafts and status=='draft':continue
            if not settings.graph_include_deprecated and status in {'deprecated','superseded'}:continue
            pages.append(p)
        except Exception as e: malformed+=1; log.warning('Skipping %s: %s',path,e)
    resolver=Resolver(pages); nodes={p.node_id:WikiNode(**node_kwargs(p)) for p in pages}
    aggr={}; unresolved=[]
    for p in pages:
        for link in extract_body_links(p.body)+extract_frontmatter_links(p.frontmatter):
            target,reason=resolver.resolve(p.node_id,link.target)
            if not target or target==p.node_id:
                unresolved.append(UnresolvedLink(source=p.node_id,rawTarget=link.target,type=link.type,label=link.label,heading=link.heading,reason=reason or 'self-link'))
                continue
            k=(p.node_id,target,link.type)
            a=aggr.setdefault(k,{'occurrences':0,'headings':set(),'label':None}); a['occurrences']+=1
            if link.source_heading:a['headings'].add(link.source_heading)
            if not a['label'] and link.label:a['label']=link.label
    edges=[]
    for (s,t,typ),a in sorted(aggr.items()):
        eid=sha256(f'{s}\0{t}\0{typ}'.encode()).hexdigest()[:24]
        edges.append(WikiEdge(id=eid,source=s,target=t,type=typ,label=a['label'],occurrences=a['occurrences'],sourceHeadings=sorted(a['headings'],key=str.casefold)))
    outgoing=defaultdict(set); incoming=defaultdict(set)
    for e in edges:outgoing[e.source].add(e.target); incoming[e.target].add(e.source)
    for n in nodes.values():
        n.outgoingCount=len(outgoing[n.id]); n.incomingCount=len(incoming[n.id]); n.isOrphan=not(n.outgoingCount or n.incomingCount)
    nl=sorted(nodes.values(),key=lambda n:n.id.casefold()); unresolved.sort(key=lambda u:(u.source.casefold(),u.rawTarget.casefold(),u.type))
    types=Counter(n.type for n in nl if n.type)
    meta=GraphMetadata(nodeCount=len(nl),edgeCount=len(edges),orphanCount=sum(n.isOrphan for n in nl),brokenLinkCount=len(unresolved),folderCount=len({n.folder for n in nl}),tagCount=len({t for n in nl for t in n.tags}),reviewNeededCount=sum(n.reviewNeeded is True for n in nl),draftCount=sum(n.status=='draft' for n in nl),typeBreakdown=dict(sorted(types.items())))
    graph=WikiGraph(generatedAt=datetime.now(timezone.utc).isoformat(),sourceVersion=source_version(settings.wiki_repo_dir),metadata=meta,nodes=nl,edges=edges,unresolvedLinks=unresolved)
    log.info('Graph built files=%d nodes=%d edges=%d unresolved=%d malformed=%d',len(paths),len(nl),len(edges),len(unresolved),malformed)
    return graph
