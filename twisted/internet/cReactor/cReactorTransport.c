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
/* cReactorTransport.c - Implementation of a Transport object. */

/* includes */
#include "cReactor.h"
#include <unistd.h>

/* Forward declare the type object. */
staticforward PyTypeObject cReactorTransportType;

/* The cReactorTransport __implements__ tuple. */
static PyObject * cReactorTransport__implements__ = NULL;

void
cReactorTransport_Read(cReactorTransport *transport)
{
    /* No extra default behavior. */
    if (transport->do_read)
    {
        (*transport->do_read)(transport);
    }
}

void
cReactorTransport_Write(cReactorTransport *transport)
{
    PyObject *result;

    /* If we have data call the transport's write function. */
    if (   transport->do_write
        && (cReactorBuffer_DataAvailable(transport->out_buf) > 0))
    {
        (*transport->do_write)(transport);
    }

    /* If we have a non-streaming producer check for an empty buffer and ask
     * the producer to produce some more data.
     * TODO: Change this to be "below some threshold" instead of "when the out
     * buffer is empty."
     */
    if (   transport->producer
        && (transport->producer_streaming == 0)
        && (cReactorBuffer_DataAvailable(transport->out_buf) == 0))
    {
        result = PyObject_CallMethod(transport->producer, "resumeProducing", NULL);
        Py_XDECREF(result);
        if (!result)
        {
            PyErr_Print();
        }
    }
}


void
cReactorTransport_Close(cReactorTransport *transport)
{
    PyObject *result;

    /* Tell our producer to stop (if we have one) */
    if (transport->producer)
    {
        result = PyObject_CallMethod(transport->producer, "stopProducing", NULL);
        Py_XDECREF(result);
        if (!result)
        {
            PyErr_Print();
        }

        /* Release our producer. */
        Py_DECREF(transport->producer);
        transport->producer = NULL;
    }

    /* Call the specialized close function. */
    if (transport->do_close)
    {
        (*transport->do_close)(transport);
    }
}


static PyObject *
cReactorTransport_write(PyObject *self, PyObject *args)
{
    char *data;
    int data_len;

    cReactorTransport *transport = (cReactorTransport *)self;

    /* Args. */
    if (!PyArg_ParseTuple(args, "s#:write", &data, &data_len))
    {
        return NULL;
    }

    /* Allocate a buffer if we need one. */
    if (! transport->out_buf)
    {
        transport->out_buf = cReactorBuffer_New(data_len * 2);
    }

    /* Write. */
    cReactorBuffer_Write(transport->out_buf, data, data_len);

    /* Mark ourselves as looking for the POLLOUT event. */
    *transport->event_mask = (*transport->event_mask) | POLLOUT;

    Py_INCREF(Py_None);
    return Py_None;
}


