#include <Python.h>
#include <windows.h>
#include "structmember.h"

PyObject *gConnectionLost;
PyObject *gFailure;

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
    PyObject *failure = NULL, *tm, *handle, *deferred, *ret;
    DWORD bytes;
    ULONG_PTR key;
    OVERLAPPED *ov;
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
    }
    res = GetQueuedCompletionStatus(self->iocp, &bytes, &key, &ov, timeout);
    if(!res) {
        err = GetLastError();
        if(!ov) {
            if(err != WAIT_TIMEOUT) {
                return PyErr_SetFromWindowsErr(err);
            } else {
                return Py_BuildValue("");
            }
        } else {
            // omg kids don't try this at home
            if(!bytes) {
                PyErr_SetString(gConnectionLost, "Connection lost");
            } else {
                PyErr_SetFromWindowsErr(err);
            }
            failure = PyObject_CallFunction(gFailure, NULL);
            if(!failure) { // I've no idea what happens ifFailure() raises an exception
                return NULL;
            }
            PyErr_Clear();
        }
    }
    // At this point, ov is non-NULL
    handle = PyInt_FromLong((long)ov); // XXX: treating pointer as a long
    deferred = PyDict_GetItem(self->cur_ops, handle);
    Py_DECREF(handle);
    if(deferred == NULL) {
        Py_XDECREF(failure);
        PyErr_SetFormat(PyExc_RuntimeError, "Spurious completion message with ov=%p", ov);
        return NULL;
    }
    if(failure) {
        ret = PyObject_CallMethod(deferred, "errback", "O", failure);
        if(!ret) {
            Py_DECREF(failure);
}

static PyMethodDef iocpcore_methods[] = {
    {"doIteration", (PyCFunction)iocpcore_doIteration, METH_VARARGS,
     "Perform one event loop iteration"},
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
    PyObject *m, *main, *dict;
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

    m = PyImport_ImportModule("twisted.internet.error");
    if(!m) {
        return;
    }
    gConnectionLost = PyObject_GetAttrString(m, "ConnectionLost");
    if(!gConnectionLost) {
        return;
    }

    m = PyImport_ImportModule("twisted.python.failure");
    if(!m) {
        return;
    }
    gFailure = PyObject_GetAttrString(m, "Failure");
    if(!gFailure) {
        return;
    }
}

