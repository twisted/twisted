#include <unistd.h>
#include <boost/python.hpp> 
#include <boost/python/call_method.hpp>
#include "Python.h"
#include "twisted/util.h"

#ifndef TWISTED_TCP_H
#define TWISTED_TCP_H


namespace Twisted
{
    using namespace boost::python;

    class Protocol;     // forward definition

    // The resulting Python class should be wrapped in to the transports
    // in twisted.internet.tcp.
    class TCPTransport
    {
    private:
	Protocol* protocol;
	object self;
	int sockfd;
	char* buffer;
	size_t buflen;
    public:
	TCPTransport(object self);
	void initProtocol(); // call when "self.protocol" exists.
	~TCPTransport() {}
	void setReadBuffer(char* buffer, size_t buflen) {
	    this->buffer = buffer;
	    this->buflen = buflen;
	}
	object doRead();
	void write(Deallocator* d, char* buf, int buflen);
	void loseConnection() { self.attr("loseConnection")(); }
    };

    class Protocol
    {
    public:
	PyObject* self;
	object transportobj; // so that we have INCREF the transport
	TCPTransport* transport;

	Protocol() {};
	virtual ~Protocol() {}
	void init(PyObject* s) { 
	    this->self = s;
	}
	void makeConnection(object t) {
	    this->transportobj = t;
	    this->transport = extract<TCPTransport*>(t);
	    call_method<void>(self, "connectionMade");
	}
	virtual void connectionMade() {}
	virtual void connectionLost(object reason) {}
	virtual void dataReceived(char* buf, int buflen) = 0;
	virtual void bufferFull() = 0;
    };
}

#endif
