
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Scheduling tasks for the future
===============================





Let's say we want to run a task X seconds in the future.
The way to do that is defined in the reactor interface :api:`twisted.internet.interfaces.IReactorTime <twisted.internet.interfaces.IReactorTime>` :




.. code-block:: python


    from twisted.internet import reactor

    def f(s):
        print("this will run 3.5 seconds after it was scheduled: %s" % s)

    reactor.callLater(3.5, f, "hello, world")

    # f() will only be called if the event loop is started.
    reactor.run()




If the result of the function is important or if it may be necessary
to handle exceptions it raises, then the :api:`twisted.internet.task.deferLater <twisted.internet.task.deferLater>` utility conveniently
takes care of creating a :api:`twisted.internet.defer.Deferred <Deferred>` and setting up a delayed
call:




.. code-block:: python

    from twisted.internet import task
    from twisted.internet import reactor

    def f(s):
        return "This will run 3.5 seconds after it was scheduled: %s" % s

    d = task.deferLater(reactor, 3.5, f, "hello, world")
    def called(result):
        print(result)
    d.addCallback(called)

    # f() will only be called if the event loop is started.
    reactor.run()

If we want a task to run every X seconds repeatedly, we can use :api:`twisted.internet.task.LoopingCall <twisted.internet.task.LoopingCall>`:

.. code-block:: python

    from twisted.internet import task
    from twisted.internet import reactor

    loopTimes = 3
    failInTheEnd = False
    _loopCounter = 0

    def runEverySecond():
        """
        Called at ever loop interval.
        """
        global _loopCounter

        if _loopCounter < loopTimes:
            _loopCounter += 1
            print('A new second has passed.')
            return

        if failInTheEnd:
            raise Exception('Failure during loop execution.')

        # We looped enough times.
        loop.stop()
        return


    def cbLoopDone(result):
        """
        Called when loop was stopped with success.
        """
        print("Loop done.")
        reactor.stop()


    def ebLoopFailed(failure):
        """
        Called when loop execution failed.
        """
        print(failure.getBriefTraceback())
        reactor.stop()


    loop = task.LoopingCall(runEverySecond)

    # Start looping every 1 second.
    loopDeferred = loop.start(1.0)

    # Add callbacks for stop and failure.
    loopDeferred.addCallback(cbLoopDone)
    loopDeferred.addErrback(ebLoopFailed)

    reactor.run()

If we want to cancel a task that we've scheduled:

.. code-block:: python

    from twisted.internet import reactor

    def f():
        print("I'll never run.")

    callID = reactor.callLater(5, f)
    callID.cancel()
    reactor.run()

As with all reactor-based code, in order for scheduling to work the reactor must be started using ``reactor.run()`` .



Timing out outstanding tasks
============================

Let's say we have a :api:`twisted.internet.defer.Deferred <Deferred>` representing a task that may take a long time.
We want to put an upper bound on that task, so we want the :api:`twisted.internet.defer.Deferred <Deferred>` to time
out X seconds in the future.

A convenient API to do so is :api:`twisted.internet.task.timeoutDeferred <twisted.internet.task.timeoutDeferred>`.
By default, it will fail with a :api:`twisted.internet.task.TimedOutError <TimedOutError>` if the :api:`twisted.internet.defer.Deferred <Deferred>` hasn't fired (with either an errback or a callback) within ``timeout`` seconds.

.. code-block:: python

    import random
    from twisted.internet import task

    def f():
        return "Hopefully this will be called in 3 seconds or less"

    def main(reactor):
        delay = random.uniform(1, 5)
        d = task.deferLater(reactor, delay, f)
        task.timeoutDeferred(d, 3, reactor)

        def called(result):
            print("{0} seconds later:".format(delay), result)
        d.addBoth(called)

        return d

    # f() will be timed out if the random delay is greater than 3 seconds
    task.react(main)


:api:`twisted.internet.task.timeoutDeferred <timeoutDeferred>` uses the :api:`twisted.internet.defer.Deferred.cancel <Deferred.cancel>` function under the hood, but can distinguish between a user's call to :api:`twisted.internet.defer.Deferred.cancel <Deferred.cancel>` and a cancellation due to a timeout.
By default, :api:`twisted.internet.task.timeoutDeferred <timeoutDeferred>` translates a :api:`twisted.internet.defer.CancelledError <CancelledError>` produced by the timeout into a :api:`twisted.internet.defer.TimedOutError <TimedOutError>`.

However, if you provided a custom cancellation callable when creating the :api:`twisted.internet.defer.Deferred <Deferred>`, then cancelling it may not produce a :api:`twisted.internet.defer.CancelledError <CancelledError>`.  In this case, you can pass a custom translation function to :api:`twisted.internet.task.timeoutDeferred <twisted.internet.task.timeoutDeferred>` that knows how to handle the custom cancellation result:

.. code-block:: python

    from twisted.internet import task, defer
    from twisted.python.failure import Failure

    class _MyCancellationError(Exception):
        pass

    def myCustomCancellerCallable(d):
        d.errback(_MyCancellationError("custom"))

    def myCustomCancellationTranslation(result, timeout):
        if isinstance(result, Failure):
            print("I failed with", result)
        else:
            print("Translations also handle success cases!", result)

    def main(reactor):
        # generate a deferred with a custom canceller function, and never
        # never callback or errback it to guarantee it gets timed out
        d = defer.Deferred(canceller=myCustomCancellerCallable)
        task.timeoutDeferred(
            d, 2, reactor,
            translateCancellation=myCustomCancellationTranslation)
        return d

    task.react(main)

You may also want a to provide a custom translation function if there was extra behavior you wanted; such as providing a default result instead of a failure if the :api:`twisted.internet.defer.Deferred <Deferred>` times out.
