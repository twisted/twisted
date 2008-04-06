/*
 * Copyright (c) 2007 Twisted Matrix Laboratories.
 * See LICENSE for details.
 *
 * A Deferred implementation in C. Cover most of the Deferred API but try
 * to be faster.
 *
 * TODO: Review failure handling - is everything decref'd properly?
 * TODO: Try to replace IsInstance calls with a fast ptr comparison?
 *
 */

#include <Python.h>
#include "structmember.h"

/* Py_VISIT and Py_CLEAR are defined here to be compatible with Python 2.3 */

#ifndef Py_VISIT
#define Py_VISIT(op) \
    do { \
        if (op) { \
            int vret = visit((PyObject *)(op), arg); \
            if (vret) \
                return vret; \
        } \
    } while (0)
#endif

#ifndef Py_CLEAR
#define Py_CLEAR(op) \
    do { \
        if (op) { \
            PyObject *tmp = (PyObject *)(op); \
            (op) = NULL; \
            Py_DECREF(tmp); \
        } \
    } while (0)
#endif

PyObject * failure_class = NULL;
PyObject * already_called = NULL;
PyObject * debuginfo_class = NULL;
PyObject * format_stack = NULL;

typedef struct {
    PyObject_HEAD
    PyObject *result;
    int paused;
    PyObject *callbacks;
    PyObject *debuginfo;
    int called;
    /* Current callback index in the callbacks list to run. This
     * allows clearing the list once per runCallbacks rather than
     * popping every item. It has to be per-deferred, because some
     * methods can be called reentrantly (e.g get callbacks list), and
     * it should not include the previously-called callbacks. */
    int callback_index;
    /* Currently running a callback. This is used to prevent
     * re-entrant running of callbacks. See #2849, this puts the C
     * deferred in line with the behaviour of the Python one. */
    int running_callbacks;
} cdefer_Deferred;

/* Prototypes */

static PyObject *cdefer_setDebugging(cdefer_Deferred *self,
        PyObject *args, PyObject *kwargs);

static PyObject *cdefer_getDebugging(cdefer_Deferred *self,
        PyObject *args, PyObject *kwargs);

static PyObject * cdefer_Deferred_new(PyTypeObject *type, PyObject *args,
        PyObject *kwargs);

static void cdefer_Deferred_dealloc(PyObject *o);

static int cdefer_Deferred_traverse(PyObject *o, visitproc visit, void *arg);

static int cdefer_Deferred_clear(PyObject *o);

static int cdefer_Deferred_clear(PyObject *o);

static int cdefer_Deferred___init__(cdefer_Deferred *self, PyObject *args,
        PyObject *kwargs);

static PyObject *cdefer_Deferred__addCallbacks(cdefer_Deferred *self,
        PyObject *callback, PyObject *errback, PyObject *callbackArgs,
        PyObject *callbackKeywords, PyObject *errbackArgs,
        PyObject *errbackKeywords);

static PyObject *cdefer_Deferred_addCallback(cdefer_Deferred *self,
        PyObject *args, PyObject *kwargs);

static PyObject *cdefer_Deferred_addErrback(cdefer_Deferred *self,
        PyObject *args, PyObject *kwargs);

static PyObject *cdefer_Deferred_addBoth(cdefer_Deferred *self, PyObject *args,
        PyObject *kwargs);

static PyObject *cdefer_Deferred_pause(cdefer_Deferred *self, PyObject *args);

static PyObject *cdefer_Deferred_unpause(cdefer_Deferred *self,
        PyObject *args);

static PyObject *cdefer_Deferred_chainDeferred(cdefer_Deferred *self,
        PyObject *args, PyObject *kwargs);

static PyObject *cdefer_Deferred__runCallbacks(cdefer_Deferred *self);

static PyObject *cdefer_Deferred__startRunCallbacks(cdefer_Deferred *self,
        PyObject *result);

static PyObject *cdefer_Deferred_callback(cdefer_Deferred *self, PyObject *args,
        PyObject *kwargs);

static PyObject *cdefer_Deferred_errback(cdefer_Deferred *self, PyObject *args,
        PyObject *kwargs);

static PyObject *cdefer_Deferred__continue(cdefer_Deferred *self,
        PyObject *args, PyObject *kwargs);


static int is_debug = 0;

static PyObject *cdefer_setDebugging(cdefer_Deferred *self,
        PyObject *args, PyObject *kwargs) {
    int new_debug;
    PyObject *on;
    static char *argnames[] = {"on", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O", argnames, &on)) {
        return NULL;
    }
    new_debug = PyObject_IsTrue(on);
    if (-1 == new_debug) {
        return NULL;
    }
    is_debug = new_debug;
    Py_INCREF(Py_None);
    return Py_None;
}

static char cdefer_setDebugging_doc[] =
    "setDebugging(on)\n"
    "Enable or disable Deferred debugging.\n"
    "\n"
    "    When debugging is on, the call stacks from creation and invocation are\n"
    "    recorded, and added to any AlreadyCalledErrors we raise.\n";


