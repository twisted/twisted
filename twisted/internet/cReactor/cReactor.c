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
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <stdio.h>
#include <signal.h>
#include <unistd.h>
#include <netdb.h>


/* Forward declare the cReactor type object. */
staticforward PyTypeObject cReactorType;

/* Available methods on the cReactor. */
static PyMethodDef cReactor_methods[] = 
{
    /* IReactorCore */
    { "resolve",                    (PyCFunction)cReactor_resolve,
      (METH_VARARGS | METH_KEYWORDS), "resolve" },
    { "run",                        cReactor_run,
      METH_VARARGS, "run" },
    { "stop",                       cReactor_stop,
      METH_VARARGS, "stop" },
    { "crash",                      cReactor_crash,
      METH_VARARGS, "crash" },
    { "iterate",                    (PyCFunction)cReactor_iterate,
      (METH_VARARGS | METH_KEYWORDS), "iterate" },
    { "fireSystemEvent",            cReactor_fireSystemEvent,
      METH_VARARGS, "fireSystemEvent" },
    { "addSystemEventTrigger",      (PyCFunction)cReactor_addSystemEventTrigger,
      (METH_VARARGS | METH_KEYWORDS), "addSystemEventTrigger" },
    { "removeSystemEventTrigger",   cReactor_removeSystemEventTrigger,
      METH_VARARGS, "removeSystemEventTrigger" },

    /* IReactorTime */
    { "callLater",          (PyCFunction)cReactorTime_callLater,
      (METH_VARARGS | METH_KEYWORDS), "callLater" },
    { "getDelayedCalls",    cReactorTime_getDelayedCalls,
      METH_VARARGS,  "getDelayedCalls" },
    { "cancelCallLater",    cReactorTime_cancelCallLater,
      METH_KEYWORDS,  "cancelCallLater" },

    /* IReactorTCP */
    { "listenTCP",          (PyCFunction)cReactorTCP_listenTCP,
      (METH_VARARGS | METH_KEYWORDS), "listenTCP" },
    { "connectTCP",          cReactorTCP_connectTCP,
      METH_VARARGS, "connectTCP" },

    /* IReactorThread */
    { "callFromThread",         (PyCFunction)cReactorThread_callFromThread,
      (METH_VARARGS | METH_KEYWORDS),   "callFromThread" },
    { "callInThread",           (PyCFunction)cReactorThread_callInThread,
      (METH_VARARGS | METH_KEYWORDS),   "callInThread" },
    { "suggestThreadPoolSize",  cReactorThread_suggestThreadPoolSize,
      METH_VARARGS,                     "suggestThreadPoolSize" },
    { "wakeUp",                 cReactorThread_wakeUp,
      METH_VARARGS,                     "wakeUp" },

    /* Custom addition to IReactorThread */
    { "initThreading",          cReactorThread_initThreading,
      METH_VARARGS,             "initThreading" },

    { NULL, NULL, METH_VARARGS, NULL },
};


PyObject *
cReactor_not_implemented(PyObject *self,
                         PyObject *args,
                         const char *text)
{
    UNUSED(self);
    UNUSED(args);

    PyErr_SetString(PyExc_NotImplementedError, text);
    return NULL;
}

/* TODO: This blocks and I don't have a async resolver library.  However, the
 * implementation in base.py also blocks :)
 */
