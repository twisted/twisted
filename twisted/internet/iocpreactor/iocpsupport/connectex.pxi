# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


def connect(long s, object addr, object obj):
    """
    CAUTION: unlike system ConnectEx(), this function returns 0 on success
    """
    cdef int family, rc
    cdef myOVERLAPPED *ov
    cdef sockaddr name

    if not have_connectex:
        raise ValueError, 'ConnectEx is not available on this system'

    family = getAddrFamily(s)
    if family == AF_INET:
        fillinetaddr(<sockaddr_in *>&name, addr)
    else:
        raise ValueError, 'unsupported address family'
    name.sa_family = family

    ov = makeOV()
    if obj is not None:
        ov.obj = <PyObject *>obj

    rc = lpConnectEx(s, &name, sizeof(name), NULL, 0, NULL, <OVERLAPPED *>ov)

    if not rc:
        rc = WSAGetLastError()
        if rc != ERROR_IO_PENDING:
            return rc

    # operation is in progress
    Py_XINCREF(obj)
    return 0

