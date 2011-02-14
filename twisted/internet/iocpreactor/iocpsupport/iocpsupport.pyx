# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


ctypedef int size_t
ctypedef unsigned long HANDLE
ctypedef unsigned long SOCKET
ctypedef unsigned long DWORD
ctypedef unsigned long ULONG_PTR
ctypedef int BOOL

cdef extern from 'io.h':
    long _get_osfhandle(int filehandle)

cdef extern from 'errno.h':
    int errno
    enum:
        EBADF

cdef extern from 'winsock2.h':
    pass

cdef extern from 'windows.h':
    ctypedef struct OVERLAPPED:
        pass
    HANDLE CreateIoCompletionPort(HANDLE fileHandle, HANDLE existing, ULONG_PTR key, DWORD numThreads)
    BOOL GetQueuedCompletionStatus(HANDLE port, DWORD *bytes, ULONG_PTR *key, OVERLAPPED **ov, DWORD timeout)
    BOOL PostQueuedCompletionStatus(HANDLE port, DWORD bytes, ULONG_PTR key, OVERLAPPED *ov)
    DWORD GetLastError()
    BOOL CloseHandle(HANDLE h)
    enum:
        INVALID_HANDLE_VALUE
    void DebugBreak()

cdef extern from 'python.h':
    struct PyObject:
        pass
    void *PyMem_Malloc(size_t n) except NULL
    void PyMem_Free(void *p)
    struct PyThreadState:
        pass
    PyThreadState *PyEval_SaveThread()
    void PyEval_RestoreThread(PyThreadState *tstate)
    void Py_INCREF(object o)
    void Py_XINCREF(object o)
    void Py_DECREF(object o)
    void Py_XDECREF(object o)
    int PyObject_AsWriteBuffer(object obj, void **buffer, int *buffer_len) except -1
    int PyObject_AsReadBuffer(object obj, void **buffer, int *buffer_len) except -1
    object PyString_FromString(char *v)
    object PyString_FromStringAndSize(char *v, int len)
    object PyBuffer_New(int size)
    char *PyString_AsString(object obj) except NULL
    object PySequence_Fast(object o, char *m)
#    object PySequence_Fast_GET_ITEM(object o, int i)
    PyObject** PySequence_Fast_ITEMS(object o)
    PyObject* PySequence_ITEM(	PyObject *o, int i)
    int PySequence_Fast_GET_SIZE(object o)

cdef extern from '':
    struct sockaddr:
        int sa_family
        char sa_data[0]
    cdef struct in_addr:
        unsigned long s_addr
    struct sockaddr_in:
        int sin_port
        in_addr sin_addr
    int getsockopt(SOCKET s, int level, int optname, char *optval, int *optlen)
    enum:
        SOL_SOCKET
        SO_PROTOCOL_INFO
        SOCKET_ERROR
        ERROR_IO_PENDING
        AF_INET
        INADDR_ANY
    ctypedef struct WSAPROTOCOL_INFO:
        int iMaxSockAddr
        int iAddressFamily
    int WSAGetLastError()
    char *inet_ntoa(in_addr ina)
    unsigned long inet_addr(char *cp)
    unsigned short ntohs(unsigned short netshort)
    unsigned short htons(unsigned short hostshort)
    ctypedef struct WSABUF:
        long len
        char *buf
#    cdef struct TRANSMIT_FILE_BUFFERS:
#        pass
    int WSARecv(SOCKET s, WSABUF *buffs, DWORD buffcount, DWORD *bytes, DWORD *flags, OVERLAPPED *ov, void *crud)
    int WSARecvFrom(SOCKET s, WSABUF *buffs, DWORD buffcount, DWORD *bytes, DWORD *flags, sockaddr *fromaddr, int *fromlen, OVERLAPPED *ov, void *crud)
    int WSASend(SOCKET s, WSABUF *buffs, DWORD buffcount, DWORD *bytes, DWORD flags, OVERLAPPED *ov, void *crud)

cdef extern from 'string.h':
    void *memset(void *s, int c, size_t n)

cdef extern from 'winsock_pointers.h':
    int initWinsockPointers()
    BOOL (*lpAcceptEx)(SOCKET listening, SOCKET accepting, void *buffer, DWORD recvlen, DWORD locallen, DWORD remotelen, DWORD *bytes, OVERLAPPED *ov)
    void (*lpGetAcceptExSockaddrs)(void *buffer, DWORD recvlen, DWORD locallen, DWORD remotelen, sockaddr **localaddr, int *locallen, sockaddr **remoteaddr, int *remotelen)
    BOOL (*lpConnectEx)(SOCKET s, sockaddr *name, int namelen, void *buff, DWORD sendlen, DWORD *sentlen, OVERLAPPED *ov)
#    BOOL (*lpTransmitFile)(SOCKET s, HANDLE hFile, DWORD size, DWORD buffer_size, OVERLAPPED *ov, TRANSMIT_FILE_BUFFERS *buff, DWORD flags)

