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
    
    def __init__(self, name, config, logger=None):
        
        self.Name = name
        Logged.__init__(self, f"[app {self.Name}]", logger)
        self.Prefix = config["prefix"]
        self.ReplacePrefix = config.get("replace_prefix")
        self.Timeout = config.get("timeout", 10)
        self.AppName = app_name = config.get("application", "application")
        self.ModuleName = config["module"]
        self.Module = module = importlib.import_module(self.ModuleName)
        self.WSGIApp = app = getattr(module, app_name)
        self.Config = config
        for name, value in config.get("env", {}).items():
            app.set_environ(name, value)
        max_workers = config.get("max_workers", 5)
        queue_capacity = config.get("queue_capacity", 10)
        self.RequestQueue = TaskQueue(max_workers, capacity = queue_capacity)
        
    def reload(self):
        module = self.Module = importlib.reload(self.Module)
        self.WSGIApp = getattr(module, self.AppName)
        
    def accept(self, request):
        header = request.HTTPHeader
        uri = header.URI
        if uri.startswith(self.Prefix):
            if self.ReplacePrefix:
                uri = self.ReplacePrefix + uri[len(self.Prefix):]
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
        sys.path += config.get("paths", [])
        self.Apps = {aname:QueuedApplication(aname, cfg, logger) for aname, cfg in config["apps"].items()}
        self.Servers = [HTTPServer(cfg["port"], self.Apps, config=cfg, logger=logger) for cfg in config["servers"]]
        self.Config = config
        
    def reload(self):
        for aname, app in self.Apps.items():
            app.reload()
            self.log(f"app {aname} reloaded")
            
    def run(self):
        for s in self.Servers:
            s.start()
        for s in self.Servers:
            s.join()
