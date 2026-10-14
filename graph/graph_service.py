from threading import RLock
import json, os, tempfile
from .graph_builder import build_graph
class GraphService:
    def __init__(self,settings):self.settings=settings;self._graph=None;self._lock=RLock()
    def build_graph(self):
        with self._lock:
            graph=build_graph(self.settings); self._graph=graph
            if self.settings.graph_write_snapshot:self._write(graph)
            return graph
    def get_graph(self,force_refresh=False):
        if force_refresh or self._graph is None or not self.settings.graph_cache_enabled:return self.build_graph()
        return self._graph
    def invalidate(self):
        with self._lock:self._graph=None
    def _write(self,graph):
        out=self.settings.graph_output_path;out.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix=out.name+'.',suffix='.tmp',dir=out.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(graph.model_dump(mode='json',exclude_none=True),f,ensure_ascii=False,sort_keys=True,separators=(',',':'))
            os.replace(tmp,out)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
