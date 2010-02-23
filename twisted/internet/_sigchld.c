/*
 * Copyright (c) 2010 Twisted Matrix Laboratories.
 * See LICENSE for details.
 */

#include <signal.h>
#include <errno.h>

#include "Python.h"

static int sigchld_pipe_fd = -1;

static void got_signal(int sig) {
    int saved_errno = errno;
    int ignored_result;

    /* write() errors are unhandled.  If the buffer is full, we don't
     * care.  What about other errors? */
    ignored_result = write(sigchld_pipe_fd, "x", 1);

    errno = saved_errno;
}

PyDoc_STRVAR(install_sigchld_handler_doc, "\
install_sigchld_handler(fd)\n\
\n\
Installs a SIGCHLD handler which will write a byte to the given fd\n\
whenever a SIGCHLD occurs. This is done in C code because the python\n\
signal handling system is not reliable, and additionally cannot\n\
specify SA_RESTART.\n\
\n\
Please ensure fd is in non-blocking mode.\n\
");

static PyObject *
install_sigchld_handler(PyObject *self, PyObject *args) {
    int fd, old_fd;
    struct sigaction sa;

    if (!PyArg_ParseTuple(args, "i:install_sigchld_handler", &fd)) {
        return NULL;
    }
    old_fd = sigchld_pipe_fd;
    sigchld_pipe_fd = fd;

    if (fd == -1) {
        sa.sa_handler = SIG_DFL;
    } else {
        sa.sa_handler = got_signal;
        sa.sa_flags = SA_RESTART;
        /* mask all signals so I don't worry about EINTR from the write. */
        sigfillset(&sa.sa_mask);
    }
    if (sigaction(SIGCHLD, &sa, 0) != 0) {
        sigchld_pipe_fd = old_fd;
        return PyErr_SetFromErrno(PyExc_OSError);
    }
    return PyLong_FromLong(old_fd);
}

PyDoc_STRVAR(is_default_handler_doc, "\
Return 1 if the SIGCHLD handler is SIG_DFL, 0 otherwise.\n\
");

static PyObject *
is_default_handler(PyObject *self, PyObject *args) {
    /*
     * This implementation is necessary since the install_sigchld_handler
     * function above bypasses the Python signal handler installation API, so
     * CPython doesn't notice that the handler has changed and signal.getsignal
     * won't return an accurate result.
     */
    struct sigaction sa;

    if (sigaction(SIGCHLD, NULL, &sa) != 0) {
        return PyErr_SetFromErrno(PyExc_OSError);
    }

    return PyLong_FromLong(sa.sa_handler == SIG_DFL);
}

static PyMethodDef sigchld_methods[] = {
    {"installHandler", install_sigchld_handler, METH_VARARGS,
     install_sigchld_handler_doc},
    {"isDefaultHandler", is_default_handler, METH_NOARGS,
     is_default_handler_doc},
    /* sentinel */
    {NULL, NULL, 0, NULL}
};


static const char _sigchld_doc[] = "\n\
This module contains an API for receiving SIGCHLD via a file descriptor.\n\
";

PyMODINIT_FUNC
init_sigchld(void) {
    /* Create the module and add the functions */
    Py_InitModule3(
        "twisted.internet._sigchld", sigchld_methods, _sigchld_doc);
}
