from win32file import CreateIoCompletionPort as cicp, ReadFile as rf, WriteFile as wf, AllocateReadBuffer as arb
from win32file import INVALID_HANDLE_VALUE, CreateFile as cf, OPEN_EXISTING, GENERIC_READ
from win32file import WSASend as ws, WSARecv as wr, GetQueuedCompletionStatus as gqcs
from win32file import PostQueuedCompletionStatus as pqcs
from win32file import AcceptEx as ae
from win32event import INFINITE
from pywintypes import OVERLAPPED
from socket import *

s1 = socket(AF_INET, SOCK_STREAM)
iocp = cicp(INVALID_HANDLE_VALUE, 0, 0, 0)
cicp(s1.fileno(), iocp, 1, 0)
ov = OVERLAPPED()
s1.bind(("", 8002))
s1.listen(5)
s2 = socket(AF_INET, SOCK_STREAM)
b = arb(64)
cicp(s2.fileno(), iocp, 2, 0)
print ae(s1.fileno(), s2.fileno(), b, ov)
print gqcs(iocp, INFINITE)
print rf(s2.fileno(), b, ov)
#print gqcs(iocp, INFINITE)
s2.close()
print gqcs(iocp, INFINITE)

