/* Python includes */
#include <Python.h>
#include <structmember.h>

/* System includes */
#include <sys/uio.h>

#define DEFAULT_NUM_VECTORS 32

typedef struct iovec IOVector;
typedef struct _IOVectors {
    size_t bytes;
    size_t size;
    /* index of first IOVector */
    int first;
    /* index _after_ last IOVector */
    int last;
    IOVector *vectors;
    PyObject **objects;
    struct _IOVectors* next;
} IOVectors;
    
/* Python wrapper around IOVectors */
typedef struct _PyIOVector {
    PyObject_HEAD
    IOVectors *head;
    IOVectors *tail;
    size_t bytes;     /* The total number of bytes in all the iovec structs */
} PyIOVector;

/* Create a new IOVectors object with size objects */
static IOVectors* IOVectors_New(size_t size);

/* Delete IOVectors object entirely */
static IOVectors* IOVectors_Del(IOVectors *v);

/* Add a string to the tail, return tail, obj is the owner if any */
/* If obj is NULL, then it is assumed you PyMem_New'ed this memory and expect
it to be reclaimed with PyMem_Del behind your back.
alloc_length is how big you want the next head to be if you need to make one */
static IOVectors* IOVectors_Add(IOVectors *tail, char *buf, size_t len, size_t alloc_length, PyObject* obj);

/* Remove BYTES from head, return head */
static IOVectors* IOVectors_Remove(IOVectors *head, size_t bytes);

/* Deallocate iovec storage for object */
static void IOVectors_Wipe(IOVectors *v);

/* Calculate the number of iovecs in an IOVectors linked list */
static int IOVectors_Length(IOVectors *v);

/* Calculate the length of the IOVectors linked list itself */
static int IOVectors_ListLength(IOVectors *v);

/* Make clean to be passed up as PyStrings */
/* -1 for err, >=0 for how many strings were created */
static int IOVectors_MakePyStrings(IOVectors *v);

/* Make a PyTuple out of the current element */
static PyObject* IOVectors_AsTuple(IOVectors *v);

/* Write to a fileno, return a new head */
/* written length stored in result, -1 if errno is set */
static IOVectors* IOVectors_writev(IOVectors *v, long fileno, int *result);

static PyTypeObject PyIOVector_Type;

static PyObject* iovec_error = NULL;

#define PyIOVector_Check(x) ((x)->ob_type == &PyIOVector_Type)

static IOVectors*
IOVectors_New(size_t size) {
    /* Make a new IOVectors chunk */
    /* XXX - assert size > 0 */
    IOVectors *v = PyMem_New(IOVectors, 1);
    if (v == NULL)
        goto IOVectors_New_NoMemoryForIOVectors;
    v->first = 0;
    v->bytes = 0;
    v->last = 0;
    v->next = NULL;
    v->size = size;
    v->vectors = PyMem_New(IOVector, size);
    if ((v->vectors = PyMem_New(IOVector, size)) == NULL) 
        goto IOVectors_New_NoMemoryForVectors;
    if ((v->objects = PyMem_New(PyObject*, size)) == NULL)
        goto IOVectors_New_NoMemoryForObjects;
    return v;
    /* error handling */
IOVectors_New_NoMemoryForObjects:
    PyMem_Del(v->vectors);
IOVectors_New_NoMemoryForVectors:
    PyMem_Del(v);
IOVectors_New_NoMemoryForIOVectors:
    return NULL;
}

static IOVectors*
IOVectors_Del(IOVectors* v) {
    IOVectors *next;
    if (v == NULL)
        return NULL;
    next = v->next;
    IOVectors_Wipe(v);
    PyMem_Del(v->vectors);
    PyMem_Del(v->objects);
    PyMem_Del(v);
    return next;
}

static void
IOVectors_Wipe(IOVectors* v) {
    int i;
    PyObject *ref;
    if (v == NULL)
        return;
    for (i = v->first; i < v->last; ++i) {
        ref = v->objects[i];
        if (ref != NULL) {
            Py_DECREF(ref);
        } else {
            PyMem_Del(v->vectors[i].iov_base);
        }
    }
    /* remember to set first, last, and size 
    if you plan to reuse the IOVectors */
}

