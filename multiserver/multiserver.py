import traceback, sys, time, signal, importlib, yaml, os, os.path, datetime, threading, pprint
from pythreader import Task, TaskQueue, Primitive, synchronized, PyThread, LogFile
from webpie import HTTPServer, RequestProcessor, yaml_expand as expand, init_uid
from multiprocessing import Process, Pipe
from webpie.logs import Logger, Logged

import re, socket

def to_bytes(s):    
    return s if isinstance(s, bytes) else s.encode("utf-8")

def to_str(b):    
    return b if isinstance(b, str) else b.decode("utf-8", "ignore")


setproctitle = None

try:    from setproctitle import setproctitle
except: pass

def services_from_config(config):
    templates = config.get("templates", {})
    defaults = config.get("defaults", {})
    services = config.get("services", [])
    
    service_list = []
    assert isinstance(services, list)
    for svc_cfg in services:
        #print("svc_cfg:", svc_cfg)
        svc = None
        c = defaults.copy()
        if "template" in svc_cfg:
            c.update(templates[svc_cfg["template"]])
        c.update(svc_cfg)
        svc_cfg = expand(c)
        if "names" in svc_cfg:
            names = svc_cfg.pop("names")
            for name in names:
                c = svc_cfg.copy()
                c["name"] = name
                yield expand(c)
        else:
            yield expand(svc_cfg)
            
class RequestTask(RequestProcessor):
    pass

class Service(Primitive, Logged):
    
    def __init__(self, config, logger=None):
        name = config["name"]
        #print("Service(): config:", config)
        self.ServiceName = name
        Logged.__init__(self, name, logger=logger, debug=config.get("debug", False))
        Primitive.__init__(self, name=f"[service {name}]")        
        self.Config = None
        self.Initialized = self.initialize(config)

    def log_request(self, *message):
        if self.Logger is not None:
            self.Logger.log(*message, channel="requests")

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
                self.error(f"Error importing module {fname}:\n{tb}")
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
                    self.error(f"Application creation function {fcn_name} not found in module {fname}")
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
                    self.error(f"Error calling the application initialization function:\n{tb}")
                    return False
                    
                if app is None:
                    self.error(f'Application creation function {fcn_name} returned None')
                    return False

            else:
                app = g.get(application)
                if app is None:
                    self.error(f'Application object "{application}" not found in {fname}')
                    return False
                    
            
            self.AppArgs = args
            self.WSGIApp = app

            max_workers = config.get("max_workers", 5)
            queue_capacity = config.get("queue_capacity", 10)
            self.QueueTimeout = config.get("queue_timeout", 0)
            self.RequestQueue = TaskQueue(max_workers, capacity = queue_capacity, delegate=self)
            log_message = f"""\
                prefix:               {self.Prefix}
                replace prefix:       {self.ReplacePrefix}
                max workers:          {max_workers}
                queue capacity:       {queue_capacity}
                queue timeout:        {self.QueueTimeout}
                timeout:              {self.Timeout}
                wsgi app:             {app}
                  args:               {args}
            """
            self.log("service initialized:\n"+log_message)
            
        except:
            tb = traceback.format_exc()
            self.error(f"Error initializing application:\n{tb}")
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
        self.error("request failed:", "".join(traceback.format_exception(exc_type, exc_value, tb)))
        try:
            # make sure the request is closed
            task.Request.close()
        except:
            pass

    def interval(self, x, y):
        if x is None or y is None:
            return 0.0
        else:
            return x - y

    def taskEnded(self, queue, task, _):
        request = task.Request
        header = request.HTTPHeader
        error = "" if not task.Error else " [%s]" % (task.Error,)
        start_time = self.interval(task.Started, task.Created)
        processing_time = self.interval(task.Ended, task.Started)
        log_line = '%s %s:%s :%s %s %s -> %s %s %s %s w:%.3f r:%.3f%s' % (   
                        request.Id, request.CAddr[0], request.CAddr[1], request.ServerPort, 
                        header.Method, header.OriginalURI, 
                        request.AppName, header.path(),
                        task.StatusCode, task.ByteCount, start_time, processing_time, error
                    )
        self.log(log_line, channel="requests")

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
            try:
                self.RequestQueue.add(RequestTask(self.WSGIApp, request), timeout=self.QueueTimeout)
            except RuntimeError:
                # queue is full
                return True, "service unavailable"
                
            #print("Service", self, "   accepted")
            return True, "accepted"
        else:
            #print("Service", self, "   rejected")
            return False, "no match"
    
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
        
