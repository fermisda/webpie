import traceback, sys, time
from .LogFile import LogFile, LogStream

from pythreader import synchronized, Primitive

Debug = False

class Logger(Primitive):

    def __init__(self, log_file, debug=False):
        #print("Logger.__init__: log_file:", log_file)
        Primitive.__init__(self)
        if isinstance(log_file, str):
            if log_file == "-":
                log_file = LogStream(sys.stdout)
            else:
                log_file = LogFile(log_file)
                log_file.start()
        self.LogFile = log_file
        self.Debug = debug
        
    @synchronized
    def log(self, who, *parts):
        #print("who:", who)
        #print("parts:", parts)
        if self.LogFile is not None:
            self.LogFile.log("%s: %s: %s" % (time.ctime(), who, " ".join([str(p) for p in parts])))
        
    debug = log

class Logged(object):

    def __init__(self, name, logger, debug=False):
        #print("Logged.__init__():", name, logger)
        self.LogName = name
        self.Logger = logger
        self.Debug = debug
        
    def debug(self, *params):
        if self.Logger is not None and self.Logger.Debug and self.Debug:
            self.Logger.log(f"{self.LogName}(DEBUG)", *params)
        
    def log(self, *params):
        #print("Logged.log():", params)
        if self.Logger is not None:
            self.Logger.log(self.LogName, *params)
        
    def log_error(self, *params):
        if self.Logger is not None:
            self.Logger.log(self.LogName, "ERROR:", *params)
        else:
            print(self.LogName, "ERROR:", *params, file=sys.stderr)
        