static IOVectors*
IOVectors_Add(IOVectors* tail, char *buf, size_t len, size_t alloc_length, PyObject* obj) {
    /* buf is assumed to be safe to keep around */
    /* also assumed that we must free it when done */
    IOVector *v = NULL;
    if (tail->last > tail->size) {
        /* XXX */
        printf("SOMETHING REALLY BAD HAPPENED HERE\n");
        return NULL;
    } else if (tail->last == tail->size) {
        IOVectors *_tail = tail;
        if (tail->next != NULL) {
            /* XXX */
            printf("SOMETHING EXTREMELY BAD HAPPENED HERE\n");
            return NULL;
        }
        tail = IOVectors_New(alloc_length);
        _tail->next = tail;
        if (tail == NULL) {
            /* XXX */
            printf("IOVectors_New() is broken or we ran out of memory\n");
            return NULL;
        }
    }
    tail->objects[tail->last] = obj;
    tail->bytes += len;
    v = &tail->vectors[tail->last++];
    v->iov_base = buf;
    v->iov_len = len;
    return tail;
}

static IOVectors*
IOVectors_Remove(IOVectors* head, size_t bytes) {
    int idx;
    IOVector* v;
    PyObject* o;
    while (head != NULL && bytes >= head->bytes) {
        if (head->next == NULL) {
            /* XXX - assert bytes == head->bytes */
            IOVectors_Wipe(head);
            head->first = head->last = 0;
            head->bytes = 0;
            return head;
        }
        head = IOVectors_Del(head);
    }
    head->bytes -= bytes;
    idx = head->first;
    while (bytes > 0) {
        v = &head->vectors[idx];
        o = head->objects[idx];
        if (v->iov_len <= bytes) {
            if (o == NULL) {
                PyMem_Del(v->iov_base);
            } else {
                Py_DECREF(o);
            }
            bytes -= v->iov_len;
            ++idx;
        } else {
            if (o != NULL) {
                v->iov_base += bytes;
                v->iov_len -= bytes;
            } else {
                /* XXX - Probably don't need to optimize this case */
                char *newbuf = PyMem_New(char, v->iov_len - bytes);
                if (newbuf == NULL) {
                    printf("OUT OF MEMORY, SUX0R\n");
                    return NULL;
                }
                memcpy((void *)newbuf, (void *)((char *)v->iov_base + bytes), v->iov_len - bytes);
                PyMem_Free(v->iov_base);
                v->iov_base = newbuf;
            }
            bytes = 0;
        }
    }
    head->first = idx;
    return head;
}

static int
IOVectors_MakePyStrings(IOVectors *v) {
    int idx;
    PyObject *obj;
    int res = 0;
    if (v == NULL) {
        return 0;
    }
    for (idx = v->first; idx < v->last; ++idx) {
        obj = v->objects[idx];
        if (obj == NULL) {
            ++res;
            obj = PyString_FromStringAndSize((const char *)v->vectors[idx].iov_base, (int)v->vectors[idx].iov_len);
            if (obj == NULL) {
                PyErr_NoMemory();
                return -1;
            }
            PyMem_Del(v->vectors[idx].iov_base);
            v->objects[idx] = obj;
            v->vectors[idx].iov_base = PyString_AsString(obj);
        } else if (v->vectors[idx].iov_base != PyString_AsString(obj)) {
            ++res;
            obj = PyString_FromStringAndSize((const char *)v->vectors[idx].iov_base, (int)v->vectors[idx].iov_len);
            if (obj == NULL) {
                PyErr_NoMemory();
                return -1;
            }
            Py_DECREF(v->objects[idx]);
            v->objects[idx] = obj;
            v->vectors[idx].iov_base = PyString_AsString(obj);
        }
    }
    if (res > 0) {
        printf("DEBUG: %d new strings created\n", res);
    }
    return res;
}

static PyObject*
IOVectors_AsTuple(IOVectors *v) {
    int i,idx;
    PyObject *tuple;
    if (v == NULL) {
        PyErr_SetString(iovec_error, "Trying to turn NULL into a tuple?!");
        return NULL;
    }
    if (IOVectors_MakePyStrings(v) == -1) {
        /* XXX - memory error */
        return NULL;
    }

    if ((tuple = PyTuple_New(v->last - v->first)) == NULL) {
        return PyErr_NoMemory();
    }

    i = 0;
    for (idx = v->first; idx < v->last; ++idx) {
        Py_INCREF(v->objects[idx]);
        PyTuple_SET_ITEM(tuple, i++, v->objects[idx]);
    }
    return tuple;   
}    

static IOVectors*
IOVectors_writev(IOVectors *v, long fileno, int *result) {
    int bytes = 0, res = 0;
    IOVectors *orig_v = v;
    if (v == NULL || v->bytes == 0)
        goto IOVectors_writev_success;
    while (v != NULL && v->bytes > 0) {
        if ((res = writev(fileno, &v->vectors[v->first], v->last - v->first)) == -1)
            goto IOVectors_writev_error;
        bytes += res;
        if (res == v->bytes) {
            v = v->next;
        } else if (res < v->bytes) {
            break;
        } else {
            /* XXX */
            printf("Woah, something awful happened here\n");
        }
    }
    v = IOVectors_Remove(orig_v, bytes);        
IOVectors_writev_success:
    *result = bytes;
    return v;
IOVectors_writev_error:
    *result = -1;
    return v;
}
    
