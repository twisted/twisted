#include <unistd.h>
#include <stdlib.h>
#include <errno.h>
#include <boost/python.hpp> 
using namespace boost::python;
#include "twisted/tcp.h"
#include "twisted/util.h"
using namespace Twisted;


static object None = import("__builtin__").attr("None");

Twisted::TCPTransport::TCPTransport(object self)
{
    this->self = self;
}

void Twisted::TCPTransport::initProtocol()
{
    extract<Twisted::Protocol*> pchecker(self.attr("protocol"));
    if (pchecker.check()) {
	this->protocol = pchecker();
	if (this->protocol == NULL) {
	    // XXX throw exception.
	}
	this->protocol->init(object(self.attr("protocol")).ptr());
	this->sockfd = extract<int>(self.attr("fileno")());
    } else {
	this->protocol = 0;
    }
}

object Twisted::TCPTransport::doRead()
{
    if (protocol) {
	if (buflen == 0) {
	    protocol->bufferFull();
	    return None;
	}
	int result = ::read(sockfd, buffer, buflen);
	if (result == 0) {
	    return import("twisted.internet.main").attr("CONNECTION_DONE");
	} else if (result > 0) {
	    buffer += result;
	    buflen += result;
	    protocol->dataReceived(buffer - result, result);
	} else if (result == EWOULDBLOCK) {
	    return None;
	} else {
	    return import("twisted.internet.main").attr("CONNECTION_LOST");
	}
    } else {
	return import("twisted.internet.tcp").attr("Connection").attr("doRead")(self);
    }
    return None;
}


/* Buffer implementation. Doesn't use boost since boost doesn't yet have
   support for the buffer object API. */
typedef struct {
    PyObject_HEAD
    void* b_ptr;
    int b_size;
    Deallocator* b_dealloc;
} DeallocBuffer;

static Twisted::DeleteDeallocator deleteDealloc;

static int Buffer_init(DeallocBuffer *self, PyObject *args)
{
    char* buf;
    int length;
    if (!PyArg_ParseTuple(args, "s#", &buf, &length)) {
	return -1;
    }
    self->b_ptr = (void*)new char[length];
    self->b_size = length;
    memcpy(self->b_ptr, buf, length);
    self->b_dealloc = &deleteDealloc;
    return 0;
}

static PyObject* Buffer_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    DeallocBuffer *self;
    self = (DeallocBuffer *)type->tp_alloc(type, 0);
    return (PyObject *)self;
}

static int Buffer_getreadbuf(DeallocBuffer *self, int idx, void **pp)
{
    *pp = self->b_ptr;
    return self->b_size;
}

static int Buffer_getsegcount(DeallocBuffer *self, int *lenp)
{
    if (lenp) {
	*lenp = self->b_size;
    }
    return 1;
}

static int Buffer_length(DeallocBuffer* self)
{
    return self->b_size;
}


/* XXX This function is copied almost verbatim from Python, and is the
   under Python's icky license. Possibly replace later on with
   reimplementation or something. */
static PyObject* Buffer_concat(DeallocBuffer *self, PyObject *other)
{
	PyBufferProcs *pb = other->ob_type->tp_as_buffer;
	void *ptr1, *ptr2;
	char *p;
	PyObject *ob;
	int size, count;

	if ( pb == NULL ||
	     pb->bf_getreadbuffer == NULL ||
	     pb->bf_getsegcount == NULL )
	{
		PyErr_BadArgument();
		return NULL;
	}
	if ( (*pb->bf_getsegcount)(other, NULL) != 1 )
	{
		/* ### use a different exception type/message? */
		PyErr_SetString(PyExc_TypeError,
				"single-segment buffer object expected");
		return NULL;
	}

	ptr1 = self->b_ptr;
	size = self->b_size;

	/* optimize special case */
	if ( size == 0 )
	{
	    Py_INCREF(other);
	    return other;
	}

	if ( (count = (*pb->bf_getreadbuffer)(other, 0, &ptr2)) < 0 )
		return NULL;

 	ob = PyString_FromStringAndSize(NULL, size + count);
 	p = PyString_AS_STRING(ob);
 	memcpy(p, ptr1, size);
 	memcpy(p + size, ptr2, count);

	/* there is an extra byte in the string object, so this is safe */
	p[size + count] = '\0';

	return ob;
}