PyObject *
cReactor_resolve(PyObject *self, PyObject *args, PyObject *kw)
{
    cReactor *reactor;
    const char *name;
    struct hostent *host;
    PyObject *defer;
    PyObject *defer_args;
    PyObject *callback;
    PyObject *errback;
    struct in_addr addr;
    int type        = 1;
    int timeout     = 10;
    static char *kwlist[] = { "name", "type", "timeout", NULL };

    reactor = (cReactor *)self;

    /* Args */
    if (!PyArg_ParseTupleAndKeywords(args, kw, "s|ii:resolve", kwlist,
                                     &name, &type, &timeout))
    {
        return NULL;
    }
        
    /* Create a Deferred. */
    defer = cReactorUtil_CreateDeferred();
    if (!defer)
    {
        return NULL;
    }

    /* Get the err and callback methods. */
    errback = PyObject_GetAttrString(defer, "errback");
    if (!errback)
    {
        Py_DECREF(defer);
        return NULL;
    }

    callback = PyObject_GetAttrString(defer, "callback");
    if (!callback)
    {
        Py_DECREF(defer);
        Py_DECREF(errback);
        return NULL;
    }

    /* Only type 1 is supported.  TODO: What is type 1? */
    if (type == 1)
    {
        /* Attempt the lookup. */
        host = gethostbyname(name);

        /* Schedule a method to call the "callback" or "errback" method on the
         * derferred whether or not we resolved the name.
         */
        if (host)
        {
            /* Verify the address length. */
            if (host->h_length == sizeof(addr))
            {
                memcpy(&addr, host->h_addr_list[0], host->h_length);
                defer_args = Py_BuildValue("(s)", inet_ntoa(addr));
                cReactorUtil_AddDelayedCall(reactor, 0, callback, defer_args, NULL);
            }
            else
            {
                defer_args = Py_BuildValue("(s)", "h_length != sizeof(addr)");
                cReactorUtil_AddDelayedCall(reactor, 0, errback, defer_args, NULL);
            }
            Py_DECREF(defer_args);
        }
        else
        {
            defer_args = Py_BuildValue("(s)", hstrerror(h_errno));
            cReactorUtil_AddDelayedCall(reactor, 0, errback, defer_args, NULL);
            Py_DECREF(defer_args);
        }
    }
    else
    {
        /* Type was not 1, schedule an errback call. */
        defer_args = Py_BuildValue("(s)", "only type 1 is supported");
        cReactorUtil_AddDelayedCall(reactor, 0, errback, defer_args, NULL);
        Py_DECREF(defer_args);
    }

    Py_DECREF(errback);
    Py_DECREF(callback);

    return defer;
}

void
cReactor_stop_finish(cReactor *reactor)
{
    /* called when shutdown triggers have completed */
    reactor->state = CREACTOR_STATE_STOPPED;
}

static void
stop_internal(cReactor *reactor)
{
    /* Change state and fire system event. */
    reactor->state = CREACTOR_STATE_STOPPING;
    fireSystemEvent_internal(reactor, "shutdown");
    /* state will move to STOPPED after all shutdown triggers have run. */
}


PyObject *
cReactor_stop(PyObject *self, PyObject *args)
{
    /* No args. */
    if (!PyArg_ParseTuple(args, ":stop"))
    {
        return NULL;
    }
    
    stop_internal((cReactor *)self);
    Py_INCREF(Py_None);
    return Py_None;
}

static volatile int received_signal;

static void
cReactor_sighandler(int sig)
{
    /* Record the signal. */
    received_signal = sig;
}

