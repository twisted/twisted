
#include <Python.h>
#include <rpc/rpc.h>
#include <rpc/pmap_clnt.h>
/*#include <sys/socket.h>*/

static PyObject * portmap_set(PyObject *self, PyObject *args)
{
	unsigned long program, version;
	int protocol;
	unsigned short port;
	
	if (!PyArg_ParseTuple(args, "llih:set", 
			      &program, &version, &protocol, &port))
		return NULL;

	pmap_unset(program, version);
	pmap_set(program, version, protocol, port);
	
	Py_INCREF(Py_None);
	return Py_None;
}

static PyObject * portmap_unset(PyObject *self, PyObject *args)
{
	unsigned long program, version;
	
	if (!PyArg_ParseTuple(args, "ll:unset",
			      &program, &version))
		return NULL;

	pmap_unset(program, version);
	
	Py_INCREF(Py_None);
	return Py_None;
}

static PyMethodDef PortmapMethods[] = {
	{"set", portmap_set, METH_VARARGS, 
	 "Set an entry in the portmapper."},
	{"unset", portmap_unset, METH_VARARGS,
	 "Unset an entry in the portmapper."},
	{NULL, NULL, 0, NULL}
};

void initportmap(void)
{
	(void) Py_InitModule("portmap", PortmapMethods);
}