static int 
IOVectors_Length(IOVectors *v) {
    int len = 0;
    while (v != NULL) {
        len += v->last - v->first;
        v = v->next;
    }
    return len;
}

static int
IOVectors_ListLength(IOVectors *v) {
    int len = 0;
    while (v != NULL && ++len) {
        v = v->next;
    }
    return len;
}

static PyIOVector*
PyIOVector_new(PyObject* args) {
    PyIOVector* self = PyObject_New(PyIOVector, &PyIOVector_Type);
    if (self == NULL)
        return NULL;
    
    self->head = NULL;
    self->tail = NULL;
    self->bytes = 0;
    
    return self;
}

static void
PyIOVector_dealloc(PyIOVector* self) {
    IOVectors *next;
    next = self->head;
    while (next != NULL)
        next = IOVectors_Del(next);
    PyObject_Del(self);
}

static char PyIOVector_append_doc[] = 
"V.append(string) -- Add a string to this IOVector";

static int
PyIOVector_append_object(PyIOVector* self, PyObject* obj) {
    const char *buf;
    int len;
    IOVectors* next_tail;
    if (PyObject_CheckReadBuffer(obj) == 0) {
        PyErr_SetString(iovec_error, "Argument must support read buffer interface");
        return -1;
    }

    if (PyObject_AsReadBuffer(obj, (const void **)&buf, &len) == -1) {
        PyErr_SetString(iovec_error, "Argument could not support simple read buffer");
        return -1;
    }

    if (len == 0) {
        return 0;
    }

    if (self->tail == NULL) {
        /* XXX - assert self->head == NULL */
        if ((self->tail = self->head = IOVectors_New(DEFAULT_NUM_VECTORS)) == NULL) {
            PyErr_NoMemory();
            return -1;
        }
    }

    if ((next_tail = IOVectors_Add(self->tail, (char *)buf, (size_t)len, DEFAULT_NUM_VECTORS, obj)) == NULL) {
        PyErr_NoMemory();
        return -1;
    }

    self->tail = next_tail;
    self->bytes += len;
    return 0;
    /* retain the item yourself */
}

static PyObject*
PyIOVector_append(PyIOVector* self, PyObject* args) {
    PyObject* obj;

    if (!PyArg_ParseTuple(args, "O:append", &obj))
        return NULL;
    
    if (PyIOVector_append_object(self, obj) == -1) {
        return NULL;
    }

    /* retain item explicitly */
    Py_INCREF(obj);
    Py_INCREF(Py_None);
    return Py_None;
}

static char PyIOVector_extend_doc[] =
"V.extend(sequence)";

static PyObject*
PyIOVector_extend(PyIOVector* self, PyObject* args) {
    PyObject *iterator;
    PyObject *item;
    if (!PyArg_ParseTuple(args, "O:extend", &iterator))
        return NULL;
    iterator = PyObject_GetIter(iterator);
    if (iterator == NULL) {
        return NULL;
    }
    while ((item = PyIter_Next(iterator)) != NULL) {
        if (PyIOVector_append_object(self, item) == -1) {
            return NULL;
        }
        /* retain item implicitly */
    }
    Py_DECREF(iterator);
    Py_INCREF(Py_None);
    return Py_None;
}

static char PyIOVector_write_doc[] =
"V.write(file descriptor or file object)";

static PyObject*
PyIOVector_write(PyIOVector* self, PyObject* args) {

    int result;
    long fileno;
    PyObject* obj;
    
    if (!PyArg_ParseTuple(args, "O:add", &obj))
        return NULL;
    
    if (PyInt_Check(obj)) {
        fileno = PyInt_AsLong(obj);
    } else {
        PyObject* func;
        PyObject* res;
        
        func = PyObject_GetAttrString(obj, "fileno");
        if (func == NULL)
            return NULL;
        
        res = PyObject_CallObject(func, NULL);
        Py_DECREF(func);
        if (res == NULL)
            return NULL;
        
        if (!PyInt_Check(res)) {
            PyErr_SetString(iovec_error, "fileno() must return an integer");
            return NULL;
        }
        
        fileno = PyInt_AsLong(res);
        Py_DECREF(res);
    }
    
    /* I really don't know if threads can be allowed here. */
    Py_BEGIN_ALLOW_THREADS
    self->head = IOVectors_writev(self->head, fileno, &result);
    Py_END_ALLOW_THREADS
    if (result == -1) {
        return PyErr_SetFromErrno(iovec_error);
    } else if (self->head == NULL) {
        PyErr_SetString(iovec_error, "head is supposed to get recycled?");
        return NULL;
    }
    self->bytes -= result;
    return PyInt_FromLong(result);
}

