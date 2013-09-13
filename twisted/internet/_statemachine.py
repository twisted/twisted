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


    def transition(self, oldstate, newstate, datum, *a, **kw):
        if oldstate == newstate:
            return
        # print hex(id(self)), 'Going from', oldstate, 'to', newstate, 'because', datum
        exitmeth = getattr(self, 'exit_%s' % (oldstate,), None)
        entermeth = getattr(self, 'enter_%s' % (newstate,), None)
        transmeth = getattr(self, 'transition_%s_to_%s' % (
                oldstate, newstate), None)
        for meth in exitmeth, entermeth, transmeth:
            if meth is not None:
                meth(*a, **kw)
        self.state = newstate


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
            self.transition(OLDSTATE, NEWSTATE, DATUM, *a, **kw)
            self.output(output, *a, **kw)


    def output(self, datum, *a, **kw):
        foo = getattr(self, 'output_' + datum.upper(), None)
        if foo is not None:
            foo(*a, **kw)


    def invalidInput(self, datum):
        raise StateError("Invalid input in %r: %r" % (self.state, datum))
