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

    // Signature for deallocation strategy function.
    typedef void (*deallocateFunc)(const char*, size_t, void*);

    // delete[] deallocation.
    void deleteDeallocate(const char* buf, size_t buflen, void* extra);

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


	// Public API for transports:

	// dealloc() will be called with buf, buflen and extra when
	// buf can be deallocated. NULL indicates doing nothing.
	void write(const char* buf, size_t buflen,
		   deallocateFunc dealloc=NULL, void* extra=NULL);

	void loseConnection() { self.attr("loseConnection")(); }
	void registerProducer(object producer, bool push) {
	    self.attr("registerProducer")(producer, push);
	}
	void unregisterProducer() { self.attr("unregisterProducer"); }
    };

    class Protocol
    {
    public:
	PyObject* self;
	object transportobj; // so that we have INCREF the transport
	TCPTransport* transport;

	Protocol() : transport(NULL) {};
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
