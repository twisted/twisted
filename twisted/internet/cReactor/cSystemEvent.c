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
/* cReactor.c - Implementation of the IReactorCore. */

/* includes */
#include "cReactor.h"
#include <stdio.h>
#include <unistd.h>

/* a set of system event triggers */
struct _cEventTriggers
{
    char *              event_type;
    cEventTriggers *    next;
    cReactorMethod *    triggers[CREACTOR_NUM_EVENT_PHASES];
    int                 before_finished;
    PyObject *          defer_list;
};

static cEventTriggers *get_event_triggers(cReactor *reactor,
                                          const char *event_type,
                                          int create);
static PyObject *system_event_defer_callback(PyObject *self,
                                             PyObject *args);

/* Small struct so we can pass more data through the user_data parameter to
 * cReactorUtil_ForEachMethod.
 */
typedef struct _SysEventInfo SysEventInfo;

struct _SysEventInfo
{
    cReactor *          reactor;
    const char *        event_type;
    int                 got_defers;
};

static PyMethodDef callback_def = {
    /* Create the PyCFunction to use for the callback. */
    "system_event_defer_callback", /* .ml_name */
    system_event_defer_callback, /* .ml_meth */
    METH_VARARGS, /* .ml_flags */
    "system_event_defer_callback", /* .ml_doc */
};

