#include<Python.h>
#include<sys/types.h>
#include<sys/socket.h>
#include<signal.h>

PyObject *g_socketerror; // socket.error

static PyObject *sendmsg_sendmsg(PyObject *self, PyObject *args, PyObject *keywds);
static PyObject *sendmsg_recvmsg(PyObject *self, PyObject *args, PyObject *keywds);

static PyMethodDef sendmsgMethods[] = {
    {"sendmsg", sendmsg_sendmsg, METH_VARARGS|METH_KEYWORDS, NULL},
    {"recvmsg", sendmsg_recvmsg, METH_VARARGS|METH_KEYWORDS, NULL},
    {NULL, NULL, 0, NULL}
};

void initsendmsg(void) {
    PyObject *module;
    module = Py_InitModule("sendmsg", sendmsgMethods);
    if(-1 == PyModule_AddIntConstant(module, "SCM_RIGHTS", SCM_RIGHTS)) {
        return;
    }

    module = PyImport_ImportModule("socket");
    if(!module) {
        return;
    }
    g_socketerror = PyObject_GetAttrString(module, "error");
    if(!g_socketerror) {
        return;
    }
}

static PyObject *sendmsg_sendmsg(PyObject *self, PyObject *args, PyObject *keywds) {
    int fd;
    int flags=0;
    int ret;
    char *cmsg_buf = NULL;
    struct msghdr msg;
    struct iovec iov[1];
    PyObject *ancillary = NULL;
//    char *host;
//    int port;

    static char *kwlist[] = {"fd",
                             "data",
//                             "host", "port",
                             "flags",
                             "ancillary",
                             NULL};

//    kill(0, SIGTRAP);
    if (!PyArg_ParseTupleAndKeywords(args, keywds, "it#|iO", kwlist,
            &fd,
            &iov[0].iov_base,
            &iov[0].iov_len,
//            &host,
//            &port,
            &flags,
            &ancillary)) {
        return NULL;
    }
//    kill(0, SIGTRAP);

    msg.msg_name = NULL;
    msg.msg_namelen = 0;

    msg.msg_iov = iov;
    msg.msg_iovlen = 1;

    msg.msg_control = NULL;
    msg.msg_controllen = 0;

    msg.msg_flags = 0;

    if(ancillary) {
        struct cmsghdr *cur;
        char *data, *cmsg_data;
        int data_len, type, level;

        if(!PyArg_ParseTuple(ancillary, "iit#",
                &level,
                &type,
                &data,
                &data_len)) {
            return NULL;
        }
        cmsg_buf = malloc(CMSG_SPACE(data_len));
        if (!cmsg_buf) {
            PyErr_NoMemory();
            return NULL;
        }
        msg.msg_control = cmsg_buf;
        msg.msg_controllen = CMSG_SPACE(data_len);

        cur = CMSG_FIRSTHDR(&msg);
        cur->cmsg_level = level;
        cur->cmsg_type = type;
        cur->cmsg_len = CMSG_LEN(data_len);
        cmsg_data = CMSG_DATA(cur);
        memcpy(cmsg_data, data, data_len);
        msg.msg_controllen = cur->cmsg_len; // ugh weird C API. CMSG_SPACE includes alignment, unline CMSG_LEN
    }

    ret = sendmsg(fd, &msg, flags);
    free(cmsg_buf); // this is initialized to NULL and then, optionally, to return value of malloc
    if(ret < 0) {
        PyErr_SetFromErrno(g_socketerror);
        return NULL;
    }

    return Py_BuildValue("i", ret);
}

#define CMSG_BUFSIZE (4*1024) // har har arbitrary and hopefully unused
static PyObject *sendmsg_recvmsg(PyObject *self, PyObject *args, PyObject *keywds) {
    int fd;
    int flags=0;
    size_t maxsize=8192;
    size_t cmsg_size=4*1024; // enough to store all file descriptors
    int ret;
    struct msghdr msg;
    struct iovec iov[1];
//    char cmsgbuf[CMSG_SPACE(CMSG_BUFSIZE)];
    char *cmsgbuf;
    PyObject *ancillary;

    static char *kwlist[] = {"fd", "flags", "maxsize", "cmsg_size", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, keywds, "i|iii", kwlist,
            &fd, &flags, &maxsize, &cmsg_size)) {
        return NULL;
    }
    cmsg_size = CMSG_SPACE(cmsg_size);

    msg.msg_name = NULL;
    msg.msg_namelen = 0;

    iov[0].iov_len = maxsize;
    iov[0].iov_base = malloc(maxsize);
    if (!iov[0].iov_base) {
        PyErr_NoMemory();
        return NULL;
    }
    msg.msg_iov = iov;
    msg.msg_iovlen = 1;

    cmsgbuf = malloc(cmsg_size);
    if (!cmsgbuf) {
        PyErr_NoMemory();
        return NULL;
    }
    memset(cmsgbuf, 0, cmsg_size);
    msg.msg_control = cmsgbuf;
    msg.msg_controllen = cmsg_size;

    ret = recvmsg(fd, &msg, flags);
    if (ret < 0) {
        PyErr_SetFromErrno(g_socketerror);
        free(iov[0].iov_base);
        free(cmsgbuf);
        return NULL;
    }

    ancillary = PyList_New(0);
    if (!ancillary) {
        free(iov[0].iov_base);
        free(cmsgbuf);
        return NULL;
    }

    {
        struct cmsghdr *cur;

        for (cur=CMSG_FIRSTHDR(&msg); cur; cur=CMSG_NXTHDR(&msg, cur)) {
            PyObject *entry;

            assert(cur->cmsg_len >= sizeof(struct cmsghdr)); // no null ancillary data messages?

            entry = Py_BuildValue("(iis#)",
                        cur->cmsg_level,
                        cur->cmsg_type,
                        CMSG_DATA(cur),
                        cur->cmsg_len - sizeof(struct cmsghdr));
            if (PyList_Append(ancillary, entry) < 0) {
                Py_DECREF(ancillary);
                Py_DECREF(entry);
                free(iov[0].iov_base);
                free(cmsgbuf);
                return NULL;
            }
        }
    }

    {
        PyObject *r;
        r = Py_BuildValue("s#iO",
                iov[0].iov_base, ret,
                msg.msg_flags,
                ancillary);
        free(iov[0].iov_base);
        free(cmsgbuf);
        return r;
    }
}

// Useful code for sendmsg, multiple ancillary data case
/*
        iterator = PyObject_GetIter(ancillary); // TODO: Py_DECREF me everywhere!
        if (!iterator) {
            return NULL;
        }
        while ((item = PyIter_Next(iterator))) {
            PyObject *rest;

            if (!cur) {
                Py_DECREF(iterator);
                return NULL;
            }

            if (!PyArg_ParseTuple(item, "iiO",
                    &cur->cmsg_level,
                    &cur->cmsg_type,
                    &rest)) {
                return NULL;
            }
            char *data;
            int len;

            if (PyString_AsStringAndSize(rest, &data, &len)) {
                return NULL;
            }

    memcpy(CMSG_DATA(cur), data, len);
    cur->cmsg_len = CMSG_LEN(len);
    real_controllen += CMSG_SPACE(len);
     }

      cur = CMSG_NXTHDR(&msg, cur);
      Py_DECREF(item);
    }
    Py_DECREF(iterator);

    if (PyErr_Occurred())
      return NULL;

    msg.msg_controllen = real_controllen;
*/

