from multiprocessing import Process
from socket import *
import sys, os, time

class Server(Process):
    
    def __init__(self, sock):
        Process.__init__(self, daemon=True)
        self.Sock = sock
        
    def run(self):
        while True:
            sock, addr = self.Sock.accept()
            print("%d: accepted from: %s" % (os.getpid(), addr))
            sock.sendall(sock.recv(1000))

port = 1234
sock = socket(AF_INET, SOCK_STREAM)
sock.bind(("", 1234))
sock.listen(10)

processes = [Server(sock) for _ in range(5)]
[p.start() for p in processes]

while True:
    new_processes = []
    for p in processes:
        if not p.is_alive():
            p = Server(sock)
            p.start
        new_processes.append(p)
    processes = new_processes
    time.sleep(5)
