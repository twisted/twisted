import os, sys
from socket import * # har har har
from tempfile import TemporaryFile
sys.path.insert(0, "../../pahan/sendmsg")
from sendmsg import sendmsg, SCM_RIGHTS
from struct import pack

tf1 = TemporaryFile()
tf1.write("I hope it breaks and you die")
tf1.flush()
tf2 = TemporaryFile()
tf2.write("I lied!")
tf2.flush()

s = socket(AF_UNIX, SOCK_STREAM)
try:
    os.unlink("fd_control")
except OSError:
    pass
s.bind("fd_control")
s.listen(1)
while 1:
    b, _ = s.accept()
    print "Connected", b
    sendmsg(b.fileno(), "stfu", 0, (SOL_SOCKET, SCM_RIGHTS, pack("2i", tf1.fileno(), tf2.fileno())))
    print "Sent"

