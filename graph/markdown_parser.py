from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import html, logging, re, yaml

log = logging.getLogger(__name__)
VALID_TYPES={'concept','decision','experiment','project','question','source','synthesis'}

@dataclass
class ParsedPage:
    node_id: str; frontmatter: dict; body: str; title: str; tags: list[str]; aliases: list[str]; excerpt: str

def _list(v):
    if v is None: return []
    values = v if isinstance(v,list) else [v]
    return sorted({str(x).strip() for x in values if str(x).strip()}, key=str.casefold)

def _scalar(v):
    return str(v).strip() if v is not None and str(v).strip() else None

def _iso(v):
    if v is None: return None
    if isinstance(v,(date,datetime)): return v.isoformat()
    return str(v).strip() or None

def split_frontmatter(text):
    if not text.startswith('---'): return {}, text
    m=re.match(r'^---\s*\n(.*?)\n---\s*(?:\n|$)', text, re.S)
    if not m: return {}, text
    try:
        data=yaml.safe_load(m.group(1)) or {}
        return (data if isinstance(data,dict) else {}), text[m.end():]
    except yaml.YAMLError as e:
        log.warning('Malformed YAML frontmatter: %s', e); return {}, text[m.end():]

def _plain(text):
    text=re.sub(r'```.*?```|~~~.*?~~~',' ',text,flags=re.S)
    text=re.sub(r'!\[.*?\]\([^)]*\)|!\[\[[^]]+\]\]',' ',text)
    text=re.sub(r'\[([^]]+)\]\([^)]*\)',r'\1',text)
    text=re.sub(r'\[\[([^]|#]+)(?:#[^]|]+)?(?:\|([^]]+))?\]\]',lambda m:m.group(2) or m.group(1),text)
    text=re.sub(r'<[^>]+>',' ',text); text=re.sub(r'(^|\s)[#>*_`~\-]+',r'\1',text)
    return re.sub(r'\s+',' ',html.unescape(text)).strip()

def parse_page(path:Path, wiki_dir:Path, excerpt_length:int):
    text=path.read_text(encoding='utf-8')
    fm,body=split_frontmatter(text)
    rel=path.relative_to(wiki_dir).as_posix()
    h1=re.search(r'^#\s+(.+?)\s*$',body,re.M)
    title=_scalar(fm.get('title')) or (_plain(h1.group(1)) if h1 else path.stem)
    description=_scalar(fm.get('description'))
    paragraphs=[p for p in re.split(r'\n\s*\n',body) if p.strip() and not p.lstrip().startswith(('#','```','~~~'))]
    excerpt=_plain(description or (paragraphs[0] if paragraphs else ''))[:excerpt_length].rstrip()
    return ParsedPage(rel,fm,body,title,_list(fm.get('tags')),_list(fm.get('aliases')),excerpt)

def node_kwargs(p:ParsedPage):
    f=p.frontmatter
    typ=(_scalar(f.get('type')) or '').lower() or None
    if typ not in VALID_TYPES: typ=None
    norm=lambda k: (_scalar(f.get(k)) or '').lower() or None
    created=next((_iso(f.get(k)) for k in ('created','started','captured','ingested') if f.get(k) is not None),None)
    return dict(id=p.node_id,title=p.title,path=p.node_id,folder=Path(p.node_id).parent.as_posix() if '/' in p.node_id else '',
      tags=p.tags,aliases=p.aliases,excerpt=p.excerpt,type=typ,status=norm('status'),confidence=norm('confidence'),
      classification=norm('classification'),knowledgeStatus=norm('knowledge_status'),reviewNeeded=(f.get('review_needed') is True),
      owner=_scalar(f.get('owner')),author=_scalar(f.get('author')),sourceKind=norm('source_kind'),createdAt=created,
      updatedAt=_iso(f.get('updated')),decisionDate=_iso(f.get('decision_date')),reviewDate=_iso(f.get('review_date')),
      completedAt=_iso(f.get('completed')))
