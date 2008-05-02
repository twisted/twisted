/*
 * eventmodule.c:  a wrapper for libevent (http://monkey.org/~provos/libevent/)
 * Copyright (c) 2007-2008 Twisted Matrix Laboratories
 * Copyright (c) 2006 Andy Gross <andy@andygross.org>
 * Copyright (c) 2006 Nick Mathewson
 * See libevent_LICENSE for licensing information.
 */

#include <Python.h>
#include <sys/time.h>
#include <sys/types.h>
#include <event.h>
#include <structmember.h>

#ifndef Py_CLEAR
/* Py_CLEAR exists only starting Python 2.4 */
#define Py_CLEAR(op) \
    do { \
        if (op) { \
            PyObject *tmp = (PyObject *)(op); \
            (op) = NULL; \
            Py_DECREF(tmp); \
        } \
    } while (0)
#endif

#ifndef Py_VISIT
/* Py_VISIT exists only starting Python 2.4 */
#define Py_VISIT(op) \
    do { \
        if (op) { \
            int vret = visit((PyObject *)(op), arg); \
            if (vret) \
                return vret; \
        } \
    } while (0)
#endif

#ifndef Py_RETURN_NONE
/* Py_RETURN_NONE exists only starting Python 2.4 */
#define Py_RETURN_NONE return Py_INCREF(Py_None), Py_None
#endif

#define DEFAULT_NUM_PRIORITIES 3

#if PY_VERSION_HEX < 0x02040200
/*
 * Due to a bug in Python < 2.4.2, we have to define our own
 * PyGILState_Release.  Basically, the problem is that if you call it before
 * PyEval_InitThreads is called, it segfaults. As we don't want to init thread
 * uselessly, we backported the small change needed to make it work.
 */
void Safe_PyGILState_Release(PyGILState_STATE oldstate) {
    PyThreadState *tcur = PyGILState_GetThisThreadState();
    if (tcur && tcur->gilstate_counter > 0 && oldstate == PyGILState_UNLOCKED) {
        // The hack is here, to replace PyEval_ReleaseThread by PyEval_SaveThread
        --tcur->gilstate_counter;
        PyEval_SaveThread();
    } else {
        // Fallback to normal behavior
        return PyGILState_Release(oldstate);
    }
}
#else
// Here the default behavior is sane
# define Safe_PyGILState_Release PyGILState_Release
#endif

/*
 * EventBaseObject wraps a (supposedly) thread-safe libevent dispatch context.
 */
typedef struct EventBaseObject {
    PyObject_HEAD
    struct event_base *ev_base;
    /* A dict of EventObject => None */
    PyObject *registeredEvents;
} EventBaseObject;

/* Forward declaration of CPython type object */
static PyTypeObject EventBase_Type;

/*
 * EventObject wraps a libevent 'struct event'
 */
typedef struct EventObject {
    PyObject_HEAD
    struct event ev;
    EventBaseObject *eventBase;
    PyObject *callback;
    /* Duplicate original event flags since they seem to be modified when we
       arrive in the callback thunk */
    short flags;
} EventObject;

/* Forward declaration of CPython type object */
static PyTypeObject Event_Type;

/* EventObject prototypes */
static PyObject *Event_New(PyTypeObject *, PyObject *, PyObject *);
static int Event_Init(EventObject *, PyObject *, PyObject *);

/* Singleton default event base */
static EventBaseObject *defaultEventBase;

/* Error Objects */
PyObject *EventErrorObject;

/* Typechecker */
int EventBase_Check(PyObject *o) {
    return ((o->ob_type) == &EventBase_Type);
}

/* Construct a new EventBaseObject */
static PyObject *EventBase_New(PyTypeObject *type, PyObject *args,
                   PyObject *kwargs) {
    EventBaseObject *self = NULL;
    self = (EventBaseObject *)type->tp_alloc(type, 0);
    if (self == NULL) {
        return NULL;
    }
    self->ev_base = event_init();
    if (self->ev_base == NULL)  {
        Py_DECREF(self);
        return NULL;
    }
    self->registeredEvents = PyDict_New();
    return (PyObject *)self;
}