static void
run_system_event_triggers(PyObject *callable, PyObject *args, PyObject *kw, void *user_data)
{
    PyObject *result;

    UNUSED(user_data);

    /* Call the callable. */
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
finish_system_event(cReactor *reactor, cEventTriggers *triggers)
{
    /* Run the "during" triggers. */
    cReactorUtil_ForEachMethod(triggers->triggers[CREACTOR_EVENT_PHASE_DURING],
                               run_system_event_triggers, NULL);

    /* Run the "after" triggers. */
    cReactorUtil_ForEachMethod(triggers->triggers[CREACTOR_EVENT_PHASE_AFTER],
                               run_system_event_triggers, NULL);

    /* If we're finishing off the "shutdown" event, we may now move the reactor
       to the STOPPED state */
    if (strcmp(triggers->event_type, "shutdown") == 0)
        cReactor_stop_finish(reactor);
}


static PyObject *
system_event_defer_callback(PyObject *self, PyObject *args)
{
    PyObject *defer_id;
    void *defer;
    int i;
    int len;
    PyObject *result;
    PyObject *empty_list;
    cReactor *reactor;
    const char *event_type;
    cEventTriggers *triggers;
    
    reactor = (cReactor *)self;

    /* We are run as a callback handler for the Deferred that one of the
       event trigger functions returned. If we raise an exception, it will
       probably be stashed in the Deferred and not noticed until they go out
       of scope. */

    /* Check args. */
    if (!PyArg_ParseTuple(args, "OOs:system_event_defer_callback",
                          &result, &defer_id, &event_type))
    {
        return NULL;
    }

    /* Deferred.callback() always takes an argument, which is passed to the
       callback function as its first arg. Ignore it. */

    /* Check arg 2. */
    defer = PyLong_AsVoidPtr(defer_id);
    if (PyErr_Occurred()) {
        return NULL;
    }

    /* Check arg 3. */
    triggers = get_event_triggers(reactor, event_type, 0);
    if (!triggers) {
        PyErr_Format(PyExc_ValueError,
                     "system_event_defer_callback arg 2 refers "
                     "to non-existent event type: %s", event_type);
        return NULL;
    }

    /* Remove the given defer id from the list. */
    len = PyList_Size(triggers->defer_list);
    for (i = 0; i < len; ++i)
    {
        /* the list holds Deferreds, our argument was an int which is equal
           to the address of the Deferred, so we can compare them. */
        if (PyList_GetItem(triggers->defer_list, i) == defer)
        {
            /* Found -- remove by replacing this piece with a slice. */
            empty_list = PyList_New(0);
            PyList_SetSlice(triggers->defer_list, i, i + 1, empty_list);
            Py_DECREF(empty_list);
            break;
        }
    }

    /* If the list is empty, and all "before" methods have been run, we can
       finish the event processing. */
    if (triggers->before_finished &&
        PyList_Size(triggers->defer_list) == 0)
    {
        finish_system_event(reactor, triggers);
    }

    Py_INCREF(Py_None);
    return Py_None;
}


static void
run_before_system_event_triggers(PyObject *callable, PyObject *args, PyObject *kw, void *user_data)
{
    PyObject *defer, *defer_id;
    PyObject *deferred_class;
    PyObject *result;
    int is_defer;
    PyObject *callback;
    cReactor *reactor;
    SysEventInfo *event_info;
    cEventTriggers *triggers;

    event_info  = (SysEventInfo *)user_data;
    reactor     = event_info->reactor;

    /* Get the deferred class object. */
    deferred_class = cReactorUtil_FromImport("twisted.internet.defer",
                                             "Deferred");
    if (!deferred_class)
    {
        PyErr_Print();
        return;
    }

    /* Call the callable. They are allowed to give us a Deferred. */
    defer = PyEval_CallObjectWithKeywords(callable, args, kw);
    if (!defer)
    {
        /* they blew up */
        Py_DECREF(deferred_class);
        return;
    }

    /* Check if they returned a Deferred. */
    is_defer = PyObject_IsInstance(defer, deferred_class);
    Py_DECREF(deferred_class);
    if (!is_defer)
    {
        /* no Deferred, no problem. We're done. */
        Py_DECREF(defer);
        return;
    }

    /* make sure that the triggers still exist */
    triggers = get_event_triggers(reactor, event_info->event_type, 0);
    if (!triggers) {
        /* somebody removed the trigger inside one of the trigger functions.
           There's nothing left for the Deferred to fire. Raise an exception
           because this is dumb. */
        PyErr_Format(PyExc_RuntimeError,
                     "They're Gone! "
                     "The cEventTriggers structure for '%s' vanished!",
                     event_info->event_type);
        /* Note: by printing and clearing the error flag here, this is
           effectively a warning. To do better than that requires changes to
           cReactorUtil_ForEachMethod, to allow the called function to
           return a value that will stop the loop and return an error
           indicator to the caller.*/
        PyErr_Print();
        Py_DECREF(defer);
        return;
    }

    /* Record the fact we got a Deferred as a return value. */
    event_info->got_defers = 1;

    /* Add the Deferred to the list. This list is owned by the
       cEventTriggers, not the deferred, so we can add the actual Deferred
       to it instead of stuffing the address into a python int */
    if (PyList_Append(triggers->defer_list, defer) < 0)
    {
        Py_DECREF(defer);
        PyErr_Print();
        return;
    }

    /* note that callback_def must stick around until the callback is run and
       freed, so it can not be on the stack. */
    callback = PyCFunction_New(&callback_def, (PyObject *)reactor);

    /* Instead of holding onto the deferred, hold onto its id(). This avoids
       a circular reference (deferred.callbacks.args[1] == deferred) which
       could prevent the Deferred from being freed */
    defer_id = PyLong_FromVoidPtr(defer);

    /* Add a call/errback to the deferred. Pass event_type as a string
       because the cEventTriggers struct might disappear by the time the
       Deferred is fired. triggers->event_type will be strdup'ed */
    result = PyObject_CallMethod(defer, "addBoth", "(OOs)",
                                 callback, defer_id, triggers->event_type);
    Py_DECREF(callback);
    Py_DECREF(defer);
    Py_DECREF(defer_id);
    Py_XDECREF(result);

    if (!result)
    {
        PyErr_Print();
    }
}


void
fireSystemEvent_internal(cReactor *reactor, const char *event_type)
{
    SysEventInfo event_info;
    cEventTriggers *triggers;

    triggers = get_event_triggers(reactor, event_type, 0);
    if (!triggers) {
        /* nothing to do */
        /* except finish off the "shutdown" job */
        if (strcmp(event_type, "shutdown") == 0)
            cReactor_stop_finish(reactor);
        return;
    }
        
    triggers->before_finished = 0;
    /* Iterate over the "before" methods. */
    event_info.reactor      = reactor;
    event_info.event_type   = event_type; /* TODO: need strdup here?? */
    event_info.got_defers   = 0;
    /* TODO: what happens if the event structure goes away during the loop?
       event_info.event_type would be left dangling, and ForEachMethod would
       be faced with an inconsistent loop. BADNESS! */
    cReactorUtil_ForEachMethod(triggers->triggers[CREACTOR_EVENT_PHASE_BEFORE],
                               run_before_system_event_triggers, &event_info);
    triggers->before_finished = 1;

    /* If we did not add any defers, or if they were all fired during the
       processing of "before" events, finish the system event now. */
    if (! event_info.got_defers ||
        PyList_Size(triggers->defer_list) == 0)
    {
        finish_system_event(reactor, triggers);
    }
}

PyObject *
cReactor_fireSystemEvent(PyObject *self, PyObject *args)
{
    cReactor *reactor;
    const char *type_str;

    reactor = (cReactor *)self;

    if (!PyArg_ParseTuple(args, "s:fireSystemEvent", &type_str))
    {
        return NULL;
    }

    /* Fire the system event. */
    fireSystemEvent_internal(reactor, type_str);
    
    Py_INCREF(Py_None);
    return Py_None;
}

static cEventTriggers *
get_event_triggers(cReactor *reactor, const char *event_type, int create)
{
    cEventTriggers *node;

    node = reactor->event_triggers;
    while (node) {
        if (strcmp(node->event_type, event_type) == 0)
            break;
        node = node->next;
    }
    if (node)
        return node;
    if (!create)
        return NULL;
    node = (cEventTriggers *)malloc(sizeof(*node));
    if (!node)
        return NULL;
    memset(node, 0, sizeof(*node));
    node->event_type = strdup(event_type);
    if (!node->event_type) {
        free(node);
        return NULL;
    }
    node->defer_list = PyList_New(0);
    if (!node->defer_list) {
        free(node->event_type);
        free(node);
        return NULL;
    }
    node->next = reactor->event_triggers;
    reactor->event_triggers = node;
    return node;
}

void
free_event_trigger(cEventTriggers *trigger)
{
    int p;
    free(trigger->event_type);
    for (p = 0; p < CREACTOR_NUM_EVENT_PHASES; p++)
        cReactorUtil_DestroyMethods(trigger->triggers[p]);
    Py_XDECREF(trigger->defer_list);
    trigger->defer_list = NULL;
    free(trigger);
}

void
cSystemEvent_FreeTriggers(cEventTriggers *triggers)
{
    cEventTriggers *node, *next;

    node = triggers;
    while (node) {
        next = node->next;
        free_event_trigger(node);
        node = next;
    }
}
        

int
cReactorUtil_GetEventPhase(const char *str, cReactorEventPhase *out_phase)
{
    static struct {
        const char *        str;
        cReactorEventPhase  phase;
    } phase_map[] = 
    {
        { "before",     CREACTOR_EVENT_PHASE_BEFORE },
        { "during",     CREACTOR_EVENT_PHASE_DURING },
        { "after",      CREACTOR_EVENT_PHASE_AFTER },
    };
    static int phase_map_len = sizeof(phase_map) / sizeof(phase_map[0]);

    int i;

    for (i = 0; i < phase_map_len; ++i)
    {
        if (strcmp(str, phase_map[i].str) == 0)
        {
            *out_phase = phase_map[i].phase;
            return 0;
        }
    }

    PyErr_Format(PyExc_ValueError, "unknown event phase: %s", str);
    return -1;
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
    cEventTriggers *triggers;
    cReactorEventPhase event_phase; 

    reactor = (cReactor *)self;

    /* Slice off the arguments we want to parse ourselves. */
    req_args = PyTuple_GetSlice(args, 0, 3);

    /* Now use PyArg_ParseTuple on the required args. */
    if (!PyArg_ParseTuple(req_args, "ssO:addSystemEventTrigger",
                          &phase_str, &event_type_str, &callable))
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

    /* Verify the given object is callable. */
    if (!PyCallable_Check(callable))
    {
        PyErr_Format(PyExc_TypeError,
                     "addSystemEventTrigger() arg 3 expected callable, got %s",
                     callable->ob_type->tp_name);
        return NULL;
    }

    triggers = get_event_triggers(reactor, event_type_str, 1);
    if (!triggers) {
        /* out of memory */
        PyErr_SetString(PyExc_MemoryError,
                        "could not allocate cEventTriggers struct");
        return NULL;
    }

    /* Now get the arguments to pass to the callable. */
    callable_args = PyTuple_GetSlice(args, 3, PyTuple_Size(args));

    /* Add this method to the appropriate list. */
    method_id = cReactorUtil_AddMethod(&triggers->triggers[event_phase],
                                       callable, callable_args, kw);
    Py_DECREF(callable_args);
    
    return PyInt_FromLong(method_id);
}


PyObject *
cReactor_removeSystemEventTrigger(PyObject *self, PyObject *args)
{
    cReactor *reactor = (cReactor *)self;
    int method_id;
    cEventTriggers *node, **last;
    int have_triggers, found = 0;
    int p;

    /* Now use PyArg_ParseTuple on the required args. */
    if (!PyArg_ParseTuple(args, "i:removeSystemEventTrigger", &method_id))
    {
        return NULL;
    }

    /* For now, just hack this in by searching all added triggers. Some day,
       the method_id returned by add() should be an object implementing
       ISystemEventTrigger or something, and that object should have a
       .remove method */

    node = reactor->event_triggers;
    while (node) {
        for (p = 0; p < CREACTOR_NUM_EVENT_PHASES; p++)
            if (cReactorUtil_RemoveMethod(&node->triggers[p], method_id) == 0)
                found++;
        node = node->next;
    }

    last = &reactor->event_triggers;
    while(*last) {
        node = *last;
        have_triggers = 0;
        for (p = 0; p < CREACTOR_NUM_EVENT_PHASES; p++)
            if (node->triggers[p])
                have_triggers++;
        if (have_triggers) {
            last = &(node->next);
        } else {
            /* delete the now-empty cEventTriggers structure */
            *last = node->next;
            free_event_trigger(node);
        } 
    }

    if (!found) {
        /* Did not find it.  ValueError. */
        PyErr_Format(PyExc_ValueError, "invalid method_id %d", method_id);
        return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

