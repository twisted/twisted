#include <iostream>
#include <boost/bind.hpp>
#include "twisted/tcp.h"
using namespace Twisted;

static char greeting[] = "hello there\n";

// sample custom deallocator
static void dealloc(const char* buf, size_t buflen, void* extra) {
    std::cout << "dealloc" << std::endl; 
}


void printNum(int i) {
    std::cout << i << " seconds passed." << std::endl;
}

class Echo : public Protocol
{
private:
    char buf[16384];
public:
    virtual void connectionMade()
    {
	transport->setReadBuffer(buf, 16384);
	callLater(1, boost::bind(printNum, 1));
	callLater(2, boost::bind(printNum, 2));
	std::cout << "connectionMade" << std::endl;
    }

    virtual void dataReceived(char* b, int buflen)
    {
	transport->write(greeting, 12, dealloc);
	transport->setReadBuffer(this->buf, 16384);
	std::cout << "RECEIVED: " << b;
    }

    virtual void connectionLost(object reason)
    {
	std::cout << "connection lost" << std::endl;
    }

    virtual void bufferFull() {;}
};


BOOST_PYTHON_MODULE(echo)
{
    class_<Echo,bases<Protocol> >("Echo", init<>());
}