static PyObject *cdefer_getDebugging(cdefer_Deferred *self,
        PyObject *args, PyObject *kwargs) {
    static char *argnames[] = {NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "", argnames)) {
        return NULL;
    }
    return PyBool_FromLong(is_debug);
}

static char cdefer_getDebugging_doc[] =
    "getDebugging()\n"
    "Determine whether Deferred debugging is enabled.\n";


static PyTypeObject cdefer_DeferredType;

static PyObject * cdefer_Deferred_new(PyTypeObject *type, PyObject *args,
                                      PyObject *kwargs) {
    cdefer_Deferred *self;
    self = (cdefer_Deferred *)type->tp_alloc(type, 0);
    return (PyObject *)self;
}

static void cdefer_Deferred_dealloc(PyObject *o) {
    cdefer_Deferred *self;
    self = (cdefer_Deferred *)o;
    PyObject_GC_UnTrack(self);
    Py_XDECREF(self->result);
    Py_XDECREF(self->debuginfo);
    Py_XDECREF(self->callbacks);
    (*o->ob_type->tp_free)(o);
}

static int cdefer_Deferred_traverse(PyObject *o, visitproc visit, void *arg) {
    cdefer_Deferred *self;
    self = (cdefer_Deferred *)o;
    Py_VISIT(self->result);
    Py_VISIT(self->debuginfo);
    Py_VISIT(self->callbacks);
    return 0;
}

static int cdefer_Deferred_clear(PyObject *o) {
    cdefer_Deferred *self;
    self = (cdefer_Deferred *)o;
    Py_CLEAR(self->result);
    Py_CLEAR(self->debuginfo);
    Py_CLEAR(self->callbacks);
    return 0;
}

static int cdefer_Deferred__set_debug_stack(cdefer_Deferred *self, char *name) {
    int rc;
    PyObject *stack;

    stack = PyObject_CallObject(format_stack, NULL);
    if (!stack) {
        return -1;
    }
    rc = PyObject_SetAttrString(self->debuginfo, name, stack);
    Py_DECREF(stack);
    if (-1 == rc) {
        return -1;
    }
    return 0;
}

static int cdefer_Deferred___init__(cdefer_Deferred *self, PyObject *args,
                                    PyObject *kwargs) {
    static char *argnames[] = {NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "", argnames)) {
        return -1;
    }
    if (is_debug) {
        self->debuginfo = PyObject_CallObject(debuginfo_class, NULL);
        if (!self->debuginfo) {
            return -1;
        }
        if (-1 == cdefer_Deferred__set_debug_stack(self, "creator")) {
            /* Keep the debug info object even if we fail to format
             * stack or place it into the dict. */
            return -1;
        }
    }

    self->paused = 0;
    self->callback_index = 0;
    self->running_callbacks = 0;
    self->callbacks = PyList_New(0);
    if (!self->callbacks) {
        Py_CLEAR(self->debuginfo);
        return -1;
    }
    return 0;
}

static PyObject *cdefer_Deferred__addCallbacks(cdefer_Deferred *self,
        PyObject *callback, PyObject *errback, PyObject *callbackArgs,
        PyObject *callbackKeywords, PyObject *errbackArgs,
        PyObject *errbackKeywords) {
    PyObject *result;
    PyObject *cbs = 0;
    int rc;

    if (callback != Py_None) {
        if (!PyCallable_Check(callback)) {
            PyErr_SetNone(PyExc_AssertionError);
            return NULL;
        }
    }
    if (errback != Py_None) {
        if (!PyCallable_Check(errback)) {
            PyErr_SetNone(PyExc_AssertionError);
            return NULL;
        }
    }

    cbs = Py_BuildValue("((OOO)(OOO))",
                        callback, callbackArgs, callbackKeywords,
                        errback, errbackArgs, errbackKeywords);
    if (!cbs) {
        return NULL;
    }

    rc = PyList_Append(self->callbacks, cbs);
    Py_CLEAR(cbs);
    if (rc == -1) {
        return NULL;
    }

    if (self->called) {
        if (cdefer_Deferred__runCallbacks(self) == NULL) {
            return NULL;
        }
    }

    result = (PyObject *)self;
    Py_INCREF(result);
    return result;
}

static char cdefer_Deferred_addCallbacks_doc[] =
    "addCallbacks(callback, errback=None, callbackArgs=None, callbackKeywords=None, errbackArgs=None, errbackKeywords=None)\n"
    "Add a pair of callbacks (success and error) to this Deferred.\n"
    "\n"
    "These will be executed when the \'master\' callback is run.";

static PyObject *cdefer_Deferred_addCallbacks(cdefer_Deferred *self,
        PyObject *args, PyObject *kwargs) {
    static char *argnames[] = {"callback", "errback", "callbackArgs",
        "callbackKeywords", "errbackArgs", "errbackKeywords", NULL};
    PyObject *callback;
    PyObject *errback = Py_None;
    PyObject *callbackArgs = Py_None;
    PyObject *callbackKeywords = Py_None;
    PyObject *errbackArgs = Py_None;
    PyObject *errbackKeywords = Py_None;
    PyObject *result;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|OOOOO", argnames,
                &callback, &errback, &callbackArgs,
                &callbackKeywords, &errbackArgs, &errbackKeywords)) {
        return NULL;
    }
    result = cdefer_Deferred__addCallbacks(self, callback, errback,
        callbackArgs, callbackKeywords, errbackArgs, errbackKeywords);
    return result;
}

