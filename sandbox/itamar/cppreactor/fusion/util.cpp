/* Utility classes and functions for both C++ and Python. */

#include <boost/python.hpp> 
using namespace boost::python;
#include "twisted/util.h"
using namespace Twisted;


DelayedCall Twisted::callLater(double delaySeconds, boost::function<void()> f) {
    // XXX faster reactor import
    return DelayedCall(import("twisted.internet.reactor").attr("callLater")(delaySeconds, CPPFunction(f)));
}
