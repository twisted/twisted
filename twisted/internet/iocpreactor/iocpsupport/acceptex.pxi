# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


def accept(long listening, long accepting, object buff, object obj):
    cdef unsigned long bytes
    cdef int size, rc
    cdef void *mem_buffer
    cdef myOVERLAPPED *ov

    PyObject_AsWriteBuffer(buff, &mem_buffer, &size)

    ov = makeOV()
    if obj is not None:
        ov.obj = <PyObject *>obj

    rc = lpAcceptEx(listening, accepting, mem_buffer, 0, size / 2, size / 2,
                    &bytes, <OVERLAPPED *>ov)
    if not rc:
        rc = WSAGetLastError()
        if rc != ERROR_IO_PENDING:
            return rc

    # operation is in progress
    Py_XINCREF(obj)
    return rc

def get_accept_addrs(long s, object buff):
    cdef WSAPROTOCOL_INFO wsa_pi
    cdef int size, locallen, remotelen
    cdef void *mem_buffer
    cdef sockaddr *localaddr, *remoteaddr

    PyObject_AsReadBuffer(buff, &mem_buffer, &size)

    lpGetAcceptExSockaddrs(mem_buffer, 0, size / 2, size / 2, &localaddr, &locallen, &remoteaddr, &remotelen)
    return remoteaddr.sa_family, _makesockaddr(localaddr, locallen), _makesockaddr(remoteaddr, remotelen)