/* Returns a NEW reference to the callback/errback arg, and to the
 * cbackArgs, but a BORROWED reference to the keywords. In case of
 * error, no references are returned/touched */
static PyObject *extract_cback_args_kw(char *argname,
                                       PyObject *args, PyObject *kwargs,
                                       PyObject **cbackArgs,
                                       PyObject **cbackKeywords) {
    PyObject *cback;

    if (kwargs) {
        (*cbackKeywords) = kwargs;
    } else {
        (*cbackKeywords) = Py_None;
    }
    if (PyTuple_Size(args) > 0) {
        cback = PyTuple_GET_ITEM(args, 0);
        if (!cback) {
            return NULL;
        }
        (*cbackArgs) = PyTuple_GetSlice(args, 1, PyTuple_Size(args));
        if (!(*cbackArgs)) {
            return NULL;
        }
        Py_INCREF(cback);
    } else {
        cback = PyDict_GetItemString((*cbackKeywords), argname);
        if (!cback) {
            PyErr_Format(PyExc_TypeError,
                         "addCallback requires '%s' argument'", argname);
            return NULL;
        }
        (*cbackArgs) = Py_None;
        Py_INCREF(Py_None);

        /* "callback" in the keyword dict may be the only reference to
         * it, and we delete it from the dict, so we must own a
         * reference too */
        Py_INCREF(cback);

        if (PyDict_DelItemString((*cbackKeywords), argname) == -1) {
            Py_DECREF(cback);
            Py_DECREF(Py_None);
            return NULL;
        }
    }
    return cback;
}

static char cdefer_Deferred_addCallback_doc[] =
    "addCallback(callback, *args, **kw)\n"
    "Convenience method for adding just a callback.\n"
    "\n"
    "See L{addCallbacks}.";

static PyObject *cdefer_Deferred_addCallback(cdefer_Deferred *self,
        PyObject *args, PyObject *kwargs) {
    PyObject *callback;
    PyObject *callbackArgs;
    PyObject *callbackKeywords;
    PyObject *result;
    callback = extract_cback_args_kw(
        "callback", args, kwargs, &callbackArgs, &callbackKeywords);
    if (!callback) {
        return NULL;
    }
    result = cdefer_Deferred__addCallbacks(self, callback, Py_None, callbackArgs,
        callbackKeywords, Py_None, Py_None);
    Py_DECREF(callback);
    Py_DECREF(callbackArgs);
    return result;
}

static char cdefer_Deferred_addErrback_doc[] =
    "addErrback(errback, *args, **kw)\n"
    "Convenience method for adding just an errback.\n"
    "\n"
    "See L{addCallbacks}.";

static PyObject *cdefer_Deferred_addErrback(cdefer_Deferred *self,
        PyObject *args, PyObject *kwargs) {
    PyObject *errback;
    PyObject *errbackArgs;
    PyObject *errbackKeywords;
    PyObject *result;
    errback = extract_cback_args_kw(
        "errback", args, kwargs, &errbackArgs, &errbackKeywords);
    if (!errback) {
        return NULL;
    }
    result = cdefer_Deferred__addCallbacks(self, Py_None, errback, Py_None,
        Py_None, errbackArgs, errbackKeywords);
    Py_DECREF(errback);
    Py_DECREF(errbackArgs);
    return result;
}

static char cdefer_Deferred_addBoth_doc[] =
    "addBoth(callback, *args, **kw)\n"
    "Convenience method for adding a single callable as both a callback\n"
    "and an errback.\n"
    "\n"
    "See L{addCallbacks}.";

static PyObject *cdefer_Deferred_addBoth(cdefer_Deferred *self, PyObject *args,
        PyObject *kwargs) {
    PyObject *callback;
    PyObject *callbackArgs;
    PyObject *callbackKeywords;
    PyObject *result;
    callback = extract_cback_args_kw(
        "callback", args, kwargs, &callbackArgs, &callbackKeywords);
    if (!callback) {
        return NULL;
    }
    result = cdefer_Deferred__addCallbacks(self, callback, callback,
        callbackArgs, callbackKeywords, callbackArgs, callbackKeywords);
    Py_DECREF(callback);
    Py_DECREF(callbackArgs);
    return result;
}

static char cdefer_Deferred_pause_doc[] =
    "pause()\n"
    "Stop processing on a Deferred until L{unpause}() is called.";

static PyObject *cdefer_Deferred_pause(cdefer_Deferred *self, PyObject *args) {
    PyObject *result;
    self->paused++;
    result = Py_None;
    Py_INCREF(Py_None);
    return result;
}

static char cdefer_Deferred_unpause_doc[] =
    "unpause()\n"
    "Process all callbacks made since L{pause}() was called.";

