from socket import * # har har har
from eunuchs.recvmsg import recvmsg
from struct import unpack
from os import fdopen
from time import sleep

s = socket(AF_UNIX, SOCK_STREAM)
s.connect("fd_control")
(message, addr, crap, ancillary) = recvmsg(s.fileno())
fds = []
tfds = ancillary[0][2]
#while 1:
#    sleep(100000)
while 1:
    fd = tfds[:4]
    if fd == "":
        break
    tfds = tfds[4:]
    fds.append(unpack("i", fd)[0])
print fds
tf1, tf2 = map(fdopen, fds)
tf1.seek(0)
tf2.seek(0)
print "Message #1:", tf1.read()
print "Message #2:", tf2.read()

