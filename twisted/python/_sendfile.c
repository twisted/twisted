/*
 * _sendfile.c  a wrapper for sendfile(2)
 * Copyright (c) Twisted Matrix Laboratories
 * See LICENSE for licensing information.
 */

#include <Python.h>
#if defined(__linux__)
#include <sys/sendfile.h>
#endif

#if defined(__FreeBSD__) || defined(__APPLE__)
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/uio.h>
#endif


PyDoc_STRVAR(sendfile_wrapper_doc,
"sendfile(inFd, outFd, offset, count)\n\
\n\
Copies data between the file descriptor inFd open for reading and the file\n\
descriptor outFd open for writing. Returns the number of bytes written to\n\
outFd.");


static PyObject * sendfile_wrapper(PyObject *self, PyObject *args) {
    int outFd, inFd;
    off_t offset;

#if defined(__FreeBSD__)
    int sts;
    size_t nbytes;
    off_t sbytes = 0;

    if (!PyArg_ParseTuple(args, "iiLi", &outFd, &inFd, &offset, &nbytes)) {
        return NULL;
    }

    Py_BEGIN_ALLOW_THREADS;
    sts = sendfile(inFd, outFd, offset, nbytes, NULL, &sbytes, 0);
    Py_END_ALLOW_THREADS;

    if (sts == -1) {
        if (errno != EAGAIN && errno != EINTR) {
            PyErr_SetFromErrno(PyExc_IOError);
            return NULL;
        }
    }

    return Py_BuildValue("L", sbytes);
#else
#if defined(__APPLE__)
    int sts;
    off_t nbytes;

    if (!PyArg_ParseTuple(args, "iiLL", &outFd, &inFd, &offset, &nbytes)) {
        return NULL;
    }

    Py_BEGIN_ALLOW_THREADS;
    sts = sendfile(inFd, outFd, offset, &nbytes, NULL, 0);
    Py_END_ALLOW_THREADS;

    if (sts == -1) {
        if (errno != EAGAIN && errno != EINTR) {
            PyErr_SetFromErrno(PyExc_IOError);
            return NULL;
        }
    }

    return Py_BuildValue("L", nbytes);
#else
    size_t count, sent;

    if (!PyArg_ParseTuple(args, "iiLl", &outFd, &inFd, &offset, &count)) {
        return NULL;
    }

    Py_BEGIN_ALLOW_THREADS;
    sent = sendfile(outFd, inFd, &offset, count);
    Py_END_ALLOW_THREADS;

    if (sent == -1) {
        PyErr_SetFromErrno(PyExc_IOError);
        return NULL;
    }

    return Py_BuildValue("l", sent);
#endif
#endif
}


static PyMethodDef sendfilemethods[] = {
    {"sendfile", (PyCFunction)sendfile_wrapper,
     METH_VARARGS|METH_KEYWORDS, sendfile_wrapper_doc},
    {NULL},
};


void init_sendfile(void) {
    Py_InitModule("_sendfile", sendfilemethods);
}
