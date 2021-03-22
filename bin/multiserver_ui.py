import sys, yaml, signal
import yaml, os
from webpie import MultiServer, Logger

Usage = """
multiserver <config.yaml>
"""

class   SignalHandler:

    def __init__(self, signum, receiver, config_file):
        self.Receiver = receiver
        self.ConfigFile = config_file
        signal.signal(signum, self)
        
    def __call__(self, signo, frame):
        try:    
            config = yaml.load(open(self.ConfigFile, 'r'), Loader=yaml.SafeLoader)
            self.Receiver.reconfigure(config)
        except: 
            import traceback
            traceback.print_exc()
            
def main():
    if not sys.argv[1:] or sys.argv[1] in ("-?", "-h", "--help", "help"):
        print(Usage)
        sys.exit(2)
    config_file = sys.argv[1]
    config = yaml.load(open(config_file, 'r'), Loader=yaml.SafeLoader)
    logger = None
    if "logger" in config:
        cfg = config["logger"]
        debug = cfg.get("debug", False)
        if cfg.get("enabled", True):
            logger = Logger(cfg.get("file", "-"), debug=debug)
    if "pid_file" in config:
        open(config["pid_file"], "w").write(str(os.getpid()))
    ms = MultiServer(config, logger)
    s = SignalHandler(signal.SIGHUP, ms, config_file)
    ms.join()
