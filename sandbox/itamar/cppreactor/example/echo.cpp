#include <iostream>
#include <boost/bind.hpp>
#include "twisted/tcp.h"
using namespace Twisted;



void printNum(int i) {
    std::cout << i << " seconds passed." << std::endl;
}

struct Writer
{
    char* buf;
    size_t len;
    Writer(char* b, size_t l) : buf(b), len(l) {}
    size_t operator() (char* out) {
	memcpy(out, buf, len);
	return len;
    }
};

class Echo : public Protocol
{
private:
    char buf[131072];
public:
    virtual void connectionMade()
    {
	transport->setReadBuffer(buf, 131072);
	callLater(1, boost::bind(printNum, 1));
	callLater(2, boost::bind(printNum, 2));
	std::cout << "connectionMade" << std::endl;
    }

    virtual void dataReceived(char* b, int buflen)
    {
	transport->write(buflen, Writer(b, buflen));
	transport->setReadBuffer(this->buf, 131072);
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
