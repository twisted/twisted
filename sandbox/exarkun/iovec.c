
#include <Python.h>

#include <sys/uio.h>

static PyObject* iovec_error = NULL;

static PyObject* iovec_writev(PyObject* self, PyObject* args) {
  int i = 0;
  int error = 0;
  int fileno = 0;
  int nStrs = 0;
  int retval = 0;
  PyObject* strList;
  PyObject* s;

  struct iovec* vectors;

  if (!PyArg_ParseTuple(args, "iO:writev", &fileno, &strList)) {
    error = 1;
    /* TypeError is set for us */
    goto parse_tuple_failure;
  }
  
  nStrs = PySequence_Size(strList);
  if (nStrs == -1) {
    error = 1;
    PyErr_SetString(iovec_error, "Argument 2 to writev() must be a sequence");
    goto non_sequence_failure;
  }

  if ((vectors = PyMem_Malloc(sizeof(struct iovec) * nStrs)) == NULL) {
    error = 1;
    /* MemoryError is set for us */
    goto mem_malloc_failure;
  }

  for (i = 0; i < nStrs; ++i) {
    s = PySequence_GetItem(strList, i);
    if (PyObject_AsReadBuffer(s, (const void**)&(vectors[i].iov_base), &vectors[i].iov_len) == -1) {
      error = 1;
      /* TypeError is set for us */
      goto acquire_readbuf_failure;
    }
    Py_INCREF(s);
  }

  Py_INCREF(strList);
  Py_BEGIN_ALLOW_THREADS;
  retval = writev(fileno, vectors, nStrs);
  Py_END_ALLOW_THREADS;
  Py_DECREF(strList);

 acquire_readbuf_failure:
  for (--i; i > 0; --i)
    Py_DECREF(PySequence_GetItem(strList, i));
  PyMem_Free(vectors);

 mem_malloc_failure:
 non_sequence_failure:
 parse_tuple_failure:

  if (error)
    return NULL;

  return Py_BuildValue("(ii)", retval, errno);
}

static PyMethodDef iovec_methods[] = {
  {"writev", iovec_writev, METH_VARARGS,
   PyDoc_STR("writev(fileno, string_list) -> bytes written")},
  {NULL, NULL},
};

PyDoc_STRVAR(module_doc,
	     "Module providing a wrapper for the scatter/gather I/O function writev()");


PyMODINIT_FUNC
initiovec(void) {
  PyObject* m;

  m = Py_InitModule3("iovec", iovec_methods, module_doc);
  
  if (iovec_error == NULL) {
    iovec_error = PyErr_NewException("iovec.error", NULL, NULL);
    if (iovec_error == NULL)
      return;
  }

  Py_INCREF(iovec_error);
  PyModule_AddObject(m, "error", iovec_error);
}