/* EventBaseObject initializer */
static int EventBase_Init(EventBaseObject *self, PyObject *args,
              PyObject *kwargs) {
    static char *kwlist[] = {"numPriorities", NULL};
    int numPriorities = 0;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|i:event", kwlist,
                     &numPriorities)) {
        return -1;
    }

    if (!numPriorities) {
        numPriorities = DEFAULT_NUM_PRIORITIES;
    }
    if (numPriorities < 0) {
        PyErr_SetString(PyExc_ValueError, "numPriorities must be a positive integer");
        return -1;
    }

    if ((event_base_priority_init(self->ev_base, numPriorities)) < 0) {
        return -1;
    }
    return 0;
}

/* Internal helper, register an event */
static void EventBase_RegisterEvent(EventBaseObject *self, PyObject *obj) {
    PyDict_SetItem(self->registeredEvents, obj, Py_None);
}

/* Internal helper, unregister an event */
static void EventBase_UnregisterEvent(EventBaseObject *self, PyObject *obj) {
    PyDict_DelItem(self->registeredEvents, obj);
}


static int EventBase_Traverse(EventBaseObject *self, visitproc visit, void *arg)
{
    Py_VISIT(self->registeredEvents);
    return 0;
}

static int EventBase_Clear(EventBaseObject *self)
{
    Py_CLEAR(self->registeredEvents);
    return 0;
}

/* EventBaseObject destructor */
static void EventBase_Dealloc(EventBaseObject *obj) {
    EventBase_Clear(obj);
    event_base_free(obj->ev_base);
    obj->ob_type->tp_free((PyObject *)obj);
}


/* EventBaseObject methods */
PyDoc_STRVAR(EventBase_LoopDoc,
"loop(self, [flags=0])\n\
\n\
Perform one iteration of the event loop.  Valid flags arg EVLOOP_NONBLOCK \n\
and EVLOOP_ONCE.");
static PyObject *EventBase_Loop(EventBaseObject *self, PyObject *args,
                PyObject *kwargs) {
    static char *kwlist[] = {"flags", NULL};
    int flags = 0;
    int rv = 0;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|i:loop", kwlist, &flags)) {
        return NULL;
    }

    Py_BEGIN_ALLOW_THREADS
    rv = event_base_loop(self->ev_base, flags);
    Py_END_ALLOW_THREADS

    if (PyErr_Occurred()) {
        return NULL;
    }

    return PyInt_FromLong(rv);
}

PyDoc_STRVAR(EventBase_LoopExitDoc,
"loopExit(self, seconds=0)\n\
\n\
Cause the event loop to exit after <seconds> seconds.");
static PyObject *EventBase_LoopExit(EventBaseObject *self, PyObject *args,
                    PyObject *kwargs) {
    static char *kwlist[] = {"seconds", NULL};
    struct timeval tv;
    int rv = 0;
    double exitAfterSecs = 0;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "d:loopExit",
                     kwlist, &exitAfterSecs)) {
        return NULL;
    }

    tv.tv_sec = (long) exitAfterSecs;
    tv.tv_usec = (exitAfterSecs - (long) exitAfterSecs) * 1000000;
    Py_BEGIN_ALLOW_THREADS
    rv = event_base_loopexit(self->ev_base, &tv);
    Py_END_ALLOW_THREADS

    if (PyErr_Occurred()) {
        return NULL;
    }

    return PyInt_FromLong(rv);
}

PyDoc_STRVAR(EventBase_DispatchDoc,
"dispatch(self)\n\
\n\
Run the main dispatch loop associated with this event base.  This function\n\
only terminates when no events remain, or the loop is terminated via an \n\
explicit call to EventBase.loopExit() or via a signal, or if a callback \n\
raises an exception.");
static PyObject *EventBase_Dispatch(EventBaseObject *self) {
    int rv = 0;
    Py_BEGIN_ALLOW_THREADS
    rv = event_base_dispatch(self->ev_base);
    Py_END_ALLOW_THREADS
    if (PyErr_Occurred()) {
        return NULL;
    }
    return PyInt_FromLong(rv);

}

