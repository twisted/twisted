/*
 * Twisted, the Framework of Your Internet
 * Copyright (C) 2001-2002 Matthew W. Lefkowitz
 * 
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of version 2.1 of the GNU Lesser General Public
 * License as published by the Free Software Foundation.
 * 
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 * 
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 * 
 */
/* cReactorTime.c - Implementation of IReactorTime */

/* includes */
#include "cReactor.h"

PyObject *
cReactorTime_callLater(PyObject *self, PyObject *args, PyObject *kw)
{
    cReactor *reactor;
    cDelayedCall *call;
    int delay                   = 0;
    PyObject *delay_obj         = NULL;
    PyObject *req_args          = NULL;
    PyObject *callable_args     = NULL;
    PyObject *callable          = NULL;

    reactor = (cReactor *)self;

    /* Slice off the arguments we want to parse. */
    req_args = PyTuple_GetSlice(args, 0, 2);

    /* Now use PyArg_ParseTuple on the required args. */
    if (!PyArg_ParseTuple(req_args, "OO:callLater", &delay_obj, &callable))
    {
        Py_DECREF(req_args);
        return NULL;
    }
    Py_DECREF(req_args);

    /* Convert delay. */
    if (delay_obj)
    {
        delay = cReactorUtil_ConvertDelay(delay_obj);
        if (delay < 0)
        {
            return NULL;
        }
    }

    /* Verify the given object is callable. */
    if (!PyCallable_Check(callable))
    {
        PyErr_Format(PyExc_TypeError, "callLater() arg 2 expected callable, found %s",
                     callable->ob_type->tp_name);
        return NULL;
    }

    /*
    printf("callLater: ");
    PyObject_Print(callable, stdout, 1);
    printf(" delay=%d\n", delay);
    */

    /* Now get the arguments to pass to the callable. */
    callable_args = PyTuple_GetSlice(args, 2, PyTuple_Size(args));

    /* Add this method to the list. */
    call = cReactorUtil_AddDelayedCall(reactor,
                                       delay, callable, callable_args, 
                                       kw);
    Py_DECREF(callable_args);
    
    return (PyObject *)call;
}

PyObject *
cReactorTime_getDelayedCalls(PyObject *self, PyObject *args)
{
    cReactor *reactor;
    cDelayedCall *node;
    PyObject *calls;

    calls = PyList_New(0);
    if (!calls) {
        return NULL; /* TODO: set exception? */
    }

    reactor = (cReactor *)self;
    node = reactor->timed_methods;
    while(node) {
        if (PyList_Append(calls, (PyObject *)node)) {
            Py_DECREF(calls);
            return NULL;
        }
        node = node->next;
    }

    return calls;
}

PyObject *
cReactorTime_cancelCallLater(PyObject *self, PyObject *args)
{
    cReactor *reactor;
    cDelayedCall *call;

    reactor = (cReactor *)self;
    /* deprecated */

    if (!PyArg_ParseTuple(args, "O:cancelCallLater", &call))
    {
        return NULL;
    }

    /* todo: verify that 'self' is really a cReactor object */
    /* todo: verify that 'call' is really a cDelayedCall object */
    /* return cDelayedCall_cancel(call, NULL); */

    if (cReactorUtil_RemoveDelayedCall(reactor, call) < 0)
    {
        return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}


/* vim: set sts=4 sw=4: */
