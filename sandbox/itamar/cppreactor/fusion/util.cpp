/* Utility classes and functions for both C++ and Python. */

#include <boost/python.hpp> 
using namespace boost::python;
#include "twisted/util.h"
using namespace Twisted;

namespace {
    /* Wrap a C++ function so it's callable from Python. */
    struct CPPFunction {
	boost::function<void()> m_function;
	CPPFunction(boost::function<void()> f) : m_function(f) {}
	void operator() () { m_function(); }
    };
}

DelayedCall Twisted::callLater(double delaySeconds, boost::function<void()> f) {
    // XXX faster reactor import
    return DelayedCall(import("twisted.internet.reactor").attr("callLater")(delaySeconds, CPPFunction(f)));
}

BOOST_PYTHON_MODULE(util)
{
    class_<CPPFunction>("CPPFunction", no_init)
	.def("__call__", &CPPFunction::operator());
}
