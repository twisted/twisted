#include "Python.h"
#include <boost/python.hpp> 
using namespace boost::python;

#ifndef TWISTED_UTIL_H
#define TWISTED_UTIL_H

namespace Twisted {

    /* Deallocate a buffer. */
    class Deallocator
    {
    public:
	virtual ~Deallocator() {}
	virtual void dealloc(void* buf) = 0;
    };
    
    inline object import(char* module)
    {
	PyObject* m = PyImport_ImportModule(module);
	return extract<object>(m);
    }
}

#endif