class MPLogger(PyThread, Logged):
    
    def __init__(self, config_file, queue_size=-1, log_path = None, debug = None, requests_path = None, name=None):
        import multiprocessing
        name = name or "MPLogger"
        Logged.__init__(self, name)
        PyThread.__init__(self, name=name, daemon=True)
        self.Queue = multiprocessing.Queue(queue_size)
        self.ConfigFile = config_file
        self.Loggers = {}           # {"sevice" -> Logger}
        self.Debug = {}
        self.LogPath = log_path
        self.RequestsPath = requests_path
        self.ForceDebug = debug
        #print("MPLogger: force debug:", debug)
        self.reconfigure()

    def reconfigure(self):
        #
        # (re-)configure logging 
        #
        self.Loggers = {}
        config = expand(yaml.load(open(self.ConfigFile, 'r'), Loader=yaml.SafeLoader))
        log_config = config.get("logger", {})
        split_by_servrce = log_config.get("split", False)
        logs_dir = log_config.get("logs_dir", "logs")
        if not os.path.isdir(logs_dir):
            raise ValueError(f"Logs directory {logs_dir} not found")
        
        for service_cfg in services_from_config(config):
            #print("MPLogger: service_cfg:", service_cfg)
            #print("service from cfg:")
            #pprint.pprint(service_cfg)
            name = service_cfg["name"]
            self.Debug[name] = debug = service_cfg.get("debug", False) if self.ForceDebug is None else self.ForceDebug

            log_path = self.LogPath
            requests_path = self.RequestsPath
            #print("MPLogger.reconfigure:", name, "    log path:", log_path, "   requests_path:", requests_path, "   debug:", debug)

            if not log_path:
                log_path = service_cfg.get("log", f"{name}.log")
                if not log_path.startswith('/') and log_path != "-":
                    log_path = logs_dir + "/" + log_path
            if not requests_path:
                requests_path = service_cfg.get("requests", f"{name}.requests")
                if not requests_path.startswith('/') and requests_path != "-":
                    requests_path = logs_dir + "/" + requests_path
            logger = Logger(log_path, debug=debug)
            #print(f"Service {name}: adding requests channel ->", requests_path)
            logger.add_channel("requests", path=requests_path)
            self.Loggers[name] = logger
            #print(f"MPLogger: added logger for service '{name}'")

    def run(self):
        while True:
            self.process_message()
    
    def process_message(self):
        msg = self.Queue.get()
        who, channel, t = msg[:3]
        parts = msg[3:]
        #print("MPLogger: message:", who, channel, t, parts)
        if who in self.Loggers:
            self.Loggers[who].log(*parts, who=f"[{who}]", t=t, channel=channel)
        else:
            Logged.log(self, *parts, who=who, t=t, channel=channel)
    
    #
    # subprocess side
    #
    def log(self, *message, sep=" ", who=None, t=None, channel="log"):
        #print("MPLogger(subprocess side).log: channel:", channel, "  message:", *message)
        message = tuple(str(p) for p in message)
        self.Queue.put((who, channel, time.time())+message)
            
    def debug(self, who, *parts):
        if self.Debug.get(who):
            self.log(who, *parts, channel="debug")

    def error(self, who, *parts):
        self.log(who, *parts, channel="error")

    def log_request(self, who, *parts):
        self.log(who, *parts, channel="requests")

class Monitor(PyThread, Logged):

    def __init__(self, logger):
        Logged.__init__(self, f"ThreadMonitor", logger=logger)
        PyThread.__init__(self, name="ThreadMonitor", daemon=True)
        
    def run(self, once=False):
        while True: 
            try:
                fd = os.open("/dev/null", os.O_RDWR)
                os.close(fd)
            except:
                self.log("Error opening/closing /dev/null: %s" % (traceback.format_exc(),))
                fd = -1
            counts = {}
            for x in threading.enumerate():
                n = x.__class__.__name__
                if isinstance(x, Primitive):
                        try:    n = x.kind
                        except: pass
                counts[n] = counts.get(n, 0)+1
            self.log("thread counts:")
            for n, c in sorted(counts.items()):
                self.log("  %-50s%d" % (n+":", c))
            if once:
                break
            time.sleep(30)

