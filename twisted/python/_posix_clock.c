/*
 * _posix_clock.c: wrapper for clock_gettime and clock_getres.
 * Copyright (c) 2008 Twisted Matrix Laboratories
 * See LICENSE for licensing information.
 */

#include <Python.h>
#include <time.h>
#include <unistd.h>

#if defined(_XOPEN_REALTIME) && _XOPEN_REALTIME != -1

PyDoc_STRVAR(posixclock_gettime_doc,
"gettime(clockid) -> nanoseconds\n\
\n\
Retrieve the value of the clock specified by clockid, in integer\n\
nanoseconds.\n\
\n\
Throws an IOError exception if the operation is not supported.");

static PyObject *
posixclock_gettime(PyObject *self, PyObject *args)
{
    int clk_id;
    int err;
    struct timespec ts;

    if (!PyArg_ParseTuple(args, "i:clock_gettime", &clk_id)) {
        return NULL;
    }

    err = clock_gettime(clk_id, &ts);
    if (err) {
        return PyErr_SetFromErrno(PyExc_IOError);
    }

    return PyLong_FromLongLong(ts.tv_sec * 1000000000LL + ts.tv_nsec);
}

PyDoc_STRVAR(posixclock_getres_doc,
"getres(clockid) -> nanoseconds\n\
\n\
Retrieve the resolution (precision) of the clock specified by clockid,\n\
in integer nanoseconds.\n\
\n\
Throws an IOError exception if the operation is not supported.");

static PyObject *
posixclock_getres(PyObject *self, PyObject *args)
{
    int clk_id;
    int err;
    struct timespec ts;

    if (!PyArg_ParseTuple(args, "i:clock_getres", &clk_id)) {
        return NULL;
    }

    err = clock_getres(clk_id, &ts);
    if (err) {
        return PyErr_SetFromErrno(PyExc_IOError);
    }

    return PyLong_FromLongLong(ts.tv_sec * 1000000000LL + ts.tv_nsec);
}

static PyMethodDef posixclock_methods[] = {
    {"gettime",   posixclock_gettime,
     METH_VARARGS, posixclock_gettime_doc},
    {"getres",   posixclock_getres,
     METH_VARARGS, posixclock_getres_doc},
};

PyMODINIT_FUNC
init_posix_clock(void)
{
    PyObject *m;
    m = Py_InitModule("_posix_clock", posixclock_methods);
    PyModule_AddIntConstant(m, "CLOCK_REALTIME", CLOCK_REALTIME);
#ifdef CLOCK_MONOTONIC
    PyModule_AddIntConstant(m, "CLOCK_MONOTONIC", CLOCK_MONOTONIC);
#endif
#ifdef CLOCK_PROCESS_CPUTIME_ID
    PyModule_AddIntConstant(m, "CLOCK_PROCESS_CPUTIME_ID", CLOCK_PROCESS_CPUTIME_ID);
#endif
#ifdef CLOCK_THREAD_CPUTIME_ID
    PyModule_AddIntConstant(m, "CLOCK_THREAD_CPUTIME_ID", CLOCK_THREAD_CPUTIME_ID);
#endif
}

#else
#error POSIX realtime extension not supported
#endif
