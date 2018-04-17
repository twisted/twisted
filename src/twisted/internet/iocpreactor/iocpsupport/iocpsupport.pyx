# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from cpython.version cimport PY_MAJOR_VERSION

# HANDLE and SOCKET are pointer-sized (they are 64 bit wide in 64-bit builds)
ctypedef size_t HANDLE
ctypedef size_t SOCKET
ctypedef unsigned long DWORD
# it's really a pointer, but we use it as an integer
ctypedef size_t ULONG_PTR
ctypedef int BOOL

cdef extern from 'io.h':
    long _get_osfhandle(int filehandle)

cdef extern from 'errno.h':
    int errno
    enum:
        EBADF

cdef extern from 'winsock2.h':
    pass

cdef extern from 'ws2tcpip.h':
    pass

cdef extern from 'windows.h':
    ctypedef struct OVERLAPPED:
        pass

    ctypedef Py_UNICODE WCHAR
    ctypedef const WCHAR* LPCWSTR
    HANDLE CreateIoCompletionPort(HANDLE fileHandle, HANDLE existing, ULONG_PTR key, DWORD numThreads)
    BOOL GetQueuedCompletionStatus(HANDLE port, DWORD *bytes, ULONG_PTR *key, OVERLAPPED **ov, DWORD timeout)
    BOOL PostQueuedCompletionStatus(HANDLE port, DWORD bytes, ULONG_PTR key, OVERLAPPED *ov)
    DWORD GetLastError()
    BOOL CloseHandle(HANDLE h)
    enum:
        INVALID_HANDLE_VALUE
    void DebugBreak()

cdef extern from 'python.h':
    ctypedef struct PyObject
    ctypedef struct PyUnicodeObject
    void *PyMem_Malloc(size_t n) except NULL
    void PyMem_Free(void *p)
    ctypedef struct PyThreadState
    PyThreadState *PyEval_SaveThread()
    void PyEval_RestoreThread(PyThreadState *tstate)
    void Py_INCREF(object o)
    void Py_XINCREF(object o)
    void Py_DECREF(object o)
    void Py_XDECREF(object o)
    int PyObject_AsWriteBuffer(object obj, void **buffer, Py_ssize_t *buffer_len) except -1
    int PyObject_AsReadBuffer(object obj, void **buffer, Py_ssize_t *buffer_len) except -1
    object PySequence_Fast(object o, char *m)
#    object PySequence_Fast_GET_ITEM(object o, Py_ssize_t i)
    PyObject** PySequence_Fast_ITEMS(object o)
    PyObject* PySequence_ITEM(PyObject *o, Py_ssize_t i)
    Py_ssize_t PySequence_Fast_GET_SIZE(object o)
    Py_ssize_t PyUnicode_AsWideChar(object o, LPCWSTR u, Py_ssize_t size)
    object PyUnicode_FromWideChar(LPCWSTR u, Py_ssize_t size)

cdef extern from '':
    struct sockaddr:
        unsigned short int sa_family
        char sa_data[0]
    cdef struct in_addr:
        unsigned long s_addr
    struct sockaddr_in:
        int sin_port
        in_addr sin_addr
    cdef struct in6_addr:
        char s6_addr[16]
    struct sockaddr_in6:
        short int sin6_family
        unsigned short int sin6_port
        unsigned long int sin6_flowinfo
        in6_addr sin6_addr
        unsigned long int sin6_scope_id
    int getsockopt(SOCKET s, int level, int optname, char *optval, int *optlen)
    enum:
        SOL_SOCKET
        SO_PROTOCOL_INFO
        SOCKET_ERROR
        ERROR_IO_PENDING
        AF_INET
        AF_INET6
        INADDR_ANY
    ctypedef struct WSAPROTOCOL_INFO:
        int iMaxSockAddr
        int iAddressFamily
    int WSAGetLastError()
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
    int WSAAddressToStringW(sockaddr *lpsaAddress, DWORD dwAddressLength,
                            WSAPROTOCOL_INFO *lpProtocolInfo,
                            LPCWSTR lpszAddressString,
                            DWORD *lpdwAddressStringLength)
    int WSAStringToAddressW(LPCWSTR AddressString, int AddressFamily,
                            WSAPROTOCOL_INFO *lpProtocolInfo,
                            sockaddr *lpAddress, int *lpAddressLength)

cdef extern from 'string.h':
    void *memset(void *s, int c, size_t n)

cdef extern from 'wchar.h':
    size_t wcslen(const WCHAR *)

