
#include "cReactor.h"


static PyObject *AlreadyCalledException, *AlreadyCancelledException;

staticforward PyTypeObject cDelayedCallType;

cDelayedCall *
cDelayedCall_new(int delay_ms,
                 PyObject *callable,
                 PyObject *args,
                 PyObject *kw)
{
    cDelayedCall *call;
    struct timeval call_time;

    /* Calc the call time. */
    gettimeofday(&call_time, NULL);

    call_time.tv_usec   += (delay_ms * 1000);
    call_time.tv_sec    += call_time.tv_usec / 1000000;
    call_time.tv_usec   = call_time.tv_usec % 1000000;

    /* Make the new DelayedCall object. */
    call = PyObject_New(cDelayedCall, &cDelayedCallType);
    memcpy(&call->call_time, &call_time, sizeof(call_time));

    call->reactor = NULL;
    call->called = 0;

    Py_INCREF(callable);
    call->callable = callable;

    /* var args */
    if (!args)
    {
        call->args = PyTuple_New(0);
    }
    else
    {
        Py_INCREF(args);
        call->args = args;
    }

    /* keyword args */
    if (!kw)
    {
        call->kw = PyDict_New();
    }
    else
    {
        Py_INCREF(kw);
        call->kw = kw;
    }

    return call;
}

static void
cDelayedCall_dealloc(PyObject *self)
{
    cDelayedCall *call = (cDelayedCall *)self;

    Py_DECREF(call->callable);
    Py_XDECREF(call->args);
    Py_XDECREF(call->kw);
    free(call);
}

static PyObject *
cDelayedCall_getTime(PyObject *self, PyObject *args)
{
    cDelayedCall *call = (cDelayedCall *)self;
    double call_time;

    if (!PyArg_ParseTuple(args, ":getTime"))
        return NULL;

    if (!call->reactor) {
        /* not scheduled */
        if (call->called) {
            PyErr_SetString(AlreadyCalledException, "");
            return NULL;
        } else {
            PyErr_SetString(AlreadyCancelledException, "");
            return NULL;
        }
    }

    call_time = call->call_time.tv_sec + call->call_time.tv_usec / 1000000;

    return PyFloat_FromDouble(call_time);
}