static PyObject *cdefer_Deferred_unpause(cdefer_Deferred *self,
        PyObject *args) {
    self->paused--;
    if (!self->paused && self->called) {
        return cdefer_Deferred__runCallbacks(self);
    }
    Py_INCREF(Py_None);
    return Py_None;
}

static char cdefer_Deferred_chainDeferred_doc[] =
    "chainDeferred(d)\n"
    "Chain another Deferred to this Deferred.\n"
    "\n"
    "This method adds callbacks to this Deferred to call d's callback or\n"
    "errback, as appropriate. It is merely a shorthand way of performing\n"
    "the following::\n"
    "\n"
    "    self.addCallbacks(d.callback, d.errback)\n"
    "\n"
    "When you chain a deferred d2 to another deferred d1 with\n"
    "d1.chainDeferred(d2), you are making d2 participate in the callback\n"
    "chain of d1. Thus any event that fires d1 will also fire d2.\n"
    "However, the converse is B{not} true; if d2 is fired d1 will not be\n"
    "affected.\n";

static PyObject *cdefer_Deferred_chainDeferred(cdefer_Deferred *self,
        PyObject *args, PyObject *kwargs) {
    PyObject *d;
    PyObject *callback;
    PyObject *errback;
    PyObject *result;
    static char *argnames[] = {"d", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O", argnames, &d)) {
        return NULL;
    }
    callback = PyObject_GetAttrString(d, "callback");
    if (!callback) {
        return NULL;
    }
    errback = PyObject_GetAttrString(d, "errback");
    if (!errback) {
        Py_DECREF(callback);
        return NULL;
    }
    result = cdefer_Deferred__addCallbacks(self, callback, errback, Py_None,
        Py_None, Py_None, Py_None);
    Py_DECREF(callback);
    Py_DECREF(errback);
    return result;
}

static int cdefer_Deferred__set_debuginfo_fail_result(cdefer_Deferred *self) {
    if (!self->debuginfo) {
        self->debuginfo = PyObject_CallObject(debuginfo_class, NULL);
        if (!self->debuginfo) {
            return -1;
        }
    }
    if (PyObject_SetAttrString(self->debuginfo, "failResult", self->result) == -1) {
        return -1;
    }
    return 0;
}

static int cdefer_Deferred__clear_debuginfo(cdefer_Deferred *self) {
    if (self->debuginfo) {
        if (PyObject_SetAttrString(self->debuginfo, "failResult", Py_None) == -1) {
            return -1;
        }
    }
    return 0;
}


static int cdefer_Deferred__verify_callbacks_item(PyObject *callbacks_item) {
    if (!PyTuple_Check(callbacks_item)) {
        PyErr_SetString(PyExc_TypeError, "Callbacks' items must be tuples");
        return -1;
    }
    if (2 != PyTuple_GET_SIZE(callbacks_item)) {
        PyErr_SetString(PyExc_TypeError, "Callbacks' items must contain exactly (callback, errback)");
        return -1;
    }

    return 0;
}


static int cdefer_Deferred__verify_callback_entry(const char *callback_name,
                                                  PyObject *callback_entry) {
    PyObject *callback;
    PyObject *args;
    PyObject *kw;
    
    if (!PyTuple_Check(callback_entry)) {
        PyErr_Format(PyExc_TypeError, "%s entries must be tuples", callback_name);
        return -1;
    }
    if (3 != PyTuple_GET_SIZE(callback_entry)) {
        PyErr_Format(PyExc_TypeError, "%s entries must contain exactly (callback, args, kw)",
                     callback_name);
        return -1;
    }

    callback = PyTuple_GET_ITEM(callback_entry, 0);
    if ((Py_None != callback) && !PyCallable_Check(callback)) {
        PyErr_Format(PyExc_TypeError, "%s entry callback must be callable",
                     callback_name);
        return -1;
    }
    
    args = PyTuple_GET_ITEM(callback_entry, 1);
    if (Py_None != args) {
        if (Py_None == callback) {
            PyErr_Format(PyExc_TypeError, "%s entry got a None callback with non-None args",
                         callback_name);
            return -1;
        }
        if (!PyTuple_Check(args)) {
            PyErr_Format(PyExc_TypeError, "%s entry args must be tuples or None",
                         callback_name);
            return -1;
        }
    }

    kw = PyTuple_GET_ITEM(callback_entry, 2);
    if (Py_None != kw) {
        if (Py_None == callback) {
            PyErr_Format(PyExc_TypeError, "%s entry got a None callback with non-None kws",
                         callback_name);
            return -1;
        }
        if (!PyDict_CheckExact(kw)) {
            PyErr_Format(PyExc_TypeError, "%s entry kws must be dicts or None",
                         callback_name);
            return -1;
        }
    }

    return 0;
}


