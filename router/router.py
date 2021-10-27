from webpie import Logged, Logger, yaml_expand as expand
from pythreader import PyThread, synchronized
import os, yaml, sys, time

def mtime(path):
    try:    return os.path.getmtime(path)
    except: return None


class App(Logged, PyThread):
    
    def __init__(self, config, logger=None):
        name = config["name"]
        self.AppName = name
        PyThread.__init__(self, name=f"[app {name}]", daemon=True)
        Logged.__init__(self, f"[app {name}]", logger, debug=True)
        self.Config = None
        self.configure(config)
        self.Stop = False
        
    def stop(self):
        self.Stop = True

    @synchronized
    def configure(self, config=None):
        config = config or self.Config
        self.Config = config

        reload_files = config.get("touch_reload", [])
        if isinstance(reload_files, str):
            reload_files = [reload_files]

        self.ReloadFileTimestamps = {path: mtime(path) for path in reload_files}

        self.Prefix = config.get("prefix", "/")
        self.ReplacePrefix = config.get("replace_prefix")
        self.Timeout = config.get("timeout", 10)

        saved_path = sys.path[:]
        saved_modules = set(sys.modules.keys())
        saved_environ = os.environ.copy()
        try:
            args = None
            fname = config["file"]
            g = {}

            extra_path = config.get("python_path")
            if extra_path is not None:
                if isinstance(extra_path, str):
                    extra_path = [extra_path]
                sys.path = extra_path + sys.path

            if "env" in config:
                os.environ.update(config["env"])
                
            exec(open(fname, "r").read(), g)
            if "create" in config:
                args = config.get("args")
                app = g[config["create"]](args)
            else:
                app = g[config.get("application", "application")]
            self.AppArgs = args
            self.WSGIApp = app

            self.log(f"configured at {self.Prefix}")

        finally:
            sys.path = saved_path
            extra_modules = set(sys.modules.keys()) - set(saved_modules)
            #print("loadApp: removing modules:", sorted(list(extra_modules)))
            for m in extra_modules:
                del sys.modules[m]
            for n in set(os.environ.keys()) - set(saved_environ.keys()):
                del os.environ[n]
            os.environ.update(saved_environ)
            self.NeedReconfigure = False
    
    def reloadIfNeeded(self):
        for path, old_timestamp in self.ReloadFileTimestamps.items():
            mt = mtime(path)
            if mt is not None and mt != old_timestamp:
                ct = time.ctime(mt)
                self.log(f"file {path} was modified at {ct}. reconfiguring")
                break
        else:
            return False
        self.configure()
        return True
    
    @synchronized
    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        assert path.startswith(self.Prefix)
        new_path = (self.ReplacePrefix or "") + path[len(self.Prefix):]
        self.log(f"path: {path} -> {new_path}")
        environ["PATH_INFO"] = new_path
        environ["WebPie.original_path"] = path
        return self.WSGIApp(environ, start_response)
        
    def run(self):
        while not self.Stop:
            time.sleep(5)
            self.reloadIfNeeded()
    

class Router(PyThread, Logged):
    
    def __init__(self, config_file):
        self.ConfigFile = config_file
        self.Config = config = expand(yaml.load(open(self.ConfigFile, 'r'), Loader=yaml.SafeLoader))
        #self.Config = config = yaml.load(open(self.ConfigFile, 'r'), Loader=yaml.SafeLoader)
        log_file = config.get("log", "-")
        self.Logger = Logger(log_file)
        Logged.__init__(self, "[router]", self.Logger)
        PyThread.__init__(self, name="[router]", daemon=True)
        self.ConfigMTime = mtime(self.ConfigFile)
        self.Apps = None
        self.configure(config)
        self.Stop = False
        
    def configure(self, config):
        self.Apps = []
        self.Templates = config.get("templates", {})
        for appcfg in config.get("apps", []):
            if "template" in appcfg:
                templ = self.Templates[appcfg["template"]]
                if "name" in appcfg:
                    names = [appcfg["name"]]
                else:
                    names = appcfg.get("names", [])
                if not names:
                    print("Warning: application without a name in the configuration.")
                    names = ["(unnamed)"]
                for name in names:
                    cfg = templ.copy()
                    cfg["name"] = name
                    cfg = expand(cfg)
                    self.Apps.append(App(cfg, self.Logger))
            else:
                self.Apps.append(App(appcfg, self.Logger))
        for app in self.Apps:
            if isinstance(app, PyThread):   app.start()
        
    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO')
        if not path:
            start_response("403 Empty path", [])
            return []
        
        for app in self.Apps:
            if path.startswith(app.Prefix):
                self.log(f"{path} -> {app.AppName}")
                return app(environ, start_response)
        else:
            start_response("403 Application not found", [])
            return []
            
    def run(self):
        self.log("thread started")
        while not self.Stop:
            time.sleep(5)
            mt = mtime(self.ConfigFile)
            if mt is not None and mt > self.ConfigMTime:
                self.log("config file modified. reloading.")
                self.ConfigMTime = mt
                self.Config = expand(yaml.load(open(self.ConfigFile, 'r'), Loader=yaml.SafeLoader))
                for app in self.Apps:
                    app.stop()
                self.configure(self.Config)
        self.log("thread ended")
    
            
def create_application(config_file=None):
    config_file = config_file or os.environ.get("WSGI_ROUTER_CFG")
    router = Router(config_file)
    if isinstance(router, PyThread):
        router.start()
    return router
    

def main():
    import getopt
    from webpie import HTTPServer
    
    Usage = "python router.py [-p <port>] <config.yaml>"
    
    if not sys.argv[1:] or sys.argv[1] in ("-h", "--help", "-?"):
        print(Usage)
        sys.exit(2)
    
    opts, args = getopt.getopt(sys.argv[1:], "p:")
    opts = dict(opts)
    if not args:
        print(Usage)
        sys.exit(2)
        
    config_file = args[0]
    port = opts.get("-p")
    if not port:
        config = yaml.load(open(config_file, 'r'), Loader=yaml.SafeLoader)
        port = config.get("port")
    
    if not port:
        print(Usage)
        sys.exit(2)

    port = int(port)
    HTTPServer(port, create_application(config_file)).run()
    
    
if __name__ == "__main__":
    main()
else:
    # uwsgi or similar
    try:
        application = create_application()
    except:
        application = None
    
    

            
            
        
                
        