class MultiServerSubprocess(Process, Logged):
    
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
        Logged.__init__(self, f"[Subprocess {self.MasterPID}]", logger=logger)
        #for key, value in sorted(self.__dict__.items()):
        #    print(key, type(value), value)
        
    def reconfigure(self):
        #print("MultiServerSubprocess.reconfigure()...")
        self.ReconfiguredTime = os.path.getmtime(self.ConfigFile)
        self.Config = config = expand(yaml.load(open(self.ConfigFile, 'r'), Loader=yaml.SafeLoader))
        service_list = []
        for svc_cfg in services_from_config(config):
            svc = Service(svc_cfg, self.Logger)
            if svc.Initialized:
                service_list.append(svc)
            else:
                self.log(f'service "{svc.ServiceName}" failed to initialize - removing from service list')
        if self.Server is None:
            self.Server = HTTPServer.from_config(self.Config, service_list, logger=self.Logger)
        else:
            self.Server.setServices(service_list)
        self.log(f"Server configured with services:", ",\n".join([s.ServiceName for s in service_list]))
        self.Services = service_list
        #print("MultiServerSubprocess.reconfigure() done")

    CheckConfigInterval = 5.0
    MonitorInterval = 60.0
        
    def run(self):
        self.Monitor = Monitor(self.Logger)

        init_uid(tag="%03d" % (os.getpid() % 1000,))
        #print("MultiServerSubprocess.run()...")
        if setproctitle is not None:
            setproctitle("multiserver %s worker" % (self.Port,))
        pid = os.getpid()
        self.LogName = f"MultiServerSubprocess({pid})"
        self.reconfigure()
        self.MasterSide = False
        self.Sock.settimeout(5.0)

        #self.Scheduler = Scheduler(max_concurrent = 2, daemon = True)
        #self.Scheduler.add(self.check_config, interval = self.CheckConfigInterval, t0 = time.time() + self.CheckConfigInterval)
        #self.Scheduler.add(self.run_monitor, interval = self.MonitorInterval)

        while not self.Stop:
            
            self.check_config()
            
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

        #self.Scheduler.stop()
        self.Server.close()
        self.Server.join()
        for svc in self.Services:
            svc.close()
            svc.join()
    
    def check_config(self):
        try:
            if os.path.getmtime(self.ConfigFile) > self.ReconfiguredTime:
                self.reconfigure()
            else:
                for svc in self.Services:
                    if isinstance(svc, Service):
                        svc.reloadIfNeeded()
        except Exception as e:
            self.error("Exception in check_config:\n", traceback.format_exc())
        return self.CheckConfigInterval

    def run_monitor(self):
        try:
            self.Monitor.run(once=True)
        except Exception as e:
            self.error("Exception in run_monitor:\n", traceback.format_exc())
        return self.MonitorInterval

    def stop(self):
        if self.MasterSide:
            self.ConnectionToSubprocess.send("stop")
        else:
            self.Stop = True
            
    def request_reconfigure(self):
        self.ConnectionToSubprocess.send("reconfigure")
            
class MPMultiServer(PyThread, Logged):
            
    def __init__(self, config_file, log_path, requests_path, debug_enabled):
        PyThread.__init__(self)
        Logged.__init__(self, "[Multiserver]")
        self.ConfigFile = config_file
        self.Server = None
        self.Port = None
        self.ReconfiguredTime = 0
        self.Subprocesses = []
        self.Sock = None
        self.Stop = False
        #print(f"MPMultiServer: log_path:", log_path, "requests_path:", requests_path)
        self.MPLogger = MPLogger(config_file, log_path = log_path, debug = debug_enabled, requests_path = requests_path)
        self.MPLogger.start()
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
python multiserver.py [options] <config.yaml>
    -d                          - enable debugging
    -l (<log file>|-)           - common log file
    -r (<requests log file>|-)  - common requests file
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
    import multiprocessing, getopt
    multiprocessing.set_start_method('fork')
    opts, args = getopt.getopt(sys.argv[1:], "?hl:r:d", ["help"])
    opts = dict(opts)

    if not args or "-?" in opts or "-h" in opts or "--help" in opts:
        print(Usage)
        sys.exit(2)

    service_log_path = log_path = opts.get("-l")
    requests_path = opts.get("-r")
    debug_enabled = "-d" in opts

    config_file = args[0]
    config = expand(yaml.load(open(config_file, 'r'), Loader=yaml.SafeLoader))
    master_logger = None
    if "logger" in config:
        cfg = config["logger"]
        debug_enabled = debug_enabled or cfg.get("debug", False)
        log_path = log_path or cfg.get("file", "multiserver.log")
        from webpie.logs import init
        #print("debug_enabled:", debug_enabled)
        init(log_path, debug_enabled=debug_enabled)
    if "pid_file" in config:
        open(config["pid_file"], "w").write(str(os.getpid()))
    ms = MPMultiServer(config_file, service_log_path, requests_path, debug_enabled or None)
    signal.signal(signal.SIGHUP, ms.reconfigure)
    #signal.signal(signal.SIGCHLD, ms.child_died)
    signal.signal(signal.SIGINT, ms.killme)
    ms.start()
    ms.join()

if __name__ == "__main__":
    main()
