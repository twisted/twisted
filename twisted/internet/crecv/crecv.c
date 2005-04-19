#include "Python.h"
#include <sys/types.h>
#include <sys/socket.h>
static PyObject *socket_error = 0;

static PyObject *
set_error(void)
{
#ifdef MS_WINDOWS
    int err_no = WSAGetLastError();
    if (err_no) {
        const char *msg = "winsock error";
        v = Py_BuildValue("(is)", err_no, msg);
        if (v != NULL) {
            PyErr_SetObject(socket_error, v);
            Py_DECREF(v);
        }
        return NULL;
    }
    else
#endif
	return PyErr_SetFromErrno(socket_error);
}

static PyObject *
crecv_recvinto(PyObject *self, PyObject *args)
{
	PyStringObject *str;
	int fd, len, flags=0, n;
	int alloced_str = 0;
	
    if (!PyArg_ParseTuple(args, "iiS|i:recvinto", 
						  &fd, &len, &str, &flags))
        return NULL;

    if (len < 0) {
        PyErr_SetString(PyExc_ValueError,
						"negative buffersize in recv");
        return NULL;
    }
	if(str->ob_refcnt != 2 || PyString_CHECK_INTERNED(str)) {
		fprintf(stderr, "recvinto: Allocating new string. %d, %d\n", 
				str->ob_refcnt, PyString_CHECK_INTERNED(str));
		str = (PyStringObject*)PyString_FromStringAndSize((char *) 0, len);
		if (str == NULL)
			return NULL;
		alloced_str = 1;
	}
	else
		Py_INCREF(str);
	
    Py_BEGIN_ALLOW_THREADS
    n = recv(fd, PyString_AS_STRING(str), len, flags);
    Py_END_ALLOW_THREADS
    if (n < 0) {
		Py_DECREF(str);
        return set_error();
    }
	
	if (alloced_str) {
		if (n != len)
			_PyString_Resize((PyObject**)&str, n);
	}
	else {
		str->ob_size = n;
		str->ob_sval[n] = '\0';
		str->ob_shash = -1;
	}
	return (PyObject *)str;
}
static PyMethodDef crecv_methods[] = {
    {"recvinto",     crecv_recvinto,     METH_VARARGS,
        PyDoc_STR(
"recvinto(fd, size, string, [flags]) -> str\n\
\n\
Reads data from the given file descriptor into given string object,\n\
*ONLY* if it is safe to do so. If it is not safe, because the string is\n\
interned or has more than two references, then allocate a new string\n\
object and recv into that.\n\
\n\
The string object is assumed to have the size specified, whatever its\n\
length attribute actually claims. *Always* pass the actual allocated\n\
size value in. \n\
")},
	{NULL, NULL}
};

PyDoc_STRVAR(module_doc,
			 "Implements recv into a string object.");

static int get_socket_error(void)
{
    PyObject *mod = 0, *v = 0;

    mod = PyImport_ImportModule("_socket");
    if (mod == NULL)
        goto onError;
	
	socket_error = PyObject_GetAttrString(mod, "error");
    if (socket_error == NULL)
        goto onError;
    Py_DECREF(mod);
	return 0;

 onError:
    Py_XDECREF(mod);
    Py_XDECREF(v);
    return -1;

}

PyMODINIT_FUNC
initcrecv(void)
{
	if(get_socket_error())
		return;
    /* Create the module and add the functions */
    Py_InitModule3("crecv", crecv_methods, module_doc);
	return;
}
