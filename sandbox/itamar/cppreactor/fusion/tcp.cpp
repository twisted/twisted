#include <unistd.h>
#include <errno.h>
#include <boost/python.hpp> 
using namespace boost::python;
#include "twisted/tcp.h"
#include "twisted/util.h"
using namespace Twisted;


static object None = import("__builtin__").attr("None");

Twisted::TCPTransport::TCPTransport(object self)
{
    this->self = self.ptr();
    extract<Twisted::Protocol*> pchecker(self.attr("protocol"));
    if (pchecker.check()) {
	this->protocol = pchecker();
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
	return import("twisted.internet.tcp").attr("Connection").attr("doRead")(object(extract<object>(self)));
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


static PyObject* Buffer_str(DeallocBuffer* self)
{
        return PyString_FromStringAndSize(reinterpret_cast<char*>(self->b_ptr),
					  self->b_size);
}

static void Buffer_dealloc(DeallocBuffer* self)
{
    self->b_dealloc->dealloc(self->b_ptr);
    self->ob_type->tp_free((PyObject*)self);
}


static PySequenceMethods buffer_as_sequence = {
    (inquiry)Buffer_length, /*sq_length*/
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
    result = PyObject_CallMethod(self, "write", "O", tup);
    Py_XDECREF(result);
    Py_DECREF(tup);
}



BOOST_PYTHON_MODULE(tcp)
{
    class_<TCPTransport>("TCPTransportMixin", init<object>())
	.def("doRead", &TCPTransport::doRead)
	;
    class_<Protocol, bases<>, boost::noncopyable>("Protocol", no_init)
	.def("connectionLost", &Protocol::connectionLost)
	.def("makeConnection", &Protocol::makeConnection)
	;
    if (PyType_Ready(&BufferType) < 0) {
	return;
    }
    Py_INCREF(&BufferType);
    PyModule_AddObject(scope().ptr(), "Buffer", (PyObject *)&BufferType);
    //lvalue_from_pytype<extract_identity<DeallocBuffer>,&BufferType>();
}
