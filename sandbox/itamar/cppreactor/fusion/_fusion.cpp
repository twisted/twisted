/* Export C++ code to Python. */

#include <boost/python.hpp> 
using namespace boost::python;
#include "twisted/util.h"
#include "twisted/tcp.h"
#include "twisted/udp.h"
using namespace Twisted;


namespace {
    struct PyObjectOwner : public Twisted::BufferOwner
    {
	boost::python::object obj;
	PyObjectOwner(boost::python::object o) : obj(o) {}
    };

    /* transport.write() for Python */
    void pyWrite(Twisted::TCPTransport* transport, boost::python::str s) {
	char* buf;
	int size;
	PyString_AsStringAndSize(s.ptr(), &buf, &size);
	boost::shared_ptr<PyObjectOwner> p;
	p.reset(new PyObjectOwner(s));
	transport->write(buf, size, p);
    }

    /* transport.writeSequence for Python */
    void pyWriteSequence(Twisted::TCPTransport* transport, boost::python::object seq)
    {
	boost::shared_ptr<PyObjectOwner> p;
	p.reset(new PyObjectOwner(seq));
	int len = boost::python::extract<int>(seq.attr("__len__")());
	for (int i = 0; i < len; i++) {
	    char* buf;
	    int size;
	    boost::python::str s(seq[i]);
	    PyString_AsStringAndSize(s.ptr(), &buf, &size);
	    transport->write(buf, size, p);
	}
    }
}


BOOST_PYTHON_MODULE(_fusion)
{
    class_<CPPFunction>("CPPFunction", no_init)
	.def("__call__", &CPPFunction::operator());

    class_<UDPPort>("UDPPortMixin", init<object>())
	.def("doRead", &UDPPort::doRead)
	;

    class_<DatagramProtocol, bases<>, boost::noncopyable>("DatagramProtocol", no_init)
	.def("makeConnection", &DatagramProtocol::makeConnection)
	.def("stopProtocol", &DatagramProtocol::stopProtocol)
	.def("startProtocol", &DatagramProtocol::startProtocol)
	.def("doStop", &DatagramProtocol::doStop)
	.def("connectionRefused", &DatagramProtocol::connectionRefused)
	.def_readonly("transport", &DatagramProtocol::m_portobj)
	;

    class_<TCPTransport>("TCPTransportMixin", init<object>())
	.def("initProtocol", &TCPTransport::initProtocol)
	.def("doRead", &TCPTransport::doRead)
	.def("doWrite", &TCPTransport::doWrite)
	.def("startWriting", &TCPTransport::startWriting)
	.def("stopWriting", &TCPTransport::stopWriting)
	.def_readwrite("connected", &TCPTransport::connected)
	.def_readwrite("disconnecting", &TCPTransport::disconnecting)
	.def_readwrite("producerPaused", &TCPTransport::producerPaused)
	.def_readwrite("streamingProducer", &TCPTransport::streamingProducer)
	.add_property("producer", &TCPTransport::_getProducer, &TCPTransport::_setProducer)
	.def("write", &pyWrite)
	.def("writeSequence", &pyWriteSequence)
	;

    class_<Protocol, bases<>, boost::noncopyable>("Protocol", no_init)
	.def("connectionMade", &Protocol::connectionMade)
	.def("connectionLost", &Protocol::connectionLost)
	.def("makeConnection", &Protocol::makeConnection)
	.def_readonly("transport", &Protocol::transportobj)
	;    
}
