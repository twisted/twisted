
/* Python includes */
#include <Python.h>

/* System includes */
#include <sys/uio.h>


/* Python wrapper around an array of iovec structs */
typedef struct {
    PyObject_VAR_HEAD;
    
    size_t bytes;
    struct iovec** vectors;
} PyIOVector;

static PyTypeObject PyIOVectorType;

#define PyIOVector_Check(x) ((x)->ob_type == &PyIOVectorType)

static PyIOVector*
PyIOVector_new(PyObject* args) {
    PyIOVector* self = PyObject_New(PyIOVector, &PyIOVectorType);
    if (self == NULL)
        return NULL;
    
    self->bytes = 0;
    self->vectors = NULL;
    return self;
}

static void
PyIOVector_dealloc(PyObject* self) {
    PyMem_Del(self->vectors);
    PyObject_Del(self);
}

PyDoc_STRVAR(add_doc,
"V.add(string) -- Add a string to this IOVector");

static PyObject*
PyIOVector_add(PyObject* self, PyObject* args) {
    struct iovec newV;
    struct iovec* vec;
    struct iovec** vectors;

    if (PyArg_ParseTuple(args, "s#:add", &newV.iov_base, &newV.iov_len) == NULL)
        return;
    
    vec = PyMem_New(struct iovec, 1);
    if (vec == NULL)
        return PyErr_NoMemory();
    
    vec->iov_base = PyMem_New(char, newV.iov_len);
    if (vec->iov_base == NULL)
        return PyErr_NoMemory();
    
    vec->iov_len = newV.iov_len;
    
    vectors = PyMem_New(struct iovec*, self->ob_size + 1);
    if (vectors == NULL)
        return PyErr_NoMemory();
    
    memcpy(vectors, self->vectors, sizeof(struct iovec*), self->ob_size);
    vectors[self->ob_size] = vec;
    ++self->ob_size;
    self->bytes += vec->iov_len;

    PyMem_Del(self->vectors);
    self->vectors = vectors;
    
    Py_INCREF(Py_None);
    return Py_None;
}

static PyMethodDef PyIOVector_methods[] = {
    {"add", (PyCFunction)PyIOVector_add, METH_VARARGS, add_doc},
    {NULL, NULL},
};

static int
PyIOVector_len(PyIOVector* self) {
    return self->bytes;
}

static PyTypeObject PyIOVector_Type = {
    PyObject_HEAD_INIT(NULL),
    PyIOVector_len,
    "iovec.IOVector",
    sizeof(PyIOVector),
    sizeof(struct iovec*),
    
    PyIOVector_dealloc,
};

DLEXPORT(void)
initiovec(void) {
    PyObject* module;
    PyObject* dict;

    PyIOVectorType.ob_type = &PyType_Type;
    if (PyType_Ready(&PyIOVectorType) < 0)
        return;
    
    module = Py_InitModule("iovec", PyIOVector_methods);
    if (module == NULL)    