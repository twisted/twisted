#include "Python.h"
#include <boost/python.hpp> 
#include <boost/function.hpp>

#ifndef TWISTED_UTIL_H
#define TWISTED_UTIL_H

namespace Twisted {
    using namespace boost::python;

    inline object import(char* module)
    {
	PyObject* m = PyImport_ImportModule(module);
	return extract<object>(m);
    }

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
