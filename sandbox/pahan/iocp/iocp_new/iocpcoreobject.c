#include <Python.h>
#include <winsock2.h>
#include <mswsock.h>
#include <windows.h>
#include "structmember.h"

typedef struct {
    OVERLAPPED ov;
    PyObject *callback;
} MyOVERLAPPED;

typedef struct {
    PyObject_HEAD
    PyObject *cur_ops;
    HANDLE iocp;
} iocpcore;

static void
iocpcore_dealloc(iocpcore* self)
{
    PyDict_Clear(self->cur_ops);
    Py_DECREF(self->cur_ops);
    CloseHandle(self->iocp);
    self->ob_type->tp_free((PyObject*)self);
}

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
        self->cur_ops = PyDict_New();
        if(!self->cur_ops) {
            CloseHandle(self->iocp);
            Py_DECREF(self);
            return NULL;
        }
    }
    return (PyObject *)self;
}

/*
static int
iocpcore_init(iocpcore *self, PyObject *args, PyObject *kwds)
{
    PyObject *first=NULL, *last=NULL;

    static char *kwlist[] = {"first", "last", "number", NULL};

    if(! PyArg_ParseTupleAndKeywords(args, kwds, "|OOi", kwlist, 
                                      &first, &last, 
                                      &self->number))
        return -1; 

    if(first) {
        Py_DECREF(self->first);
        Py_INCREF(first);
        self->first = first;
    }

    if(last) {
        Py_DECREF(self->last);
        Py_INCREF(last);
        self->last = last;
    }

    return 0;
}
*/

/*static PyMemberDef iocpcore_members[] = {
    {"number", T_INT, offsetof(iocpcore, number), 0,
     "noddy number"},
    {NULL}
};*/

/*
static PyObject *
iocpcore_getfirst(iocpcore *self, void *closure)
{
    Py_INCREF(self->first);
    return self->first;
}

static int
iocpcore_setfirst(iocpcore *self, PyObject *value, void *closure)
{
  if(!value) {
    PyErr_SetString(PyExc_TypeError, "Cannot delete the first attribute");
    return -1;
  }
  
  if(! PyString_Check(value)) {
    PyErr_SetString(PyExc_TypeError, 
                    "The first attribute value must be a string");
    return -1;
  }
      
  Py_DECREF(self->first);
  Py_INCREF(value);
  self->first = value;    

  return 0;
}

static PyObject *
iocpcore_getlast(iocpcore *self, void *closure)
{
    Py_INCREF(self->last);
    return self->last;
}

static int
iocpcore_setlast(iocpcore *self, PyObject *value, void *closure)
{
  if(!value) {
    PyErr_SetString(PyExc_TypeError, "Cannot delete the last attribute");
    return -1;
  }
  
  if(! PyString_Check(value)) {
    PyErr_SetString(PyExc_TypeError, 
                    "The last attribute value must be a string");
    return -1;
  }
      
  Py_DECREF(self->last);
  Py_INCREF(value);
  self->last = value;    

  return 0;
}*/

/*static PyGetSetDef iocpcore_getseters[] = {
    {"first", 
     (getter)iocpcore_getfirst, (setter)iocpcore_setfirst,
     "first name",
     NULL},
    {"last", 
     (getter)iocpcore_getlast, (setter)iocpcore_setlast,
     "last name",
     NULL},
    {NULL}
};*/

