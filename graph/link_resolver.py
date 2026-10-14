from collections import defaultdict
from pathlib import PurePosixPath
import posixpath, urllib.parse

def key(s): return s.strip().replace('\\','/').casefold()
class Resolver:
    def __init__(self,pages):
        self.ids={key(p.node_id):p.node_id for p in pages}; self.noext={key(p.node_id[:-3]):p.node_id for p in pages}
        self.title=defaultdict(list); self.alias=defaultdict(list); self.stem=defaultdict(list)
        for p in pages:
            self.title[key(p.title)].append(p.node_id); self.stem[key(PurePosixPath(p.node_id).stem)].append(p.node_id)
            for a in p.aliases:self.alias[key(a)].append(p.node_id)
    def resolve(self,source,target):
        t=urllib.parse.unquote(target.strip()).replace('\\','/'); low=key(t)
        if low.startswith(('../raw/','raw/','/raw/')): return None,'target-outside-wiki'
        candidates=[low, key(t+'.md') if not low.endswith('.md') else low]
        for c in candidates:
            if c in self.ids:return self.ids[c],None
            if c in self.noext:return self.noext[c],None
        rel=posixpath.normpath(posixpath.join(posixpath.dirname(source),t))
        for c in (key(rel),key(rel+'.md')):
            if c in self.ids:return self.ids[c],None
            if c in self.noext:return self.noext[c],None
        for index in (self.title,self.alias,self.stem):
            vals=index.get(key(PurePosixPath(t).stem if index is self.stem else t),[])
            if len(vals)==1:return vals[0],None
            if len(vals)>1:return None,'ambiguous-target'
        return None,'target-not-found'