PyDoc_STRVAR(EventBase_CreateEventDoc,
"createEvent(self, fd, events, callback)\n\
\n\
Create a new Event object for the given file descriptor that will call\n\
<callback> with a 3-tuple of (fd, events, eventObject) when the event\n\
fires. The first argument, fd, can be either an integer file descriptor\n\
or a 'file-like' object with a fileno() method.");
static EventObject *EventBase_CreateEvent(EventBaseObject *self,
                      PyObject *args, PyObject *kwargs) {
    EventObject *newEvent = NULL;

    newEvent = (EventObject *)Event_New(&Event_Type, NULL, NULL);

    if (Event_Init(newEvent, args, kwargs) < 0) {
        Py_DECREF(newEvent);
        return NULL;
    }

    if (PyObject_CallMethod((PyObject *)newEvent,
                "setEventBase", "O", self) == NULL) {
        Py_DECREF(newEvent);
        return NULL;
    }
    return newEvent;
}

PyDoc_STRVAR(EventBase_CreateTimerDoc,
"createTimer(self, callback, persist=False) -> new timer Event\n\
\n\
Create a new timer object that will call <callback>.  The timeout is not\n\
specified here, but rather via the Event.addToLoop([timeout]) method");
static EventObject *EventBase_CreateTimer(EventBaseObject *self,
                      PyObject *args, PyObject *kwargs) {
    static char *kwlist[] = {"callback", "persist", NULL};
    EventObject *newTimer = NULL;
    PyObject *callback = NULL;
    int persist = 0;
    int flags = EV_TIMEOUT;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|i:createTimer",
                     kwlist, &callback, &persist)) {
        return NULL;
    }

    if (persist) {
        flags |= EV_PERSIST;
    }

    newTimer = (EventObject *)PyObject_CallMethod((PyObject *)self,
                          "createEvent",
                          "OiO",
                          Py_None,
                          flags,
                          callback);
    return newTimer;
}

PyDoc_STRVAR(EventBase_CreateSignalHandlerDoc,
"createSignalHandler(self, signum, callback, persist=False) -> new signal handler Event\n\
\n\
Create a new signal handler object that will call <callback> when the signal\n\
is received.  Signal handlers are by default persistent - you must manually\n\
remove them with removeFromLoop().");
static EventObject *EventBase_CreateSignalHandler(EventBaseObject *self,
                          PyObject *args,
                          PyObject *kwargs) {
    static char *kwlist[] = {"signal", "callback", "persist", NULL};
    EventObject *newSigHandler = NULL;
    PyObject *callback = NULL;
    int sig = 0;
    int persist = 0;
    int flags = EV_SIGNAL;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "iO|i:createSignalHandler",
                     kwlist, &sig, &callback, &persist)) {
        return NULL;
    }

    if (persist) {
        flags |= EV_PERSIST;
    }

    newSigHandler = (EventObject *)PyObject_CallMethod((PyObject *)self,
                               "createEvent",
                               "iiO",
                               sig,
                               flags,
                               callback);
    return newSigHandler;
}

static PyGetSetDef EventBase_Properties[] = {
    {NULL}
};

static PyMemberDef EventBase_Members[] = {
    {NULL}
};

static PyMethodDef EventBase_Methods[] = {
    {"loop",                     (PyCFunction)EventBase_Loop,
     METH_VARARGS|METH_KEYWORDS, EventBase_LoopDoc},
    {"loopExit",                 (PyCFunction)EventBase_LoopExit,
     METH_VARARGS|METH_KEYWORDS, EventBase_LoopExitDoc},
    {"createEvent",              (PyCFunction)EventBase_CreateEvent,
     METH_VARARGS|METH_KEYWORDS, EventBase_CreateEventDoc},
    {"createSignalHandler",      (PyCFunction)EventBase_CreateSignalHandler,
     METH_VARARGS|METH_KEYWORDS, EventBase_CreateSignalHandlerDoc},
    {"createTimer",              (PyCFunction)EventBase_CreateTimer,
     METH_VARARGS|METH_KEYWORDS, EventBase_CreateTimerDoc},
    {"dispatch",                 (PyCFunction)EventBase_Dispatch,
     METH_NOARGS,                EventBase_DispatchDoc},
    {NULL},
};

