import socket, sys

test_type = sys.argv[1]
port = int(sys.argv[2])

s = socket.socket(socket.AF_INET)
s.connect(("127.0.0.1", port))

print >> sys.stderr, ">> Making request"
s.send("GET /error HTTP/1.0\r\n")
s.send("Host: localhost\r\n")

if test_type == "lingeringClose":
    print >> sys.stderr, ">> Sending lots of data"
    s.send("Content-Length: 1000000\r\n\r\n")
    s.send("X"*1000000)
else:
    s.send('\r\n')
    
print >> sys.stderr, ">> Getting data"
print s.recv(10000),
    