static PyObject *iocpcore_doIteration(iocpcore* self, PyObject *args) {
    long timeout;
    PyObject *tm, *ret, *object;
    DWORD bytes;
    unsigned long key;
    MyOVERLAPPED *ov;
    int res, err;
    if(!PyArg_ParseTuple(args, "O", &tm)) {
        return NULL;
    }
    if(tm == Py_None) {
        timeout = INFINITE;
    } else if(PyFloat_Check(tm)) {
        timeout = (int)(PyFloat_AsDouble(tm) * 1000);
    } else {
        PyErr_SetString(PyExc_TypeError, "Wrong type for timeout parameter");
        return NULL;
    }
    Py_BEGIN_ALLOW_THREADS;
    res = GetQueuedCompletionStatus(self->iocp, &bytes, &key, (OVERLAPPED**)&ov, timeout);
    Py_END_ALLOW_THREADS;
    printf("gqcs returned %d\n", res);
    err = GetLastError();
    printf("    GLE returned %d\n", err);
    if(!res) {
        if(!ov) {
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
    if(object) {
        // this is retarded. GQCS only sets error value if it wasn't succesful
        // (what about forth case, when handle is closed?)
        if(res) {
            err = 0;
        }
        ret = PyObject_CallFunction(object, "ll", err, bytes);
        if(!ret) {
            return NULL;
        }
        Py_DECREF(ret);
        Py_DECREF(object);
    }
    free(ov);
    return Py_BuildValue("");
}

static PyObject *iocpcore_WriteFile(iocpcore* self, PyObject *args) {
    HANDLE handle;
    char *buf;
    int buflen, res, len = -1;
    DWORD err, bytes;
    PyObject *object;
    MyOVERLAPPED *ov;
    if(!PyArg_ParseTuple(args, "lt#O|l", &handle, &buf, &buflen, &object, &len)) {
        return NULL;
    }
    if(len == -1) {
        len = buflen;
    }
    if(len <= 0 || len > buflen) {
        PyErr_SetString(PyExc_ValueError, "Invalid length specified");
    }
    if(!PyCallable_Check(object)) {
        PyErr_SetString(PyExc_TypeError, "Callback must be callable");
    }
    ov = malloc(sizeof(MyOVERLAPPED));
    if(!ov) {
        PyErr_NoMemory();
        return NULL;
    }
    memset(ov, 0, sizeof(MyOVERLAPPED));
    Py_INCREF(object);
    ov->callback = object;
    CreateIoCompletionPort(handle, self->iocp, 0, 1);
    printf("calling WriteFile(%d, %p, %d, %p, %p)\n", handle, buf, len, &bytes, ov);
    Py_BEGIN_ALLOW_THREADS;
    res = WriteFile(handle, buf, len, &bytes, (OVERLAPPED *)ov);
    Py_END_ALLOW_THREADS;
    err = GetLastError();
    printf("    wf returned %d, err %d\n", res, err);
    if(!res && err != ERROR_IO_PENDING) {
        return PyErr_SetFromWindowsErr(err);
    }
    return Py_BuildValue("ll", err, bytes);
}

static PyObject *iocpcore_ReadFile(iocpcore* self, PyObject *args) {
    HANDLE handle;
    char *buf;
    int buflen, res, len = -1;
    DWORD err, bytes;
    PyObject *object;
    MyOVERLAPPED *ov;
    if(!PyArg_ParseTuple(args, "lw#O|l", &handle, &buf, &buflen, &object, &len)) {
        return NULL;
    }
    if(len == -1) {
        len = buflen;
    }
    if(len <= 0 || len > buflen) {
        PyErr_SetString(PyExc_ValueError, "Invalid length specified");
    }
    if(!PyCallable_Check(object)) {
        PyErr_SetString(PyExc_TypeError, "Callback must be callable");
    }
    ov = malloc(sizeof(MyOVERLAPPED));
    if(!ov) {
        PyErr_NoMemory();
        return NULL;
    }
    memset(ov, 0, sizeof(MyOVERLAPPED));
    Py_INCREF(object);
    ov->callback = object;
    CreateIoCompletionPort(handle, self->iocp, 0, 1);
    Py_BEGIN_ALLOW_THREADS;
    res = ReadFile(handle, buf, len, &bytes, (OVERLAPPED *)ov);
    Py_END_ALLOW_THREADS;
    err = GetLastError();
    if(!res && err != ERROR_IO_PENDING) {
        return PyErr_SetFromWindowsErr(err);
    }
    return Py_BuildValue("ll", err, bytes);
}

static PyObject *iocpcore_WSARecv(iocpcore* self, PyObject *args) {
    SOCKET handle;
    char *buf;
    int buflen, res, len = -1;
    DWORD bytes, err, flags;
    PyObject *object;
    MyOVERLAPPED *ov;
    WSABUF wbuf;
    if(!PyArg_ParseTuple(args, "lw#O|ll", &handle, &buf, &buflen, &object, &len, &flags)) {
        return NULL;
    }
    if(len == -1) {
        len = buflen;
    }
    if(len <= 0 || len > buflen) {
        PyErr_SetString(PyExc_ValueError, "Invalid length specified");
    }
    if(!PyCallable_Check(object)) {
        PyErr_SetString(PyExc_TypeError, "Callback must be callable");
    }
    ov = malloc(sizeof(MyOVERLAPPED));
    if(!ov) {
        PyErr_NoMemory();
        return NULL;
    }
    memset(ov, 0, sizeof(MyOVERLAPPED));
    Py_INCREF(object);
    ov->callback = object;
    wbuf.len = len;
    wbuf.buf = buf;
    CreateIoCompletionPort((HANDLE)handle, self->iocp, 0, 1);
    Py_BEGIN_ALLOW_THREADS;
    res = WSARecv(handle, &wbuf, 1, &bytes, &flags, (OVERLAPPED *)ov, NULL);
    Py_END_ALLOW_THREADS;
    err = GetLastError();
    if(res == SOCKET_ERROR && err != ERROR_IO_PENDING) {
        return PyErr_SetFromWindowsErr(err);
    }
    return Py_BuildValue("ll", err, bytes);
}

static PyObject *iocpcore_WSASend(iocpcore* self, PyObject *args) {
    SOCKET handle;
    char *buf;
    int buflen, res, len = -1;
    DWORD bytes, err, flags;
    PyObject *object;
    MyOVERLAPPED *ov;
    WSABUF wbuf;
    if(!PyArg_ParseTuple(args, "lt#O|ll", &handle, &buf, &buflen, &object, &len, &flags)) {
        return NULL;
    }
    if(len == -1) {
        len = buflen;
    }
    if(len <= 0 || len > buflen) {
        PyErr_SetString(PyExc_ValueError, "Invalid length specified");
    }
    if(!PyCallable_Check(object)) {
        PyErr_SetString(PyExc_TypeError, "Callback must be callable");
    }
    ov = malloc(sizeof(MyOVERLAPPED));
    if(!ov) {
        PyErr_NoMemory();
        return NULL;
    }
    memset(ov, 0, sizeof(MyOVERLAPPED));
    Py_INCREF(object);
    ov->callback = object;
    wbuf.len = len;
    wbuf.buf = buf;
    CreateIoCompletionPort((HANDLE)handle, self->iocp, 0, 1);
    Py_BEGIN_ALLOW_THREADS;
    res = WSASend(handle, &wbuf, 1, &bytes, flags, (OVERLAPPED *)ov, NULL);
    Py_END_ALLOW_THREADS;
    err = GetLastError();
    if(res == SOCKET_ERROR && err != ERROR_IO_PENDING) {
        return PyErr_SetFromWindowsErr(err);
    }
    return Py_BuildValue("ll", err, bytes);
}

static PyObject *iocpcore_AcceptEx(iocpcore* self, PyObject *args) {
    SOCKET handle, list;
    char *buf;
    int buflen, res, len = -1;
    DWORD bytes, err, flags;
    PyObject *object;
    MyOVERLAPPED *ov;
    if(!PyArg_ParseTuple(args, "llt#O|ll", &handle, &list, &buf, &buflen, &object, &len, &flags)) {
        return NULL;
    }
    if(len == -1) {
        len = buflen;
    }
    if(len <= 0 || len > buflen) {
        PyErr_SetString(PyExc_ValueError, "Invalid length specified");
    }
    if(!PyCallable_Check(object)) {
        PyErr_SetString(PyExc_TypeError, "Callback must be callable");
    }
    ov = malloc(sizeof(MyOVERLAPPED));
    if(!ov) {
        PyErr_NoMemory();
        return NULL;
    }
    memset(ov, 0, sizeof(MyOVERLAPPED));
    Py_INCREF(object);
    ov->callback = object;
    CreateIoCompletionPort((HANDLE)handle, self->iocp, 0, 1);
    Py_BEGIN_ALLOW_THREADS;
    // TODO: what the comments in ops.AcceptExOp say
    res = AcceptEx(handle, list, buf, 0, len/2, len/2, &bytes, (OVERLAPPED *)ov);
    Py_END_ALLOW_THREADS;
    err = GetLastError();
    if(!res && err != ERROR_IO_PENDING) {
        return PyErr_SetFromWindowsErr(err);
    }
    return Py_BuildValue("ll", err, bytes);
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
    {"issueWSARecv", (PyCFunction)iocpcore_WSARecv, METH_VARARGS,
     "Issue an overlapped WSARecv operation"},
    {"issueWSASend", (PyCFunction)iocpcore_WSASend, METH_VARARGS,
     "Issue an overlapped WSASend operation"},
    {"issueAcceptEx", (PyCFunction)iocpcore_AcceptEx, METH_VARARGS,
     "Issue an overlapped AcceptEx operation"},
    {"AllocateReadBuffer", (PyCFunction)iocpcore_AllocateReadBuffer, METH_VARARGS,
     "Allocate a buffer to read into"},
    {NULL}
};

static PyTypeObject iocpcoreType = {
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "iocpcore.iocpcore",             /*tp_name*/
    sizeof(iocpcore),             /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)iocpcore_dealloc, /*tp_dealloc*/
    0,                         /*tp_print*/
    0,                         /*tp_getattr*/
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
    "core functionality for IOCP reactor",           /* tp_doc */
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
initiocpcore(void) 
{
    PyObject *m;
    if(PyType_Ready(&iocpcoreType) < 0) {
        return;
    }

    m = Py_InitModule3("iocpcore", module_methods,
                       "core functionality for IOCP reactor");

    if(!m) {
        return;
    }

    Py_INCREF(&iocpcoreType);
    PyModule_AddObject(m, "iocpcore", (PyObject *)&iocpcoreType);
}

