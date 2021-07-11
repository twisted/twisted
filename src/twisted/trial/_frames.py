# -*- test-case-name: twisted.trial.test.test_reporter -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
#

"""
Format trial tracebacks and trim frames to remove internal paths.
"""

import importlib
import os
import pathlib


def _getCvarFrame():
    try:
        from contextvars import Context
    except ModuleNotFoundError:
        return ("run", "defer")  # defer._NoContext.run

    try:
        _cvar_mod = Context.run.__module__
    except AttributeError:
        return None  # cpython 3.7 Context.run is a builtin

    # pypy3.7 or https://pypi.org/project/contextvars
    return ("run", pathlib.Path(importlib.import_module(_cvar_mod).__file__).stem)


_cvarFrame = _getCvarFrame()


def _trimRunnerFrames(frames):
    def frameInfo(f):
        return f[0], os.path.splitext(os.path.basename(f[1]))[0]

    syncCase = [("_run", "_synctest")]

    if len(frames) < 1:
        return frames

    frame0 = frameInfo(frames[0])
    if [frame0] == syncCase:
        return frames[1:]

    if len(frames) < 2:
        return frames

    asyncCase = [
        ("_inlineCallbacks", "defer"),
        ("_runCorofnWithWarningsSuppressed", "_asynctest"),
    ]

    frame1 = frameInfo(frames[1])
    if [frame0, frame1] == asyncCase:
        return frames[2:]

    if len(frames) < 3:
        return frames

    asyncShimCvarCase = [
        ("_inlineCallbacks", "defer"),
        _cvarFrame,
        ("_runCorofnWithWarningsSuppressed", "_asynctest"),
    ]

    frame2 = frameInfo(frames[2])
    if [frame0, frame1, frame2] == asyncShimCvarCase:
        return frames[3:]

    if len(frames) < 4:
        return frames

    asyncFailureCase = [
        ("_inlineCallbacks", "defer"),
        ("throwExceptionIntoGenerator", "failure"),
        ("_runCorofnWithWarningsSuppressed", "_asynctest"),
        ("_runCallbacks", "defer"),
    ]

    frame2 = frameInfo(frames[2])
    frame3 = frameInfo(frames[3])
    if [frame0, frame1, frame2, frame3] == asyncFailureCase:
        return frames[4:]

    if len(frames) < 5:
        return frames

    asyncFailureShimCvarCase = [
        ("_inlineCallbacks", "defer"),
        _cvarFrame,
        ("throwExceptionIntoGenerator", "failure"),
        ("_runCorofnWithWarningsSuppressed", "_asynctest"),
        ("_runCallbacks", "defer"),
    ]

    frame4 = frameInfo(frames[4])
    if [frame0, frame1, frame2, frame3, frame4] == asyncFailureShimCvarCase:
        return frames[5:]

    return frames


def _trimFrames(frames):
    """
    Trim frames to remove internal paths.
    
    TODO: https://twistedmatrix.com/trac/ticket/10220

    When a C{SynchronousTestCase} method fails synchronously, the stack
    looks like this:
     - [0]: C{SynchronousTestCase._run}
     - [1:-2]: code in the test method which failed
     - [-1]: C{_synctest.fail}

    When a C{TestCase} method fails synchronously, the stack looks like
    this:
     - [0]: C{defer._inlineCallbacks}
     - [1]: C{TestCase._runCorofnWithWarningsSuppressed}
     - [2:-2]: code in the test method which failed
     - [-1]: C{_synctest.fail}

    When a method fails inside a C{Deferred} (i.e., when the test method
    returns a C{Deferred}, and that C{Deferred}'s errback fires), the stack
    captured inside the resulting C{Failure} looks like this:
     - [0]: C{defer._inlineCallbacks}
     - [1]: C{defer.throwExceptionIntoGenerator}
     - [2]: C{TestCase._runCorofnWithWarningsSuppressed}
     - [3]: C{defer._runCallbacks}
     - [4:-2]: code in the testmethod which failed
     - [-1]: C{_synctest.fail}

    As a result, we want to trim those frames from the front,
    and trim the [unittest.fail] from the end.

    There is also another case, when the test method is badly defined and
    contains extra arguments.

    If it doesn't recognize one of these cases, it just returns the
    original frames.

    @param frames: The C{list} of frames from the test failure.

    @return: The C{list} of frames to display.
    """
    newFrames = _trimRunnerFrames(list(frames))

    if not newFrames:
        # The method fails before getting called, probably an argument
        # problem
        return newFrames

    last = newFrames[-1]
    if (
        last[0].startswith("fail")
        and os.path.splitext(os.path.basename(last[1]))[0] == "_synctest"
    ):
        return newFrames[:-1]

    return newFrames


def _formatFailureTraceback(*, detail, fail):
    if isinstance(fail, str):
        return fail.rstrip() + "\n"
    fail.frames, frames = _trimFrames(fail.frames), fail.frames
    result = fail.getTraceback(detail=detail, elideFrameworkCode=True)
    fail.frames = frames
    return result