static PyObject *cdefer_Deferred__runCallbacks(cdefer_Deferred *self) {
    PyObject *cb;
    PyObject *item;
    PyObject *callbacktuple;
    PyObject *callback;
    PyObject *args;
    PyObject *newArgs;
    PyObject *newArgs2;
    PyObject *kwargs;
    PyObject *_continue;
    PyObject *type, *value, *traceback;
    PyObject *tmp;
    PyObject *result;
    int size;
    int offset;
    const char *callback_name;

    if (self->running_callbacks) {
        Py_INCREF(Py_None);
        return Py_None;
    }
    if (!self->paused) {
        cb = self->callbacks;

        if (!PyList_Check(cb)) {
            PyErr_SetString(PyExc_TypeError, "callbacks must be a list");
            return NULL;
        }

        for (;;) {
            size = PyList_GET_SIZE(cb);
            if (size == -1) {
                return NULL;
            }
            if (self->callback_index >= size) {
                break;
            }

            item = PyList_GET_ITEM(cb, self->callback_index);
            if (!item) {
                return NULL;
            }
            if (cdefer_Deferred__verify_callbacks_item(item)) {
                return NULL;
            }
            
            if (PyObject_IsInstance(self->result, failure_class)) {
                offset = 1;
                callback_name = "errback";
            } else {
                offset = 0;
                callback_name = "callback";
            }

            callbacktuple = PyTuple_GET_ITEM(item, offset);
            if (!callbacktuple) {
                return NULL;
            }

            if (cdefer_Deferred__verify_callback_entry(callback_name, callbacktuple)) {
                return NULL;
            }
            
            callback = PyTuple_GET_ITEM(callbacktuple, 0);
            if(!callback) {
                return NULL;
            }

            if (callback == Py_None) {
                ++self->callback_index;
                continue;
            }

            args = PyTuple_GET_ITEM(callbacktuple, 1);
            if (!args) {
                return NULL;
            }

            kwargs = PyTuple_GET_ITEM(callbacktuple, 2);
            if (!kwargs) {
                return NULL;
            }

            newArgs = Py_BuildValue("(O)", self->result);
            if (!newArgs) {
                return NULL;
            }

            if (args != Py_None) {
                newArgs2 = PySequence_InPlaceConcat(newArgs, args);
                Py_CLEAR(newArgs);
                if (!newArgs2) {
                    return NULL;
                }
            } else {
                newArgs2 = newArgs;
                newArgs = NULL;
            }

            ++self->callback_index;
            if (kwargs == Py_None) {
                kwargs = NULL;
            }
            self->running_callbacks = 1;
            tmp = PyObject_Call(callback, newArgs2, kwargs);
            self->running_callbacks = 0;
            Py_DECREF(self->result);
            self->result = tmp;

            Py_CLEAR(newArgs2);

            if (!self->result) {
                PyErr_Fetch(&type, &value, &traceback);
                PyErr_NormalizeException(&type, &value, &traceback);
                if (!traceback) {
                    traceback = Py_None;
                    Py_INCREF(traceback);
                }

                self->result = PyObject_CallFunction(failure_class, "OOO", value, type, traceback);
                if (!self->result) {
                    PyErr_Restore(type, value, traceback);
                    return NULL;
                }
                Py_DECREF(type);
                Py_DECREF(value);
                Py_DECREF(traceback);
                continue;
            }
            Py_INCREF(self->result);
            if (PyObject_TypeCheck(self->result, &cdefer_DeferredType)) {
                if (PyList_SetSlice(cb, 0, self->callback_index, NULL) == -1) {
                    return NULL;
                }
                self->callback_index = 0;

                result = PyObject_CallMethod((PyObject *)self, "pause", NULL);
                if (!result) {
                    return NULL;
                }
                Py_DECREF(result);

                _continue = PyObject_GetAttrString((PyObject *)self,
                                                   "_continue");
                if (!_continue) {
                    return NULL;
                }

                result = cdefer_Deferred__addCallbacks(
                    (cdefer_Deferred *)self->result, _continue,
                    _continue, Py_None, Py_None, Py_None, Py_None);
                /* The reference was either copied/incref'd or not
                 * (when errored) in addCallbacks, either way, we own
                 * one too, and don't need it anymore. */
                Py_DECREF(_continue);

                if (!result) {
                    return NULL;
                }
                Py_DECREF(result);

                goto endLabel;
            }
        }
        if (PyList_SetSlice(cb, 0, PyList_GET_SIZE(cb), NULL) == -1) {
            return NULL;
        }
        self->callback_index = 0;
    }
endLabel:
    if (PyObject_IsInstance(self->result, failure_class)) {
        result = PyObject_CallMethod((PyObject *)self->result,
                                     "cleanFailure", NULL);
        if (!result) {
            return NULL;
        }
        Py_DECREF(result);
        if (cdefer_Deferred__set_debuginfo_fail_result(self) == -1) {
            return NULL;
        }
    } else {
        if (cdefer_Deferred__clear_debuginfo(self) == -1) {
            return NULL;
        }
    }
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *cdefer_Deferred__startRunCallbacks(cdefer_Deferred *self,
                                                    PyObject *result) {
    PyObject * already_called_instance;
    PyObject * debug_tracebacks;

    if (is_debug && !self->debuginfo) {
        self->debuginfo = PyObject_CallObject(debuginfo_class, NULL);
        if (!self->debuginfo) {
            return NULL;
        }
    }

    if (self->called) {
        if (is_debug) {
            debug_tracebacks = PyObject_CallMethod(
                self->debuginfo, "_getDebugTracebacks", "s", "\n");
            if (!debug_tracebacks) {
                return NULL;
            }
            already_called_instance = PyObject_CallFunction(already_called, "O", debug_tracebacks);
            Py_DECREF(debug_tracebacks);
            if (!already_called_instance) {
                return NULL;
            }
            PyErr_SetObject(already_called, already_called_instance);
            Py_DECREF(already_called_instance);
            return NULL;
        }
        PyErr_SetNone(already_called);
        return NULL;
    }
    if (is_debug) {
        if (-1 == cdefer_Deferred__set_debug_stack(self, "invoker")) {
            /* Keep the debug info object even if we fail to format
             * stack or place it into the dict. */
            return NULL;
        }
    }

    self->called = 1;
    Py_XDECREF(self->result);
    self->result = result;
    Py_INCREF(self->result);
    return cdefer_Deferred__runCallbacks(self);
}

static char cdefer_Deferred_callback_doc[] =
    "callback(result)\n"
    "Run all success callbacks that have been added to this Deferred.\n"
    "\n"
    "Each callback will have its result passed as the first\n"
    "argument to the next; this way, the callbacks act as a\n"
    "'processing chain'. Also, if the success-callback returns a Failure\n"
    "or raises an Exception, processing will continue on the *error*-\n"
    "callback chain.";

static PyObject *cdefer_Deferred_callback(cdefer_Deferred *self, PyObject *args,
        PyObject *kwargs) {
    PyObject *result;
    static char *argnames[] = {"result", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O", argnames, &result)) {
        return NULL;
    }
    return cdefer_Deferred__startRunCallbacks(self, result);
}

static char cdefer_Deferred_errback_doc[] =
    "errback(fail=None)\n"
    "Run all error callbacks that have been added to this Deferred.\n"
    "\n"
    "Each callback will have its result passed as the first\n"
    "argument to the next; this way, the callbacks act as a\n"
    "'processing chain'. Also, if the error-callback returns a non-Failure\n"
    "or doesn't raise an Exception, processing will continue on the\n"
    "*success*-callback chain.\n"
    "\n"
    "If the argument that's passed to me is not a Failure instance,\n"
    "it will be embedded in one. If no argument is passed, a Failure\n"
    "instance will be created based on the current traceback stack.\n"
    "\n"
    "Passing a string as `fail' is deprecated, and will be punished with\n"
    "a warning message.";

static PyObject *cdefer_Deferred_errback(cdefer_Deferred *self, PyObject *args,
        PyObject *kwargs) {
    PyObject *fail;
    PyObject *tmp;
    PyObject *result;
    static char *argnames[] = {"fail", NULL};
    fail = Py_None;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|O", argnames, &fail)) {
        return NULL;
    }

    if (PyObject_IsInstance(fail, failure_class)) {
        /* Make "fail" belong to us even if we don't create a Failure
         * wrapper (If we do, the wrapper belongs to us) */
        Py_INCREF(fail);
    } else {
        tmp = PyObject_CallFunction(failure_class, "(O)", fail);
        if (!tmp) {
            return NULL;
        }
        fail = tmp;
    }
    result = cdefer_Deferred__startRunCallbacks(self, fail);
    Py_DECREF(fail);
    return result;
}

