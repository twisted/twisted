#include <Python.h>
#include <winsock2.h>
#include <mswsock.h>
#include <windows.h>
#include "structmember.h"

//#define SPEW
// compensate for mingw's lack of recent Windows headers
#ifndef _MSC_VER
#define WSAID_CONNECTEX {0x25a207b9,0xddf3,0x4660,{0x8e,0xe9,0x76,0xe5,0x8c,0x74,0x06,0x3e}}
#define WSAID_ACCEPTEX {0xb5367df1,0xcbac,0x11cf,{0x95,0xca,0x00,0x80,0x5f,0x48,0xa1,0x92}}

typedef
BOOL
(PASCAL FAR * LPFN_CONNECTEX) (
    IN SOCKET s,
    IN const struct sockaddr FAR *name,
    IN int namelen,
    IN PVOID lpSendBuffer OPTIONAL,
    IN DWORD dwSendDataLength,
    OUT LPDWORD lpdwBytesSent,
    IN LPOVERLAPPED lpOverlapped
    );

typedef
BOOL
(PASCAL FAR * LPFN_ACCEPTEX)(
    IN SOCKET sListenSocket,
    IN SOCKET sAcceptSocket,
    IN PVOID lpOutputBuffer,
    IN DWORD dwReceiveDataLength,
    IN DWORD dwLocalAddressLength,
    IN DWORD dwRemoteAddressLength,
    OUT LPDWORD lpdwBytesReceived,
    IN LPOVERLAPPED lpOverlapped
    );
#endif

typedef struct {
    int size;
    char buffer[0];
} AddrBuffer;

LPFN_CONNECTEX gConnectEx;
LPFN_ACCEPTEX gAcceptEx;

typedef struct {
    OVERLAPPED ov;
    PyObject *callback;
    PyObject *callback_arg;
} MyOVERLAPPED;

typedef struct {
    PyObject_HEAD
//    PyObject *cur_ops;
    HANDLE iocp;
} iocpcore;

void CALLBACK dummy_completion(DWORD err, DWORD bytes, OVERLAPPED *ov, DWORD flags) {
}

static void
iocpcore_dealloc(iocpcore *self)
{
//    PyDict_Clear(self->cur_ops);
//    Py_DECREF(self->cur_ops);
    CloseHandle(self->iocp);
    self->ob_type->tp_free((PyObject*)self);
}

/*
static PyObject *
iocpcore_getattr(iocpcore *self, char *name) {
    if(!strcmp(name, "have_connectex
}
*/

static PyObject *
iocpcore_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    iocpcore *self;

    self = (iocpcore *)type->tp_alloc(type, 0);
    if(self != NULL) {
        self->iocp = CreateIoCompletionPort(INVALID_HANDLE_VALUE, NULL, 0, 1);
        if(!self->iocp) {
            Py_DECREF(self);
            return PyErr_SetFromWindowsErr(0);
        }
//        self->cur_ops = PyDict_New();
//        if(!self->cur_ops) {
//            CloseHandle(self->iocp);
//            Py_DECREF(self);
//            return NULL;
//        }
    }
    return (PyObject *)self;
}

static PyObject *iocpcore_doIteration(iocpcore* self, PyObject *args) {
    long timeout;
    double ftimeout;
    PyObject *tm, *ret, *object, *object_arg;
    DWORD bytes;
    unsigned long key;
    MyOVERLAPPED *ov;
    int res, err;
    if(!PyArg_ParseTuple(args, "d", &ftimeout)) {
        PyErr_Clear();
        if(!PyArg_ParseTuple(args, "O", &tm)) {
            return NULL;
        }
        if(tm == Py_None) {
            timeout = INFINITE;
        } else {
            PyErr_SetString(PyExc_TypeError, "Wrong timeout argument");
            return NULL;
        }
    } else {
        timeout = (int)(ftimeout * 1000);
    }
    Py_BEGIN_ALLOW_THREADS;
    res = GetQueuedCompletionStatus(self->iocp, &bytes, &key, (OVERLAPPED**)&ov, timeout);
    Py_END_ALLOW_THREADS;
#ifdef SPEW
    printf("gqcs returned res %d, ov 0x%p\n", res, ov);
#endif
    err = GetLastError();
#ifdef SPEW
    printf("    GLE returned %d\n", err);
#endif
    if(!res) {
        if(!ov) {
#ifdef SPEW
            printf("gqcs returned NULL ov\n");
#endif
            if(err != WAIT_TIMEOUT) {
                return PyErr_SetFromWindowsErr(err);
            } else {
                return Py_BuildValue("");
            }
        }
    }
    // At this point, ov is non-NULL
    // steal its reference, then clobber it to death! I mean free it!
    object = ov->callback;
    object_arg = ov->callback_arg;
    if(object) {
        // this is retarded. GQCS only sets error value if it wasn't succesful
        // (what about forth case, when handle is closed?)
        if(res) {
            err = 0;
        }
#ifdef SPEW
        printf("calling callback with err %d, bytes %ld\n", err, bytes);
#endif
        ret = PyObject_CallFunction(object, "llO", err, bytes, object_arg);
        if(!ret) {
            Py_DECREF(object);
            PyMem_Free(ov);
            return NULL;
        }
        Py_DECREF(ret);
        Py_DECREF(object);
    }
    PyMem_Free(ov);
    return Py_BuildValue("");
}

