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
/* cReactorUtil.c - various utility functions. */

/* includes */
#include "cReactor.h"
#include <sys/time.h>
#include <unistd.h>

/* The global method id allocator. */
static int next_call_id = 1;

/* The sorted method list node. */
struct _cReactorMethod
{
    int                 call_id;
    PyObject *          callable;
    PyObject *          args;
    PyObject *          kw;
    cReactorMethod *    next;
};

/* Do the equivalent of:
 * from foo.bar import baz
 * where "foo.bar" is 'name' and "baz" is 'from_item'
 */
PyObject *cReactorUtil_FromImport(const char *name, const char *from_item)
{
  PyObject *from_list;
  PyObject *module;
  PyObject *item;

  /* Make the from list. */
  from_list = PyList_New(1);
  PyList_SetItem(from_list, 0, PyString_FromString(from_item));

  /* Attempt the import, with const correctness removed. */
  module = PyImport_ImportModuleEx((char *)name, NULL, NULL, from_list);
  Py_DECREF(from_list);
  if (!module)
  {
    return NULL;
  }

  /* Get the from_item from the module. */
  item = PyObject_GetAttrString(module, (char *)from_item);
  Py_DECREF(module);

  return item;
}


int
cReactorUtil_AddMethod(cReactorMethod **list,
                       PyObject *callable,
                       PyObject *args,
                       PyObject *kw)
{
    cReactorMethod *method, **node;

    /* Make the new method node. */
    method = (cReactorMethod *)malloc(sizeof(cReactorMethod));
    memset(method, 0x00, sizeof(cReactorMethod));
    method->call_id = next_call_id++;

    Py_INCREF(callable);
    method->callable = callable;

    /* var args */
    if (!args)
    {
        method->args = PyTuple_New(0);
    }
    else
    {
        Py_INCREF(args);
        method->args = args;
    }

    /* keyword args */
    if (!kw)
    {
        method->kw = PyDict_New();
    }
    else
    {
        Py_INCREF(kw);
        method->kw = kw;
    }

    /* Append to the list: find the end */
    node = list;
    while(*node) {
        node = &((*node)->next);
    }

    method->next = *node;
    *node = method;

    return method->call_id;
}

cDelayedCall *
cReactorUtil_AddDelayedCall(cReactor *reactor,
                            int delay_ms,
                            PyObject *callable,
                            PyObject *args,
                            PyObject *kw)
{
    cDelayedCall *call;

    call = cDelayedCall_new(delay_ms, callable, args, kw);
    if (!call)
        return NULL;

    cReactorUtil_InsertDelayedCall(reactor, call);
    return call;
}

int
cReactorUtil_RemoveMethod(cReactorMethod **list, int call_id)
{
    cReactorMethod *node;
    cReactorMethod *shadow;

    /* Try to find the given call id. */
    shadow  = NULL;
    node    = *list;
    while (node)
    {
        if (node->call_id == call_id)
        {
            /* Patch up the list to remove node. */
            if (shadow)
            {
                shadow->next = node->next;
            }
            else
            {
                *list = node->next;
            }

            /* Free resources. */
            Py_DECREF(node->callable);
            Py_XDECREF(node->args);
            Py_XDECREF(node->kw);
            free(node);

            return 0;
        }

        shadow  = node;
        node    = node->next;
    }

    /* Did not find it. Caller may want to return a ValueError with
       something like: PyErr_Format(PyExc_ValueError, "invalid callID %d",
       call_id);, but we'll leave that up to them. */
    return -1;
}


int
cReactorUtil_RunDelayedCalls(cReactor *reactor)
{
    cDelayedCall *node;
    cDelayedCall *method;
    cDelayedCall **list = &reactor->timed_methods;
    PyObject *result;
    struct timeval now;
    int delay;

    gettimeofday(&now, NULL);

    node = *list;
    while (node)
    {
        /* Check for stopping condition. */
        if (   (node->call_time.tv_sec > now.tv_sec)
            || (node->call_time.tv_usec > now.tv_usec))
        {
            break;
        }

        /* Remove this method from the head of the list. */
        method  = node;
        node    = node->next;
        *list   = node;
        method->reactor = NULL;
        method->called = 1;

        /* Run it. -- This can add or remove methods in 'list'. */
        result = PyEval_CallObjectWithKeywords(method->callable, method->args, method->kw);
        if (!result)
        {
            PyErr_Print();
        }
        else
        {
            Py_DECREF(result);
        }

        Py_DECREF(method);
    }

    /* If there is a node left, return the number of milliseconds until it
     * needs to be called.
     */
    if (node)
    {
        delay = ((node->call_time.tv_sec - now.tv_sec) * 1000)
                + ((node->call_time.tv_usec - now.tv_usec) / 1000);
    }
    else
    {
        delay = -1;
    }

    return delay;
}

void
cReactorUtil_DestroyMethods(cReactorMethod *list)
{
    cReactorMethod *node;

    while (list)
    {
        node = list;
        list = list->next;

        Py_DECREF(node->callable);
        Py_XDECREF(node->args);
        Py_XDECREF(node->kw);
        free(node);
    }
}


