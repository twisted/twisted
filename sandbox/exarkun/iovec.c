
/* Python includes */
#include <Python.h>

/* System includes */
#include <sys/uio.h>

/* Python wrapper around an array of iovec structs */
typedef struct {
    PyObject_HEAD
    
    size_t size;      /* The number of iovec structs contained */
    size_t bytes;     /* The total number of bytes in all the iovec structs */
    struct iovec* vectors;
} PyIOVector;

/* Deallocates the dynamic memory held by iovec */
void iovec_dealloc_vectors(PyIOVector* iovec);

static PyTypeObject PyIOVector_Type;

static PyObject* iovec_error = NULL;

#define PyIOVector_Check(x) ((x)->ob_type == &PyIOVector_Type)

static PyIOVector*
PyIOVector_new(PyObject* args) {
    PyIOVector* self = PyObject_New(PyIOVector, &PyIOVector_Type);
    if (self == NULL)
        return NULL;
    
    self->bytes = 0;
    self->size = 0;
    self->vectors = NULL;
    
    return self;
}

static void
PyIOVector_dealloc(PyIOVector* self) {
    iovec_dealloc_vectors(self);
    PyObject_Del(self);
}

void iovec_dealloc_vectors(PyIOVector* iovec) {
    if (iovec->vectors) {
        int i;
        for (i = 0; i < iovec->size; ++i) {
            printf("Deallocate (iovec->vectors[%d].iov_base) %p\n", i, iovec->vectors[i].iov_base);
            PyMem_Del(iovec->vectors[i].iov_base);
        }

        printf("Deallocate (iovec->vectors) %p\n", iovec->vectors);
        PyMem_Del(iovec->vectors);
    }
    iovec->vectors = NULL;
    iovec->bytes = 0;
    iovec->size = 0;
}

static char PyIOVector_add_doc[] = 
"V.add(string) -- Add a string to this IOVector";

static PyObject*
PyIOVector_add(PyIOVector* self, PyObject* args) {
    int len;
    char* buf;
    struct iovec* vectors;

    if (!PyArg_ParseTuple(args, "s#:add", &buf, &len))
        return NULL;

    vectors = PyMem_New(struct iovec, self->size + 1);
    if (vectors == NULL)
        return PyErr_NoMemory();
    
    printf("Allocated (vectors) %p\n", vectors);

    memcpy(vectors, self->vectors, sizeof(struct iovec) * self->size);

    vectors[self->size].iov_base = PyMem_New(char, len);
    if (vectors[self->size].iov_base == NULL) {
        printf("Deallocate (vectors) %p\n", vectors);
        PyMem_Del(vectors);
        return PyErr_NoMemory();
    }
    
    printf("Allocated (vectors[%d].iov_base) %p\n", self->size, vectors[self->size].iov_base);

    memcpy(vectors[self->size].iov_base, buf, len);
    vectors[self->size].iov_len = len;

    self->size += 1;
    self->bytes += len;

    printf("Deallocate (self->vectors) %p\n", self->vectors);
    PyMem_Del(self->vectors);
    self->vectors = vectors;

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject*
iovec_delete(PyIOVector* iovec, int bytes) {
    int i, j;
    int origBytes = bytes;

    if (bytes == iovec->bytes) {
        iovec_dealloc_vectors(iovec);
        return;
    }
    
    for (i = 0; i < iovec->size; ++i) {
        if (bytes == 0) {
            /* Chop! */
            struct iovec* vtmp;
            
            printf("Deletion at i=%d\n", i);
            
            vtmp = PyMem_New(struct iovec, iovec->size - i);
            if (iovec == NULL)
                return PyErr_NoMemory();

            printf("Allocated (vtmp (1)) %p\n", vtmp);
            
            memcpy(vtmp, iovec->vectors + i, iovec->size - i);
            printf("Deallocate (iovec->vectors) %p\n", iovec->vectors);
            PyMem_Del(iovec->vectors);
            iovec->vectors = vtmp;
            
            iovec->size -= i;
            iovec->bytes -= origBytes;
            return;
        } else if (bytes < iovec->vectors[i].iov_len) {
            /* Partial deletion */
            struct iovec* vtmp = iovec->vectors;
            int L = iovec->vectors[i].iov_len - bytes;
            char* tmp = iovec->vectors[i].iov_base;

            printf("Partial deletion at i=%d\n", i);
            
            iovec->vectors[i].iov_len = L;
            iovec->vectors[i].iov_base = PyMem_New(char, L);
            if (iovec->vectors[i].iov_base == NULL)
                return PyErr_NoMemory();
            
            printf("Allocated (iovec->vectors[%d].iov_base) %p\n", i, iovec->vectors[i].iov_base);
            
            strncpy(iovec->vectors[i].iov_base, tmp + bytes, L);
            printf("Deallocate (previous iovec->vectors[%d].iov_base) %p\n", i, tmp);
            PyMem_Del(tmp);
            tmp = NULL;

            /* Now clean up everything before this element */
            iovec->bytes -= origBytes;
            iovec->size -= i;

            if (i == 0) /* We're actually done cleaning up already */
                return;

            printf("New iovec %d elements\n", iovec->size);
            iovec->vectors = PyMem_New(struct iovec, iovec->size);
            if (iovec->vectors == NULL) {
                printf("Deallocate (tmp) %p\n", tmp);
                PyMem_Del(tmp);
                return PyErr_NoMemory();
            }

            for (j = 0; j < i - 1; ++j) {
                printf("Deallocate (previous iovec->vectors[%d].iov_base) %p\n", j, vtmp[j].iov_base);
                PyMem_Del(vtmp[j].iov_base);
            }
            printf("Allocated (iovec->vectors) %p\n", iovec->vectors);
            memcpy(iovec->vectors, vtmp + i, iovec->size);
            
            printf("Deallocate (previous iovec->vectors) %p\n", vtmp);
            PyMem_Del(vtmp);

            return;
        }
        bytes -= iovec->vectors[i].iov_len;
    }
}

static char PyIOVector_write_doc[] =
"V.write(file descriptor or file object)";

static PyObject*
PyIOVector_write(PyIOVector* self, PyObject* args) {

    int result;
    long fileno;
    PyObject* obj;
    
    if (!PyArg_ParseTuple(args, "O:write", &obj))
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
    result = writev(fileno, self->vectors, self->size);
    
    iovec_delete(self, result);
    return PyInt_FromLong(result);
}

static PyMethodDef PyIOVector_methods[] = {
    {"add", (PyCFunction)PyIOVector_add, METH_VARARGS, PyIOVector_add_doc},
    {"write", (PyCFunction)PyIOVector_write, METH_VARARGS, PyIOVector_write_doc},
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
    0,               /* tp_members */
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

    /* __asm__("int $3"); */
}
