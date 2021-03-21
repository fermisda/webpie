import traceback, sys, time, signal, importlib, yaml
from pythreader import Task, TaskQueue

from .py3 import PY2, PY3, to_str, to_bytes
from .HTTPServer import HTTPServer, RequestProcessor
from .logs import Logged, Logger

class RequestTask(RequestProcessor, Task):
    
    def __init__(self, wsgi_app, request, logger):
        #print("RequestTask.__init__: args:", wsgi_app, request, logger)
        Task.__init__(self, name=f"[RequestTask {request.Id}]")
        RequestProcessor.__init__(self, wsgi_app, request, logger)

class QueuedApplication(Logged):
    
    def __init__(self, config, logger=None):
        
        self.Config = config
        self.Name = config["name"]
        Logged.__init__(self, f"[app {self.Name}]", logger)
        self.Prefix = config["prefix"]
        self.ReplacePrefix = config.get("replace_prefix")
        self.ModuleName = config["module"]
        self.Env = env = {}
        env.update(config.get("env", {}))
        self.Module = module = importlib.import_module(self.ModuleName)
        self.WSGIApp = app = getattr(module, "create_application")(env)
        self.Timeout = config.get("timeout", 10)
        max_workers = config.get("max_workers", 5)
        queue_capacity = config.get("queue_capacity", 10)
        self.RequestQueue = TaskQueue(max_workers, capacity = queue_capacity)
        
    def reload(self):
        importlib.reload(self.Module)
        self.WSGIApp = getattr(self.Module, "create_application")(self.Env)
        
    def accept(self, request):
        header = request.HTTPHeader
        uri = header.URI
        if uri.startswith(self.Prefix):
            uri = uri[len(self.Prefix):]
            if not uri.startswith("/"):     uri = "/" + uri
            if self.ReplacePrefix:
                uri = self.ReplacePrefix + uri
            header.replaceURI(uri)
            self.RequestQueue.addTask(RequestTask(self.WSGIApp, request, self.Logger))
            return True
        else:
            return False

class MultiServer(Logged):
            
    def __init__(self, config, logger=None):
        if logger is None:
            if "logger" in config:
                cfg = config["logger"]
                if cfg.get("enabled", True):
                    logger = Logger(cfg.get("file","-"))
        Logged.__init__(self, "[Multiserver]", logger)
        self.Config = config
        sys.path += config.get("paths", [])
        self.Servers = []
        for cfg in config["servers"]:
            port = cfg["port"]
            apps = [QueuedApplication(app_cfg, logger) for app_cfg in cfg["apps"]]
            self.Servers.append(HTTPServer(port, apps, config=cfg, logger=logger))
        
    def reload(self):
        for s in self.Servers:
            s.reload()
            
    def run(self):
        for s in self.Servers:
            s.start()
        for s in self.Servers:
            s.join()
