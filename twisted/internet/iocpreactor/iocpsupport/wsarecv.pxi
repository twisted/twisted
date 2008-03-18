# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.


def recv(long s, object bufflist, object obj, unsigned long flags = 0):
    cdef int rc, buffcount, i, res
    cdef myOVERLAPPED *ov
    cdef WSABUF *ws_buf
    cdef unsigned long bytes
    cdef PyObject **buffers

    bufflist = PySequence_Fast(bufflist, 'second argument needs to be a list')
    buffcount = PySequence_Fast_GET_SIZE(bufflist)
    buffers = PySequence_Fast_ITEMS(bufflist)

    ws_buf = <WSABUF *>PyMem_Malloc(buffcount*sizeof(WSABUF))

    try:
        for i from 0 <= i < buffcount:
            PyObject_AsWriteBuffer(<object>buffers[i], <void **>&ws_buf[i].buf, <int *>&ws_buf[i].len)

        ov = makeOV()
        if obj is not None:
            ov.obj = <PyObject *>obj

        rc = WSARecv(s, ws_buf, buffcount, &bytes, &flags, <OVERLAPPED *>ov, NULL)

        if rc == SOCKET_ERROR:
            rc = WSAGetLastError()
            if rc != ERROR_IO_PENDING:
                return rc, 0

        Py_XINCREF(obj)
        return rc, bytes
    finally:
        PyMem_Free(ws_buf)

def recvfrom(long s, object buff, object addr_buff, object obj, unsigned long flags = 0):
    cdef int rc, fromlen
    cdef myOVERLAPPED *ov
    cdef WSABUF ws_buf
    cdef unsigned long bytes
    cdef sockaddr *fromaddr

    PyObject_AsWriteBuffer(buff, <void **>&ws_buf.buf, <int *>&ws_buf.len)
    PyObject_AsWriteBuffer(addr_buff, <void **>&fromaddr, &fromlen)

    ov = makeOV()
    if obj is not None:
        ov.obj = <PyObject *>obj

    rc = WSARecvFrom(s, &ws_buf, 1, &bytes, &flags, fromaddr, &fromlen, <OVERLAPPED *>ov, NULL)

    if rc == SOCKET_ERROR:
        rc = WSAGetLastError()
        if rc != ERROR_IO_PENDING:
            return rc, 0

    Py_XINCREF(obj)
    return rc, bytes

