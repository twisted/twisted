#include <Python.h>

inline PyTypeObject *Pyrex_GETTYPE(PyObject *op)
{
	PyTypeObject *x = op->ob_type;
	Py_INCREF(x);
	return x;
}