static PyObject *iocpcore_WriteFile(iocpcore* self, PyObject *args) {
    HANDLE handle;
    char *buf;
    int buflen, res;
    DWORD err, bytes;
    PyObject *object, *object_arg;
    MyOVERLAPPED *ov;
//    LARGE_INTEGER time, time_after;
//    QueryPerformanceCounter(&time);
    if(!PyArg_ParseTuple(args, "lt#OO", &handle, &buf, &buflen, &object, &object_arg)) {
        return NULL;
    }
    if(buflen <= 0) {
        PyErr_SetString(PyExc_ValueError, "Invalid length specified");
        return NULL;
    }
    if(!PyCallable_Check(object)) {
        PyErr_SetString(PyExc_TypeError, "Callback must be callable");
        return NULL;
    }
    ov = PyMem_Malloc(sizeof(MyOVERLAPPED));
    if(!ov) {
        PyErr_NoMemory();
        return NULL;
    }
    memset(ov, 0, sizeof(MyOVERLAPPED));
    Py_INCREF(object);
    Py_INCREF(object_arg);
    ov->callback = object;
    ov->callback_arg = object_arg;
    CreateIoCompletionPort(handle, self->iocp, 0, 1);
#ifdef SPEW
    printf("calling WriteFile(%p, 0x%p, %d, 0x%p, 0x%p)\n", handle, buf, buflen, &bytes, ov);
#endif
    Py_BEGIN_ALLOW_THREADS;
    res = WriteFile(handle, buf, buflen, &bytes, (OVERLAPPED *)ov);
    Py_END_ALLOW_THREADS;
    err = GetLastError();
#ifdef SPEW
    printf("    wf returned %d, err %ld\n", res, err);
#endif
    if(!res && err != ERROR_IO_PENDING) {
        Py_DECREF(object);
        Py_DECREF(object_arg);
        PyMem_Free(ov);
        return PyErr_SetFromWindowsErr(err);
    }
    if(res) {
        err = 0;
    }
//    QueryPerformanceCounter(&time_after);
//    printf("wf total ticks is %ld", time_after.LowPart - time.LowPart);
    return Py_BuildValue("ll", err, bytes);
}

