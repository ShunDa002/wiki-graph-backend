from dataclasses import dataclass
import re
from .models import LinkType

WIKI_RE=re.compile(r'(!?)\[\[([^\]|#]+)(?:#([^\]|]+))?(?:\|([^\]]+))?\]\]')
MD_RE=re.compile(r'(?<!!)\[([^\]]+)\]\(([^)\s]+)(?:\s+["\'][^"\']*["\'])?\)')
FRONTMATTER_FIELDS={'sources':'sources','project':'project','knowledge_basis':'knowledge-basis','validated_by':'validated-by','tests_decision':'tests-decision','informed_by':'informed-by','based_on':'based-on','raw_file':'raw-file'}
@dataclass(frozen=True)
class RawLink:
    target:str; type:LinkType; label:str|None=None; heading:str|None=None; source_heading:str|None=None

def extract_body_links(body):
    links=[]; current=None
    for line in body.splitlines():
        hm=re.match(r'^#{1,6}\s+(.+?)\s*$',line)
        if hm: current=hm.group(1).strip()
        spans=[]
        for m in WIKI_RE.finditer(line):
            links.append(RawLink(m.group(2).strip(),'embed' if m.group(1) else 'wikilink',m.group(4),m.group(3),current)); spans.append(m.span())
        clean=''.join(' ' if any(a<=i<b for a,b in spans) else c for i,c in enumerate(line))
        for m in MD_RE.finditer(clean):
            target=m.group(2)
            if re.match(r'^(?:https?://|mailto:|#)',target,re.I): continue
            base,_,frag=target.partition('#')
            if base.lower().endswith('.md'):
                links.append(RawLink(base,'markdown-link',m.group(1),frag or None,current))
    return links

def extract_frontmatter_links(fm, fields=FRONTMATTER_FIELDS):
    out=[]
    for field,label in fields.items():
        val=fm.get(field); vals=val if isinstance(val,list) else [val]
        for item in vals:
            if not isinstance(item,str): continue
            for m in WIKI_RE.finditer(item): out.append(RawLink(m.group(2).strip(),'frontmatter-link',label,m.group(3),None))
    return out
