#include<Python.h>
#include<sys/types.h>
#include<sys/socket.h>

static PyObject *sendmsg_sendmsg(PyObject *self, PyObject *args);
static PyObject *sendmsg_recvmsg(PyObject *self, PyObject *args);

static PyMethodDef sendmsgMethods[] = {
    {"sendmsg", sendmsg_sendmsg, METH_VARARGS, NULL},
    {"recvmsg", sendmsg_recvmsg, METH_VARARGS, NULL},
    {NULL, NULL, 0, NULL}
};

void initsendmsg(void) {
    PyObject *module;
    module = Py_InitModule("sendmsg", sendmsgMethods);
}

static PyObject *sendmsg_sendmsg(PyObject *self, PyObject *args) {
    struct msghdr *msg;
    int s, dummy, flags, ret;
    if(!PyArg_ParseTuple(args, "is#i", &s, &msg, &dummy, &flags)) {
        return NULL;
    }
    ret = sendmsg(s, msg, flags);
    if(ret == -1) {
        return PyErr_SetFromErrno(PyExc_IOError);
    } else {
        return Py_BuildValue("i", ret);
    }
}

static PyObject *sendmsg_recvmsg(PyObject *self, PyObject *args) {
    struct msghdr *msg;
    int s, dummy, flags, ret;
    if(!PyArg_ParseTuple(args, "is#i", &s, &msg, &dummy, &flags)) {
        return NULL;
    }
    ret = recvmsg(s, msg, flags);
    if(ret == -1) {
        return PyErr_SetFromErrno(PyExc_IOError);
    } else {
        return Py_BuildValue("i", ret);
    }
}

