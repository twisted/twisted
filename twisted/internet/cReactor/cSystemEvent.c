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
/* cSystemEvent.c - functions relating to addSystemEventTrigger and friends. */

/* includes */
#include "cReactor.h"
#include <stdio.h>
#include <unistd.h>

/* Small struct so we can pass more data through the user_data parameter to
 * cReactorUtil_ForEachMethod.
 */
typedef struct _SysEventInfo SysEventInfo;

struct _SysEventInfo
{
    cReactor *          reactor;
    cReactorEventType   event;
    int                 got_defers;
};

static void
run_system_event_triggers(PyObject *callable, PyObject *args, PyObject *kw, void *user_data)
{
    PyObject *result;

    UNUSED(user_data);

    /* Call the callable. */
    /*
    printf("calling ");
    PyObject_Print(callable, stdout, 1);
    printf("\n");
    */
    result = PyEval_CallObjectWithKeywords(callable, args, kw);
    if (!result)
    {
        PyErr_Print();
        return;
    }

    /* Ignore the return value. */
    Py_DECREF(result);
}


static void
finish_system_event(cReactor *reactor, cReactorEventType type)
{
    /* Run the "during" triggers. */
    cReactorUtil_ForEachMethod(reactor->event_triggers[type][CREACTOR_EVENT_PHASE_DURING],
                               run_system_event_triggers, NULL);

    /* Run the "after" triggers. */
    cReactorUtil_ForEachMethod(reactor->event_triggers[type][CREACTOR_EVENT_PHASE_AFTER],
                               run_system_event_triggers, NULL);

    /* If we are in the STOPPING state, move to DONE. */
    if (reactor->state == CREACTOR_STATE_STOPPING)
    {
        reactor->state = CREACTOR_STATE_DONE;
    }
}


static PyObject *
system_event_defer_callback(PyObject *self, PyObject *args)
{
    PyObject *defer_id;
    int i;
    int len;
    PyObject *empty_list;
    cReactor *reactor;
    int event_type;
    cReactorEventType event;
    
    reactor = (cReactor *)self;

    /* Check args. */
    if (!PyArg_ParseTuple(args, "Oi:system_event_defer_callback", &defer_id, &event_type))
    {
        return NULL;
    }

    /* Check arg 1. */
    if (!PyLong_Check(defer_id))
    {
        PyErr_Format(PyExc_ValueError, "system_event_defer_callback arg 1 expected long, found %s",
                     defer_id->ob_type->tp_name);
        return NULL;
    }

    /* Check arg 2. */
    switch (event_type)
    {
        case CREACTOR_EVENT_TYPE_STARTUP:
        case CREACTOR_EVENT_TYPE_SHUTDOWN:
        case CREACTOR_EVENT_TYPE_PERSIST:
            event = (cReactorEventType)event_type;
            break;

        default:
            PyErr_Format(PyExc_ValueError, "system_event_defer_callback arg 2 invalid event type: %d",
                         event_type);
            return NULL;
    }

    /* Remove the given defer id from the list. */
    len = PyList_Size(reactor->defer_list);
    for (i = 0; i < len; ++i)
    {
        /* We can do a direct compare because were looking for a specific
         * object.
         */
        if (PyList_GetItem(reactor->defer_list, i) == defer_id)
        {
            /* Found -- remove by replacing this piece with a slice. */
            empty_list = PyList_New(0);
            PyList_SetSlice(reactor->defer_list, i, i + 1, empty_list);
            Py_DECREF(empty_list);
            break;
        }
    }

    /* If the list is empty, we can finish the event processing. */
    if (PyList_Size(reactor->defer_list) == 0)
    {
        finish_system_event(reactor, event);
    }

    Py_INCREF(Py_None);
    return Py_None;
}