static PyObject *iocpcore_ReadFile(iocpcore* self, PyObject *args) {
    HANDLE handle;
    char *buf;
    int buflen, res;
    DWORD err, bytes;
    PyObject *object, *object_arg;
    MyOVERLAPPED *ov;
//    LARGE_INTEGER time, time_after;
//    QueryPerformanceCounter(&time);
    if(!PyArg_ParseTuple(args, "lw#OO", &handle, &buf, &buflen, &object, &object_arg)) {
        return NULL;
    }
    if(buflen <= 0) {
        PyErr_SetString(PyExc_ValueError, "Invalid length specified");
        return NULL;
    }
    if(!PyCallable_Check(object)) {
        PyErr_SetString(PyExc_TypeError, "Callback must be callable");
        return NULL;
    }
    ov = PyMem_Malloc(sizeof(MyOVERLAPPED));
    if(!ov) {
        PyErr_NoMemory();
        return NULL;
    }
    memset(ov, 0, sizeof(MyOVERLAPPED));
    Py_INCREF(object);
    Py_INCREF(object_arg);
    ov->callback = object;
    ov->callback_arg = object_arg;
    CreateIoCompletionPort(handle, self->iocp, 0, 1);
#ifdef SPEW
    printf("calling ReadFile(%p, 0x%p, %d, 0x%p, 0x%p)\n", handle, buf, buflen, &bytes, ov);
#endif
    Py_BEGIN_ALLOW_THREADS;
    res = ReadFile(handle, buf, buflen, &bytes, (OVERLAPPED *)ov);
    Py_END_ALLOW_THREADS;
    err = GetLastError();
#ifdef SPEW
    printf("    rf returned %d, err %ld\n", res, err);
#endif
    if(!res && err != ERROR_IO_PENDING) {
        Py_DECREF(object);
        Py_DECREF(object_arg);
        PyMem_Free(ov);
        return PyErr_SetFromWindowsErr(err);
    }
    if(res) {
        err = 0;
    }
//    QueryPerformanceCounter(&time_after);
//    printf("rf total ticks is %ld", time_after.LowPart - time.LowPart);
    return Py_BuildValue("ll", err, bytes);
}

// yay, rape'n'paste of getsockaddrarg from socketmodule.c. "I couldn't understand what it does, so I removed it!"
static int makesockaddr(int sock_family, PyObject *args, struct sockaddr **addr_ret, int *len_ret)
{
    switch (sock_family) {
    case AF_INET:
    {
        struct sockaddr_in* addr;
        char *host;
        int port;
        unsigned long result;
        if(!PyTuple_Check(args)) {
            PyErr_Format(PyExc_TypeError, "AF_INET address must be tuple, not %.500s", args->ob_type->tp_name);
            return 0;
        }
        if(!PyArg_ParseTuple(args, "si", &host, &port)) {
            return 0;
        }
        addr = PyMem_Malloc(sizeof(struct sockaddr_in));
        result = inet_addr(host);
        if(result == -1) {
            PyMem_Free(addr);
            PyErr_SetString(PyExc_ValueError, "Can't parse ip address string");
            return 0;
        }
#ifdef SPEW
        printf("makesockaddr setting addr, %lu, %d, %hu\n", result, AF_INET, htons((short)port));
#endif
        addr->sin_addr.s_addr = result;
        addr->sin_family = AF_INET;
        addr->sin_port = htons((short)port);
        *addr_ret = (struct sockaddr *) addr;
        *len_ret = sizeof *addr;
        return 1;
    }
    default:
        PyErr_SetString(PyExc_ValueError, "bad family");
        return 0;
    }
}

static PyObject *iocpcore_WSASendTo(iocpcore* self, PyObject *args) {
    HANDLE handle;
    char *buf;
    int buflen, res, family, addrlen;
    DWORD err, bytes, flags = 0;
    PyObject *object, *object_arg, *address;
    MyOVERLAPPED *ov;
    WSABUF wbuf;
    struct sockaddr *addr;
//    LARGE_INTEGER time, time_after;
//    QueryPerformanceCounter(&time);
    if(!PyArg_ParseTuple(args, "lt#iOOO", &handle, &buf, &buflen, &family, &address, &object, &object_arg)) {
        return NULL;
    }
    if(buflen <= 0) {
        PyErr_SetString(PyExc_ValueError, "Invalid length specified");
        return NULL;
    }
    if(!makesockaddr(family, address, &addr, &addrlen)) {
        return NULL;
    }
    if(!PyCallable_Check(object)) {
        PyErr_SetString(PyExc_TypeError, "Callback must be callable");
        return NULL;
    }
    ov = PyMem_Malloc(sizeof(MyOVERLAPPED));
    if(!ov) {
        PyErr_NoMemory();
        return NULL;
    }
    memset(ov, 0, sizeof(MyOVERLAPPED));
    Py_INCREF(object);
    Py_INCREF(object_arg);
    ov->callback = object;
    ov->callback_arg = object_arg;
    wbuf.len = buflen;
    wbuf.buf = buf;
    CreateIoCompletionPort(handle, self->iocp, 0, 1);
#ifdef SPEW
    printf("calling WSASendTo(%d, 0x%p, %d, 0x%p, %ld, 0x%p, %d, 0x%p, 0x%p)\n", handle, &wbuf, 1, &bytes, flags, addr, addrlen, ov, NULL);
#endif
    Py_BEGIN_ALLOW_THREADS;
    res = WSASendTo((SOCKET)handle, &wbuf, 1, &bytes, flags, addr, addrlen, (OVERLAPPED *)ov, NULL);
    Py_END_ALLOW_THREADS;
    err = GetLastError();
#ifdef SPEW
    printf("    wst returned %d, err %ld\n", res, err);
#endif
    if(res == SOCKET_ERROR && err != ERROR_IO_PENDING) {
        Py_DECREF(object);
        Py_DECREF(object_arg);
        PyMem_Free(ov);
        return PyErr_SetFromWindowsErr(err);
    }
    if(!res) {
        err = 0;
    }
//    QueryPerformanceCounter(&time_after);
//    printf("st total ticks is %ld", time_after.LowPart - time.LowPart);
    return Py_BuildValue("ll", err, bytes);
}

