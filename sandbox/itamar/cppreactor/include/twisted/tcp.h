#include <unistd.h>
#include <boost/python.hpp> 
using namespace boost::python;
#include <boost/python/call_method.hpp> 
using namespace boost::python;
#include "Python.h"

#ifndef TWISTED_TCP_H
#define TWISTED_TCP_H


object BufferClass; // the Python class wrapping Twisted::Buffer


namespace Twisted
{

    class Deallocator
    {
    public:
	virtual ~Deallocator() {}
	virtual void operator() (char* buf) = 0;
    };

    class Buffer
    {
    private:
	Deallocator* dealloc;
	char* buf;
	size_t buflen;
    public:
	Buffer() {}
	void initialize(Deallocator *d, char* b, size_t l) {
	    dealloc = d; buf = b; buflen = l;
	}
	~Buffer() { (*dealloc)(buf); }
	// XXXX
    };

    class Protocol;     // forward definition

    // The resulting Python class should be wrapped in to the transports
    // in twisted.internet.tcp.
    class TCPTransport
    {
    private:
	Protocol* protocol;
	PyObject* self;
	int sockfd;
	char* buffer;
	size_t buflen;
    public:
	TCPTransport(object self);
	~TCPTransport() {}
	void setReadBuffer(char* buffer, size_t buflen) {
	    this->buffer = buffer;
	    this->buflen = buflen;
	}
	object doRead();
	void write(Deallocator* d, char* buf, size_t buflen) {
	    object b = BufferClass();
	    ((Buffer)(extract<Buffer>(b))).initialize(d, buf, buflen);
	    call_method<void, object>(self, "write", b);
	}
	void loseConnection() { call_method<void>(self, "loseConnection"); }
    };

    class Protocol
    {
    private:
	object transportobj; // so that we have INCREF the transport
    public:
	PyObject* self;
	TCPTransport* transport;

	Protocol() {};
	virtual ~Protocol() {}
	void init(PyObject* s) { 
	    this->self = s;
	}
	void makeConnection(object t) {
	    this->transportobj = t;
	    this->transport = extract<TCPTransport*>(t);
	    this->connectionMade();
	}
	virtual void connectionMade() {
	    call_method<void>(self, "connectionMade");
	}
	virtual void connectionLost(object reason) {
	     call_method<void,object>(self, "connectionLost", reason);
	}
	virtual void dataReceived(char* buf, int buflen) = 0;
	virtual void bufferFull() = 0;
    };
}

#endif