cdef extern from 'winsock_pointers.h':
    int initWinsockPointers()
    BOOL (*lpAcceptEx)(SOCKET listening, SOCKET accepting, void *buffer, DWORD recvlen, DWORD locallen, DWORD remotelen, DWORD *bytes, OVERLAPPED *ov)
    void (*lpGetAcceptExSockaddrs)(void *buffer, DWORD recvlen, DWORD locallen, DWORD remotelen, sockaddr **localaddr, int *locallen, sockaddr **remoteaddr, int *remotelen)
    BOOL (*lpConnectEx)(SOCKET s, sockaddr *name, int namelen, void *buff, DWORD sendlen, DWORD *sentlen, OVERLAPPED *ov)
#    BOOL (*lpTransmitFile)(SOCKET s, HANDLE hFile, DWORD size, DWORD buffer_size, OVERLAPPED *ov, TRANSMIT_FILE_BUFFERS *buff, DWORD flags)



cdef struct myOVERLAPPED:
    # myOVERLAPPED is the C-level structure that is fed into and read out of a
    # L{CompletionPort}.

    # It attaches some Python data (C{attached}) to the native Windows
    # structure for putting things into and taking them out of an I/O
    # Completion Port (C{OVERLAPPED}).

    # The C{attached} attribute is a 2-tuple of C{(event, other)}, where
    # C{event} is the object created by Python and passed to an iocpsupport
    # operation, and C{other} is an opaque reference to any other Python
    # objects necessary to remain alive.  For example, C{WSASend} takes a
    # buffer to send, and that uses the Python buffer API to share the
    # underlying pointer with a python data structure such as a memoryview.
    # Therefore C{other} in that case would be whatever object (bytes,
    # memoryview, etc) was passed into the WSASend wrapper, and that reference
    # would be held until the completion status was posted to the completion
    # port.

    OVERLAPPED ov
    PyObject* attached



cdef myOVERLAPPED *makeOV(object evt, object other=None) except NULL:
    """
    Make a myOVERLAPPED structure for passing along to a low-level C object.
    """
    cdef myOVERLAPPED *res = <myOVERLAPPED *>PyMem_Malloc(sizeof(myOVERLAPPED))
    if not res:
        raise MemoryError
    memset(res, 0, sizeof(myOVERLAPPED))
    tupl = (evt, other)
    res.attached = <PyObject *>tupl
    Py_XINCREF(tupl)
    return res



cdef void unmakeOV(myOVERLAPPED* ov):
    """
    Clean up a myOVERLAPPED structure, decrefing the Python object and freeing
    its memory.
    """
    Py_XDECREF(<object>ov.attached)
    memset(ov, 0, sizeof(myOVERLAPPED))
    PyMem_Free(ov)



cdef void raise_error(int err, object message) except *:
    if not err:
        err = GetLastError()
    raise WindowsError(message, err)

class Event:
    def __init__(self, callback, owner, **kw):
        self.callback = callback
        self.owner = owner
        for k, v in kw.items():
            setattr(self, k, v)

cdef class CompletionPort:
    # A wrapper around an I/O completion port created with
    # C{CreateIoCompletionPort}.

    # Note that all C{OVERLAPPED} structures posted to this port must be
    # C{myOVERLAPPED} pointers, containing associated Python data.

    cdef HANDLE port
    def __init__(self):
        cdef HANDLE res
        res = CreateIoCompletionPort(INVALID_HANDLE_VALUE, 0, 0, 0)
        if not res:
            raise_error(0, 'CreateIoCompletionPort')
        self.port = res

    def addHandle(self, HANDLE handle, size_t key=0):
        cdef HANDLE res
        res = CreateIoCompletionPort(handle, self.port, key, 0)
        if not res:
            raise_error(0, 'CreateIoCompletionPort')

    def getEvent(self, long timeout):
        cdef PyThreadState *_save
        cdef unsigned long bytes, rc
        cdef size_t key
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
            obj, ignored = <object>ov.attached
            unmakeOV(ov)

        return (rc, bytes, key, obj)

    def postEvent(self, unsigned long bytes, size_t key, obj):
        cdef myOVERLAPPED *ov
        cdef unsigned long rc

        if obj is not None:
            ov = makeOV(obj)
        else:
            ov = NULL

        rc = PostQueuedCompletionStatus(self.port, bytes, key, <OVERLAPPED *>ov)
        if not rc:
            if ov:
                unmakeOV(ov)
            raise_error(0, 'PostQueuedCompletionStatus')

    def __del__(self):
        CloseHandle(self.port)