static PyObject *cdefer_Deferred__continue(cdefer_Deferred *self,
        PyObject *args, PyObject *kwargs) {
    PyObject *result;
    static char *argnames[] = {"result", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O", argnames, &result)) {
        return NULL;
    }
    Py_XDECREF(self->result);
    self->result = result;
    Py_INCREF(self->result);
    return PyObject_CallMethod((PyObject *)self, "unpause", NULL);
}

static struct PyMethodDef cdefer_Deferred_methods[] = {
  {"addCallbacks", (PyCFunction)cdefer_Deferred_addCallbacks,
                   METH_VARARGS|METH_KEYWORDS, cdefer_Deferred_addCallbacks_doc},
  {"addCallback", (PyCFunction)cdefer_Deferred_addCallback,
                  METH_VARARGS|METH_KEYWORDS, cdefer_Deferred_addCallback_doc},
  {"addErrback", (PyCFunction)cdefer_Deferred_addErrback,
                 METH_VARARGS|METH_KEYWORDS, cdefer_Deferred_addErrback_doc},
  {"addBoth", (PyCFunction)cdefer_Deferred_addBoth,
               METH_VARARGS|METH_KEYWORDS, cdefer_Deferred_addBoth_doc},
  {"chainDeferred", (PyCFunction)cdefer_Deferred_chainDeferred,
                    METH_VARARGS|METH_KEYWORDS, cdefer_Deferred_chainDeferred_doc},
  {"callback", (PyCFunction)cdefer_Deferred_callback,
               METH_VARARGS|METH_KEYWORDS, cdefer_Deferred_callback_doc},
  {"errback", (PyCFunction)cdefer_Deferred_errback,
              METH_VARARGS|METH_KEYWORDS, cdefer_Deferred_errback_doc},
  {"pause", (PyCFunction)cdefer_Deferred_pause,
            METH_VARARGS, cdefer_Deferred_pause_doc},
  {"unpause", (PyCFunction)cdefer_Deferred_unpause,
              METH_VARARGS, cdefer_Deferred_unpause_doc},
  {"_continue", (PyCFunction)cdefer_Deferred__continue,
                METH_VARARGS|METH_KEYWORDS, ""},
  {0, 0, 0, 0}
};