static PyObject *iocpcore_WSARecvFrom(iocpcore* self, PyObject *args) {
    HANDLE handle;
    char *buf;
    int buflen, res, ablen;
    DWORD err, bytes, flags = 0;
    PyObject *object, *object_arg;
    MyOVERLAPPED *ov;
    WSABUF wbuf;
    AddrBuffer *ab;
//    LARGE_INTEGER time, time_after;
//    QueryPerformanceCounter(&time);
    if(!PyArg_ParseTuple(args, "lw#w#OO", &handle, &buf, &buflen, &ab, &ablen, &object, &object_arg)) {
        return NULL;
    }
    if(buflen <= 0) {
        PyErr_SetString(PyExc_ValueError, "Invalid length specified");
        return NULL;
    }
    if(ablen < sizeof(int)+sizeof(struct sockaddr)) {
        PyErr_SetString(PyExc_ValueError, "Address buffer too small");
        return NULL;
    }
    if(!PyCallable_Check(object)) {
        PyErr_SetString(PyExc_TypeError, "Callback must be callable");
        return NULL;
    }
    ov = PyMem_Malloc(sizeof(MyOVERLAPPED));
    if(!ov) {
        PyErr_NoMemory();
        return NULL;
    }
    memset(ov, 0, sizeof(MyOVERLAPPED));
    Py_INCREF(object);
    Py_INCREF(object_arg);
    ov->callback = object;
    ov->callback_arg = object_arg;
    wbuf.len = buflen;
    wbuf.buf = buf;
    ab->size = ablen;
    CreateIoCompletionPort(handle, self->iocp, 0, 1);
#ifdef SPEW
    printf("calling WSARecvFrom(%d, 0x%p, %d, 0x%p, 0x%p, 0x%p, 0x%p, 0x%p, 0x%p)\n", handle, &wbuf, 1, &bytes, &flags, (struct sockaddr *)ab->buffer, &ab->size, ov, NULL);
#endif
    Py_BEGIN_ALLOW_THREADS;
    res = WSARecvFrom((SOCKET)handle, &wbuf, 1, &bytes, &flags, (struct sockaddr *)ab->buffer, &ab->size, (OVERLAPPED *)ov, NULL);
    Py_END_ALLOW_THREADS;
    err = GetLastError();
#ifdef SPEW
    printf("    wrf returned %d, err %ld\n", res, err);
#endif
    if(res == SOCKET_ERROR && err != ERROR_IO_PENDING) {
        Py_DECREF(object);
        Py_DECREF(object_arg);
        PyMem_Free(ov);
        return PyErr_SetFromWindowsErr(err);
    }
    if(!res) {
        err = 0;
    }
//    QueryPerformanceCounter(&time_after);
//    printf("wrf total ticks is %ld", time_after.LowPart - time.LowPart);
    return Py_BuildValue("ll", err, bytes);
}

