#include <unistd.h>
#include <resolv.h>
#include <sys/socket.h>
#include <boost/python.hpp> 
using namespace boost::python;
#include <boost/python/call_method.hpp> 
using namespace boost::python;
#include "Python.h"
#include "twisted/util.h"

#ifndef TWISTED_UDP_H
#define TWISTED_UDP_H

namespace Twisted
{
    class DatagramProtocol;     // forward definition

    // The resulting Python class should be wrapped in to the transports
    // in twisted.internet.udp.
    class UDPPort
    {
    private:
	DatagramProtocol* protocol;
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
	/* For non-connected UDP */
	int write(const char* buf, size_t buflen, struct sockaddr_in sender);
	/* For connected UDP */
	int write(const char* buf, size_t buflen);
	void wasConnected() { connected = true; }
    };

    class DatagramProtocol
    {
    private:
	object portobj; // so that we have INCREF the port
    public:
	PyObject* self;
	UDPPort* port;

	DatagramProtocol() {};
	virtual ~DatagramProtocol() {}
	void init(PyObject* s) { 
	    this->self = s;
	}
	void makeConnection(object t) {
	    this->portobj = t;
	    this->port = extract<UDPPort*>(t);
	    this->startProtocol();
	}
	virtual void startProtocol() {
	    call_method<void>(self, "startProtocol");
	}
	virtual void stopProtocol() {
	     call_method<void>(self, "stopProtocol");
	}
	virtual void connectionRefused() {
	     call_method<void>(self, "connectionRefused");
	}
	/* For non-connected UDP */
	virtual void datagramReceived(char* buf, size_t buflen, struct sockaddr_in sender) {};
	/* For connected UDP */
	virtual void datagramReceived(char* buf, size_t buflen) {};
    };

}

#endif
