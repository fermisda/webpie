import traceback, sys, time
from pythreader import LogFile, LogStream


class Logger(object):

    def __init__(self, log_file, debug=False):
        if isinstance(log_file, str):
            if log_file == "-":
                log_file = LogStream(sys.stdout)
            else:
                log_file = LogFile(log_file)
                log_file.start()
        self.LogFile = log_file
        self.Debug = debug
        
    def log(self, who, *parts, sep=" "):
        if self.LogFile is not None:
            self.LogFile.log("%s: %s" % (who, sep.join([str(p) for p in parts])))
            
    def debug(self, who, *parts, sep=" "):
        if self.Debug:
            self.log(f"{who} [DEBUG]", *parts, sep=sep)
            
    def error(self, who, *parts, sep=" "):
        self.log(f"{who} [ERROR]", *parts, sep=sep)
            
    def write(self, msg):
        self.LogFile.write(msg)


class Logged(object):

    def __init__(self, name, logger, error_logger = None, debug_logger = None, debug=False):
        #print("Logged.__init__():", name, logger)
        self.LogName = name
        self.Logger = logger
        self.ErrorLogger = error_logger or logger
        self.DebugLogger = debug_logger or logger
        self.Debug = debug
        
    def debug(self, *params):
        if self.DebugLogger is not None and self.Debug:
            self.DebugLogger.debug(self.LogName, *params)

    def log(self, *params):
        if self.Logger is not None:
            self.Logger.log(self.LogName, *params)

    def error(self, *params):
        if self.ErrorLogger is not None:
            self.ErrorLogger.error(self.LogName, *params)
        else:
            print(self.LogName, "[ERROR]", *params, file=sys.stderr)
    
    log_error = error       # for compatibility