// rape'n'paste from socketmodule.c
static PyObject *parsesockaddr(struct sockaddr *addr, int addrlen)
{
    PyObject *ret = NULL;
    if (addrlen == 0) {
        /* No address -- may be recvfrom() from known socket */
        Py_INCREF(Py_None);
        return Py_None;
    }

    switch (addr->sa_family) {
    case AF_INET:
    {
        struct sockaddr_in *a = (struct sockaddr_in *)addr;
        char *s;
        s = inet_ntoa(a->sin_addr);
        if (s) {
            ret = Py_BuildValue("si", s, ntohs(a->sin_port));
        } else {
            PyErr_SetString(PyExc_ValueError, "Invalid AF_INET address");
        }
        return ret;
    }
    default:
        /* If we don't know the address family, don't raise an
           exception -- return it as a tuple. */
        return Py_BuildValue("is#",
                     addr->sa_family,
                     addr->sa_data,
                     sizeof(addr->sa_data));

    }
}

static PyObject *iocpcore_interpretAB(iocpcore* self, PyObject *args) {
    char *buf;
    int len;
    AddrBuffer *ab;
    if(!PyArg_ParseTuple(args, "t#", &buf, &len)) {
        return NULL;
    }
    ab = (AddrBuffer *)buf;
    return parsesockaddr((struct sockaddr *)(ab->buffer), ab->size);
}

static PyObject *iocpcore_getsockinfo(iocpcore* self, PyObject *args) {
    SOCKET handle;
    WSAPROTOCOL_INFO pinfo;
    int size = sizeof(pinfo), res;
    if(!PyArg_ParseTuple(args, "l", &handle)) {
        return NULL;
    }
    res = getsockopt(handle, SOL_SOCKET, SO_PROTOCOL_INFO, (char *)&pinfo, &size);
    if(res == SOCKET_ERROR) {
        return PyErr_SetFromWindowsErr(0);
    }
    return Py_BuildValue("iiii", pinfo.iMaxSockAddr, pinfo.iAddressFamily, pinfo.iSocketType, pinfo.iProtocol);
}

static PyObject *iocpcore_AcceptEx(iocpcore* self, PyObject *args) {
    SOCKET handle, acc_sock;
    char *buf;
    int buflen, res;
    DWORD bytes, err;
    PyObject *object, *object_arg;
    MyOVERLAPPED *ov;
    if(!PyArg_ParseTuple(args, "llOOw#", &handle, &acc_sock, &object, &object_arg, &buf, &buflen)) {
        return NULL;
    }
    if(!PyCallable_Check(object)) {
        PyErr_SetString(PyExc_TypeError, "Callback must be callable");
        return NULL;
    }
    ov = PyMem_Malloc(sizeof(MyOVERLAPPED));
    if(!ov) {
        PyErr_NoMemory();
        return NULL;
    }
    memset(ov, 0, sizeof(MyOVERLAPPED));
    Py_INCREF(object);
    Py_INCREF(object_arg);
    ov->callback = object;
    ov->callback_arg = object_arg;
    CreateIoCompletionPort((HANDLE)handle, self->iocp, 0, 1);
#ifdef SPEW
    printf("calling AcceptEx(%d, %d, 0x%p, %d, %d, %d, 0x%p, 0x%p)\n", handle, acc_sock, buf, 0, buflen/2, buflen/2, &bytes, ov);
#endif
    Py_BEGIN_ALLOW_THREADS;
    res = gAcceptEx(handle, acc_sock, buf, 0, buflen/2, buflen/2, &bytes, (OVERLAPPED *)ov);
    Py_END_ALLOW_THREADS;
    err = WSAGetLastError();
#ifdef SPEW
    printf("    ae returned %d, err %ld\n", res, err);
#endif
    if(!res && err != ERROR_IO_PENDING) {
        Py_DECREF(object);
        Py_DECREF(object_arg);
        PyMem_Free(ov);
        return PyErr_SetFromWindowsErr(err);
    }
    if(res) {
        err = 0;
    }
    return Py_BuildValue("ll", err, 0);
}

