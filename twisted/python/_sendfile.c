/*
 * pysendfile
 *
 * A Python module interface to sendfile(2)
 *
 * Original author:
 *     Copyright (C) 2005 Ben Woolley <user tautolog at gmail>
 *
 * The AIX support code is:
 *     Copyright (C) 2008,2009 Niklas Edmundsson <nikke@acc.umu.se>
 *
 * Rewritten from scratch and maintained by Giampaolo Rodola'
 *     Copyright (C) 2009,2012 <g.rodola@gmail.com>
 *
 *
 *  The MIT License
 *
 *  Copyright (c) <2011> <Ben Woolley, Niklas Edmundsson, Giampaolo Rodola'>
 *
 *  Permission is hereby granted, free of charge, to any person obtaining a copy
 *  of this software and associated documentation files (the "Software"), to deal
 *  in the Software without restriction, including without limitation the rights
 *  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 *  copies of the Software, and to permit persons to whom the Software is
 *  furnished to do so, subject to the following conditions:
 *
 *  The above copyright notice and this permission notice shall be included in
 *  all copies or substantial portions of the Software.
 *
 *  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 *  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 *  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 *  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 *  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 *  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 *  THE SOFTWARE.
 */

#include <Python.h>
#include <stdlib.h>

// force a compilation error if platform is not supported
#if !defined(__FreeBSD__)   && \
    !defined(__DragonFly__) && \
    !defined(__APPLE__)     && \
    !defined(_AIX)          && \
    !defined(__linux__)     && \
    !defined(__sun)
#error platfom not supported
#endif

static int
_parse_off_t(PyObject* arg, void* addr)
{
#if !defined(HAVE_LARGEFILE_SUPPORT)
    *((off_t*)addr) = PyLong_AsLong(arg);
#else
    *((off_t*)addr) = PyLong_AsLongLong(arg);
#endif
    if (PyErr_Occurred())
        return 0;
    return 1;
}


/* --- begin FreeBSD / Dragonfly / OSX --- */
#if defined(__FreeBSD__) || defined(__DragonFly__) || defined(__APPLE__)
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/uio.h>

// needed on OSX - Python < 2.6
#if defined(__APPLE__) && defined(_POSIX_C_SOURCE)
struct sf_hdtr {
    struct iovec *headers;
    int hdr_cnt;
    struct iovec *trailers;
    int trl_cnt;
};
#endif

static PyObject *
method_sendfile(PyObject *self, PyObject *args, PyObject *kwdict)
{
    int fd;
    int sock;
    int flags = 0;
    off_t offset;
    Py_ssize_t ret;
    Py_ssize_t nbytes;
    char * head = NULL;
    char * tail = NULL;
    Py_ssize_t head_len = 0;
    Py_ssize_t tail_len = 0;
    off_t sent;
    struct sf_hdtr hdtr;
    PyObject *offobj;
    static char *keywords[] = {"out", "in", "offset", "nbytes", "header",
                               "trailer", "flags", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwdict,
                                     "iiOn|s#s#i:sendfile",
                                     keywords, &fd, &sock, &offobj, &nbytes,
                                     &head, &head_len, &tail, &tail_len,
                                     &flags)) {
        return NULL;
    }

    if (!_parse_off_t(offobj, &offset))
        return NULL;

#ifdef __APPLE__
    sent = nbytes;
