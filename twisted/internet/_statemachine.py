# -*- test-case-name: twisted.internet.test.test_statemachine -*-
# Copyright (c) 2005 Divmod Inc.


NOTHING = 'nothing'             # be quiet (no output)

class StateError(Exception):
    """
    """


class StateMachine:
    # TODO: Class decorator instead of a superclass.

    initialState = None         # a str describing initial state

    states = None     # dict, mapping state to dict of str input: (str output,
                      # str new-state)

    def __init__(self, initialState=None):
        if initialState is None:
            initialState = self.initialState
        self.state = self.initialState


    def input(self, datum, *a, **kw):
        if datum == NOTHING:
            return
        try:
            output, newstate = self.states[self.state][datum]
        except KeyError:
            self.invalidInput(datum)
        else:
            OLDSTATE = self.state.upper()
            NEWSTATE = newstate.upper()
            DATUM = datum.upper()
            self.output(output, *a, **kw)


    def output(self, datum, *a, **kw):
        foo = getattr(self, 'output_' + datum.upper(), None)
        if foo is not None:
            foo(*a, **kw)


    def invalidInput(self, datum):
        raise StateError("Invalid input in %r: %r" % (self.state, datum))
