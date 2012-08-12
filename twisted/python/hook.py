
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.



"""
I define support for hookable instance methods.

These are methods which you can register pre-call and post-call external
functions to augment their functionality.  People familiar with more esoteric
languages may think of these as \"method combinations\".

This could be used to add optional preconditions, user-extensible callbacks
(a-la emacs) or a thread-safety mechanism.

The four exported calls are:

   - L{addPre}
   - L{addPost}
   - L{removePre}
   - L{removePost}

All have the signature (class, methodName, callable), and the callable they
take must always have the signature (instance, *args, **kw) unless the
particular signature of the method they hook is known.

Hooks should typically not throw exceptions, however, no effort will be made by
this module to prevent them from doing so.  Pre-hooks will always be called,
but post-hooks will only be called if the pre-hooks do not raise any exceptions
(they will still be called if the main method raises an exception).  The return
values and exception status of the main method will be propogated (assuming
none of the hooks raise an exception).  Hooks will be executed in the order in
which they are added.
"""


### Public Interface

class HookError(Exception):
    "An error which will fire when an invariant is violated."

def addPre(klass, name, func):
    """hook.addPre(klass, name, func) -> None

    Add a function to be called before the method klass.name is invoked.
    """

    _addHook(klass, name, PRE, func)

def addPost(klass, name, func):
    """hook.addPost(klass, name, func) -> None

    Add a function to be called after the method klass.name is invoked.
    """
    _addHook(klass, name, POST, func)

def removePre(klass, name, func):
    """hook.removePre(klass, name, func) -> None

    Remove a function (previously registered with addPre) so that it
    is no longer executed before klass.name.
    """

    _removeHook(klass, name, PRE, func)

def removePost(klass, name, func):
    """hook.removePre(klass, name, func) -> None

    Remove a function (previously registered with addPost) so that it
    is no longer executed after klass.name.
    """
    _removeHook(klass, name, POST, func)

### "Helper" functions.

hooked_func = """

import %(module)s

def %(name)s(*args, **kw):
    klazz = %(module)s.%(klass)s
    for preMethod in klazz.%(preName)s:
        preMethod(*args, **kw)
    try:
        return klazz.%(originalName)s(*args, **kw)
    finally:
        for postMethod in klazz.%(postName)s:
            postMethod(*args, **kw)
"""

_PRE = '__hook_pre_%s_%s_%s__'
_POST = '__hook_post_%s_%s_%s__'
_ORIG = '__hook_orig_%s_%s_%s__'


def _XXX(k,n,s):
    """
    String manipulation garbage.
    """
    x = s % (k.__module__.replace('.', '_'), k.__name__, n)
    return x

def PRE(k,n):
    "(private) munging to turn a method name into a pre-hook-method-name"
    return _XXX(k,n,_PRE)

def POST(k,n):
    "(private) munging to turn a method name into a post-hook-method-name"
    return _XXX(k,n,_POST)

def ORIG(k,n):
    "(private) munging to turn a method name into an `original' identifier"
    return _XXX(k,n,_ORIG)


def _addHook(klass, name, phase, func):
    "(private) adds a hook to a method on a class"
    _enhook(klass, name)

    if not hasattr(klass, phase(klass, name)):
        setattr(klass, phase(klass, name), [])

    phaselist = getattr(klass, phase(klass, name))
    phaselist.append(func)


def _removeHook(klass, name, phase, func):
    "(private) removes a hook from a method on a class"
    phaselistname = phase(klass, name)
    if not hasattr(klass, ORIG(klass,name)):
        raise HookError("no hooks present!")

    phaselist = getattr(klass, phase(klass, name))
    try: phaselist.remove(func)
    except ValueError:
        raise HookError("hook %s not found in removal list for %s"%
                    (name,klass))

    if not getattr(klass, PRE(klass,name)) and not getattr(klass, POST(klass, name)):
        _dehook(klass, name)

def _enhook(klass, name):
    "(private) causes a certain method name to be hooked on a class"
    if hasattr(klass, ORIG(klass, name)):
        return

    def newfunc(*args, **kw):
        for preMethod in getattr(klass, PRE(klass, name)):
            preMethod(*args, **kw)
        try:
            return getattr(klass, ORIG(klass, name))(*args, **kw)
        finally:
            for postMethod in getattr(klass, POST(klass, name)):
                postMethod(*args, **kw)
    try:
        newfunc.func_name = name
    except TypeError:
        # Older python's don't let you do this
        pass

    oldfunc = getattr(klass, name).im_func
    setattr(klass, ORIG(klass, name), oldfunc)
    setattr(klass, PRE(klass, name), [])
    setattr(klass, POST(klass, name), [])
    setattr(klass, name, newfunc)

def _dehook(klass, name):
    "(private) causes a certain method name no longer to be hooked on a class"

    if not hasattr(klass, ORIG(klass, name)):
        raise HookError("Cannot unhook!")
    setattr(klass, name, getattr(klass, ORIG(klass,name)))
    delattr(klass, PRE(klass,name))
    delattr(klass, POST(klass,name))
    delattr(klass, ORIG(klass,name))