static PyObject *
cDelayedCall_cancel(PyObject *self, PyObject *args)
{
    int rc;
    cDelayedCall *call = (cDelayedCall *)self;

    if (!call->reactor) {
        /* not scheduled */
        if (call->called) {
            PyErr_SetString(AlreadyCalledException, "");
            return NULL;
        } else {
            PyErr_SetString(AlreadyCancelledException, "");
            return NULL;
        }
    }

    rc = cReactorUtil_RemoveDelayedCall(call->reactor, call);
    if (rc != 0)
        return NULL;
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *
cDelayedCall_delay(PyObject *self, PyObject *args)
{
    cDelayedCall *call = (cDelayedCall *)self;
    PyObject *delay_obj = NULL;
    int delay_ms = 0;
    int rc;

    if (!PyArg_ParseTuple(args, "O:delay", &delay_obj))
        return NULL;

    if (delay_obj)
    {
        delay_ms = cReactorUtil_ConvertDelay(delay_obj);
        if (delay_ms < 0)
        {
            return NULL;
        }
    }

    if (!call->reactor) {
        /* not scheduled */
        if (call->called) {
            PyErr_SetString(AlreadyCalledException, "");
            return NULL;
        } else {
            PyErr_SetString(AlreadyCancelledException, "");
            return NULL;
        }
    }

    /* self.time += secondsLater */
    call->call_time.tv_usec   += (delay_ms * 1000);
    call->call_time.tv_sec    += call->call_time.tv_usec / 1000000;
    call->call_time.tv_usec   = call->call_time.tv_usec % 1000000;

    rc = cReactorUtil_ReInsertDelayedCall(call->reactor, call);
    if (rc != 0)
        return NULL;

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *
cDelayedCall_reset(PyObject *self, PyObject *args)
{
    cDelayedCall *call = (cDelayedCall *)self;
    PyObject *delay_obj = NULL;
    int delay_ms = 0;
    int rc;

    if (!PyArg_ParseTuple(args, "O:reset", &delay_obj))
        return NULL;

    if (delay_obj)
    {
        delay_ms = cReactorUtil_ConvertDelay(delay_obj);
        if (delay_ms < 0)
        {
            return NULL;
        }
    }

    if (!call->reactor) {
        /* not scheduled */
        if (call->called) {
            PyErr_SetString(AlreadyCalledException, "");
            return NULL;
        } else {
            PyErr_SetString(AlreadyCancelledException, "");
            return NULL;
        }
    }

    /* self.time = time() + secondsFromNow */
    gettimeofday(&call->call_time, NULL);

    call->call_time.tv_usec   += (delay_ms * 1000);
    call->call_time.tv_sec    += call->call_time.tv_usec / 1000000;
    call->call_time.tv_usec   = call->call_time.tv_usec % 1000000;

    rc = cReactorUtil_ReInsertDelayedCall(call->reactor, call);
    if (rc != 0)
        return NULL;

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *
cDelayedCall_active(PyObject *self, PyObject *args)
{
    cDelayedCall *call = (cDelayedCall *)self;

    if (!PyArg_ParseTuple(args, ":active"))
        return NULL;

    if (call->called)
        return PyInt_FromLong(0);
    else
        return PyInt_FromLong(1);
}

static PyMethodDef cDelayedCall_methods[] = 
{
    /* IDelayedCall */
    { "getTime", cDelayedCall_getTime, METH_VARARGS, "getTime" },
    { "cancel",  cDelayedCall_cancel,  METH_VARARGS, "cancel" },
    { "delay",   cDelayedCall_delay,   METH_VARARGS, "delay" },
    { "reset",   cDelayedCall_reset,   METH_VARARGS, "reset" },
    { "active",  cDelayedCall_active,  METH_VARARGS, "active" },

    { NULL, NULL, METH_VARARGS, NULL },
};

static PyObject *
cDelayedCall_getattr(PyObject *self, char *attr_name)
{
    PyObject *obj;

    /* check for a method with the given name. */
    obj = Py_FindMethod(cDelayedCall_methods, self, attr_name);
    if (obj)
        return obj;

    /* If we didn't find anything raise PyExc_AttributeError. */
    PyErr_SetString(PyExc_AttributeError, attr_name);
    return NULL;
}

/* todo: make a __str__ method that includes a description of the callable
   and args. It should also show how many seconds into the future the call
   will be fired. */

/* The cDelayedCall type. */
static PyTypeObject cDelayedCallType = 
{
    PyObject_HEAD_INIT(NULL)
    0,
    "cDelayedCall",        /* tp_name */
    sizeof(cDelayedCall),  /* tp_basicsize */
    0,                     /* tp_itemsize */
    cDelayedCall_dealloc,  /* tp_dealloc */
    NULL,                  /* tp_print */
    cDelayedCall_getattr,  /* tp_getattr */
    NULL,                  /* tp_setattr */
    NULL,                  /* tp_compare */
    NULL,                  /* tp_repr */
    NULL,                  /* tp_as_number */
    NULL,                  /* tp_as_sequence */
    NULL,                  /* tp_as_mapping */
    NULL,                  /* tp_hash */
    NULL,                  /* tp_call */
    NULL,                  /* tp_str */
    NULL,                  /* tp_getattro */
    NULL,                  /* tp_setattro */
    NULL,                  /* tp_as_buffer */
    0,                     /* tp_flags */
    NULL,                  /* tp_doc */
    NULL,                  /* tp_traverse */
    NULL,                  /* tp_clear */
    NULL,                  /* tp_richcompare */
    0,                     /* tp_weaklistoffset */
};

void
cDelayedCall_init(void)
{
    cDelayedCallType.ob_type = &PyType_Type;
    AlreadyCalledException =
        cReactorUtil_FromImport("twisted.internet.error",
                                "AlreadyCalled");
    if (!AlreadyCalledException) {
        PyErr_Print();
        return;
    }
    AlreadyCancelledException =
        cReactorUtil_FromImport("twisted.internet.error",
                                "AlreadyCancelled");
    if (!AlreadyCancelledException) {
        PyErr_Print();
        return;
    }
}
