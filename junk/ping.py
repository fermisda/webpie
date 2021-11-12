from socket import *
import sys, os

host, port, msg = sys.argv[1:]
port = int(port)

sock = socket(AF_INET, SOCK_STREAM)
sock.connect((host, port))
sock.send(msg.encode("utf-8"))
print(sock.recv(1000).decode("utf-8"))