static PyTypeObject EventBase_Type = {
    PyObject_HEAD_INIT(&PyType_Type)
    0,
    "_libevent.EventBase",                     /*tp_name*/
    sizeof(EventBaseObject),                   /*tp_basicsize*/
    0,                                         /*tp_itemsize*/
    /* methods */
    (destructor)EventBase_Dealloc,             /*tp_dealloc*/
    0,                                         /*tp_print*/
    0,                                         /*tp_getattr*/
    0,                                         /*tp_setattr*/
    0,                                         /*tp_compare*/
    0,                                         /*tp_repr*/
    0,                                         /*tp_as_number*/
    0,                                         /*tp_as_sequence*/
    0,                                         /*tp_as_mapping*/
    0,                                         /*tp_hash*/
    0,                                         /*tp_call*/
    0,                                         /*tp_str*/
    PyObject_GenericGetAttr,                   /*tp_getattro*/
    PyObject_GenericSetAttr,                   /*tp_setattro*/
    0,                                         /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE | Py_TPFLAGS_HAVE_GC, /*tp_flags*/
    0,                                         /*tp_doc*/
    (traverseproc)EventBase_Traverse,          /*tp_traverse*/
    (inquiry)EventBase_Clear,                  /*tp_clear*/
    0,                                         /*tp_richcompare*/
    0,                                         /*tp_weaklistoffset*/
    0,                                         /*tp_iter*/
    0,                                         /*tp_iternext*/
    EventBase_Methods,                         /*tp_methods*/
    EventBase_Members,                         /*tp_members*/
    EventBase_Properties,                      /*tp_getset*/
    0,                                         /*tp_base*/
    0,                                         /*tp_dict*/
    0,                                         /*tp_descr_get*/
    0,                                         /*tp_descr_set*/
    0,                                         /*tp_dictoffset*/
    (initproc)EventBase_Init,                  /*tp_init*/
    PyType_GenericAlloc,                       /*tp_alloc*/
    EventBase_New                              /*tp_new*/
};

/* Typechecker */
int Event_Check(PyObject *o) {
    return ((o->ob_type) == &Event_Type);
}

/* Construct a new EventObject */
static PyObject *Event_New(PyTypeObject *type, PyObject *args,
        PyObject *kwargs) {
    EventObject *self = NULL;
    self = (EventObject *)type->tp_alloc(type, 0);
    self->eventBase = NULL;
    return (PyObject *)self;
}

/* Callback thunk. */
static void __libevent_ev_callback(int fd, short events, void *arg) {
    EventObject *ev = arg;
    PyObject *result = 0;
    PyObject *tupleArgs;
    PyGILState_STATE gstate;
    gstate = PyGILState_Ensure();
    tupleArgs = Py_BuildValue("(iiO)", fd, events, ev);
    Py_INCREF((PyObject *) ev);
    result = PyObject_CallObject(ev->callback, tupleArgs);
    Py_CLEAR(tupleArgs);
    if (!(ev->flags & EV_PERSIST)) {
        /* Register the event for deletion but do not delete it right now.
           The list will be destroyed and its contents deallocated when the
           event loop returns. */
        EventBase_UnregisterEvent(ev->eventBase, (PyObject *) ev);
    }
    if (result) {
        Py_CLEAR(result);
    }
    else {
        struct timeval tv;
        tv.tv_sec = 0;
        tv.tv_usec = 0;
        /* Exit the loop, so that the error pops out to dispatch/loop. */
        event_base_loopexit(ev->ev.ev_base, &tv);
    }
    Py_DECREF((PyObject *) ev);
    Safe_PyGILState_Release(gstate);
}