#endif
    if (head_len != 0 || tail_len != 0) {
        struct iovec ivh = {head, head_len};
        struct iovec ivt = {tail, tail_len};
        hdtr.headers = &ivh;
        hdtr.hdr_cnt = 1;
        hdtr.trailers = &ivt;
        hdtr.trl_cnt = 1;
        Py_BEGIN_ALLOW_THREADS
#ifdef __APPLE__
        sent += head_len;
        ret = sendfile(sock, fd, offset, &sent, &hdtr, flags);
#else
        ret = sendfile(sock, fd, offset, nbytes, &hdtr, &sent, flags);
#endif
        Py_END_ALLOW_THREADS
    }
    else {
        Py_BEGIN_ALLOW_THREADS
#ifdef __APPLE__
        ret = sendfile(sock, fd, offset, &sent, NULL, flags);
#else
        ret = sendfile(sock, fd, offset, nbytes, NULL, &sent, flags);
#endif
        Py_END_ALLOW_THREADS
    }

    if (ret < 0) {
        if ((errno == EAGAIN) || (errno == EBUSY) || (errno == EWOULDBLOCK)) {
            if (sent != 0) {
                // some data has been sent
                errno = 0;
                goto done;
            }
            else {
                // no data has been sent; upper application is supposed
                // to retry on EAGAIN / EBUSY / EWOULDBLOCK
                PyErr_SetFromErrno(PyExc_OSError);
                return NULL;
            }
        }
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    goto done;

done:
    #if defined(HAVE_LARGEFILE_SUPPORT)
        return Py_BuildValue("L", sent);
    #else
        return Py_BuildValue("l", sent);
    #endif
}
/* --- end OSX / FreeBSD / Dragonfly --- */

/* --- begin AIX --- */
#elif defined(_AIX)
#include <sys/socket.h>

static PyObject *
method_sendfile(PyObject *self, PyObject *args)
{
    int out_fd, in_fd;
    off_t offset;
    size_t nbytes;
    char *hdr=NULL, *trail=NULL;
    int hdrsize, trailsize;
    ssize_t sts=0;
    struct sf_parms sf_iobuf;
    int rc;

    if (!PyArg_ParseTuple(args, "iiLk|s#s#",
                          &out_fd, &in_fd, &offset, &nbytes, &hdr, &hdrsize,
                          &trail, &trailsize))
        return NULL;

    if(hdr != NULL) {
        sf_iobuf.header_data = hdr;
        sf_iobuf.header_length = hdrsize;
    }
    else {
        sf_iobuf.header_data = NULL;
        sf_iobuf.header_length = 0;
    }
    if(trail != NULL) {
        sf_iobuf.trailer_data = trail;
        sf_iobuf.trailer_length = trailsize;
    }
    else {
        sf_iobuf.trailer_data = NULL;
        sf_iobuf.trailer_length = 0;
    }
    sf_iobuf.file_descriptor = in_fd;
    sf_iobuf.file_offset = offset;
    sf_iobuf.file_bytes = nbytes;

    Py_BEGIN_ALLOW_THREADS;
    do {
            sf_iobuf.bytes_sent = 0; /* Really needed? */
            rc = send_file(&out_fd, &sf_iobuf, SF_DONT_CACHE);
            sts += sf_iobuf.bytes_sent;
    } while( rc == 1 || (rc == -1 && errno == EINTR) );
    Py_END_ALLOW_THREADS;

    offset = sf_iobuf.file_offset;

    if (rc == -1) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
    else {
    #if defined(HAVE_LARGEFILE_SUPPORT)
        return Py_BuildValue("L", sts);
    #else
        return Py_BuildValue("l", sts);
    #endif
    }
}
/* --- end AIX --- */

/* --- start Linux --- */
#elif defined (__linux__)
#include <sys/sendfile.h>

static PyObject *
method_sendfile(PyObject *self, PyObject *args, PyObject *kwdict)
{
    int out_fd, in_fd;
    off_t offset;
    Py_ssize_t nbytes;
    Py_ssize_t sent;
    PyObject *offobj;

    if (!PyArg_ParseTuple(args, "iiOn", &out_fd, &in_fd, &offobj, &nbytes)) {
        return NULL;
    }

    if (offobj == Py_None) {
        Py_BEGIN_ALLOW_THREADS;
        sent = sendfile(out_fd, in_fd, NULL, nbytes);
        Py_END_ALLOW_THREADS;
    }
    else {
        if (!_parse_off_t(offobj, &offset))
            return NULL;
        Py_BEGIN_ALLOW_THREADS;
        sent = sendfile(out_fd, in_fd, &offset, nbytes);
        Py_END_ALLOW_THREADS;
    }

    if (sent == -1)
        return PyErr_SetFromErrno(PyExc_OSError);

    return Py_BuildValue("n", sent);
}
/* --- end Linux --- */

