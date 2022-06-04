import traceback, sys, time, signal, importlib, yaml, os, os.path, datetime
from pythreader import Task, TaskQueue, Primitive, synchronized, PyThread, LogFile
from webpie import Logged, Logger, HTTPServer, RequestProcessor, yaml_expand as expand, init_uid
from multiprocessing import Process, Pipe

import re, socket

setproctitle = None

try:    from setproctitle import setproctitle
except: pass


RequestTask = RequestProcessor

#class RequestTask(RequestProcessor, Task):
#    
#    def __init__(self, wsgi_app, request, logger):
#        #print("RequestTask.__init__: args:", wsgi_app, request, logger)
#        Task.__init__(self, name=f"[RequestTask {request.Id}]")
#        RequestProcessor.__init__(self, wsgi_app, request, logger)

class Service(Primitive, Logged):
    
    def __init__(self, config, logger=None):
        name = config["name"]
        #print("Service(): config:", config)
        self.ServiceName = name
        Primitive.__init__(self, name=f"[service {name}]")        
        Logged.__init__(self, f"[app {name}]", logger, debug=True)
        self.Config = None
        self.Initialized = self.initialize(config)

    @synchronized
    def initialize(self, config=None):
        config = config or self.Config
        self.Config = config

        reload_files = config.get("touch_reload", [])
        if isinstance(reload_files, str):
            reload_files = [reload_files]

        self.ReloadFileTimestamps = {path: self.mtime(path) for path in reload_files}

        self.Prefix = config.get("prefix", "/")
        self.ReplacePrefix = config.get("replace_prefix")
        self.Timeout = config.get("timeout", 10)

        saved_path = sys.path[:]
        saved_modules = set(sys.modules.keys())
        saved_environ = os.environ.copy()
        try:
            args = None
            if "file" in config:
                print('*** Use of "file" parameter is deprecated. Use "module" instead')
            self.ScriptFileName = fname = config.get("module", config.get("file"))
            g = {}

            extra_path = config.get("python_path")
            if extra_path is not None:
                if isinstance(extra_path, str):
                    extra_path = [extra_path]
                sys.path = extra_path + sys.path

            if "env" in config:
                os.environ.update(config["env"])
                
            try:    exec(open(fname, "r").read(), g)
            except:
                tb = traceback.format_exc()
                self.log_error(f"Error importing module {fname}:\n{tb}")
                return False
                
            if "create" in config:
                # deprecated
                print('*** Use of "create" parameter is deprecated. Use "application: function()" instead')
                application = config["create"] + "()"
            else:
                application = config.get("application", "application")
            if application.endswith("()"):
                args = config.get("args")
                fcn_name = application[:-2]
                fcn = g.get(fcn_name)
                if fcn is None:
                    self.log_error(f"Application creation function {fcn_name} not found in module {fname}")
                    return False
                
                try:    
                    if isinstance(args, dict):
                        app = fcn(**args)
                    elif isinstance(args, (list, tuple)):
                        app = fcn(*args)
                    elif args is None:
                        app = fcn()
                    else:
                        app = fcn(args)
                except:
                    tb = traceback.format_exc()
                    self.log_error(f"Error calling the application initialization function:\n{tb}")
                    return False
                    
                if app is None:
                    self.log_error(f'Application creation function {fcn_name} returned None')
                    return False

            else:
                app = g.get(application)
                if app is None:
                    self.log_error(f'Application object "{application}" not found in {fname}')
                    return False
                    
            
            self.AppArgs = args
            self.WSGIApp = app

            max_workers = config.get("max_workers", 5)
            queue_capacity = config.get("queue_capacity", 10)
            self.RequestQueue = TaskQueue(max_workers, capacity = queue_capacity,
                delegate=self)
            self.log("initiaized")
            
        except:
            tb = traceback.format_exc()
            self.log_error(f"Error initializing application:\n{tb}")
            return False
            

        finally:
            sys.path = saved_path
            extra_modules = set(sys.modules.keys()) - set(saved_modules)
            #print("loadApp: removing modules:", sorted(list(extra_modules)))
            for m in extra_modules:
                del sys.modules[m]
            for n in set(os.environ.keys()) - set(saved_environ.keys()):
                del os.environ[n]
            os.environ.update(saved_environ)
            
        return True
            
    def taskFailed(self, queue, task, exc_type, exc_value, tb):
        self.log_error("request failed:", "".join(traceback.format_exception(exc_type, exc_value, tb)))
        try:
            task.Request.close()
        except:
            pass

    def accept(self, request):
        #print(f"Service {self}: accept()")
        if not self.Initialized:
            return False
        header = request.HTTPHeader
        uri = header.URI
        self.debug("accept: uri:", uri, " prefix:", self.Prefix)
        #print("Sevice", self,"   accept: uri:", uri, " prefix:", self.Prefix)
        if uri.startswith(self.Prefix):
            uri = uri[len(self.Prefix):]
            if not uri.startswith("/"):     uri = "/" + uri
            if self.ReplacePrefix:
                uri = self.ReplacePrefix + uri
            header.replaceURI(uri)
            request.AppName = self.ServiceName
            script_path = self.Prefix
            while script_path and script_path.endswith("/"):
                script_path = script_path[:-1]
            request.Environ["SCRIPT_NAME"] = script_path
            request.Environ["SCRIPT_FILENAME"] = self.ScriptFileName
            self.RequestQueue.addTask(RequestTask(self.WSGIApp, request, self.Logger))
            #print("Service", self, "   accepted")
            return True
        else:
            #print("Service", self, "   rejected")
            return False
    
    def close(self):
        self.RequestQueue.hold()
    
    def join(self):
        self.RequestQueue.join()
            
    def mtime(self, path):
        try:    return os.path.getmtime(path)
        except: return None

    def reloadIfNeeded(self):
        for path, old_timestamp in self.ReloadFileTimestamps.items():
            mt = self.mtime(path)
            if mt is not None and mt != old_timestamp:
                ct = time.ctime(mt)
                self.log(f"file {path} was modified at {ct}")
                break
        else:
            return False
        self.Initialized = self.initialize()

