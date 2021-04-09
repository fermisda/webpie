import traceback, sys, time

from pythreader import synchronized, Primitive

#from .py3 import PY2, PY3, to_str, to_bytes
Debug = False

class Logger(Primitive):

    def __init__(self, log_file):
        #print("Logger.__init__: log_file:", log_file)
        Primitive.__init__(self)
        if isinstance(log_file, str):
            if log_file == "-":
                log_file = sys.stdout
            else:
                log_file = open(log_file, "w")
        self.LogFile = log_file
        
    @synchronized
    def log(self, who, *parts):
        #print("who:", who)
        #print("parts:", parts)
        if self.LogFile is not None:
            print("%s: %s: %s" % (time.ctime(), who, " ".join([str(p) for p in parts])), file=self.LogFile)
        
    debug = log

class Logged(object):

    def __init__(self, name, logger):
        #print("Logged.__init__():", name, logger)
        self.LogName = name
        self.Logger = logger
        
    def debug(self, *params):
        if self.Logger is not None and Debug:
            params = (self.LogName, "debug:") + params
            self.Logger.log(*params)
        
    def log(self, *params):
        #print("Logged.log():", params)
        if self.Logger is not None:
            self.Logger.log(self.LogName, *params)
        
    def log_error(self, *params):
        if self.Logger is not None:
            self.Logger.log(self.LogName, "ERROR:", *params)
        else:
            print(self.LogName, "ERROR:", *params, file=sys.stderr)
        
