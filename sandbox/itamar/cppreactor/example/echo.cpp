#include <iostream>
using namespace std;
#include "twisted/tcp.h"
using namespace Twisted;

static char greeting[] = "hello there\n";

class TestDeallocator: public Deallocator
{
public:
    void dealloc(void* buf) { cout << "dealloc"; }
};

class Echo : public Protocol
{
private:
    TestDeallocator dealloc;
    char buf[16384];
public:
    virtual void connectionMade()
    {
	transport->setReadBuffer(buf, 16384);
	cout << "connectionMade" << endl;
    }

    virtual void dataReceived(char* b, int buflen)
    {
	transport->write(&dealloc, greeting, 12);
	transport->setReadBuffer(this->buf, 16384);
	cout << b;
    }

    virtual void connectionLost(object reason)
    {
	cout << "connection lost" << endl;
    }

    virtual void bufferFull() {;}
};


BOOST_PYTHON_MODULE(echo)
{
    class_<Echo,bases<Protocol> >("Echo", init<>());
}
