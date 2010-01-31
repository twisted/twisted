/*
 * Copyright (c) 2001-2004 Twisted Matrix Laboratories.
 * See LICENSE for details.

 *
 */
/* _c_urlarg.c */

#ifdef __cplusplus
extern "C" {
#endif
#include <Python.h>
#ifdef __cplusplus
}
#endif

#ifdef __GNUC__
#       define TM_INLINE inline
#else
#       define TM_INLINE /* */
#endif

static PyObject* UrlargError;

#define OUTPUTCHAR(c,n) do{memcpy(output, c, n);output+=n;}while(0)

#define STATE_INITIAL 0
#define STATE_PERCENT 1
#define STATE_HEXDIGIT 2

#define NOT_HEXDIGIT 255
unsigned char hexdigits[256];

TM_INLINE int ishexdigit(unsigned char c) {
    return hexdigits[c];
}

static PyObject *unquote(PyObject *self, PyObject *args, PyObject *kwargs)
{
    unsigned char *s, *r, *end, *output_start, *output;
    unsigned char quotedchar, quotedchartmp = 0, tmp;
    unsigned char escchar = '%'; /* the character we use to begin %AB sequences */
    static char *kwlist[] = {"s", "escchar", NULL};
    int state = STATE_INITIAL, length;
    PyObject *str;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "s#|c:unquote", kwlist, &s, &length, &escchar)) {
        return NULL;
    }
    if (length == 0) {
        return PyString_FromStringAndSize("", 0);
    }
    /* Allocating an output buffer of length will be sufficient,
       as the output can only be smaller. We resize the output in the end. */
    str = PyString_FromStringAndSize(NULL, length);
    if (str == NULL) {
        return NULL;
    }
    output = output_start = (unsigned char*)PyString_AsString(str);
    end = s + length;
    s = s - 1;
    while ((++s) < end) {
        switch(state) {
        case STATE_INITIAL:
            if (*s == escchar) {
                state = STATE_PERCENT;
            } else {
                r = s - 1;
                while (*(++r) != escchar && r < end);
                OUTPUTCHAR(s, r-s);
                s = r-1;
            }
            break;
        case STATE_PERCENT:
            if ((quotedchartmp = ishexdigit(*s)) != NOT_HEXDIGIT) {
                tmp = *s;
                state = STATE_HEXDIGIT;
            } else {
                state = STATE_INITIAL;
                OUTPUTCHAR(&escchar, 1);
                s--;
            }
            break;
        case STATE_HEXDIGIT:
            state = STATE_INITIAL;
            if ((quotedchar = ishexdigit(*s)) != NOT_HEXDIGIT) {
                quotedchar |= (quotedchartmp << 4);
                OUTPUTCHAR(&quotedchar, 1);
            } else {
                OUTPUTCHAR(&escchar, 1);
                s -= 2;
            }
            break;
        }
    }
    switch(state) {
    case STATE_PERCENT:
        OUTPUTCHAR(&escchar, 1);
        break;
    case STATE_HEXDIGIT:
        OUTPUTCHAR(&escchar, 1);
        OUTPUTCHAR(&tmp, 1);
        break;
    }

    _PyString_Resize(&str, output-output_start);
    return str;
}

static PyMethodDef _c_urlarg_methods[] = {
    {"unquote",  (PyCFunction)unquote, METH_VARARGS|METH_KEYWORDS},
    {NULL, NULL} /* sentinel */
};

DL_EXPORT(void) init_c_urlarg(void)
{
    PyObject* m;
    PyObject* d;
    unsigned char i;

    m = Py_InitModule("_c_urlarg", _c_urlarg_methods);
    d = PyModule_GetDict(m);

    /* add our base exception class */
    UrlargError = PyErr_NewException("urlarg.UrlargError", PyExc_Exception, NULL);
    PyDict_SetItemString(d, "UrlargError", UrlargError);

    /* initialize hexdigits */
    for(i = 0; i < 255; i++) {
        hexdigits[i] = NOT_HEXDIGIT;
    }
    hexdigits[255] = NOT_HEXDIGIT;
    for(i = '0'; i <= '9'; i++) {
        hexdigits[i] = i - '0';
    }
    for(i = 'a'; i <= 'f'; i++) {
        hexdigits[i] = 10 + (i - 'a');
    }
    for(i = 'A'; i <= 'F'; i++) {
        hexdigits[i] = 10 + (i - 'A');
    }
    /* Check for errors */
    if (PyErr_Occurred()) {
        PyErr_Print();
        Py_FatalError("can't initialize module _c_urlarg");
    }
}