static PyObject *
cReactorTransport_loseConnection(PyObject *self, PyObject *args)
{
    cReactorTransport *transport;

    transport = (cReactorTransport *)self;

    /* Args */
    if (!PyArg_ParseTuple(args, ":loseConnection"))
    {
        return NULL;
    }

    /* Change the state to CLOSING.  This will continue to write out any data
     * left in the write buffer, then it will close the connection.
     */
    transport->state = CREACTOR_TRANSPORT_STATE_CLOSING;

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *
cReactorTransport_getPeer(PyObject *self, PyObject *args)
{
    cReactorTransport *transport;
    transport = (cReactorTransport *)self;

    /* Args */
    if (!PyArg_ParseTuple(args, ":getPeer"))
    {
        return NULL;
    }
   
    if (!transport->get_peer)
    {
        PyErr_SetString(PyExc_NotImplementedError, "getPeer");
        return NULL;
    }

    return (*transport->get_peer)(transport);
}


static PyObject *
cReactorTransport_getHost(PyObject *self, PyObject *args)
{
    cReactorTransport *transport;
    transport = (cReactorTransport *)self;

    /* Args */
    if (!PyArg_ParseTuple(args, ":getHost"))
    {
        return NULL;
    }
   
    if (!transport->get_host)
    {
        PyErr_SetString(PyExc_NotImplementedError, "getHost");
        return NULL;
    }

    return (*transport->get_host)(transport);
}


static PyObject *
cReactorTransport_registerProducer(PyObject *self, PyObject *args)
{
    PyObject *producer;
    int streaming;
    cReactorTransport *transport;

    transport = (cReactorTransport *)self;

    /* Args */
    if (!PyArg_ParseTuple(args, "Oi:registerProducer", &producer, &streaming))
    {
        return NULL;
    }

    /* Do not allow multiple producers. */
    if (transport->producer)
    {
        PyErr_SetString(PyExc_ValueError, "a producer is already registered!");
        return NULL;
    }

    /* Record the fact that we have a producer. */
    Py_INCREF(producer);
    transport->producer             = producer;
    transport->producer_streaming   = streaming;

    /* Modify our poll flags to indicate we are looking for POLLOUT events.
     */
    *transport->event_mask = (*transport->event_mask) | POLLOUT;

    Py_INCREF(Py_None);
    return Py_None;
}


static PyObject *
cReactorTransport_unregisterProducer(PyObject *self, PyObject *args)
{
    cReactorTransport *transport;
    transport = (cReactorTransport *)self;

    /* Args */
    if (!PyArg_ParseTuple(args, ":unregisterProducer"))
    {
        return NULL;
    }

    /* Just release the reference. */
    Py_XDECREF(transport->producer);
    transport->producer = NULL;

    Py_INCREF(Py_None);
    return Py_None;
}


cReactorTransport *
cReactorTransport_New(cReactor *reactor,
                       int fd,
                       cReactorTransportReadFunc do_read,
                       cReactorTransportWriteFunc do_write,
                       cReactorTransportCloseFunc do_close)
{
    cReactorTransport *transport;
    static const char *interfaces[] = 
    {
        "ITransport",
        "IConsumer",
    };


    /* Create the __implements__ attribute if needed. */
    if (! cReactorTransport__implements__)
    {
        cReactorTransport__implements__ = cReactorUtil_MakeImplements(interfaces,
                                                                      sizeof(interfaces) / sizeof(interfaces[0]));
        if (! cReactorTransport__implements__)
        {
            return NULL;
        }
    }

    cReactorTransportType.ob_type = &PyType_Type;
    transport = PyObject_New(cReactorTransport, &cReactorTransportType);
    transport->next                 = NULL;
    transport->state                = CREACTOR_TRANSPORT_STATE_ACTIVE;
    transport->fd                   = fd;
    transport->event_mask           = NULL;
    transport->do_read              = do_read;
    transport->do_write             = do_write;
    transport->do_close             = do_close;
    transport->get_peer             = NULL;
    transport->get_host             = NULL;
    transport->out_buf              = NULL;
    transport->object               = NULL;
    Py_INCREF(reactor);
    transport->reactor              = reactor;
    transport->producer             = NULL;
    transport->producer_streaming   = 0;


    return transport;
}

static void
cReactorTransport_dealloc(PyObject *self)
{
    cReactorTransport *transport;
    transport = (cReactorTransport *)self;

    cReactorBuffer_Destroy(transport->out_buf);
    transport->out_buf = NULL;

    Py_DECREF(transport->reactor);
    transport->reactor = NULL;

    PyObject_Del(self);
}

static PyMethodDef cReactorTransport_methods[] = 
{
    /* ITransport */
    { "write",          cReactorTransport_write,           METH_VARARGS, "write" },
    { "loseConnection", cReactorTransport_loseConnection,  METH_VARARGS, "loseConnection" },
    { "getPeer",        cReactorTransport_getPeer,         METH_VARARGS, "getPeer" },
    { "getHost",        cReactorTransport_getHost,         METH_VARARGS, "getHost" },

    /* IConsumer */
    { "registerProducer",   cReactorTransport_registerProducer,     METH_VARARGS, "registerProducer" },
    { "unregisterProducer", cReactorTransport_unregisterProducer,   METH_VARARGS, "unregisterProducer" },
    /* The "write" method is ITransport.write */

    { NULL, NULL, METH_VARARGS, NULL },
};

static PyObject *
cReactorTransport_getattr(PyObject *self, char *attr)
{
    PyObject *obj;

    cReactorTransport *transport = (cReactorTransport *)self;

    /* Try the method name lookup first. */
    obj = Py_FindMethod(cReactorTransport_methods, self, attr);
    if (obj)
    {
        return obj;
    }
    PyErr_Clear();

    /* The __implements__ attribute. */
    if (strcmp(attr, "__implements__") == 0)
    {
        Py_INCREF(cReactorTransport__implements__);
        return cReactorTransport__implements__;
    }
    else if (strcmp(attr, "disconnecting") == 0)
    {
        /* I wish I didn't have to do this. */
        return PyInt_FromLong(transport->state >= CREACTOR_TRANSPORT_STATE_CLOSING);
    }
    
    /* AttributeError */
    PyErr_SetString(PyExc_AttributeError, attr);
    return NULL;
}

static PyObject *
cReactorTransport_repr(PyObject *self)
{
    UNUSED(self);
    return PyString_FromString("<cReactorTransport>");
}


/* The Transport type. */
static PyTypeObject cReactorTransportType = 
{
    PyObject_HEAD_INIT(NULL)
    0,
    "cReactorTransport", /* tp_name */
    sizeof(cReactorTransport),  /* tp_basicsize */
    0,                  /* tp_itemsize */
    cReactorTransport_dealloc,   /* tp_dealloc */
    NULL,               /* tp_print */
    cReactorTransport_getattr,   /* tp_getattr */
    NULL,               /* tp_setattr */
    NULL,               /* tp_compare */
    cReactorTransport_repr,      /* tp_repr */
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