/* EventObject initializer */
static int Event_Init(EventObject *self, PyObject *args, PyObject *kwargs) {
    int fd = -1;
    PyObject *fdObj = NULL;
    int events = 0;
    PyObject *callback = NULL;
    static char *kwlist[] = {"fd", "events", "callback", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OiO:event", kwlist,
                     &fdObj, &events, &callback)) {
        return -1;
    }

    if (!PyCallable_Check(callback)) {
        PyErr_SetString(PyExc_TypeError, "callback argument must be callable");
        return -1;
    }

    if (fdObj != Py_None) {
        if ((fd = PyObject_AsFileDescriptor(fdObj)) == -1) {
            return -1;
        }
    }
    event_set(&self->ev, fd, events, __libevent_ev_callback, self);
    if (!event_initialized(&self->ev)) {
        return -1;
    }

    Py_INCREF(callback);
    self->callback = callback;
    self->flags = events;
    return 0;
}

static int Event_Traverse(EventObject *self, visitproc visit, void *arg)
{
    /* Python 2.4 doesn't do the cast itself */
    Py_VISIT((PyObject *)self->eventBase);
    Py_VISIT(self->callback);
    return 0;
}

static int Event_Clear(EventObject *self)
{
    Py_CLEAR(self->eventBase);
    Py_CLEAR(self->callback);
    return 0;
}


PyDoc_STRVAR(Event_SetPriorityDoc,
"setPriority(self, priority)\n\
\n\
Set the priority for this event.");
static PyObject *Event_SetPriority(EventObject *self, PyObject *args,
                   PyObject *kwargs) {
    static char *kwlist[] = {"priority", NULL};
    int priority = 0;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs , "|i:setPriority",
                     kwlist, &priority)) {
        return NULL;
    }
    if (event_priority_set(&self->ev, priority) < 0) {
        PyErr_SetString(EventErrorObject,
                "error setting event priority - event is either already active or priorities are not enabled");
        return NULL;
    }
    Py_RETURN_NONE;
}

PyDoc_STRVAR(Event_AddToLoopDoc,
"addToLoop(self, timeout=-1)\n\
\n\
Add this event to the event loop, with a timeout of <timeout> seconds.\n\
A timeout value of -1 seconds causes the event to remain in the loop \n\
until it fires or is manually removed with removeFromLoop().");
static PyObject *Event_AddToLoop(EventObject *self, PyObject *args,
                 PyObject *kwargs) {
    double timeout = -1.0;
    struct timeval tv;
    static char *kwlist[] = {"timeout", NULL};
    int rv;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|d:addToLoop", kwlist,
                     &timeout)) {
        return NULL;
    }

    if (timeout >= 0.0) {
        tv.tv_sec = (long) timeout;
        tv.tv_usec = (timeout - (long) timeout) * 1000000;
        rv = event_add(&self->ev, &tv);
    }
    else {
        rv = event_add(&self->ev, NULL);
    }
    if (rv != 0) {
        return PyErr_SetFromErrno(EventErrorObject);
    }
    EventBase_RegisterEvent(self->eventBase, (PyObject *) self);
    Py_RETURN_NONE;
}

PyDoc_STRVAR(Event_RemoveFromLoopDoc,
"removeFromLoop(self)\n\
\n\
Remove the event from the event loop.");
static PyObject *Event_RemoveFromLoop(EventObject *self) {

    if (event_del(&self->ev) < 0) {
        return PyErr_SetFromErrno(EventErrorObject);
    }
    EventBase_UnregisterEvent(self->eventBase, (PyObject *) self);
    Py_RETURN_NONE;
}

PyDoc_STRVAR(Event_SetEventBaseDoc,
"setEventBase(self, eventBase)\n\
\n\
Set the event base for this event.");
static PyObject *Event_SetEventBase(EventObject *self, PyObject *args,
                    PyObject *kwargs) {
    static char *kwlist[] = {"eventBase", NULL};
    PyObject *eventBase, *old_eventBase;
    int rv = 0;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O", kwlist, &eventBase)) {
        return NULL;
    }

    if (!EventBase_Check(eventBase)) {
        PyErr_SetString(EventErrorObject, "argument is not an EventBase object");
        return NULL;
    }
    rv = event_base_set(((EventBaseObject *)eventBase)->ev_base, &self->ev);
    if (rv < 0) {
        PyErr_SetString(EventErrorObject, "unable to set event base");
        return NULL;
    }
    Py_INCREF(eventBase);
    /* Thread-safe way of removing an attr value */
    old_eventBase = (PyObject *) self->eventBase;
    self->eventBase = (EventBaseObject *)eventBase;
    Py_XDECREF(old_eventBase);
    Py_RETURN_NONE;
}