class MPLogger(PyThread):
    
    def __init__(self, logger, queue_size=-1, debug=False, name=None):
        import multiprocessing
        PyThread.__init__(self, name=name, daemon=True)
        self.Logger = logger
        self.Queue = multiprocessing.Queue(queue_size)
        self.Debug = debug

    def run(self):
        #
        # master side
        #
        from queue import Empty
        while True:
            msg = self.Queue.get()
            who, t = msg[:2]
            parts = [str(p) for p in msg[2:]]
            t = datetime.datetime.fromtimestamp(t)
            process_timestamp = t.strftime("%m/%d/%Y %H:%M:%S") + ".%03d" % (t.microsecond//1000)
            self.Logger.log(who, "%s: %s" % (process_timestamp, " ".join(parts)))
    
    def log(self, who, *parts):
        #
        # subprocess side
        #
        parts = tuple(str(p) for p in parts)
        self.Queue.put((who, time.time())+parts)
            
    def debug(self, who, *parts):
        #
        # subprocess side
        #
        if self.Debug:
            self.log(f"{who} [DEBUG]", *parts)

    def error(self, who, *parts):
        #
        # subprocess side
        #
        self.log(f"{who} [ERROR]", *parts)

class MultiServerSubprocess(Process):
    
    def __init__(self, port, sock, config_file, logger=None):
        Process.__init__(self, daemon=True)
        #print("MultiServerSubprocess.__init__: logger:", logger)
        self.Sock = sock
        self.Logger = logger
        self.Port = port
        self.Server = None
        self.ConnectionToMaster, self.ConnectionToSubprocess = Pipe()
        self.ConfigFile = config_file   # path
        self.ReconfiguredTime = 0
        self.Services = []
        self.MasterSide = True
        self.Stop = False
        self.MasterPID = os.getpid()
        
    def log(self, *parts):
        mypid=os.getpid()
        self.Logger.log(f"[Subprocess {mypid}]", *parts)

    def reconfigure(self):
        #print("MultiServerSubprocess.reconfigure()...")
        self.ReconfiguredTime = os.path.getmtime(self.ConfigFile)
        self.Config = config = expand(yaml.load(open(self.ConfigFile, 'r'), Loader=yaml.SafeLoader))
        
        templates = config.get("templates", {})
        services = config.get("services", [])
        
        service_list = []
        assert isinstance(services, list)
        for svc_cfg in services:
            #print("svc_cfg:", svc_cfg)
            svc = None
            if "template" in svc_cfg:
                template = templates.get(svc_cfg.get("template", "*"))
                if template is not None:
                    c = {}
                    c.update(template)
                    c.update(svc_cfg)
                    svc_cfg = expand(c)
                names = svc_cfg.get("names", [svc_cfg.get("name")])
                for name in names:
                    c = svc_cfg.copy()
                    c["name"] = name
                    svc = Service(expand(c), self.Logger)
                    if svc.Initialized:
                        service_list.append(svc)
                        #print("Service", svc, "created and added to the list")
                    else:
                        self.log(f'service "{svc.ServiceName}" failed to initialize - removing from service list')
            else:
                #print("MultiServerSubprocess.reconfigure: svc_cfg:", svc_cfg)
                #print("MultiServerSubprocess.reconfigure: expanded:", expand(svc_cfg))
                svc = Service(expand(svc_cfg), self.Logger)
                if not svc.Initialized:
                    #print("service not initialzed")
                    self.log(f'service "{svc.ServiceName}" failed to initialize - removing from service list')
                else:
                    service_list.append(svc)
                    #print("Service", svc, "created and added to the list")
            #print("--------")
        names = ",".join(s.Name for s in service_list)
        if self.Server is None:
            self.Server = HTTPServer.from_config(self.Config, service_list, logger=self.Logger)
            self.log(f"server created with services: {names}")
        else:
            self.Server.setServices(service_list)
            self.log(f"server reconfigured with services: {names}")
        self.Services = service_list
        self.log("reconfigured")
        #print("MultiServerSubprocess.reconfigure() done")

    CheckConfigInterval = 5.0
        
    def run(self):
        init_uid(tag="%03d" % (os.getpid() % 1000,))
        #print("MultiServerSubprocess.run()...")
        if setproctitle is not None:
            setproctitle("multiserver %s worker" % (self.Port,))
        pid = os.getpid()
        self.LogName = f"MultiServerSubprocess({pid})"
        self.reconfigure()
        self.MasterSide = False
        self.Sock.settimeout(5.0)
        last_check_config = 0
        
        while not self.Stop:
            
            # see if the parent process is still alive
            try:    os.kill(self.MasterPID, 0)
            except:
                print("master process died")
                break

            try:    csock, caddr = self.Sock.accept()
            except socket.timeout:
                pass
            else:
                #print("run(): services:", [str(s) for s in self.Services])
                self.Server.connection_accepted(csock, caddr)
            
            if self.ConnectionToMaster.poll(0):
                msg = self.ConnectionToMaster.recv()
                self.log("message from master:", msg)
                if msg == "stop":
                    self.Stop = True
                elif msg == "reconfigure":
                    self.reconfigure()

            if not self.Stop and time.time() > last_check_config + self.CheckConfigInterval:
                if os.path.getmtime(self.ConfigFile) > self.ReconfiguredTime:
                    self.reconfigure()
                else:
                    for svc in self.Services:
                        if isinstance(svc, Service):
                            svc.reloadIfNeeded()
            last_check_config = time.time()
            
        self.Server.close()
        self.Server.join()
        for svc in self.Services:
            svc.close()
            svc.join()
        
    def stop(self):
        if self.MasterSide:
            self.ConnectionToSubprocess.send("stop")
        else:
            self.Stop = True
            
    def request_reconfigure(self):
        self.ConnectionToSubprocess.send("reconfigure")
            
class MPMultiServer(PyThread, Logged):
            
    def __init__(self, config_file, logger=None, debug=False):
        PyThread.__init__(self)
        Logged.__init__(self, "[Multiserver]", logger, debug=debug)
        self.ConfigFile = config_file
        self.Server = None
        self.Port = None
        self.ReconfiguredTime = 0
        self.Subprocesses = []
        self.Sock = None
        self.Stop = False
        self.MPLogger = None
        if logger is not None:
            self.MPLogger = MPLogger(logger, debug=debug)
            self.MPLogger.start()
        self.Debug = debug
        self.reconfigure()

    @synchronized
    def reconfigure(self, *ignore):
        self.ReconfiguredTime = os.path.getmtime(self.ConfigFile)
        self.Config = config = expand(yaml.load(open(self.ConfigFile, 'r'), Loader=yaml.SafeLoader))

        port = self.Config["port"]
        if self.Port is None:
            self.Port = port
            self.Sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.Sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.Sock.bind(('', self.Port))
            self.Sock.listen(10)
        elif port != self.Port:
            print("Can not change port number")
            sys.exit(1)
        
        new_nprocesses = self.Config.get("processes", 1)
        if new_nprocesses > len(self.Subprocesses):
            for p in self.Subprocesses:
                p.request_reconfigure()
            for _ in range(new_nprocesses - len(self.Subprocesses)):
                p = MultiServerSubprocess(self.Port, self.Sock, self.ConfigFile, logger=self.MPLogger)
                p.start()
                self.Subprocesses.append(p)
                #self.log("started new subprocess")
        elif new_nprocesses < len(self.Subprocesses):
            while new_nprocesses < len(self.Subprocesses):
                p = self.Subprocesses.pop()
                p.stop()
                #self.log("stopped a subprocess")
            for p in self.Subprocesses:
                p.request_reconfigure()
        else:
            for p in self.Subprocesses:
                p.request_reconfigure()
        #self.log("subprocesses running now:", len(self.Subprocesses))
        
    def run(self):
        if setproctitle is not None:
            setproctitle("multiserver %s master" % (self.Port,))
        while not self.Stop:
            time.sleep(5)
            if os.path.getmtime(self.ConfigFile) > self.ReconfiguredTime:
                self.reconfigure()
            self.check_children()
                
    @synchronized
    def check_children(self, *ignore):
        #print("child died")
        n_died = 0
        alive = []
        for p in self.Subprocesses:
            if not p.is_alive():
                print("subprocess died with status", p.exitcode, file=sys.stderr)
                self.log("subprocess died with status", p.exitcode)
                n_died += 1
            else:
                alive.append(p)
        self.Subprocesses = alive
        if n_died and not self.Stop:
            #time.sleep(5)   # do not restart subprocesses too often
            for _ in range(n_died):
                time.sleep(1)   # do not restart subprocesses too often
                p = MultiServerSubprocess(self.Port, self.Sock, self.ConfigFile, logger=self.MPLogger)
                p.start()
                self.Subprocesses.append(p)
                print("subprocess died with status", p.exitcode, file=sys.stderr)
                self.log("started new subprocess")
                
    @synchronized
    def killme(self, *ignore):
        self.log("INT signal received. Stopping subprocesses...")
        self.Stop = True
        for p in self.Subprocesses:
            p.stop()
        
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
    ms = MPMultiServer(config_file, logger, debug)
    signal.signal(signal.SIGHUP, ms.reconfigure)
    #signal.signal(signal.SIGCHLD, ms.child_died)
    signal.signal(signal.SIGINT, ms.killme)
    ms.start()
    ms.join()

if __name__ == "__main__":
    main()