static void
iterate_rebuild_pollfd_arrray(cReactor *reactor)
{
    unsigned int num_transports;
    struct pollfd *pfd;
    cReactorTransport *transport;
    cReactorTransport *shadow;
    cReactorTransport *target;

    /* Make sure we have enough space to hold everything. */
    if (reactor->pollfd_size < reactor->num_transports)
    {
        if (reactor->pollfd_array)
        {
            free(reactor->pollfd_array);
        }
        reactor->pollfd_size    = reactor->num_transports * 2;
        reactor->pollfd_array   = (struct pollfd *)malloc(sizeof(struct pollfd) * reactor->pollfd_size);
    }

    /* Fill in the pollfd event struct using the transport info. */
    num_transports  = 0;
    pfd             = reactor->pollfd_array;
    transport       = reactor->transports;
    shadow          = NULL;
    while (transport)
    {
        /* Check for transports that are closed. */
        if (transport->state == CREACTOR_TRANSPORT_STATE_CLOSED)
        {
            target      = transport;
            transport   = transport->next;

            /* Remove the target node from the linked list. */
            if (shadow)
            {
                shadow->next = transport;
            }
            else
            {
                reactor->transports = transport;
            }

            /* Call the close function. */
            cReactorTransport_Close(target);
            Py_DECREF((PyObject *)target);
        }
        else
        {
            /* The transport is still valid, so fill in a pollfd struct. */
            pfd->fd     = transport->fd;
            pfd->events = 0;

            /* If they are active and have a do_read function add the POLLIN
             * event. */
            if (   (transport->state == CREACTOR_TRANSPORT_STATE_ACTIVE)
                && transport->do_read)
            {
                pfd->events |= POLLIN;
            }

            /* If they have a do_write function and there is data in the write
             * buffer or they have a producer, add in the POLLOUT event. */
            if (   transport->do_write 
                && (   (cReactorBuffer_DataAvailable(transport->out_buf) > 0)
                    || transport->producer))
            {
                pfd->events |= POLLOUT;
            }

            /* Update the transport's pointer to the events mask */
            transport->event_mask = &pfd->events;

            ++pfd;
            ++num_transports;
            shadow      = transport;
            transport   = transport->next;
        }
    }

    /* Update the number of active transports. */
    reactor->num_transports = num_transports;

    /* No longer stale. */
    reactor->pollfd_stale = 0;
}


static void
iterate_process_pollfd_array(cReactor *reactor)
{
    struct pollfd *pfd;
    cReactorTransport *transport;

    /* Iterate over the results. */
    for (pfd = reactor->pollfd_array, transport = reactor->transports;
         transport;
         ++pfd, transport = transport->next)
    {
        /* Verify */
        if (pfd->fd != transport->fd)
        {
            kill(0, SIGTRAP);
        }

        /* Check for any flags. */
        if (! pfd->revents)
        {
            continue;
        }

        if (pfd->revents & POLLIN)
        {
            cReactorTransport_Read(transport);
        }

        if (pfd->revents & POLLOUT)
        {
            cReactorTransport_Write(transport);
        }

        if (pfd->revents & (~(POLLIN | POLLOUT)))
        {
            /* TODO: Handle errors. */
            /* printf("fd=%d revents=0x%x\n", transport->fd, pfd->revents); */
            transport->state        = CREACTOR_TRANSPORT_STATE_CLOSED;
            reactor->pollfd_stale   = 1;
        }
    }
}


static void
ctrl_pipe_do_read(cReactorTransport *transport)
{
    char buf[16];
    read(transport->fd, buf, sizeof(buf));
}


static int
iterate_internal_init(cReactor *reactor)
{
    cReactorTransport *transport;
    int ctrl_pipes[2];

    /* Clear the received signal. */
    received_signal = 0;

    /* Install signal handlers. */
    signal(SIGINT, cReactor_sighandler);
    signal(SIGTERM, cReactor_sighandler);

    /* Create the control pipe. */
    if (pipe(ctrl_pipes) < 0)
    {
        PyErr_SetFromErrno(PyExc_RuntimeError);
        return -1; 
    }

    /* Make the read descriptor non-blocking. */
    if (fcntl(ctrl_pipes[0], F_SETFL, O_NONBLOCK) < 0)
    {
        close(ctrl_pipes[0]);
        close(ctrl_pipes[1]);
        PyErr_SetFromErrno(PyExc_RuntimeError);
        return -1;
    }

    /* Save the write descriptor. */
    reactor->ctrl_pipe = ctrl_pipes[1];

    /* Create a control transport for reading. */
    transport = cReactorTransport_New(reactor,
                                      ctrl_pipes[0], 
                                      ctrl_pipe_do_read,
                                      NULL,
                                      NULL);
    cReactor_AddTransport(reactor, transport);

    return 0;
}


