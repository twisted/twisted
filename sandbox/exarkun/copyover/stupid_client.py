import sys
from socket import * # har har har
sys.path.insert(0, "../../pahan/sendmsg")
from sendmsg import recvmsg
from struct import unpack
from os import fdopen, read, close
from time import sleep

s = socket(AF_UNIX, SOCK_STREAM)
s.connect("fd_control")
#foo = read(s.fileno(), 1)
#print "got foo", foo
(message, flags, ancillary) = recvmsg(s.fileno())
print (message, flags, ancillary)
try:
    close(4)
    close(5)
    print "descriptors WERE passed"
except:
    print "descriptors weren't passed"
"""
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
"""