static PyObject* Buffer_str(DeallocBuffer* self)
{
        return PyString_FromStringAndSize(reinterpret_cast<char*>(self->b_ptr),
					  self->b_size);
}

static void Buffer_dealloc(DeallocBuffer* self)
{
    self->b_dealloc->dealloc(reinterpret_cast<char*>(self->b_ptr));
    self->ob_type->tp_free((PyObject*)self);
}


static PySequenceMethods buffer_as_sequence = {
    (inquiry)Buffer_length, /*sq_length*/
    (binaryfunc)Buffer_concat, /*sq_concat*/
};

static PyBufferProcs buffer_as_buffer = {
    (getreadbufferproc)Buffer_getreadbuf,
    0,
    (getsegcountproc)Buffer_getsegcount,
    0,
};

PyTypeObject BufferType = {
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "fusion.tcp.Buffer",       /*tp_name*/
    sizeof(DeallocBuffer),     /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)Buffer_dealloc, /*tp_dealloc*/
    0,                         /*tp_print*/
    0,                         /*tp_getattr*/
    0,                         /*tp_setattr*/
    0,                         /*tp_compare*/
    0,                         /*tp_repr*/
    0,                         /*tp_as_number*/
    &buffer_as_sequence,       /*tp_as_sequence*/
    0,                         /*tp_as_mapping*/
    0,                         /*tp_hash */
    0,                         /*tp_call*/
    (reprfunc)Buffer_str,      /*tp_str*/
    0,                         /*tp_getattro*/
    0,                         /*tp_setattro*/
    &buffer_as_buffer,         /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,        /*tp_flags*/
    "Buffer with custom deallocator.", /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    0,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    0,                         /* tp_methods */
    0,                         /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    (initproc)Buffer_init,     /* tp_init */
    0,                         /* tp_alloc */
    Buffer_new,
};

static PyObject* createDeallocBuffer(Deallocator* d, void* buf, int size) {
    DeallocBuffer* b;
    b = (DeallocBuffer*)BufferType.tp_alloc(&BufferType, 0);
    if (b != NULL) {
	b->b_dealloc = d;
	b->b_ptr = buf;
	b->b_size = size;
    }
    return (PyObject *) b;
}

void Twisted::TCPTransport::write(Deallocator* d, char* buf, int buflen) 
{
    // Commented out until I redo twisted's buffering system.
    /* 
    PyObject* result;
    PyObject* tup;
    PyObject* b = createDeallocBuffer(d, (void*)buf, buflen);
    tup = PyTuple_New(1);
    if (tup == NULL) {
	return;
    }
    if (PyTuple_SetItem(tup, 0, b) < 0) {
	return;
    }
    result = PyObject_CallMethod(self.ptr(), "write", "O", tup);
    Py_XDECREF(result);
    Py_DECREF(tup);
    */
    self.attr("write")(str(buf, buflen));
    d->dealloc(buf);
}



BOOST_PYTHON_MODULE(tcp)
{
    class_<TCPTransport>("TCPTransportMixin", init<object>())
	.def("initProtocol", &TCPTransport::initProtocol)
	.def("doRead", &TCPTransport::doRead)
	;
    class_<Protocol, bases<>, boost::noncopyable>("Protocol", no_init)
	.def("connectionMade", &Protocol::connectionMade)
	.def("connectionLost", &Protocol::connectionLost)
	.def("makeConnection", &Protocol::makeConnection)
	.def_readonly("transport", &Protocol::transportobj)
	;
    if (PyType_Ready(&BufferType) < 0) {
	return;
    }
    Py_INCREF(&BufferType);
    PyModule_AddObject(scope().ptr(), "Buffer", (PyObject *)&BufferType);
    //lvalue_from_pytype<extract_identity<DeallocBuffer>,&BufferType>();
}
