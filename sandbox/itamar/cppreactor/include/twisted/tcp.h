#include <unistd.h>
#include <boost/python.hpp> 
using namespace boost::python;
#include <boost/python/call_method.hpp> 
using namespace boost::python;
#include "Python.h"

#ifndef TWISTED_TCP_H
#define TWISTED_TCP_H

// not in Python.h, alas
typedef struct {
        PyObject_HEAD
        PyObject *b_base;
        void *b_ptr;
        int b_size;
        int b_readonly;
        long b_hash;
} PyBufferObject;


namespace Twisted
{

    class Deallocator
    {
    public:
	virtual ~Deallocator() {}
	virtual void dealloc(void* buf) = 0;
    };

    typedef struct {
	PyBufferObject buffer;
	Deallocator* dealloc;
    } DeallocBuffer;
    
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
	void write(Deallocator* d, char* buf, int buflen);
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