static struct PyMemberDef cdefer_Deferred_members[] = {
  {"result", T_OBJECT_EX, offsetof(cdefer_Deferred, result), 0, 0},
  {"called", T_INT, offsetof(cdefer_Deferred, called), 0, 0},
  {"paused", T_INT, offsetof(cdefer_Deferred, paused), 0, 0},
  {0, 0, 0, 0, 0}
};

static PyObject *cdefer_Deferred_get_callbacks(PyObject *o, void *context) {
    cdefer_Deferred *self = (cdefer_Deferred *)o;
    PyObject *cb = self->callbacks;
    return PyList_GetSlice(cb, self->callback_index, PyList_GET_SIZE(cb));
}

static int cdefer_Deferred_set_callbacks(PyObject *o, PyObject *new_value, void *context) {
    cdefer_Deferred *self = (cdefer_Deferred *)o;
    PyObject *cb = self->callbacks;
    return PyList_SetSlice(cb, self->callback_index, PyList_GET_SIZE(cb), new_value);
}

static PyGetSetDef cdefer_Deferred_getset[] = {
  {"callbacks",
   cdefer_Deferred_get_callbacks,
   cdefer_Deferred_set_callbacks,
   "DEPRECATED: The list of registered callbacks and errbacks on this deferred"},
};

static PyObject *cdefer_DeferredMetaType_get_debug(PyObject *deferredClass, void *context) {

    return PyBool_FromLong(is_debug);
}

static int cdefer_DeferredMetaType_set_debug(PyObject *deferredClass, PyObject *on, void *context) {
    int new_debug;
    
    if (NULL == on) {
        PyErr_SetString(PyExc_TypeError, "Cannot delete the deprecated debug attribute!");
        return -1;
    }

    new_debug = PyObject_IsTrue(on);
    if (-1 == new_debug) {
        return -1;
    }
    is_debug = new_debug;

    return 0;
}

static PyGetSetDef cdefer__DeferredMetaType_getset[] = {
  {"debug",
   cdefer_DeferredMetaType_get_debug,
   cdefer_DeferredMetaType_set_debug,
   "DEPRECATED: use getDebugging/setDebugging instead"},
};


/* The default tp_setattro assumes that to support setattr, the
 * instances have to be on the heap... */
static int
cdefer_DeferredMetaType_setattro(PyObject *type, PyObject *name, PyObject *value)
{
    return PyObject_GenericSetAttr(type, name, value);
}


static PyTypeObject cdefer_DeferredMetaType = {
    PyObject_HEAD_INIT(NULL)
    0,                          /*ob_size*/
    "cdefer._DeferredClass",    /*tp_name*/
    0,                          /*tp_basicsize*/
    0,                          /*tp_itemsize*/
    0,                          /*tp_dealloc*/
    0,                          /*tp_print*/
    0,                          /*tp_getattr*/
    0,                          /*tp_setattr*/
    0,                          /*tp_compare*/
    0,                          /*tp_repr*/
    0,                          /*tp_as_number*/
    0,                          /*tp_as_sequence*/
    0,                          /*tp_as_mapping*/
    0,                          /*tp_hash */
    0,                          /*tp_call*/
    0,                          /*tp_str*/
    0,                          /*tp_getattro*/
    cdefer_DeferredMetaType_setattro,/*tp_setattro*/
    0,                          /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT,         /*tp_flags*/
    "The type of the cdefer.Deferred type", /*tp_doc*/
    0,                          /*tp_traverse*/
    0,                          /*tp_clear*/
    0,                          /*tp_richcompare*/
    0,                          /*tp_weaklistoffset*/
    0,                          /*tp_iter*/
    0,                          /*tp_iternext*/
    0,                          /*tp_methods*/
    0,                          /*tp_members*/
    cdefer__DeferredMetaType_getset,/*tp_getset*/
    &PyType_Type,               /*tp_base*/
    0,                          /*tp_dict*/
    0,                          /*tp_descr_get*/
    0,                          /*tp_descr_set*/
    0,                          /*tp_dictoffset*/
    0,                          /*tp_init*/
    0,                          /*tp_alloc*/
    0,                          /*tp_new*/
    0,                          /*tp_free*/
    0,                          /*tp_is_gc*/
    0,                          /*tp_bases*/
    0,                          /*tp_mro*/
    0,                          /*tp_cache*/
    0,                          /*tp_subclasses*/
    0,                          /*tp_weaklist*/
};

