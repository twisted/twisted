
/* Python includes */
#include <Python.h>

/* System includes */
#include <sys/uio.h>


/* Python wrapper around an array of iovec structs */
typedef struct {
    PyObject_HEAD
    
    size_t size;
    size_t bytes;
    struct iovec* vectors;
} PyIOVector;

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
    if (self->vectors) {
        int i;
        for (i = 0; i < self->size; ++i)
            PyMem_Del(self->vectors[i].iov_base);

        PyMem_Del(self->vectors);
    }
    PyObject_Del(self);
}

static char PyIOVector_add_doc[] = 
"V.add(string) -- Add a string to this IOVector";

static PyObject*
PyIOVector_add(PyIOVector* self, PyObject* args) {
    char* tmp;
    struct iovec vec;
    struct iovec* vectors;

    if (!PyArg_ParseTuple(args, "s#:add", &vec.iov_base, &vec.iov_len))
        return NULL;
    
    vectors = PyMem_New(struct iovec, self->size + 1);
    if (vectors == NULL)
        return PyErr_NoMemory();
    
    memcpy(vectors, self->vectors, sizeof(struct iovec) * self->size);

    tmp = PyMem_New(char, vec.iov_len);
    memcpy(tmp, vec.iov_base, vec.iov_len);
    vec.iov_base = tmp;

    vectors[self->size] = vec;
    ++self->size;
    self->bytes += vec.iov_len;

    PyMem_Del(self->vectors);
    self->vectors = vectors;
    
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
    
    result = writev(fileno, self->vectors, self->size);
    
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
    "iovec.IOVector",   /* tp_name */
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
    if (PyDict_SetItemString(dict, "IOVectorType", (PyObject*)&PyIOVector_Type) < 0)
        return;
    
    iovec_error = PyErr_NewException("iovec.error", NULL, NULL);
    if (iovec_error == NULL)
        return;
    
    if (PyDict_SetItemString(dict, "error", iovec_error) < 0)
        return;
}
