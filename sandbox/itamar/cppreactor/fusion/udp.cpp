#include "errno.h"
#include "twisted/udp.h"
using namespace Twisted;


Twisted::UDPPort::UDPPort(object self)
{
    this->connected = false;
    this->self = self.ptr();
    extract<Twisted::DatagramProtocol*> pchecker(self.attr("protocol"));
    if (pchecker.check()) {
	this->protocol = pchecker();
	this->pyprotocol = object(self.attr("protocol")).ptr();
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
			return object();
		    }
		    if (recvlen == ECONNREFUSED) {
			call_method<void>(pyprotocol, "connectionRefused");
		    }
		    /* XXX log error? */
		    return object();
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
			return object();
		    }
		    /* XXX log error? */
		    return object();
		}
		protocol->datagramReceived(buffer, recvlen, recvaddr);
	    }
	}
    } else {
	return import("twisted.internet.udp").attr("Port").attr("doRead")(object(extract<object>(self)));
    }
    return object();
}


int Twisted::UDPPort::write(const char* buf, size_t buflen)
{
    if (sockfd == -1) {
	return -1;
    }
    int result = ::write(sockfd, buf, buflen);
    if (result < 0) {
	if (result == EINTR) {
	    this->write(buf, buflen);
	} else if (result == ECONNREFUSED) {
	    call_method<void>(this->pyprotocol, "connectionRefused"); 
	} else {
	    return result;
	}
    }
    return 0;
}

int Twisted::UDPPort::write(const char* buf, size_t buflen, sockaddr_in sender)
{
    if (sockfd == -1) {
	return -1;
    }
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