static PyObject *iocpcore_ConnectEx(iocpcore* self, PyObject *args) {
    SOCKET handle;
    int res, addrlen, family;
    DWORD err;
    PyObject *object, *object_arg, *address;
    MyOVERLAPPED *ov;
    struct sockaddr *addr;
    if(!PyArg_ParseTuple(args, "liOOO", &handle, &family, &address, &object, &object_arg)) {
        return NULL;
    }
    if(!makesockaddr(family, address, &addr, &addrlen)) {
        return NULL;
    }
    if(!PyCallable_Check(object)) {
        PyErr_SetString(PyExc_TypeError, "Callback must be callable");
        return NULL;
    }
    ov = PyMem_Malloc(sizeof(MyOVERLAPPED));
    if(!ov) {
        PyErr_NoMemory();
        return NULL;
    }
    memset(ov, 0, sizeof(MyOVERLAPPED));
    Py_INCREF(object);
    Py_INCREF(object_arg);
    ov->callback = object;
    ov->callback_arg = object_arg;
    CreateIoCompletionPort((HANDLE)handle, self->iocp, 0, 1);
#ifdef SPEW
    printf("calling ConnectEx(%d, 0x%p, %d, 0x%p)\n", handle, addr, addrlen, ov);
#endif
    Py_BEGIN_ALLOW_THREADS;
    res = gConnectEx(handle, addr, addrlen, NULL, 0, NULL, (OVERLAPPED *)ov);
    Py_END_ALLOW_THREADS;
    PyMem_Free(addr);
    err = WSAGetLastError();
#ifdef SPEW
    printf("    ce returned %d, err %ld\n", res, err);
#endif
    if(!res && err != ERROR_IO_PENDING) {
        Py_DECREF(object);
        Py_DECREF(object_arg);
        PyMem_Free(ov);
        return PyErr_SetFromWindowsErr(err);
    }
    if(res) {
        err = 0;
    }
    return Py_BuildValue("ll", err, 0);
}

static PyObject *iocpcore_PostQueuedCompletionStatus(iocpcore* self, PyObject *args) {
    int res;
    DWORD err;
    PyObject *object, *object_arg;
    MyOVERLAPPED *ov;
    if(!PyArg_ParseTuple(args, "OO", &object, &object_arg)) {
        return NULL;
    }
    if(!PyCallable_Check(object)) {
        PyErr_SetString(PyExc_TypeError, "Callback must be callable");
        return NULL;
    }
    ov = PyMem_Malloc(sizeof(MyOVERLAPPED));
    if(!ov) {
        PyErr_NoMemory();
        return NULL;
    }
    memset(ov, 0, sizeof(MyOVERLAPPED));
    Py_INCREF(object);
    Py_INCREF(object_arg);
    ov->callback = object;
    ov->callback_arg = object_arg;
#ifdef SPEW
    printf("calling PostQueuedCompletionStatus(0x%p)\n", ov);
#endif
    Py_BEGIN_ALLOW_THREADS;
    res = PostQueuedCompletionStatus(self->iocp, 0, 0, (OVERLAPPED *)ov);
    Py_END_ALLOW_THREADS;
    err = WSAGetLastError();
#ifdef SPEW
    printf("    pqcs returned %d, err %ld\n", res, err);
#endif
    if(!res && err != ERROR_IO_PENDING) {
        Py_DECREF(object);
        Py_DECREF(object_arg);
        PyMem_Free(ov);
        return PyErr_SetFromWindowsErr(err);
    }
    if(res) {
        err = 0;
    }
    return Py_BuildValue("ll", err, 0);
}

PyObject *iocpcore_AllocateReadBuffer(PyObject *self, PyObject *args)
{
    int bufSize;
    if(!PyArg_ParseTuple(args, "i", &bufSize)) {
        return NULL;
    }
    return PyBuffer_New(bufSize);
}

static PyMethodDef iocpcore_methods[] = {
    {"doIteration", (PyCFunction)iocpcore_doIteration, METH_VARARGS,
     "Perform one event loop iteration"},
    {"issueWriteFile", (PyCFunction)iocpcore_WriteFile, METH_VARARGS,
     "Issue an overlapped WriteFile operation"},
    {"issueReadFile", (PyCFunction)iocpcore_ReadFile, METH_VARARGS,
     "Issue an overlapped ReadFile operation"},
    {"issueWSASendTo", (PyCFunction)iocpcore_WSASendTo, METH_VARARGS,
     "Issue an overlapped WSASendTo operation"},
    {"issueWSARecvFrom", (PyCFunction)iocpcore_WSARecvFrom, METH_VARARGS,
     "Issue an overlapped WSARecvFrom operation"},
    {"interpretAB", (PyCFunction)iocpcore_interpretAB, METH_VARARGS,
     "Interpret address buffer as returned by WSARecvFrom"},
    {"issueAcceptEx", (PyCFunction)iocpcore_AcceptEx, METH_VARARGS,
     "Issue an overlapped AcceptEx operation"},
    {"issueConnectEx", (PyCFunction)iocpcore_ConnectEx, METH_VARARGS,
     "Issue an overlapped ConnectEx operation"},
    {"issuePostQueuedCompletionStatus", (PyCFunction)iocpcore_PostQueuedCompletionStatus, METH_VARARGS,
     "Issue an overlapped PQCS operation"},
    {"getsockinfo", (PyCFunction)iocpcore_getsockinfo, METH_VARARGS,
     "Given a socket handle, retrieve its protocol info"},
    {"AllocateReadBuffer", (PyCFunction)iocpcore_AllocateReadBuffer, METH_VARARGS,
     "Allocate a buffer to read into"},
    {NULL}
};

