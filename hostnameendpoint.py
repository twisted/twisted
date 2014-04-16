
from machinist import TransitionTable, constructFiniteStateMachine

from twisted.python.constants import Names, NamedConstant


class Input(Names):
    # Initial name resolution produced some results to try
    NAME_RESOLUTION_SUCCESS = NamedConstant()

    # Initial name resolution failed or produced zero results, nothing to do
    NAME_RESOLUTION_FAILURE = NamedConstant()

    # connect() Deferred was cancelled
    API_CANCEL = NamedConstant()

    # The last pending connection attempt failed and there are no more addresses to try.
    ALL_FAIL = NamedConstant()

    # An attempted connection failed.
    CONNECTION_FAILURE = NamedConstant()

    # A connection attempt succeeded.
    CONNECTION_SUCCESS = NamedConstant()

    # The happy eyeballs interval (300 ms) elapsed between a connection attempt
    # starting and it *not* having completed.  ie, it is time to start another
    # connection attempt.
    TIME_PASSES = NamedConstant()

    # An attempt has been started to connect to the last potential address.
    NO_MORE_ADDRESSES = NamedConstant()


class ConnectionSuccess(object):
    symbol = Input.CONNECTION_SUCCESS

    def __init__(self, protocol):
        self.protocol = protocol



class Output(Names):
    # Try to connect to an address.
    CONNECT = NamedConstant()

    # Clean up any connection attempts in progress but not yet completed.
    # Cancel timeouts or whatever.
    CLEANUP = NamedConstant()

    # 
    API_SUCCESS = NamedConstant()

    API_FAIL = NamedConstant()

    NAME_RESOLUTION_CANCEL = NamedConstant()



class State(Names):
    # In this state the initial name resolution is being performed.  It lasts
    # until we get some addresses to try.
    RESOLVING = NamedConstant()

    # In this state some connection attempts are being made but we also have
    # some more addresses held in reserve that we might try.
    HAPPY_EYEBALLS = NamedConstant()

    # In this state some connection attempts are still being made but there are
    # no more addresses we can try if the pending attempts fail.
    ONLY_WAITING = NamedConstant()

    # The connection attempt is over.  Nothing is happening.
    DONE = NamedConstant()


_table = TransitionTable()
_table = _table.addTransitions(
    State.RESOLVING, {
        Input.API_CANCEL:
            ([Output.NAME_RESOLUTION_CANCEL, Output.API_FAIL], State.DONE),
        Input.NAME_RESOLUTION_SUCCESS:
            ([Output.CONNECT], State.HAPPY_EYEBALLS),
        Input.NAME_RESOLUTION_FAILURE:
            ([Output.API_FAIL], State.DONE),
        })

_table = _table.addTransitions(
    State.HAPPY_EYEBALLS, {
        Input.CONNECTION_FAILURE:
            ([Output.CONNECT], State.HAPPY_EYEBALLS),
        Input.CONNECTION_SUCCESS:
            ([Output.CLEANUP, Output.API_SUCCESS], State.DONE),
        Input.API_CANCEL:
            ([Output.CLEANUP, Output.API_FAIL], State.DONE),
        Input.NO_MORE_ADDRESSES:
            ([], State.ONLY_WAITING),
        Input.TIME_PASSES:
            ([Output.CONNECT], State.HAPPY_EYEBALLS),
        })

_table = _table.addTransitions(
    State.ONLY_WAITING, {
        Input.ALL_FAIL: ([Output.API_FAIL], State.DONE),
        Input.CONNECTION_SUCCESS: ([Output.CLEANUP, Output.API_SUCCESS], State.DONE),
        Input.API_CANCEL: ([Output.CLEANUP, Output.API_FAIL], State.DONE),
        })


class _HostnameEndpointThing(object):
    def __init__(self, factory, resolving, winner):
        self._factory = factory
        self._resolving = resolving
        self._winner = winner
        self._pending = []
        self._endpoints = []


    def output_CONNECT(self, endpoints):
        e = next(endpoints)
        d = e.connect(self._factory)
        self._pending.append(d)

        # sneaky - maybe the rich input interface for CONNECTION_SUCCESS is
        # IProtocol protocols provide IProtocol!  And maybe Failure is the rich
        # input for CONNECTION_FAILURE!  Or is this too crazy?  Ooops this
        # doesn't work, neither object has the required "symbol" attribute.
        d.addBoth(self.fsm.receive)


    def output_NAME_RESOLUTION_CANCEL(self, address):
        self._resolving.cancel()
        self._resolving = None


    def output_CLEANUP(self):
        for attempt in self._pending:
            attempt.cancel()
        self._pending = None


    def output_API_SUCCESS(self, protocol):
        self._winner.callback(protocol)
        self._winner = None


    def output_API_FAILURE(self, reason):
        self._winner.errback(reason)
        self._winner = None



class HostnameEndpoint:
    def connect(self, factory):
        winner = Deferred()
        resolving = reactor.resolve(self.hostname)
        outputer = _HostnameEndpointThing(resolving, winner)
        fsm = constructFiniteStateMachine(
            Input, Output, State, _table, initial=State.RESOLVING,
            richInputs={Output.API_SUCCESS: ISuccess}, inputContext={},
            world=MethodSuffixOutputer(outputer))
        
