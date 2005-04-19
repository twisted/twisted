
#include <Python.h>

#include <sys/uio.h>

static PyObject* iovec_writev(PyObject* self, PyObject* args) {
  int i = 0;
  int error = 0;
  int fileno = 0;
  int nStrs = 0;
  int retval = 0;
  long maxLen = -1, totLen = 0;
  PyObject* strList;
  PyObject* s;
  int buflen;
  
  PyObject *fast_strList;
  
  struct iovec stack_vectors[8];
  struct iovec *vectors = stack_vectors;
  
  if (!PyArg_ParseTuple(args, "iO|l:writev", &fileno, &strList, &maxLen)) {
    error = 1;
    /* TypeError is set for us */
    goto parse_tuple_failure;
  }
  
  fast_strList = PySequence_Fast(strList, "Argument 2 to writev() must be a sequence");
  if(!fast_strList)
  {
    error = 1;
    goto non_sequence_failure;
  }
  
  nStrs = PySequence_Fast_GET_SIZE(strList);
  if (nStrs > 8) {
    if (maxLen < 0) {
      if ((vectors = PyMem_Malloc(sizeof(struct iovec) * nStrs)) == NULL) {
        error = 1;
        /* MemoryError is set for us */
        goto mem_malloc_failure;
      }
    } else {
      /* If we specified a max size hint, assume it's okay to send less than that too. 
         This may be questionable behavior, but it works for me. :) */
      nStrs = 8;
    }
  }

  for (i = 0; i < nStrs; ++i) {
    s = PySequence_Fast_GET_ITEM(fast_strList, i);
    Py_INCREF(s);
    if (PyObject_AsReadBuffer(s, (const void**)&(vectors[i].iov_base), &buflen) == -1) {
      error = 1;
      i++;
      /* TypeError is set for us */
      goto acquire_readbuf_failure;
    }
    vectors[i].iov_len = buflen;
    totLen += buflen;
    if (maxLen > 0 && totLen >= maxLen) {
      i++;
      break;
    }
  }

  Py_BEGIN_ALLOW_THREADS;
  retval = writev(fileno, vectors, i);
  Py_END_ALLOW_THREADS;

 acquire_readbuf_failure:
  for (--i; i >= 0; --i)
    Py_DECREF(PySequence_Fast_GET_ITEM(fast_strList, i));

  if (nStrs > 8)
    PyMem_Free(vectors);

 mem_malloc_failure:
  Py_DECREF(fast_strList);
 non_sequence_failure:
 parse_tuple_failure:

  if (error)
    return NULL;

  return Py_BuildValue("(ii)", retval, errno);
}

static PyMethodDef iovec_methods[] = {
  {"writev", iovec_writev, METH_VARARGS,
   PyDoc_STR("writev(fileno, buf_list[, max_len_hint]) -> bytes written")},
  {NULL, NULL},
};

PyDoc_STRVAR(module_doc,
	     "Module providing a wrapper for the scatter/gather I/O function writev()");


PyMODINIT_FUNC
initiovec(void) {
  PyObject* m;

  m = Py_InitModule3("iovec", iovec_methods, module_doc);
}