static int
iterate_internal(cReactor *reactor, int delay)
{
    int method_delay;
    int sleep_delay;
    PyObject *result;
    cReactorJob *job;
    int poll_res;
    PyThreadState *thread_state = NULL;

    /* Figure out the method delay. */
    method_delay = cReactorUtil_NextMethodDelay(reactor);
    if (method_delay < 0)
    {
        /* No methods to run.  Sleep for the specified delay time. */
        sleep_delay = delay;
    }
    else if (delay >= 0)
    {
        /* Sleep until the next method or (at max) the given delay. */
        sleep_delay = (method_delay < delay) ? method_delay : delay;
    }
    else
    {
        /* Sleep until the next method. */
        sleep_delay = method_delay;
    }

    /* Refresh the pollfd list (if needed). */
    if (reactor->pollfd_stale)
    {
        iterate_rebuild_pollfd_arrray(reactor);
    }

    /* If in threaded mode release the global interpreter lock. */
    if (reactor->multithreaded)
    {
        thread_state = PyThreadState_Swap(NULL);
        PyEval_ReleaseLock(); 
    }

    /* Look for activity. */
    poll_res = poll(reactor->pollfd_array,
                    reactor->num_transports,
                    sleep_delay);

    /* Acquire the lock if we are using threads. */
    if (reactor->multithreaded)
    {
        PyEval_AcquireLock();
        PyThreadState_Swap(thread_state);
    }

    /* Check the poll() result. */
    if (poll_res < 0)
    {
        /* Anything other an EINTR raises an exception. */
        if (errno != EINTR)
        {
            PyErr_SetFromErrno(PyExc_RuntimeError);
            return -1;
        }
    }
    else
    {
        iterate_process_pollfd_array(reactor);
    }

    /* Run all the methods that need to run. */ 
    cReactorUtil_RunDelayedCalls(reactor);

    /* Check our job queue -- if there is one. */
    if (reactor->main_queue)
    {
        /* Run all scheduled jobs.  This might not be the safest idea. */
        for ( ; ; )
        {
            job = cReactorJobQueue_Pop(reactor->main_queue);
            if (! job)
            {
                break;
            }

            switch (job->type)
            {
                case CREACTOR_JOB_APPLY:
                    /* Run the callable. */
                    result = PyEval_CallObjectWithKeywords(job->u.apply.callable,
                                                           job->u.apply.args,
                                                           job->u.apply.kw);
                    Py_XDECREF(result);
                    if (! result)
                    {
                        PyErr_Print();
                    }
                    break;

                case CREACTOR_JOB_EXIT:
                    /* No one can tell the reactor's main thread to quit! */
                    break;
            }
            cReactorJob_Destroy(job);
        }
    }

    /* Lame signal handling for now. */
    if (received_signal)
    {
        if (reactor->state == CREACTOR_STATE_RUNNING)
        {
            /* Stop. */
            stop_internal(reactor);
        }
    }

    return 0;
}


