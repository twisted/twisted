#include <unistd.h>
#include <resolv.h>
#include <sys/socket.h>
#include <boost/python.hpp> 
#include <boost/python/call_method.hpp> 
#include "Python.h"
#include "twisted/util.h"

#ifndef TWISTED_UDP_H
#define TWISTED_UDP_H

namespace Twisted
{
    using namespace boost::python;

    class DatagramProtocol;     // forward definition

    // The resulting Python class should be wrapped in to the transports
    // in twisted.internet.udp.
    class UDPPort
    {
    private:
	DatagramProtocol* protocol;
	PyObject* pyprotocol;
	PyObject* self;
	int sockfd;
	char* buffer;
	size_t buflen;
	bool connected;
    public:
	UDPPort(object self);
	~UDPPort() {
	    delete[] buffer;
	}
	object doRead();
	void wasConnected() { connected = true; }

	/* Public API for use of DatagramProtocol subclasses: */
	object stopListening() {
	    this->sockfd = -1; // so writes don't blow up later on.
	    return call_method<object>(pyprotocol, "stopListening");
	}
	/* For non-connected UDP. Returns negative number on errors: */
	int write(const char* buf, size_t buflen, struct sockaddr_in sender);
	/* For connected UDP. Returns negative number on errors: */
	int write(const char* buf, size_t buflen);
    };

    class DatagramProtocol
    {
    private:
	object portobj; // so that we have INCREF the port
    public:
	PyObject* self;
	UDPPort* transport;

	DatagramProtocol() {};
	virtual ~DatagramProtocol() {}
	void init(PyObject* s) { 
	    this->self = s;
	}
	void makeConnection(object t) {
	    this->portobj = t;
	    this->transport = extract<UDPPort*>(t);
	    call_method<void>(self, "startProtocol");
	}
	virtual void startProtocol() {}
	virtual void stopProtocol() {}
	virtual void connectionRefused() {}
	/* For non-connected UDP */
	virtual void datagramReceived(const char* buf, size_t buflen, struct sockaddr_in sender) {};
	/* For connected UDP */
	virtual void datagramReceived(const char* buf, size_t buflen) {};
    };

}

#endif
