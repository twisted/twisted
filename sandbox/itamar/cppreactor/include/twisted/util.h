#include "Python.h"
#include <boost/python.hpp> 
#include <boost/function.hpp>

#ifndef TWISTED_UTIL_H
#define TWISTED_UTIL_H

namespace Twisted {
    using namespace boost::python;

    inline object import(const char* module)
    {
	PyObject* m = PyImport_ImportModule(const_cast<char*>(module));
	return extract<object>(m);
    }

    /* Wrap a C++ function so it's callable from Python. */
    class CPPFunction 
    {
    private:
	boost::function<void()> m_function;
    public:
	CPPFunction(boost::function<void()> f) : m_function(f) {}
	void operator() () { m_function(); }
    };

    /* Call a function every <interval> seconds.

    May want to reimplement this in C++ for efficiency at some point.
    */
    class LoopingCall
    {
    private:
	object m_lc;
    public:
	LoopingCall(boost::function<void()> f) {
	    m_lc = import("twisted.internet.task").attr("LoopingCall")(CPPFunction(f));
	}
	void start(double interval) {
	    m_lc.attr("start")(interval);
	}
	void stop() {
	    m_lc.attr("stop")();
	}
    };

    /* Result of scheduled call via callLater().

    Should not be created directly.
    */
    class DelayedCall
    {
    private:
	object m_delayed;
    public:
	DelayedCall() {} // for default objects create in e.g. std::map
	DelayedCall(object d) : m_delayed(d) {}
	void cancel() { m_delayed.attr("cancel")(); }
	bool active() { return extract<bool>(m_delayed.attr("active")()); }
	// XXX add getTime, reset and delay
    };

    DelayedCall callLater(double delaySeconds, boost::function<void()> f);
}

#endif
