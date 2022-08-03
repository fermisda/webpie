import traceback, sys, time
from .log_file import LogFile, LogStream

DefaultLogger = None

class StreamLogger(object):

    def log_to_stream(self, stream, *message, sep=" ", who=None):
        raise NotImplementedError()


class AbstractLogger(object):

    def log(self, *message, sep=" ", who=None):
        raise NotImplementedError()

    def error(self, who, *message, sep=" "):
        raise NotImplementedError()

    def debug(self, who, *message, sep=" "):
        raise NotImplementedError()


class Logger(StreamLogger):

    def __init__(self, log_path, error_path=None, debug_path=None, debug=False, **streams):
        log_out = self.make_log(log_path, sys.stdout)
        self.Streams = {
            "log":      log_out,
            "error":    log_out if error_path is None else self.make_log(error_path, sys.stderr),
            "debug":    log_out if debug_path is None else self.make_log(debug_path, sys.stderr)
        }

        for name, path in streams.items():
            self.Streams[name] = log_out if path is None else self.make_log(path, sys.stdout)
            print(f"custom stream {name} added")
        self.Debug = debug

    def add_stream(self, name, path=None):
        out = self.Streams["log"]
        self.Streams[name] = out if path is None else self.make_log(path, sys.stdout)

    def log_to_stream(self, stream, *message, sep=" ", who=None):
        assert who is not None, "Message originator (who) must be specified"
        print(f"logging to stream {stream}:", message)
        self.Streams[stream].log("%s: %s" % (who, sep.join([str(p) for p in message])))

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
            print("Logger.__init__: output:", output)
            out = LogFile(output, **params)
            out.start()
            return out

    def log(self, *message, sep=" ", who=None):
        assert who is not None, "Message originator (who) must be specified"
        self.log_to_stream("log", *message, sep=sep, who=who)

    def error(self, *message, sep=" ", who=None):
        assert who is not None, "Message originator (who) must be specified"
        self.log_to_stream("error", *message, sep=sep, who=f"{who} [ERROR]")

    def debug(self, *message, sep=" ", who=None):
        assert who is not None, "Message originator (who) must be specified"
        if self.Debug:
            self.log_to_stream("error", *message, sep=sep, who=f"{who} [DEBUG]")

class Logged(AbstractLogger, StreamLogger):

    def __init__(self, name=None, debug=False, logger=None):
        assert logger is None or isinstance(logger, StreamLogger), "logger must be either None or a Logger or a Logged"
        self.Logger = logger
        self.LogName = name or self.__class__.__name__
        self.Debug = debug
        print("Logged: LogName=", self.LogName)

    def log_to_stream(self, stream, *message, sep=" ", who=None):
        logger = self.Logger or DefaultLogger
        logger.log_to_stream(stream, *message, sep=sep, who=who)
    
    def log(self, *message, sep=" ", who=None, stream="log"):
        self.log_to_stream(stream, *message, sep=sep, who=who or self.LogName)

    def error(self, *message, sep=" ", who=None):
        self.log_to_stream("error", *message, sep=sep, who=who or self.LogName)

    def debug(self, *message, sep=" ", who=None):
        if self.Debug:
            self.log_to_stream("debug", *message, sep=sep, who=who or self.LogName)

def init(log_output, error_out=None, debug_out=None, debug_enabled=False):
    global DefaultLogger
    DefaultLogger = Logger(log_output, error_out, debug_out, debug_enabled)
    
