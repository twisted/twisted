#include "Python.h"
#include <boost/python.hpp> 

#ifndef TWISTED_UTIL_H
#define TWISTED_UTIL_H

namespace Twisted {
    using namespace boost::python;

    // Deallocation strategy for buffers.
    class Deallocator
    {
    public:
	virtual ~Deallocator() {}
	virtual void dealloc(char* buf) = 0;
    };
    
    // delete[] the buffer.
    class DeleteDeallocator : public Deallocator
    {
	virtual void dealloc(char* buf) { delete[] buf; }
    };

    // Do nothing.
    class NullDeallocator : public Deallocator
    {
	virtual void dealloc(char* buf) {}
    };

    inline object import(char* module)
    {
	PyObject* m = PyImport_ImportModule(module);
	return extract<object>(m);
    }
}

#endif