static PyTypeObject cdefer_DeferredType = {
    PyObject_HEAD_INIT(&cdefer_DeferredMetaType)
    0,                          /*ob_size*/
    "cdefer.Deferred",          /*tp_name*/
    sizeof(cdefer_Deferred),    /*tp_basicsize*/
    0,                          /*tp_itemsize*/
    (destructor)cdefer_Deferred_dealloc,    /*tp_dealloc*/
    0,                          /*tp_print*/
    0,                          /*tp_getattr*/
    0,                          /*tp_setattr*/
    0,                          /*tp_compare*/
    0,                          /*tp_repr*/
    0,                          /*tp_as_number*/
    0,                          /*tp_as_sequence*/
    0,                          /*tp_as_mapping*/
    0,                          /*tp_hash */
    0,                          /*tp_call*/
    0,                          /*tp_str*/
    0,                          /*tp_getattro*/
    0,                          /*tp_setattro*/
    0,                          /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT|Py_TPFLAGS_BASETYPE|Py_TPFLAGS_HAVE_GC, /*tp_flags*/
    "This is a callback which will be put off until later.\n\nWhy do we want this? Well, in cases where a function in a threaded\nprogram would block until it gets a result, for Twisted it should\nnot block. Instead, it should return a Deferred.\n\nThis can be implemented for protocols that run over the network by\nwriting an asynchronous protocol for twisted.internet. For methods\nthat come from outside packages that are not under our control, we use\nthreads (see for example L{twisted.enterprise.adbapi}).\n\nFor more information about Deferreds, see doc/howto/defer.html or\nU{http://www.twistedmatrix.com/documents/howto/defer}.", /*tp_doc*/
    (traverseproc)cdefer_Deferred_traverse,   /*tp_traverse*/
    (inquiry)cdefer_Deferred_clear,           /*tp_clear*/
    0,                          /*tp_richcompare*/
    0,                          /*tp_weaklistoffset*/
    0,                          /*tp_iter*/
    0,                          /*tp_iternext*/
    cdefer_Deferred_methods,    /*tp_methods*/
    cdefer_Deferred_members,    /*tp_members*/
    cdefer_Deferred_getset,     /*tp_getset*/
    0,                          /*tp_base*/
    0,                          /*tp_dict*/
    0,                          /*tp_descr_get*/
    0,                          /*tp_descr_set*/
    0,                          /*tp_dictoffset*/
    (initproc)cdefer_Deferred___init__,   /*tp_init*/
    0,                          /*tp_alloc*/
    cdefer_Deferred_new,        /*tp_new*/
    0,                          /*tp_free*/
    0,                          /*tp_is_gc*/
    0,                          /*tp_bases*/
    0,                          /*tp_mro*/
    0,                          /*tp_cache*/
    0,                          /*tp_subclasses*/
    0,                          /*tp_weaklist*/
};

static PyMethodDef cdefer_methods[] = {
    {"setDebugging", (PyCFunction)cdefer_setDebugging,
     METH_VARARGS|METH_KEYWORDS, cdefer_setDebugging_doc},

    {"getDebugging", (PyCFunction)cdefer_getDebugging,
     METH_VARARGS|METH_KEYWORDS, cdefer_getDebugging_doc},

    {NULL}  /* Sentinel */
};

#ifndef PyMODINIT_FUNC  /* declarations for DLL import/export */
#define PyMODINIT_FUNC void
#endif
PyMODINIT_FUNC initcdefer(void) {
    PyObject * m = NULL;
    PyObject * failure_module = NULL;
    PyObject * defer_module = NULL;
    PyObject * traceback_module = NULL;

    if (PyType_Ready(&cdefer_DeferredMetaType) < 0) {
        return;
    }

    if (PyType_Ready(&cdefer_DeferredType) < 0) {
        return;
    }

    m = Py_InitModule3("cdefer", cdefer_methods, "cdefer");
    if (!m) {
        return;
    }

    Py_INCREF(&cdefer_DeferredType);
    PyModule_AddObject(m, "Deferred", (PyObject *)&cdefer_DeferredType);
    PyModule_AddObject(m, "_DeferredClass", (PyObject *)&cdefer_DeferredMetaType);

    failure_module = PyImport_ImportModule("twisted.python.failure");
    if (!failure_module) {
        goto Error;
    }

    failure_class = PyObject_GetAttrString(failure_module, "Failure");
    if (!failure_class) {
        goto Error;
    }

    defer_module = PyImport_ImportModule("twisted.internet.defer");
    if (!defer_module) {
        goto Error;
    }
    already_called = PyObject_GetAttrString(defer_module, "AlreadyCalledError");
    if (!already_called) {
        goto Error;
    }

    debuginfo_class = PyObject_GetAttrString(defer_module, "DebugInfo");
    if(!debuginfo_class) {
        goto Error;
    }

    traceback_module = PyImport_ImportModule("traceback");
    if (!traceback_module) {
        goto Error;
    }

    format_stack = PyObject_GetAttrString(traceback_module, "format_stack");
    if(!format_stack) {
        goto Error;
    }

    return;
Error:
    Py_XDECREF(failure_module);
    Py_XDECREF(failure_class);
    Py_XDECREF(defer_module);
    Py_XDECREF(already_called);
    Py_XDECREF(debuginfo_class);
    Py_XDECREF(traceback_module);
    Py_XDECREF(format_stack);
}