def makesockaddr(object buff):
    cdef void *mem_buffer
    cdef Py_ssize_t size

    PyObject_AsReadBuffer(buff, &mem_buffer, &size)
    # XXX: this should really return the address family as well
    return _makesockaddr(<sockaddr *>mem_buffer, size)

cdef object _makesockaddr(sockaddr *addr, Py_ssize_t len):
    cdef sockaddr_in *sin
    cdef sockaddr_in6 *sin6
    cdef WCHAR buff[256]
    cdef DWORD buffWcharLen = <DWORD>(sizeof(buff) / sizeof(WCHAR)) - 1
    cdef int rc
    if not len:
        return None

    memset(buff, 0, sizeof(buff))

    if addr.sa_family == AF_INET:
        sin = <sockaddr_in *>addr
        rc = WSAAddressToStringW(addr, sizeof(sockaddr_in), NULL, buff,
                                 &buffWcharLen)
        if rc == SOCKET_ERROR:
            raise_error(0, 'WSAAddressToStringW')
        sa_port = ntohs(sin.sin_port)
        host = PyUnicode_FromWideChar(buff, wcslen(buff))
        host, port = host.rsplit(u':', 1)
        port = int(port)
        assert port == sa_port

        return host, port
    elif addr.sa_family == AF_INET6:
        sin6 = <sockaddr_in6 *>addr
        rc = WSAAddressToStringW(addr, sizeof(sockaddr_in6), NULL, buff,
                                 &buffWcharLen)
        if rc == SOCKET_ERROR:
            raise_error(0, 'WSAAddressToStringW')
        sa_port = ntohs(sin6.sin6_port)
        host = PyUnicode_FromWideChar(buff, wcslen(buff))
        host, port = host.rsplit(u':', 1)
        port = int(port)
        assert host[0] == '['
        assert host[-1] == ']'
        assert port == sa_port

        return host[1:-1], port
    else:
        raise_error(0, "unsupported address family %d" % (addr.sa_family))


cdef object fillinetaddr(sockaddr_in *dest, object addr):
    cdef unsigned short port
    cdef WCHAR hostStr[256] # slightly larger than longest valid DNS hostname
    cdef Py_ssize_t hostStrWcharLen = (sizeof(hostStr) / sizeof(WCHAR)) - 1
    cdef int addrlen = sizeof(sockaddr_in)
    cdef Py_ssize_t rc
    host, port = addr

    if PY_MAJOR_VERSION < 3:
        if (isinstance(host, str)):
            host = unicode(host, "utf-8")

    memset(hostStr, 0, sizeof(hostStr))
    rc = PyUnicode_AsWideChar(host, hostStr, hostStrWcharLen)
    if rc == -1:
        raise ValueError, 'invalid IP address %r' % (host,)
    cdef int parseresult = WSAStringToAddressW(hostStr, AF_INET, NULL,
                                               <sockaddr *>dest, &addrlen)
    if parseresult == SOCKET_ERROR:
        raise ValueError, 'invalid IP address %r' % (host,)

    dest.sin_port = htons(port)


cdef object fillinet6addr(sockaddr_in6 *dest, object addr):
    cdef unsigned short port
    cdef unsigned long res
    cdef WCHAR hostStr[256]
    cdef Py_ssize_t hostStrWcharLen = (sizeof(hostStr) / sizeof(WCHAR)) - 1
    cdef Py_ssize_t rc
    cdef int addrlen = sizeof(sockaddr_in6)
    host, port, flow, scope = addr
    host = host.split("%")[0] # remove scope ID, if any

    if PY_MAJOR_VERSION < 3:
        if (isinstance(host, str)):
            host = unicode(host, "utf-8")

    memset(hostStr, 0, sizeof(hostStr))
    rc = PyUnicode_AsWideChar(host, hostStr, hostStrWcharLen)
    if rc == -1:
        raise ValueError, 'invalid IPv6 address %r' % (host,)
    cdef int parseresult = WSAStringToAddressW(hostStr, AF_INET6, NULL,
                                               <sockaddr *>dest, &addrlen)
    if parseresult == SOCKET_ERROR:
        raise ValueError, 'invalid IPv6 address %r' % (host,)
    if parseresult != 0:
        raise RuntimeError, 'undefined error occurred during address parsing'
    # sin6_host field was handled by WSAStringToAddress
    dest.sin6_port = htons(port)
    dest.sin6_flowinfo = flow
    dest.sin6_scope_id = scope


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