PyObject *
cReactor_iterate(PyObject *self, PyObject *args, PyObject *kw)
{
    cReactor *reactor;
    PyObject *delay_obj     = NULL;
    int delay               = 0;
    static char *kwlist[]   = { "delay", NULL };

    reactor = (cReactor *)self;

    /* Args. */
    if (!PyArg_ParseTupleAndKeywords(args, kw, "|O:delay", kwlist, &delay_obj))
    {
        return NULL;
    }

    if (delay_obj)
    {
        delay = cReactorUtil_ConvertDelay(delay_obj);
        if (delay < 0)
        {
            return NULL;
        }
    }

    /* Run once. */
    if (iterate_internal(reactor, delay) < 0)
    {
        return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}


PyObject *
cReactor_run(PyObject *self, PyObject *args)
{
    cReactor *reactor;

    reactor = (cReactor *)self;

    /* We shouldn't get any args. */
    if (!PyArg_ParseTuple(args, ":run"))
    {
        return NULL;
    }

    if (reactor->state != CREACTOR_STATE_STOPPED)
    {
        /* _RUNNING means they tried to nest reactor.run() calls, and we
         don't allow that. _STOPPING means reactor.run() hasn't finished yet
         (XXX:??) */
        if (reactor->state == CREACTOR_STATE_RUNNING)
            PyErr_SetString(PyExc_RuntimeError,
                            "the reactor was already running!");
        else
            PyErr_SetString(PyExc_RuntimeError,
                            "the reactor was trying to stop!");
        return NULL;
    }
        

    /* Change our state to running. */
    reactor->state = CREACTOR_STATE_RUNNING;

    /* Fire the the startup system event. */
    fireSystemEvent_internal(reactor, "startup");

    /* "Begin at the beginning", the King said, very gravely, "and go on
       till you come to the end: then stop." */
    while (reactor->state != CREACTOR_STATE_STOPPED)
    {
        if (iterate_internal(reactor, -1) < 0)
        {
            return NULL;
        }
    }

    /* do cleanup when we stop running */
    cReactorThread_freeThreadpool(reactor); 

    Py_INCREF(Py_None);
    return Py_None;
}


PyObject *
cReactor_crash(PyObject *self, PyObject *args)
{
    cReactor *reactor;

    reactor = (cReactor *)self;

    /* Args */
    if (!PyArg_ParseTuple(args, ":crash"))
    {
        return NULL;
    }

    /* Move the state to done. */
    reactor->state = CREACTOR_STATE_STOPPED;

    Py_INCREF(Py_None);
    return Py_None;
}


void
cReactor_AddTransport(cReactor *reactor, cReactorTransport *transport)
{
    /* Add the new transport into the list.  This steals a reference. */
    transport->next         = reactor->transports;
    reactor->transports     = transport;
    ++(reactor->num_transports);
    
    /* PollFD array is now stale */
    reactor->pollfd_stale = 1;
}


static int
cReactor_init(cReactor *reactor)
{
    PyObject *when_threaded;
    PyObject *init_threading;
    PyObject *obj;
    static const char * interfaces[] = 
    {
        "IReactorCore",
        "IReactorTime",
        "IReactorTCP",
        "IReactorThreads",
    };

    /* Create the __implements__ attribute. */
    obj = cReactorUtil_MakeImplements(interfaces, sizeof(interfaces) / sizeof(interfaces[0]));
    if (!obj)
    {
        return -1;
    }

    /* Add the tuple into the attr dict. */
    if (PyDict_SetItemString(reactor->attr_dict, "__implements__", obj) != 0)
    {
        Py_DECREF(obj);
        return -1;
    }

    /* Add an attribute named __class__.  We will use our type object. */
    obj = (PyObject *)reactor->ob_type;
    if (PyDict_SetItemString(reactor->attr_dict, "__class__", obj) != 0)
    {
        return -1;
    }

    /* Set our state. */
    reactor->state = CREACTOR_STATE_STOPPED;

    /* We need to know when threading has begun. */
    when_threaded = cReactorUtil_FromImport("twisted.python.threadable",
                                            "whenThreaded");
    if (! when_threaded)
    {
        return -1;
    }

    /* Get our initThreading method. */
    init_threading = Py_FindMethod(cReactor_methods,
                                   (PyObject *)reactor,
                                   "initThreading");
    if (! init_threading)
    {
        Py_DECREF(when_threaded);
        return -1;
    }

    /* Register a callback. */
    obj = PyObject_CallFunction(when_threaded, "(O)", init_threading);
    Py_DECREF(when_threaded);
    Py_DECREF(init_threading);
    Py_XDECREF(obj);
    if (! obj)
    {
        return -1;
    }

    /* initialize signal handlers, signal-delivering pipes, */
    if (iterate_internal_init(reactor))
        return -1;

    return 0;
}


PyObject *
cReactor_New(void)
{
    cReactor *reactor;

    /* Create a new object. */
    cReactorType.ob_type = &PyType_Type;
    reactor = PyObject_New(cReactor, &cReactorType);

    /* No control pipe descriptors. */
    reactor->ctrl_pipe = -1;

    /* The object's attribute dictionary. */
    reactor->attr_dict = PyDict_New();

    /* List of timed methods. */
    reactor->timed_methods = NULL;

    /* Event triggers and the deferred list. */
    reactor->event_triggers = NULL;

    /* List of transports */
    reactor->transports         = NULL;
    reactor->num_transports     = 0;

    /* Array of pollfd structs. */
    reactor->pollfd_array       = NULL;
    reactor->pollfd_size        = 0;
    reactor->pollfd_stale       = 0;

    /* No thread job queue, or thread pool to start with. */
    reactor->multithreaded      = 0;
    reactor->main_queue         = NULL;
    reactor->thread_pool        = NULL;
    reactor->worker_queue       = NULL;
    reactor->req_thread_pool_size = 3;

    /* Attempt to initialize it. */
    if (   (! reactor->attr_dict)
        || (cReactor_init(reactor) < 0))
    {
        Py_DECREF((PyObject *)reactor);
        return NULL;
    }

    return (PyObject *)reactor;
}


static void
cReactor_dealloc(PyObject *self)
{
    cReactor *reactor;
    cReactorTransport *transport;
    cReactorTransport *target;

    reactor = (cReactor *)self;

    Py_DECREF(reactor->attr_dict);
    reactor->attr_dict = NULL;
    
    cReactorUtil_DestroyDelayedCalls(reactor);
    reactor->timed_methods = NULL;

    cSystemEvent_FreeTriggers(reactor->event_triggers);
    reactor->event_triggers = NULL;

    transport = reactor->transports;
    while (transport)
    {
        target      = transport;
        transport   = transport->next;
        Py_DECREF(target);
    }
    reactor->transports = NULL;

    free(reactor->pollfd_array);
    reactor->pollfd_array = NULL;

    PyObject_Del(self);
}

static PyObject *
cReactor_getattr(PyObject *self, char *attr_name)
{
    cReactor *reactor;
    PyObject *obj;
  
    reactor = (cReactor *)self;

    /* First check for a method with the given name.
     */
    obj = Py_FindMethod(cReactor_methods, self, attr_name);
    if (obj)
    {
        return obj;
    }
    /* Py_FindMethod raises an exception if it does not find the mthod */
    PyErr_Clear();

    /* Special case!  Woo */
    if (!strcmp("__dict__", attr_name))
    {
        return reactor->attr_dict;
    }

    /* Now check the attribute dictionary. */
    obj = PyDict_GetItemString(reactor->attr_dict, attr_name);

    /* If we didn't find anything raise PyExc_AttributeError. */
    if (!obj)
    {
        PyErr_SetString(PyExc_AttributeError, attr_name);
        return NULL;
    }

    /* PyDict_GetItemString returns a borrowed reference so we need to incref
     * it before returning it.
     */
    Py_INCREF(obj);
    return obj;
}

static PyObject *
cReactor_repr(PyObject *self)
{
    char buf[100];

    snprintf(buf, sizeof(buf) - 1, "<cReactor instance %p>", self);
    buf[sizeof(buf) - 1] = 0x00;

    return PyString_FromString(buf);
}

/* The cReactor type. */
static PyTypeObject cReactorType = 
{
    PyObject_HEAD_INIT(NULL)
    0,
    "cReactor",         /* tp_name */
    sizeof(cReactor),   /* tp_basicsize */
    0,                  /* tp_itemsize */
    cReactor_dealloc,   /* tp_dealloc */
    NULL,               /* tp_print */
    cReactor_getattr,   /* tp_getattr */
    NULL,               /* tp_setattr */
    NULL,               /* tp_compare */
    cReactor_repr,      /* tp_repr */
    NULL,               /* tp_as_number */
    NULL,               /* tp_as_sequence */
    NULL,               /* tp_as_mapping */
    NULL,               /* tp_hash */
    NULL,               /* tp_call */
    NULL,               /* tp_str */
    NULL,               /* tp_getattro */
    NULL,               /* tp_setattro */
    NULL,               /* tp_as_buffer */
    0,                  /* tp_flags */
    NULL,               /* tp_doc */
    NULL,               /* tp_traverse */
    NULL,               /* tp_clear */
    NULL,               /* tp_richcompare */
    0,                  /* tp_weaklistoffset */
};

/* vim: set sts=4 sw=4: */