PyDoc_STRVAR(Event_PendingDoc,
"pending(self)\n\
\n\
Returns the event flags set for this event OR'd together.");
static PyObject *Event_Pending(EventObject *self) {
    int flags;
    flags = event_pending(&((EventObject *) self)->ev,
              EV_TIMEOUT | EV_READ | EV_WRITE | EV_SIGNAL, NULL);
    return PyInt_FromLong(flags);
}

PyDoc_STRVAR(Event_GetTimeoutDoc,
"getTimeout(self)\n\
\n\
Returns the expiration time of this event.");
static PyObject *Event_GetTimeout(EventObject *self) {
    double d;
    struct timeval tv;

    tv.tv_sec = -1;
    event_pending(&((EventObject *) self)->ev, 0, &tv);

    if (tv.tv_sec > -1) {
        d = tv.tv_sec + (tv.tv_usec / 1000000.0);
        return PyFloat_FromDouble(d);
    }
    Py_RETURN_NONE;
}

PyDoc_STRVAR(Event_FilenoDoc,
"fileno(self)\n\
\n\
Return the integer file descriptor number associated with this event.\n\
Not especially meaningful for signal or timer events.");
static PyObject *Event_Fileno(EventObject *self) {
    return PyInt_FromLong(self->ev.ev_fd);
}

/* EventObject destructor */
static void Event_Dealloc(EventObject *obj) {
    Event_Clear(obj);
    obj->ob_type->tp_free((PyObject *)obj);
}

static PyObject *Event_Repr(EventObject *self) {
    char buf[512];
    PyOS_snprintf(buf, sizeof(buf),
              "<event object, fd=%ld, events=%d>",
              (long) self->ev.ev_fd,
              (int) self->ev.ev_events);
    return PyString_FromString(buf);
}

#define OFF(x) offsetof(EventObject, x)
static PyMemberDef Event_Members[] = {
    {"eventBase", T_OBJECT, OFF(eventBase),
     RO, "The EventBase for this event object"},
    {"callback",  T_OBJECT, OFF(callback),
     RO, "The callback for this event object"},
    {"events",    T_SHORT,  OFF(ev.ev_events),
     RO, "Events registered for this event object"},
    {"numCalls",  T_SHORT,  OFF(ev.ev_ncalls),
     RO, "Number of times this event has been called"},
    {"priority",  T_INT,    OFF(ev.ev_pri),
     RO, "Event priority"},
    {"flags",     T_INT,    OFF(ev.ev_flags),
     RO, "Event flags (internal)"},
    {NULL}
};
#undef OFF

static PyGetSetDef Event_Properties[] = {
    {NULL},
};

static PyMethodDef Event_Methods[] = {
    {"addToLoop",                (PyCFunction)Event_AddToLoop,
     METH_VARARGS|METH_KEYWORDS, Event_AddToLoopDoc},
    {"removeFromLoop",           (PyCFunction)Event_RemoveFromLoop,
     METH_NOARGS,                Event_RemoveFromLoopDoc},
    {"fileno",                   (PyCFunction)Event_Fileno,
     METH_NOARGS,                Event_FilenoDoc},
    {"setPriority",              (PyCFunction)Event_SetPriority,
     METH_VARARGS|METH_KEYWORDS, Event_SetPriorityDoc},
    {"setEventBase",             (PyCFunction)Event_SetEventBase,
     METH_VARARGS|METH_KEYWORDS, Event_SetEventBaseDoc},
    {"pending",                  (PyCFunction)Event_Pending,
     METH_NOARGS,                Event_PendingDoc},
    {"getTimeout",               (PyCFunction)Event_GetTimeout,
     METH_NOARGS,                Event_GetTimeoutDoc},
    {NULL},
};

