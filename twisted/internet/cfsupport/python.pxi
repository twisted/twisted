cdef extern from "Python.h":
    ctypedef void *PyGILState_STATE
    void PyErr_Clear()
    PyGILState_STATE PyGILState_Ensure()
    void PyGILState_Release(PyGILState_STATE)