static PyTypeObject iocpcoreType = {
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "_iocp.iocpcore",             /*tp_name*/
    sizeof(iocpcore),             /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)iocpcore_dealloc, /*tp_dealloc*/
    0,                         /*tp_print*/
//    (getattrfunc)iocpcore_getattr, /*tp_getattr*/
    0, /*tp_getattr*/
    0,                         /*tp_setattr*/
    0,                         /*tp_compare*/
    0,                         /*tp_repr*/
    0,                         /*tp_as_number*/
    0,                         /*tp_as_sequence*/
    0,                         /*tp_as_mapping*/
    0,                         /*tp_hash */
    0,                         /*tp_call*/
    0,                         /*tp_str*/
    0,                         /*tp_getattro*/
    0,                         /*tp_setattro*/
    0,                         /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE, /*tp_flags*/
    "core functionality for IOCP reactor", /* tp_doc */
    0,                         /* tp_traverse */
    0,                         /* tp_clear */
    0,                         /* tp_richcompare */
    0,                         /* tp_weaklistoffset */
    0,                         /* tp_iter */
    0,                         /* tp_iternext */
    iocpcore_methods,             /* tp_methods */
//    iocpcore_members,             /* tp_members */
    0,             /* tp_members */
//    iocpcore_getseters,           /* tp_getset */
    0,           /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
//    (initproc)iocpcore_init,      /* tp_init */
    0,      /* tp_init */
    0,                         /* tp_alloc */
    iocpcore_new,                 /* tp_new */
};

static PyMethodDef module_methods[] = {
    {NULL}  /* Sentinel */
};

#ifndef PyMODINIT_FUNC /* declarations for DLL import/export */
#define PyMODINIT_FUNC void
#endif
PyMODINIT_FUNC
init_iocp(void) 
{
    int have_connectex = 1;
    PyObject *m;
    GUID guid1 = WSAID_CONNECTEX; // should use one GUID variable, but oh well
    GUID guid2 = WSAID_ACCEPTEX;
    DWORD bytes, ret;
    SOCKET s;
    if(PyType_Ready(&iocpcoreType) < 0) {
        return;
    }
    m = PyImport_ImportModule("_socket"); // cause WSAStartup to get called
    if(!m) {
        return;
    }

    s = socket(AF_INET, SOCK_STREAM, 0);
    ret = WSAIoctl(s, SIO_GET_EXTENSION_FUNCTION_POINTER, &guid1, sizeof(GUID),
                   &gConnectEx, sizeof(gConnectEx), &bytes, NULL, NULL);
    if(ret == SOCKET_ERROR) {
        have_connectex = 0;
    }
    
    ret = WSAIoctl(s, SIO_GET_EXTENSION_FUNCTION_POINTER, &guid2, sizeof(GUID),
                   &gAcceptEx, sizeof(gAcceptEx), &bytes, NULL, NULL);
    if(ret == SOCKET_ERROR) {
        PyErr_SetFromWindowsErr(0);
        return;
    }

    closesocket(s);

    m = Py_InitModule3("_iocp", module_methods,
                       "core functionality for IOCP reactor");
    if(!m) {
        return;
    }

    ret = PyModule_AddIntConstant(m, "have_connectex", have_connectex);
    if(ret == -1) {
        return;
    }

    Py_INCREF(&iocpcoreType);
    PyModule_AddObject(m, "iocpcore", (PyObject *)&iocpcoreType);
}

