import traceback, sys, time, signal, importlib, yaml
from pythreader import Task, TaskQueue, Primitive, synchronized

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
        Logged.__init__(self, f"[app {self.Name}]", logger, debug=True)
        self.Prefix = config.get("prefix", "/")
        self.ReplacePrefix = config.get("replace_prefix")
        self.Timeout = config.get("timeout", 10)
        max_workers = config.get("max_workers", 5)
        queue_capacity = config.get("queue_capacity", 10)
        self.loadApp(self.Config)
        self.RequestQueue = TaskQueue(max_workers, capacity = queue_capacity)
        
    def loadApp(self, config):
        args = None
        fname = config["file"]
        g = {}
        exec(open(fname, "r").read(), g)
        if "create" in config:
            args = config.get("args")
            app = g[config["create"]](args)
        else:
            app = g[config.get("application", "application")]
        self.AppArgs = args
        self.WSGIApp = app
        return app
        
    def accept(self, request):
        header = request.HTTPHeader
        uri = header.URI
        self.debug("accept: uri:", uri, " prefix:", self.Prefix)
        if uri.startswith(self.Prefix):
            uri = uri[len(self.Prefix):]
            if not uri.startswith("/"):     uri = "/" + uri
            if self.ReplacePrefix:
                uri = self.ReplacePrefix + uri
            header.replaceURI(uri)
            request.AppName = self.Name
            self.RequestQueue.addTask(RequestTask(self.WSGIApp, request, self.Logger))
            return True
        else:
            return False
            
class MultiServer(Primitive, Logged):
            
    def __init__(self, config, logger=None):
        Primitive.__init__(self)
        Logged.__init__(self, "[Multiserver]", logger, debug=True)
        self.Config = config
        self.Servers = []
        self.ServersByPort = {}
        self.reconfigure(config)
        self.debug("debug is enabled")
    
    def reconfigure(self, config):
        new_servers = config["servers"]
        new_ports = {cfg["port"] for cfg in new_servers}
        to_stop = []
        
        for p, s in list(self.ServersByPort.items()):
            if not p in new_ports:
                to_stop.append(s)
        
        new_lst = []
        for cfg in new_servers:
            port = cfg["port"]
            apps = [QueuedApplication(app_cfg, self.Logger) for app_cfg in cfg["apps"]]
            app_list = ",".join(a.Name for a in apps)
            srv = self.ServersByPort.get(port)
            if srv is None:
                srv = HTTPServer.from_config(cfg, apps, logger=self.Logger)
                srv.start()
                self.log(f"server {srv.Port} started with apps: {app_list}")
            else:
                srv.reconfigureApps(apps)
                self.log(f"server {srv.Port} reconfigured with apps: {app_list}")
            new_lst.append(srv)
        
        self.Servers = new_lst
        self.ServersByPort = {srv.Port:srv for srv in self.Servers}

        for s in to_stop:
            s.stop()
            self.log(f"server {s.Port} stopped")
            
        self.debug("reconfigured")
        
    def join(self):
        while self.Servers:
            for s in self.Servers:
                s.join()
