# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Support code for implementing state-based method dispatch.
"""

def makeStatefulDispatcher(template, name=None):
    """
    Given a I{dispatch} name and a function, return a function which can be
    used as a method and which, when called, will call another method defined
    on the instance and return the result.  The other method which is called
    is determined by the value of the C{_state} attribute of the instance.

    @param template: A function object which is used to give the returned
        function a docstring.

    @param name: A string which is used to construct the name of the
        subsidiary method to invoke. If C{None} is given, the template
        function's name is used. The subsidiary method is named like
        C{'_%s_%s' % (name, _state)}.

    @return: The dispatcher function.
    """
    if name is None:
        name = template.__name__
    def dispatcher(self, *args, **kwargs):
        func = (getattr(self, '_' + name + '_' + self._state, None) or
                getattr(self, '_' + name + '_default', None))
        if func is None:
            raise RuntimeError(
                "%r has no %s method in state %s" % (self, name, self._state))
        return func(*args, **kwargs)
    dispatcher.__doc__ = template.__doc__
    dispatcher.__name__ = name
    return dispatcher
