from socket import *

def f():
    s = socket(AF_INET, SOCK_STREAM)
    s.connect(('127.0.0.1', 8080))
    s.send('GET / HTTP/1.0\r\n\r\n')
    print s.recv(100)

