#include <unistd.h>
#include <errno.h>
#include <boost/python.hpp> 
using namespace boost::python;
#include "twisted/tcp.h"
using namespace Twisted;

static object import(char* module)
{
    return object(extract<object>(PyImport_AddModule(module)));
}

static object None = import("twisted.internet.main").attr("None");


Twisted::TCPTransport::TCPTransport(object self)
{
    this->self = self.ptr();
    extract<Twisted::Protocol*> pchecker(self.attr("protocol"));
    if (pchecker.check()) {
	this->protocol = pchecker;
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
	return import("twisted.internet.tcp").attr("Connection").attr("doRead")(extract<object>(self));
    }
    return None;
}


BOOST_PYTHON_MODULE(tcp)
{
    class_<TCPTransport>("TCPTransportMixin", init<object>())
	.def("doRead", &TCPTransport::doRead)
	;

    BufferClass = class_<Buffer>("Buffer");
}
