import traceback, sys, time, signal, importlib, yaml, os, os.path
from pythreader import Task, TaskQueue, Primitive, synchronized, PyThread
from webpie import Logged, Logger, HTTPServer, RequestProcessor
from multiprocessing import Process

import re

subst = re.compile("(%\((\w+)\))")

def expand_str(text, vars):
    out = []
    i0 = 0
    for m in subst.finditer(text):
        name = m.group(2)
        i1 = m.end(1)
        if name in vars:
            out.append(text[i0:m.start(1)])
            out.append(str(vars[name]))
        else:
            out.append(text[i0:i1])
        i0 = i1
    out.append(text[i0:])
    return "".join(out)


def expand(item, vars={}):
    if isinstance(item, str):
        item = expand_str(item, vars)
    elif isinstance(item, dict):
        new_vars = {}
        new_vars.update(vars)

        # substitute top level strings only
        out = {k:expand_str(v, vars) for k, v in item.items() if isinstance(v, str)}

        # use this as the substitution dictionary
        new_vars.update(out)    
        out.update({k:expand(v, new_vars) for k, v in item.items()})
        item = out
    elif isinstance(item, list):
        item = [expand(x, vars) for x in item]
    return item
            
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
        saved_path = sys.path[:]
        try:
            args = None
            fname = config["file"]
            g = {}
            extra_path = config.get("python_path")
            if extra_path is not None:
                if isinstance(extra_path, str):
                    extra_path = [extra_path]
                sys.path = extra_path + sys.path
            exec(open(fname, "r").read(), g)
            if "create" in config:
                args = config.get("args")
                app = g[config["create"]](args)
            else:
                app = g[config.get("application", "application")]
            self.AppArgs = args
            self.WSGIApp = app
            return app
        finally:
            sys.path = saved_path
        
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
            
class MultiServer(PyThread, Logged):
            
    def __init__(self, config_file, logger=None):
        PyThread.__init__(self)
        Logged.__init__(self, "[Multiserver]", logger, debug=True)
        self.ConfigFile = config_file
        self.Servers = []
        self.ServersByPort = {}
        self.ReconfiguredTime = 0
        self.reconfigure()
        self.debug("debug is enabled")
    
    def reconfigure(self):
        self.ReconfiguredTime = os.path.getmtime(self.ConfigFile)
        self.Config = config = expand(yaml.load(open(self.ConfigFile, 'r'), Loader=yaml.SafeLoader))
        templates = config.get("templates", {})
        new_servers = config["servers"]
        new_ports = {cfg["port"] for cfg in new_servers}
        to_stop = []
        
        for p, s in list(self.ServersByPort.items()):
            if not p in new_ports:
                to_stop.append(s)
        
        new_lst = []
        for cfg in new_servers:
            port = cfg["port"]
            apps = []
            for app_cfg in cfg["apps"]:
                template = templates.get(app_cfg.get("template", "*"))
                if template is not None:
                    c = {}
                    c.update(template)
                    c.update(app_cfg)
                    app_cfg = expand(c)
                #print("reconfigure: app_cfg:", app_cfg)
                apps.append(QueuedApplication(app_cfg, self.Logger))
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
        
    def run(self):
        while True:
            time.sleep(5)
            if os.path.getmtime(self.ConfigFile) > self.ReconfiguredTime:
                self.reconfigure()
                
    def ___join(self):
        while self.Servers:
            for s in self.Servers:
                s.join()

Usage = """
multiserver <config.yaml>
"""

class   SignalHandler:

    def __init__(self, signum, receiver):
        self.Receiver = receiver
        signal.signal(signum, self)
        
    def __call__(self, signo, frame):
        try:    
            self.Receiver.reconfigure()
        except: 
            import traceback
            traceback.print_exc()
            
def main():
    if not sys.argv[1:] or sys.argv[1] in ("-?", "-h", "--help", "help"):
        print(Usage)
        sys.exit(2)
    config_file = sys.argv[1]
    config = expand(yaml.load(open(config_file, 'r'), Loader=yaml.SafeLoader))
    logger = None
    if "logger" in config:
        cfg = config["logger"]
        debug = cfg.get("debug", False)
        if cfg.get("enabled", True):
            logger = Logger(cfg.get("file", "-"), debug=debug)
    if "pid_file" in config:
        open(config["pid_file"], "w").write(str(os.getpid()))
    ms = MultiServer(config_file, logger)
    s = SignalHandler(signal.SIGHUP, ms)
    ms.start()
    ms.join()

if __name__ == "__main__":
    main()