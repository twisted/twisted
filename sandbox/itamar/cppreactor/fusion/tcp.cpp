#include <iostream>
using namespace std;
#include <unistd.h>
#include <errno.h>
#include <boost/python.hpp> 
#include <boost/python/lvalue_from_pytype.hpp>
using namespace boost::python;
#include "twisted/tcp.h"
using namespace Twisted;

static object import(char* module)
{
    PyObject* m = PyImport_ImportModule(module);
    return extract<object>(m);
}

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

static void Buffer_dealloc(DeallocBuffer* self)
{
    self->dealloc->dealloc(self->buffer.b_ptr);
    PyObject_DEL(self);
}

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
    0,                         /*tp_as_sequence*/
    0,                         /*tp_as_mapping*/
    0,                         /*tp_hash */
    0,                         /*tp_call*/
    0,                         /*tp_str*/
    0,                         /*tp_getattro*/
    0,                         /*tp_setattro*/
    0,                         /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,        /*tp_flags*/
    "Buffer with custom deallocator.", /* tp_doc */
};

static PyObject* createDeallocBuffer(Deallocator* d, void* buf, int size) {
    DeallocBuffer* b;
    b = PyObject_NEW(DeallocBuffer, &BufferType);
    if (b == NULL) {
	return NULL;
    }
    b->dealloc = d;
    b->buffer.b_base = NULL;
    b->buffer.b_ptr = buf;
    b->buffer.b_size = size;
    b->buffer.b_readonly = 1;
    b->buffer.b_hash = -1;
    return (PyObject *) b;
}

void Twisted::TCPTransport::write(Deallocator* d, char* buf, int buflen) 
{
    PyObject_CallMethod(self, "write", "O", createDeallocBuffer(d, (void*)buf, buflen));
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
    BufferType.tp_base = &PyBuffer_Type;
    if (PyType_Ready(&BufferType) < 0) {
	return;
    }
    PyModule_AddObject(scope().ptr(), "Buffer", (PyObject *)&BufferType);
    //lvalue_from_pytype<extract_identity<DeallocBuffer>,&BufferType>();
}