static char PyIOVector__asTuple_doc[] = "Internal use";

static PyObject*
PyIOVector__asTuple(PyIOVector* self, PyObject* args) {
    int i=0;
    PyObject *tuple, *innerTuple;
    IOVectors *v = self->head;
    if ((tuple = PyTuple_New(IOVectors_ListLength(v))) == NULL) {
        goto PyIOVector__asTuple_NoTuple;
    }
    while (v != NULL) {
        if ((innerTuple = IOVectors_AsTuple(v)) == NULL) {
            goto PyIOVector__asTuple_NoInnerTuple;
        }
        PyTuple_SET_ITEM(tuple, i++, innerTuple);
        v = v->next;
    }
    return tuple;

PyIOVector__asTuple_NoInnerTuple:
    Py_DECREF(tuple);
PyIOVector__asTuple_NoTuple:
    return PyErr_NoMemory();
}

static PyMethodDef PyIOVector_methods[] = {
    {"add", (PyCFunction)PyIOVector_append, METH_VARARGS, PyIOVector_append_doc},
    {"append", (PyCFunction)PyIOVector_append, METH_VARARGS, PyIOVector_append_doc},
    /*{"read", (PyCFunction)PyIOVector_read, METH_VARARGS, PyIOVector_read_doc},*/
    {"write", (PyCFunction)PyIOVector_write, METH_VARARGS, PyIOVector_write_doc},
    {"extend", (PyCFunction)PyIOVector_extend, METH_VARARGS, PyIOVector_extend_doc},
    {"_asTuple", (PyCFunction)PyIOVector__asTuple, METH_VARARGS, PyIOVector__asTuple_doc},
    {NULL, NULL},
};

static PyMemberDef PyIOVector_members[] = {
    {"bytes", T_INT, offsetof(PyIOVector, bytes), RO, "bytes"},
    {NULL, NULL},
};

static PyTypeObject PyIOVector_Type = {
    PyObject_HEAD_INIT(NULL)
    
    0,                  /* ob_size */
    "iovec.iovec",      /* tp_name */
    sizeof(PyIOVector), /* tp_basicsize */
    0,                  /* tp_itemsize */
    
    (destructor)PyIOVector_dealloc, /* to_dealloc */
    0,              /* tp_print */
    0,              /* tp_getattr */
    0,              /* tp_setattr */
    0,              /* tp_compare */
    0,              /* tp_repr */
    0,              /* tp_as_number */
    0,              /* tp_as_sequence */
    0,              /* tp_as_mapping */
    0,              /* tp_hash */
    0,              /* tp_call */
    0,              /* tp_str */
    0,              /* tp_getattro */
    0,              /* tp_setattro */
    0,              /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT, /* tp_flags */
    0,               /* tp_doc */
    0,               /* tp_traverse */
    0,               /* tp_clear */
    0,               /* tp_richcompare */
    0,               /* tp_weaklistoffset */
    0,               /* tp_iter */
    0,               /* tp_iternext */
    PyIOVector_methods, /* tp_methods */
    PyIOVector_members, /* tp_members */
    0,               /* tp_getset */
    0,               /* tp_base */
    0,               /* tp_dict */
    0,               /* tp_descr_get */
    0,               /* tp_descr_set */
    0,               /* tp_dictoffset */
    0,               /* tp_init */
    0,               /* tp_alloc */
    (newfunc)PyIOVector_new, /* tp_new */  
    
};

static PyMethodDef iovec_functions[] = {
    {NULL, NULL},
};

DL_EXPORT(void)
initiovec(void) {
    PyObject* module;
    PyObject* dict;

    PyIOVector_Type.ob_type = &PyType_Type;
    PyIOVector_Type.tp_base = &PyBaseObject_Type;
    if (PyType_Ready(&PyIOVector_Type) < 0)
        return;
    
    module = Py_InitModule("iovec", iovec_functions);
    if (module == NULL)
        return;
    
    dict = PyModule_GetDict(module);
    if (dict == NULL)
        return;
    
    Py_INCREF(&PyIOVector_Type);
    if (PyDict_SetItemString(dict, "iovec", (PyObject*)&PyIOVector_Type) < 0)
        return;
    
    iovec_error = PyErr_NewException("iovec.error", NULL, NULL);
    if (iovec_error == NULL)
        return;
    
    if (PyDict_SetItemString(dict, "error", iovec_error) < 0)
        return;
}
