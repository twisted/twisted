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

void Twisted::TCPTransport::write(const char* buf,
				  size_t buflen,
				  deallocateFunc dealloc,
				  void* extra)
{
    // XXX totally inefficient, redo twisted's buffering system.
    self.attr("write")(str(buf, buflen));
    if (dealloc != NULL) {
	dealloc(buf, buflen, extra);
    }
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
}
