from win32file import CreateIoCompletionPort as cicp, ReadFile as rf, WriteFile as wf, AllocateReadBuffer as arb
from win32file import INVALID_HANDLE_VALUE

f1 = file("qq1")
f2 = file("qq2")

iocp = cicp(INVALID_HANDLE_VALUE, 0, 0, 0)
print iocp
print f1.fileno()
print f2.fileno()
cicp(f1.fileno(), iocp, 1, 0)
cicp(f2.fileno(), iocp, 2, 0)

