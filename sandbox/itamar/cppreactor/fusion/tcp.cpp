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


BOOST_PYTHON_MODULE(tcp)
{
    class_<TCPTransport>("TCPTransportMixin", init<object>())
	.def("doRead", &TCPTransport::doRead)
	;
    class_<Protocol, bases<>, boost::noncopyable>("Protocol", no_init)
	.def("connectionLost", &Protocol::connectionLost)
	.def("makeConnection", &Protocol::makeConnection)
	;
    BufferClass = class_<Buffer>("Buffer");
}
