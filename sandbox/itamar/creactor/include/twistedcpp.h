/* C++ integration for rexactor based protocols. */

#include "twisted.h"

#ifndef TWISTEDCPP_H
#define TWISTEDCPP_H

namespace Twisted
{
    class Transport
    {
    private:
	TwistedTransport* _transport;
    public:
	Transport(TwistedTransport* t) : _transport(t) {}
	void setReadBuffer(char* buf, unsigned int buflen) { 
	    tt_setReadBuffer(this->_transport, buf, buflen);
	}
	void write(void (*dealloc)(void (*)), char* buf, unsigned int buflen) { 
	    tt_write(this->_transport, dealloc, buf, buflen);
	}
	void loseConnection() { tt_loseConnection(this->_transport); }
    };


    class Protocol
    {
    public:
	Transport transport;
	Protocol(TwistedTransport* t) : transport(t) {}
	virtual ~Protocol() {}
	virtual void dataReceived(char* buf, int buflen) = 0;
	virtual void connectionLost() = 0;
	virtual void bufferFull() = 0;
    };
}

#endif
