#include "errno.h"
#include "twisted/udp.h"
using namespace Twisted;


static object None = import("__builtin__").attr("None");

Twisted::UDPPort::UDPPort(object self)
{
    this->connected = false;
    this->self = self.ptr();
    extract<Twisted::DatagramProtocol*> pchecker(self.attr("protocol"));
    if (pchecker.check()) {
	this->protocol = pchecker();
	this->protocol->init(object(self.attr("protocol")).ptr());
	this->sockfd = extract<int>(self.attr("fileno")());
	this->buflen = extract<int>(self.attr("maxPacketSize"));
	this->buffer = new char[this->buflen];
    } else {
	this->protocol = 0;
    }
}

object Twisted::UDPPort::doRead()
{
    if (protocol) {
	if (connected) {
	    for (int i = 0; i < 50; ++i) {
		ssize_t recvlen = ::read(sockfd, buffer, buflen);
		if (recvlen < 0) {
		    if (recvlen == EWOULDBLOCK || recvlen == EAGAIN || recvlen == EINTR) {
			return None;
		    }
		    if (recvlen == ECONNREFUSED) {
			protocol->connectionRefused();
		    }
		    /* XXX log error? */
		    return None;
		}
		protocol->datagramReceived(buffer, recvlen);
	    }
	} else {
	    for (int i = 0; i < 50; ++i) {
		sockaddr_in recvaddr;
		socklen_t addrlen; 
		ssize_t recvlen = ::recvfrom(sockfd, buffer, buflen, 0, (sockaddr*)&recvaddr, &addrlen);
		if (recvlen < 0) {
		    if (recvlen == EWOULDBLOCK || recvlen == EAGAIN || recvlen == EINTR) {
			return None;
		    }
		    /* XXX log error? */
		    return None;
		}
		protocol->datagramReceived(buffer, recvlen, recvaddr);
	    }
	}
    } else {
	return import("twisted.internet.udp").attr("Port").attr("doRead")(object(extract<object>(self)));
    }
    return None;
}


int Twisted::UDPPort::write(const char* buf, size_t buflen)
{
    int result = ::write(sockfd, buf, buflen);
    if (result < 0) {
	if (result == EINTR) {
	    this->write(buf, buflen);
	} else if (result == ECONNREFUSED) {
	    this->protocol->connectionRefused();
	} else {
	    return result;
	}
    }
    return 0;
}

int Twisted::UDPPort::write(const char* buf, size_t buflen, sockaddr_in sender)
{
    int result = ::sendto(sockfd, buf, buflen, 0, (sockaddr*) &sender, sizeof(sender));
    if (result < 0) {
	if (result == EINTR) {
	    this->write(buf, buflen, sender);
	} else {
	    return result;
	}
    }
    return 0;
}

BOOST_PYTHON_MODULE(udp)
{
    class_<UDPPort>("UDPPortMixin", init<object>())
	.def("doRead", &UDPPort::doRead)
	;
    class_<DatagramProtocol, bases<>, boost::noncopyable>("DatagramProtocol", no_init)
	.def("makeConnection", &DatagramProtocol::makeConnection)
	;
}