void 
cReactorUtil_ForEachMethod(cReactorMethod *list,
                           cReactorMethodListIterator func,
                           void *user_data)
{
    while (list)
    {
        (*func)(list->callable, list->args, list->kw, user_data);
        list = list->next;
    }
}


int
cReactorUtil_NextMethodDelay(cReactor *reactor)
{
    int delay;
    struct timeval now;
    cDelayedCall *list = reactor->timed_methods;

    /* No methods on this list. */
    if (!list)
    {
        return -1;
    }

    /* Get the delta. */
    gettimeofday(&now, NULL);
    delay = ((list->call_time.tv_sec - now.tv_sec) * 1000)
            + ((list->call_time.tv_usec - now.tv_usec) / 1000);

    /* Clamp to zero. */
    if (delay < 0)
    {   
        delay = 0;
    }

    return delay;
}


PyObject *
cReactorUtil_MakeImplements(const char **names, unsigned int num_names)
{
    PyObject *obj;
    PyObject *impl_tup;
    const char **s;
    unsigned int u;

    /* Create the empty __implements__ tuple. */
    impl_tup = PyTuple_New(num_names);

    /* Add the appropriate interface classes into the tuple. */
    for (s = names, u = 0; u < num_names; ++s, ++u)
    {
        obj = cReactorUtil_FromImport("twisted.internet.interfaces", *s);
        if (   (!obj)
            || (PyTuple_SetItem(impl_tup, u, obj) < 0))
        {
            Py_DECREF(impl_tup);
            return NULL;
        }
    }

    return impl_tup;
}


PyObject *
cReactorUtil_CreateDeferred(void)
{
    PyObject *defer_class;

    /* Get the class object. */
    defer_class = cReactorUtil_FromImport("twisted.internet.defer", "Deferred");
    if (!defer_class)
    {   
        return NULL;
    }

    /* Return a new instance. */
    return PyObject_CallFunction(defer_class, "()");
}


int
cReactorUtil_ConvertDelay(PyObject *delay_obj)
{
    int delay;
    double delay_float;

    /* Verify we have a number. */
    if (!PyNumber_Check(delay_obj))
    {
        PyErr_SetString(PyExc_ValueError, "delay arg must be a number!");
        return -1;
    }

    /* Convert to double obj. */
    delay_obj = PyNumber_Float(delay_obj);
    if (!delay_obj)
    {
        return -1;
    }
   
    /* Get a double. */
    delay_float = PyFloat_AsDouble(delay_obj);
    Py_DECREF(delay_obj);

    /* Convert to millisecond int. */
    delay = (int)(delay_float * 1000.0f);

    /* If it is negative, raise. */
    if (delay < 0)
    {
        PyErr_SetString(PyExc_ValueError, "delay is negative!");
    }

    return delay;
}

void
cReactorUtil_InsertDelayedCall(cReactor *reactor, cDelayedCall *call)
{
    cDelayedCall *node, *shadow;
    cDelayedCall **list = &reactor->timed_methods;

    /* Find the insert point. */
    node    = *list;
    shadow  = NULL;
    while (node)
    {
        /* Check if we come before this node, if we have equal call times we
         * will work like a FIFO and put this new call after any calls
         * with the same call time.
         */
        if (   (call->call_time.tv_sec < node->call_time.tv_sec)
            && (call->call_time.tv_usec < node->call_time.tv_usec))
        {
            break;
        }
        shadow  = node;
        node    = node->next;
    }

    /* We should insert ourselves before node. */
    call->reactor = reactor;
    call->next = node;
    if (shadow)
    {
        shadow->next = call;
    }
    else
    {
        *list = call;
    }
    /* there will be two references to the new node: the one in the list,
       and the one returned to the caller. */
    Py_INCREF((PyObject *)call);
}

int
cReactorUtil_RemoveDelayedCall(cReactor *reactor, cDelayedCall *call)
{
    cDelayedCall *node;
    cDelayedCall *shadow;
    cDelayedCall **list = &reactor->timed_methods;

    /* Try to find the given call */
    shadow  = NULL;
    node    = *list;
    while (node)
    {
        if (node == call)
        {
            /* Patch up the list to remove node. */
            if (shadow)
            {
                shadow->next = node->next;
            }
            else
            {
                *list = node->next;
            }
            node->reactor = NULL;

            Py_DECREF(node);

            return 0;
        }

        shadow  = node;
        node    = node->next;
    }

    /* Did not find it.  ValueError. */
    PyErr_Format(PyExc_ValueError, "no such cDelayedCall");
    /* TODO: tell them which delayed call */
    return -1;
}

int
cReactorUtil_ReInsertDelayedCall(cReactor *reactor, cDelayedCall *call)
{
    int rc;

    Py_INCREF(call);
    rc = cReactorUtil_RemoveDelayedCall(reactor, call);
    if (rc == 0)
        cReactorUtil_InsertDelayedCall(reactor, call);
    Py_DECREF(call);

    return rc;
}

void
cReactorUtil_DestroyDelayedCalls(cReactor *reactor)
{
    cDelayedCall *list = reactor->timed_methods;
    cDelayedCall *node;

    while (list)
    {
        node = list;
        list = list->next;
        node->reactor = NULL;

        Py_DECREF(node);
    }
}

/* vim: set sts=4 sw=4: */