static PyTypeObject Event_Type = {
    PyObject_HEAD_INIT(&PyType_Type)
    0,
    "event.Event",                             /*tp_name*/
    sizeof(EventObject),                       /*tp_basicsize*/
    0,                                         /*tp_itemsize*/
    /* methods */
    (destructor)Event_Dealloc,                 /*tp_dealloc*/
    0,                                         /*tp_print*/
    0,                                         /*tp_getattr*/
    0,                                         /*tp_setattr*/
    0,                                         /*tp_compare*/
    (reprfunc)Event_Repr,                      /*tp_repr*/
    0,                                         /*tp_as_number*/
    0,                                         /*tp_as_sequence*/
    0,                                         /*tp_as_mapping*/
    0,                                         /*tp_hash*/
    0,                                         /*tp_call*/
    0,                                         /*tp_str*/
    PyObject_GenericGetAttr,                   /*tp_getattro*/
    PyObject_GenericSetAttr,                   /*tp_setattro*/
    0,                                         /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE | Py_TPFLAGS_HAVE_GC,  /*tp_flags*/
    0,                                         /*tp_doc*/
    (traverseproc)Event_Traverse,              /*tp_traverse*/
    (inquiry)Event_Clear,                      /*tp_clear*/
    0,                                         /*tp_richcompare*/
    0,                                         /*tp_weaklistoffset*/
    0,                                         /*tp_iter*/
    0,                                         /*tp_iternext*/
    Event_Methods,                             /*tp_methods*/
    Event_Members,                             /*tp_members*/
    Event_Properties,                          /*tp_getset*/
    0,                                         /*tp_base*/
    0,                                         /*tp_dict*/
    0,                                         /*tp_descr_get*/
    0,                                         /*tp_descr_set*/
    0,                                         /*tp_dictoffset*/
    (initproc)Event_Init,                      /*tp_init*/
    PyType_GenericAlloc,                       /*tp_alloc*/
    Event_New                                  /*tp_new*/
};

static PyMethodDef EventModule_Functions[] = {
    {NULL},
};

DL_EXPORT(void) init_libevent(void) {
    PyObject *m, *d;

    m = Py_InitModule("_libevent", EventModule_Functions);
    d = PyModule_GetDict(m);

    if (EventErrorObject == NULL) {
        EventErrorObject = PyErr_NewException("libevent.EventError",
                          NULL, NULL);
        if (EventErrorObject == NULL) {
            return;
        }
    }
    Py_INCREF(EventErrorObject);
    PyModule_AddObject(m, "EventError", EventErrorObject);

    if (PyType_Ready(&EventBase_Type) < 0) {
        return;
    }
    PyModule_AddObject(m, "EventBase", (PyObject *)&EventBase_Type);

    if (PyType_Ready(&Event_Type) < 0) {
        return;
    }
    PyModule_AddObject(m, "Event", (PyObject *)&Event_Type);

    defaultEventBase = (EventBaseObject *)EventBase_New(&EventBase_Type,
                            NULL, NULL);

    if (defaultEventBase == NULL) {
        PyErr_SetString(EventErrorObject,
                "error: couldn't create default event base");
        return;
    }
    if (EventBase_Init(defaultEventBase, PyTuple_New(0), NULL) < 0) {
        PyErr_SetString(EventErrorObject,
                "error: couldn't initialize default event base");
        return;
    }
    PyModule_AddObject(m, "DefaultEventBase", (PyObject *)defaultEventBase);

    /* Add constants to the module */
    PyModule_AddIntConstant(m, "EV_READ", EV_READ);
    PyModule_AddIntConstant(m, "EV_WRITE", EV_WRITE);
    PyModule_AddIntConstant(m, "EV_TIMEOUT", EV_TIMEOUT);
    PyModule_AddIntConstant(m, "EV_SIGNAL", EV_SIGNAL);
    PyModule_AddIntConstant(m, "EV_PERSIST", EV_PERSIST);
    PyModule_AddIntConstant(m, "EVLOOP_ONCE", EVLOOP_ONCE);
    PyModule_AddIntConstant(m, "EVLOOP_NONBLOCK", EVLOOP_NONBLOCK);
    PyModule_AddObject(m, "LIBEVENT_VERSION",
               PyString_FromString(event_get_version()));
    PyModule_AddObject(m, "LIBEVENT_METHOD",
               PyString_FromString(event_get_method()));
}

