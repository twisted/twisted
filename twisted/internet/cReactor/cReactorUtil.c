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

/* The global method id allocator. */
static int next_call_id = 1;

/* The sorted method list node. */
struct _cReactorMethod
{
  int               call_id;
  time_t            call_time;
  PyObject *        callable;
  PyObject *        args;
  PyObject *        kw;
  cReactorMethod *  next;
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
    return cReactorUtil_AddDelayedMethod(list, 0, callable, args, kw);
}


int 
cReactorUtil_AddDelayedMethod(cReactorMethod **list,
                              int delay,
                              PyObject *callable,
                              PyObject *args,
                              PyObject *kw)
{
    cReactorMethod *method;
    cReactorMethod *node, *shadow;
    time_t call_time;

    /* Calc the call time. */
    time(&call_time);
    call_time += delay;

    /* Make the new method node. */
    method = (cReactorMethod *)malloc(sizeof(cReactorMethod));
    memset(method, 0x00, sizeof(cReactorMethod));
    method->call_id     = next_call_id++;
    method->call_time   = call_time;

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

    /* Find the insert point. */
    node    = *list;
    shadow  = NULL;
    while (node)
    {
        /* Check if we come before this node, if we have equal call times we
         * will work like a FIFO and put this new method after any methods
         * with the same call time.
         */
        if (method->call_time < node->call_time)
        {
            break;
        }
        shadow  = node;
        node    = node->next;
    }

    /* We should insert ourselves before node. */
    method->next = node;
    if (shadow)
    {
        shadow->next = method;
    }
    else
    {
        *list = method;
    }

    return method->call_id;
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

    /* Did not find it.  ValueError. */
    PyErr_Format(PyExc_ValueError, "invalid callID %d", call_id);
    return -1;
}
    

time_t
cReactorUtil_RunMethods(cReactorMethod **list, time_t now)
{
    cReactorMethod *node;
    cReactorMethod *method;
    PyObject *result;

    node = *list;
    while (node)
    {
        /* Check for stopping condition. */
        if (node->call_time > now)
        {
            break;
        }

        /* Remove this method from the head of the list. */
        method  = node;
        node    = node->next;
        *list   = node;

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

        /* Free resources. */
        Py_DECREF(method->callable);
        Py_XDECREF(method->args);
        Py_XDECREF(method->kw);
        free(method);
    }

    /* If there is a node left, return its call time. */
    return node ? node->call_time : 0;
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

int
cReactorUtil_GetEventType(const char *str, cReactorEventType *out_type)
{
    static struct {
        const char *        str;
        cReactorEventType   type;
    } type_map[] = 
    {
        { "startup",    CREACTOR_EVENT_TYPE_STARTUP },
        { "shutdown",   CREACTOR_EVENT_TYPE_SHUTDOWN },
        { "persist",    CREACTOR_EVENT_TYPE_PERSIST },
    };
    static int type_map_len = sizeof(type_map) / sizeof(type_map[0]);

    int i;

    for (i = 0; i < type_map_len; ++i)
    {
        if (strcmp(str, type_map[i].str) == 0)
        {
            *out_type = type_map[i].type;
            return 0;
        }
    }

    PyErr_Format(PyExc_ValueError, "unknown event type: %s", str);
    return -1;
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
cReactorUtil_NextMethodDelay(cReactorMethod *list)
{
    int delay;

    /* No methods on this list. */
    if (!list)
    {
        return -1;
    }

    /* Return something >= 0 */
    delay = list->call_time - time(NULL);
    return (delay > 0) ? delay : 0;
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
/* vim: set sts=4 sw=4: */
