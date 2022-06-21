import traceback, sys, time
from .log_file import LogFile, LogStream

DefaultLogger = None

class StreamLogger(object):

    def log_to_stream(self, stream, *message, sep=" ", who=None):
        raise NotImplementedError()


class Logger(StreamLogger):

    def __init__(self, log_path, error_path=None, debug_path=None, debug=True, **streams):
        log_out = self.make_log(log_path, sys.stdout)
        self.Streams = {
            "log":      log_out,
            "error":    log_out if error_path is None else self.make_log(error_path, sys.stderr),
            "debug":    log_out if debug_path is None else self.make_log(debug_path, sys.stderr)
        }

        for name, path in streams.items():
            self.Streams[name] = log_out if path is None else self.make_log(path, sys.stdout)
            #print(f"custom stream {name} added")
        self.Debug = debug

    def add_stream(self, name, path=None):
        out = self.Streams["log"]
        self.Streams[name] = out if path is None else self.make_log(path, sys.stdout)

    def log_to_stream(self, stream, *message, sep=" ", who=None, t=None):
        assert who is not None, "Message originator (who) must be specified"
        #print(f"logging to stream {stream}:", message)
        #print(self.Streams[stream], self.Streams[stream].__class__.__name__)
        if stream != "debug" or self.Debug:
            self.Streams[stream].log("%s: %s" % (who, sep.join([str(p) for p in message])), t=t)

    def make_log(self, output, dash_stream, **params):
        if output is None:  
            return None
        elif isinstance(output, (LogFile, LogStream)):
            return output
        elif output == "-":
            return LogStream(dash_stream)
        elif output is sys.stderr or output is sys.stdout:
            return LogStream(output)
        else:
            #print("Logger.__init__: output:", output)
            out = LogFile(output, **params)
            out.start()
            return out

    def log(self, *message, sep=" ", who=None, t=None, stream="log"):
        assert who is not None, "Message originator (who) must be specified"
        self.log_to_stream(stream, *message, sep=sep, who=who, t=t)

    def error(self, *message, sep=" ", who=None, t=None):
        assert who is not None, "Message originator (who) must be specified"
        self.log_to_stream("error", "[ERROR]", *message, sep=sep, who=who, t=t)

    def debug(self, *message, sep=" ", who=None, t=None):
        assert who is not None, "Message originator (who) must be specified"
        if self.Debug:
            self.log_to_stream("debug", "[DEBUG]", *message, sep=sep, who=who, t=t)

class Logged(StreamLogger):

    def __init__(self, name=None, debug=False, logger=None):
        assert logger is None or isinstance(logger, StreamLogger), "logger must be either None or a Logger or a Logged"
        self.Logger = logger
        self.LogName = name or self.__class__.__name__
        self.Debug = debug
        #print("Logged: LogName=", self.LogName)

    def log_to_stream(self, stream, *message, sep=" ", who=None, t=None):
        logger = self.Logger or DefaultLogger
        if logger is not None:
            if stream != "debug" or self.Debug:
               logger.log_to_stream(stream, *message, sep=sep, who=who, t=t)
    
    def log(self, *message, sep=" ", who=None, t=None, stream="log"):
        self.log_to_stream(stream, *message, sep=sep, who=who or self.LogName, t=t)

    def error(self, *message, sep=" ", who=None, t=None):
        self.log_to_stream("error", "[ERROR]", *message, sep=sep, who=who or self.LogName, t=t)

    def debug(self, *message, sep=" ", who=None, t=None):
        self.log_to_stream("debug", "[DEBUG]", *message, sep=sep, who=who or self.LogName, t=t)

def init(log_output, error_out=None, debug_out=None, debug_enabled=False):
    global DefaultLogger
    DefaultLogger = Logger(log_output, error_out, debug_out, debug_enabled)
    
