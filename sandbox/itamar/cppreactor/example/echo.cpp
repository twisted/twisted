#include <iostream>
using namespace std;
#include "twisted/tcp.h"
using namespace Twisted;

class Echo : public Protocol
{
private:
    char buf[16384];
public:
    virtual void connectionMade()
    {
	transport->setReadBuffer(buf, 16384);
	cout << "connectionMade\n";
    }

    virtual void dataReceived(char* buf, int buflen)
    {
	transport->setReadBuffer(buf, 16384);
	cout << buf;
    }

    virtual void connectionLost(object reason)
    {
	cout << "connection lost\n";
    }

    virtual void bufferFull() {;}
};


BOOST_PYTHON_MODULE(echo)
{
    class_<Echo,bases<Protocol> >("Echo", init<>());
}