cdef struct myOVERLAPPED:
    OVERLAPPED ov
    PyObject *obj

cdef myOVERLAPPED *makeOV() except NULL:
    cdef myOVERLAPPED *res
    res = <myOVERLAPPED *>PyMem_Malloc(sizeof(myOVERLAPPED))
    if not res:
        raise MemoryError
    memset(res, 0, sizeof(myOVERLAPPED))
    return res

cdef void raise_error(int err, object message) except *:
    if not err:
        err = GetLastError()
    raise WindowsError(message, err)

class Event:
    def __init__(self, callback, owner, **kw):
        self.callback = callback
        self.owner = owner
        self.ignore = False
        for k, v in kw.items():
            setattr(self, k, v)

cdef class CompletionPort:
    cdef HANDLE port
    def __init__(self):
        cdef HANDLE res
        res = CreateIoCompletionPort(INVALID_HANDLE_VALUE, 0, 0, 0)
        if not res:
            raise_error(0, 'CreateIoCompletionPort')
        self.port = res

    def addHandle(self, long handle, long key=0):
        cdef HANDLE res
        res = CreateIoCompletionPort(handle, self.port, key, 0)
        if not res:
            raise_error(0, 'CreateIoCompletionPort')

    def getEvent(self, long timeout):
        cdef PyThreadState *_save
        cdef unsigned long bytes, key, rc
        cdef myOVERLAPPED *ov

        _save = PyEval_SaveThread()
        rc = GetQueuedCompletionStatus(self.port, &bytes, &key, <OVERLAPPED **>&ov, timeout)
        PyEval_RestoreThread(_save)

        if not rc:
            rc = GetLastError()
        else:
            rc = 0

        obj = None
        if ov:
            if ov.obj:
                obj = <object>ov.obj
                Py_DECREF(obj) # we are stealing a reference here
            PyMem_Free(ov)

        return (rc, bytes, key, obj)

    def postEvent(self, unsigned long bytes, unsigned long key, obj):
        cdef myOVERLAPPED *ov
        cdef unsigned long rc

        if obj is not None:
            ov = makeOV()
            Py_INCREF(obj) # give ov its own reference to obj
            ov.obj = <PyObject *>obj
        else:
            ov = NULL

        rc = PostQueuedCompletionStatus(self.port, bytes, key, <OVERLAPPED *>ov)
        if not rc:
            raise_error(0, 'PostQueuedCompletionStatus')

    def __del__(self):
        CloseHandle(self.port)

def makesockaddr(object buff):
    cdef void *mem_buffer
    cdef int size

    PyObject_AsReadBuffer(buff, &mem_buffer, &size)
    # XXX: this should really return the address family as well
    return _makesockaddr(<sockaddr *>mem_buffer, size)

cdef object _makesockaddr(sockaddr *addr, int len):
    cdef sockaddr_in *sin
    if not len:
        return None
    if addr.sa_family == AF_INET:
        sin = <sockaddr_in *>addr
        return PyString_FromString(inet_ntoa(sin.sin_addr)), ntohs(sin.sin_port)
    else:
        return PyString_FromStringAndSize(addr.sa_data, sizeof(addr.sa_data))

cdef object fillinetaddr(sockaddr_in *dest, object addr):
    cdef unsigned short port
    cdef unsigned long res
    cdef char *hoststr
    host, port = addr

    hoststr = PyString_AsString(host)
    res = inet_addr(hoststr)
    if res == INADDR_ANY:
        raise ValueError, 'invalid IP address'
    dest.sin_addr.s_addr = res

    dest.sin_port = htons(port)

def AllocateReadBuffer(int size):
    return PyBuffer_New(size)

def maxAddrLen(long s):
    cdef WSAPROTOCOL_INFO wsa_pi
    cdef int size, rc

    size = sizeof(wsa_pi)
    rc = getsockopt(s, SOL_SOCKET, SO_PROTOCOL_INFO, <char *>&wsa_pi, &size)
    if rc == SOCKET_ERROR:
        raise_error(WSAGetLastError(), 'getsockopt')
    return wsa_pi.iMaxSockAddr

cdef int getAddrFamily(SOCKET s) except *:
    cdef WSAPROTOCOL_INFO wsa_pi
    cdef int size, rc

    size = sizeof(wsa_pi)
    rc = getsockopt(s, SOL_SOCKET, SO_PROTOCOL_INFO, <char *>&wsa_pi, &size)
    if rc == SOCKET_ERROR:
        raise_error(WSAGetLastError(), 'getsockopt')
    return wsa_pi.iAddressFamily

import socket # for WSAStartup
if not initWinsockPointers():
    raise ValueError, 'Failed to initialize Winsock function vectors'

have_connectex = (lpConnectEx != NULL)

include 'acceptex.pxi'
include 'connectex.pxi'
include 'wsarecv.pxi'
include 'wsasend.pxi'