/* --- begin SUN OS --- */
#elif defined(__sun)
#include <sys/sendfile.h>

static PyObject *
method_sendfile(PyObject *self, PyObject *args, PyObject *kwdict)
{
    int out_fd;
    int in_fd;
    off_t offset;
    Py_ssize_t nbytes;
    Py_ssize_t sent;
    PyObject *offobj;

    if (!PyArg_ParseTuple(args, "iiOn", &out_fd, &in_fd, &offobj, &nbytes)) {
        return NULL;
    }
    if (!_parse_off_t(offobj, &offset))
        return NULL;
    sent = sendfile(out_fd, in_fd, &offset, nbytes);
    if (sent == -1)
        return PyErr_SetFromErrno(PyExc_OSError);

    return Py_BuildValue("n", sent);
}
#else
/* --- end SUN OS --- */

#error platfom not supported

#endif


/* --- module initialization --- */

struct module_state {
    PyObject *error;
};

#if PY_MAJOR_VERSION >= 3
#define GETSTATE(m) ((struct module_state*)PyModule_GetState(m))
#else
#define GETSTATE(m) (&_state)
static struct module_state _state;
#endif

static PyMethodDef sendfile_methods[] = {
    {"sendfile", (PyCFunction)method_sendfile, METH_VARARGS | METH_KEYWORDS,
     "sendfile(out, in, offset, nbytes, header=\"\", trailer=\"\", flags=0)\n\n"
     "Copy nbytes bytes from file descriptor in (a regular file) to\n"
     "file descriptor out (a socket) starting at offset.\n"
     "Return the number of bytes just being sent. When the end of\n"
     "file is reached return 0.\n"
     "On Linux, if offset is given as None, the bytes are read from\n"
     "the current position of in and the position of in is updated.\n"
     "headers and trailers are strings that are written before and\n"
     "after the data from in is written. In cross platform applications\n"
     "their usage is discouraged (socket.send() or socket.sendall()\n"
     "can be used instead).\n"
     "On Solaris, out may be the file descriptor of a regular file\n"
     "or the file descriptor of a socket. On all other platforms,\n"
     "out must be the file descriptor of an open socket.\n"
     "flags argument is only supported on FreeBSD.\n"
    },
    {NULL, NULL}
};

#if PY_MAJOR_VERSION >= 3

static int sendfile_traverse(PyObject *m, visitproc visit, void *arg) {
    Py_VISIT(GETSTATE(m)->error);
    return 0;
}

static int sendfile_clear(PyObject *m) {
    Py_CLEAR(GETSTATE(m)->error);
    return 0;
}

static struct PyModuleDef moduledef = {
        PyModuleDef_HEAD_INIT,
        "sendfile",
        NULL,
        sizeof(struct module_state),
        sendfile_methods,
        NULL,
        sendfile_traverse,
        sendfile_clear,
        NULL
};

#define INITERROR return NULL

PyObject *
PyInit_sendfile(void)

#else
#define INITERROR return

void
init_sendfile(void)
#endif
{
#if PY_MAJOR_VERSION >= 3
    PyObject *module = PyModule_Create(&moduledef);
#else
    PyObject *module = Py_InitModule("_sendfile", sendfile_methods);
#endif
#ifdef SF_NODISKIO
    PyModule_AddIntConstant(module, "SF_NODISKIO", SF_NODISKIO);
#endif
#ifdef SF_MNOWAIT
    PyModule_AddIntConstant(module, "SF_MNOWAIT", SF_MNOWAIT);
#endif
#ifdef SF_SYNC
    PyModule_AddIntConstant(module, "SF_SYNC", SF_SYNC);
#endif
    if (module == NULL)
        INITERROR;
    struct module_state *st = GETSTATE(module);

    st->error = PyErr_NewException("_sendfile.Error", NULL, NULL);
    if (st->error == NULL) {
        Py_DECREF(module);
        INITERROR;
    }

#if PY_MAJOR_VERSION >= 3
    return module;
#endif
}
