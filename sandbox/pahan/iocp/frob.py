from win32file import CreateIoCompletionPort as cicp, ReadFile as rf, WriteFile as wf, AllocateReadBuffer as arb
from win32file import INVALID_HANDLE_VALUE, CreateFile as cf, OPEN_EXISTING, GENERIC_READ
from win32file import WSASend as ws, WSARecv as wr, GetQueuedCompletionStatus as gqcs
from pywintypes import OVERLAPPED
from socket import *

s1=socket(AF_INET, SOCK_STREAM)
s2=socket(AF_INET, SOCK_STREAM)
iocp = cicp(INVALID_HANDLE_VALUE, 0, 0, 0)
cicp(s1.fileno(), iocp, 1, 0)
cicp(s2.fileno(), iocp, 2, 0)
ad = ("172.16.107.1", 7777)
s1.connect(ad)
s2.connect(ad)
ov1 = OVERLAPPED()
ov1.object = "s1"
ov2 = OVERLAPPED()
ov2.object = "s2"
print ws(s1, "Hi, echo server. I am s1!!@#", ov1, 0)
print ws(s2, "Yo, echo servah, I be s2!!@#", ov2, 0)
b1 = arb(1024)
b2 = arb(1024)
ov3 = OVERLAPPED()
ov3.object = "s3"
ov4 = OVERLAPPED()
ov4.object = "s4"
print wr(s1, b1, ov3, 0)
print wr(s2, b2, ov4, 0)
while 1:
    (rc, bytes, key, pyov) = gqcs(iocp, -1)
    print (rc, bytes, key, pyov, pyov.object)

