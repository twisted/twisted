import socket, sys

test_type = sys.argv[1]
port = int(sys.argv[2])
socket_type = sys.argv[3]

s = socket.socket(socket.AF_INET)
s.connect(("127.0.0.1", port))
s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 40000)

if socket_type == 'ssl':
    s2 = socket.ssl(s)
    send=s2.write
    recv=s2.read
else:
    send=s.send
    recv=s.recv
    
print >> sys.stderr, ">> Making %s request to port %d" % (socket_type, port)

send("GET /error HTTP/1.0\r\n")
send("Host: localhost\r\n")

if test_type == "lingeringClose":
    print >> sys.stderr, ">> Sending lots of data"
    send("Content-Length: 1000000\r\n\r\n")
    send("X"*1000000)
else:
    send('\r\n')

#import time
#time.sleep(5)
print >> sys.stderr, ">> Getting data"
data=''
while len(data) < 299999:
    try:
        x=recv(10000)
    except:
        break
    if x == '':
        break
    data+=x
sys.stdout.write(data)
