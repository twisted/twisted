
#include <Python.h>

#include <sys/uio.h>

static PyObject* iovec_error = NULL;

static PyObject* iovec_writev(PyObject* self, PyObject* args) {
  int i = 0;
  int fileno = 0;
  int nStrs = 0;
  int retval = 0;
  PyObject* strList;
  PyObject* s;

  struct iovec* vectors;

  if (!PyArg_ParseTuple(args, "iO:writev", &fileno, &strList))
    return NULL;
  
  Py_INCREF(strList);
  nStrs = PySequence_Size(strList);
  if (nStrs == -1) {
    PyErr_SetString(iovec_error, "Argument 2 to writev() must be a sequence");
    return NULL;
  }

  if ((vectors = PyMem_Malloc(sizeof(struct iovec) * nStrs)) == NULL)
    return NULL;

  for (i = 0; i < nStrs; ++i) {
    s = PySequence_GetItem(strList, i);
    if (PyObject_AsReadBuffer(s, (const void**)&(vectors[i].iov_base), &vectors[i].iov_len) == -1)
      goto acquire_readbuf_failure;
    Py_INCREF(s);
  }

  retval = writev(fileno, vectors, nStrs);

  for (i = 0; i < nStrs; ++i)
    Py_DECREF(PySequence_GetItem(strList, i));
  Py_DECREF(strList);

  if (retval == -1) {
    PyErr_SetFromErrno(iovec_error);
    return NULL;
  }

  return PyInt_FromLong(retval);

 acquire_readbuf_failure:
  for (i = i - 1; i >= 0; --i)
    Py_DECREF(PySequence_GetItem(strList, i));
  Py_DECREF(strList);
  return NULL;
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