static void
run_before_system_event_triggers(PyObject *callable, PyObject *args, PyObject *kw, void *user_data)
{
    PyObject *defer;
    PyObject *deferred_class;
    PyObject *result;
    int is_defer;
    PyMethodDef callback_def;
    PyObject *callback;
    PyObject *defer_id;
    cReactor *reactor;
    SysEventInfo *event_info;

    event_info  = (SysEventInfo *)user_data;
    reactor     = event_info->reactor;

    /* Get the deferred class object. */
    deferred_class = cReactorUtil_FromImport("twisted.internet.defer", "Deferred");
    if (!deferred_class)
    {
        PyErr_Print();
        return;
    }

    /* Call the callable. */
    /*
    printf("calling ");
    PyObject_Print(callable, stdout, 1);
    printf("\n");
    */
    defer = PyEval_CallObjectWithKeywords(callable, args, kw);
    if (!defer)
    {
        Py_DECREF(deferred_class);
        PyErr_Print();
        return;
    }

    /* Check if the defer is a Deferred. */
    is_defer = PyObject_IsInstance(defer, deferred_class);
    Py_DECREF(deferred_class);
    
    if (is_defer)
    {
        /* Record the fact we got a Deferred as a return value. */
        event_info->got_defers = 1;

        /*
        printf("is_defer: ");
        PyObject_Print(defer, stdout, 1);
        printf("\n");
        */

        /* Instead of holding onto the deferred, hold onto its id() */
        defer_id = PyLong_FromVoidPtr(defer);

        /* Add the Deferred to the list. */
        if (PyList_Append(reactor->defer_list, defer_id) < 0)
        {
            Py_DECREF(defer_id);
            Py_DECREF(defer);
            PyErr_Print();
            return;
        }

        /* Create the PyCFunction to use for the callback. */
        callback_def.ml_name    = "system_event_defer_callback";
        callback_def.ml_meth    = system_event_defer_callback;
        callback_def.ml_flags   = METH_VARARGS;
        callback_def.ml_doc     = "system_event_defer_callback";
        callback                = PyCFunction_New(&callback_def, (PyObject *)reactor);

        /* Add a call/errback to the deferred. */
        result = PyObject_CallMethod(defer, "addBoth", "(OOi)",
                                     callback, defer_id, event_info->event);
        Py_DECREF(callback);
        Py_DECREF(defer_id);
        Py_XDECREF(result);

        if (!result)
        {
            PyErr_Print();
        }
    }
    else
    {
        Py_DECREF(defer);
    }
}


void
fireSystemEvent_internal(cReactor *reactor, cReactorEventType event)
{
    SysEventInfo event_info;

    /* Iterate over the "before" methods. */
    event_info.reactor      = reactor;
    event_info.event        = event;
    event_info.got_defers   = 0;
    cReactorUtil_ForEachMethod(reactor->event_triggers[event][CREACTOR_EVENT_PHASE_BEFORE],
                               run_before_system_event_triggers, &event_info);

    /* If we did not add any defers finish the system event. */
    if (! event_info.got_defers)
    {
        finish_system_event(reactor, event);
    }

}

PyObject *
cReactor_fireSystemEvent(PyObject *self, PyObject *args)
{
    cReactor *reactor;
    const char *type_str;
    cReactorEventType event;

    reactor = (cReactor *)self;

    if (!PyArg_ParseTuple(args, "s:fireSystemEvent", &type_str))
    {
        return NULL;
    }
   
    /* Get the event event. */
    if (cReactorUtil_GetEventType(type_str, &event) < 0)
    {
        return NULL;
    }
    
    /* Fire the system event. */
    fireSystemEvent_internal(reactor, event);
    Py_INCREF(Py_None);
    return Py_None;
}

PyObject *
cReactor_addSystemEventTrigger(PyObject *self, PyObject *args, PyObject *kw)
{
    cReactor *reactor;
    int method_id;
    PyObject *req_args          = NULL;
    PyObject *callable_args     = NULL;
    PyObject *callable          = NULL;
    const char *phase_str       = NULL;
    const char *event_type_str  = NULL;
    cReactorEventType event_type;
    cReactorEventPhase event_phase; 

    reactor = (cReactor *)self;

    /* Slice off the arguments we want to parse ourselves. */
    req_args = PyTuple_GetSlice(args, 0, 3);

    /* Now use PyArg_ParseTuple on the required args. */
    if (!PyArg_ParseTuple(req_args, "ssO:callLater", &phase_str, &event_type_str, &callable))
    {
        Py_DECREF(req_args);
        return NULL;
    }
    Py_DECREF(req_args);

    /*
    printf("addSystemEventTrigger: \"%s\" \"%s\" ", phase_str, event_type_str);
    PyObject_Print(callable, stdout, 1);
    printf("\n");
    */

    /* Phase can only be one of: "before", "during", and "after" */
    if (cReactorUtil_GetEventPhase(phase_str, &event_phase) < 0)
    {
        return NULL;
    }

    /* EventType can only be on of: "startup", "shutdown", and "persist" */
    if (cReactorUtil_GetEventType(event_type_str, &event_type) < 0)
    {
        return NULL;
    }

    /* Verify the given object is callable. */
    if (!PyCallable_Check(callable))
    {
        PyErr_Format(PyExc_TypeError, "addSystemEventTrigger() arg 3 expected callable, found %s",
                     callable->ob_type->tp_name);
        return NULL;
    }

    /* Now get the arguments to pass to the callable. */
    callable_args = PyTuple_GetSlice(args, 3, PyTuple_Size(args));

    /* Add this method to the appropriate list. */
    method_id = cReactorUtil_AddMethod(&(reactor->event_triggers[event_type][event_phase]),
                                       callable, callable_args, kw);
    Py_DECREF(callable_args);
    
    return PyInt_FromLong(method_id);
}


PyObject *
cReactor_removeSystemEventTrigger(PyObject *self, PyObject *args)
{
    return cReactor_not_implemented(self, args, "cReactor_removeSystemEventTrigger");
}

