
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Using Threads in Twisted
========================

How Twisted Uses Threads Itself
-------------------------------

All callbacks registered with the reactor - for example, ``dataReceived``, ``connectionLost``, or any higher-level method that comes from these, such as ``render_GET`` in twisted.web, or a callback added to a ``Deferred`` - are called from ``reactor.run``.
The terminology around this is that we say these callbacks are run in the "main thread", or "reactor thread" or "I/O thread".

Therefore, internally, Twisted makes very little use of threads.
This is not to say that it makes *no* use of threads; there are plenty of APIs which have no non-blocking equivalent, so when Twisted needs to call those, it calls them in a thread.
One prominent example of this is system hostname resolution: unless you have configured Twisted to use its own DNS client in ``twisted.names``, it will have to use your operating system's blocking APIs to map host names to IP addresses, in the reactor's thread pool.
However, this is something you only need to know about for resource-tuning purposes, like setting the number of threads to use; otherwise, it is an implementation detail you can ignore.

It is a common mistake is to think that because Twisted can manage multiple connections once, things are happening in multiple threads, and so you need to carefully manage locks.
Lucky for you, Twisted does most things in one thread!
This document will explain how to interact with existing APIs which need to be run within their own threads because they block.
If you're just using Twisted's own APIs, the rule for threads is simply "don't use them".

Invoking Twisted From Other Threads
-----------------------------------

Methods within Twisted may only be invoked from the reactor thread unless otherwise noted.
Very few things within Twisted are thread-safe.
For example, writing data to a transport from a protocol is not thread-safe.
This means that if you start a thread and call a Twisted method, you might get correct behavior... or you might get hangs, crashes, or corrupted data.
So don't do it.

The right way to call methods on the reactor from another thread, and therefore any objects which might call methods on the reactor, is to give a function to the reactor to execute within its own thread.
This can be done using the function :api:`twisted.internet.interfaces.IReactorThreads.callFromThread <callFromThread>`::

    from twisted.internet import reactor
    def notThreadSafe(someProtocol, message):
        someProtocol.transport.write(b"a message: " + message)
    def callFromWhateverThreadYouWant():
        reactor.callFromThread(notThreadSafe, b"hello")

In this example, ``callFromWhateverThreadYouWant`` is thread-safe and can be invoked by any thread, but ``notThreadSafe`` should only ever be called by code running in the thread where ``reactor.run`` is running.

.. note::

    There are many objects within Twisted that represent values - for example, :api:`twisted.python.filepath.FilePath <FilePath>` and :api:`twisted.python.urlpath.URLPath <URLPath>` - which you may construct yourself.
    These may be safely constructed and used within a non-reactor thread as long as they are not shared with other threads.
    However, you should be sure that these objects do not share any state, especially not with the reactor.
    One good rule of thumb is that any object whose methods return ``Deferred``\ s is almost certainly touching the reactor at some point, and should never be accessed from a non-reactor thread.

Running Code In Threads
-----------------------

Sometimes we may want to run code in a non-reactor thread, to avoid blocking the reactor.
Twisted provides an API for doing so, the :api:`twisted.internet.interfaces.IReactorThreads.callInThread <callInThread>` method on the reactor.

For example, to run a method in a non-reactor thread we can do::

    from twisted.internet import reactor

    def aSillyBlockingMethod(x):
        import time
        time.sleep(2)
        print(x)

    reactor.callInThread(aSillyBlockingMethod, "2 seconds have passed")
    reactor.run()

``callInThread`` will put your code into a queue, to be run by the next available thread in the reactor's thread pool.
This means that depending on what other work has been submitted to the pool, your method may not run immediately.

.. note::
    Keep in mind that ``callInThread`` can only concurrently run a fixed maximum number of tasks, and all users of the reactor are sharing that limit.
    Therefore, you should not submit *tasks which depend on other tasks in order to complete* to be executed by ``callInThread``.
    An example of such a task would be something like this::

        q = Queue()
        def blocker():
            print(q.get() + q.get())
        def unblocker(a, b):
            q.put(a)
            q.put(b)

    In this case, ``blocker`` will block *forever* unless ``unblocker`` can successfully run to give it inputs; similarly, ``unblocker`` might block forever if ``blocker`` is not run to consume its outputs.
    So if you had a threadpool of maximum size X, and you ran ``for each in range(X): reactor.callInThread(blocker)``, the reactor threadpool would be wedged forever, unable to process more work or even shut down.

    See "Managing the Reactor Thread Pool" below to tune these limits.

Getting Results
---------------

callInThread and callFromThread allow you to move the execution of your code out of and into the reactor thread, respectively, but that isn't always enough.

When we run some code, we often want to know what its result was.  For this, Twisted provides two methods: :api:`twisted.internet.threads.deferToThread <deferToThread>` and :api:`twisted.internet.threads.blockingCallFromThread <blockingCallFromThread>`, defined in the ``twisted.internet.threads`` module.

To get a result from some blocking code back into the reactor thread, we can use :api:`twisted.internet.threads.deferToThread <deferToThread>` to execute it instead of callFromThread.

    from twisted.internet import reactor, threads

    def doLongCalculation():
        # .... do long calculation here ...
        return 3

    def printResult(x):
        print(x)

    # run method in thread and get result as defer.Deferred
    d = threads.deferToThread(doLongCalculation)
    d.addCallback(printResult)
    reactor.run()

Similarly, you want some code running in a non-reactor thread wants to invoke some code in the reactor thread and get its result, you can use :api:`twisted.internet.threads.blockingCallFromThread <blockingCallFromThread>`::

    from twisted.internet import threads, reactor, defer
    from twisted.web.client import getPage
    from twisted.web.error import Error

    def inThread():
        try:
            result = threads.blockingCallFromThread(
                reactor, getPage, "http://twistedmatrix.com/")
        except Error, exc:
            print exc
        else:
            print result
        reactor.callFromThread(reactor.stop)

    reactor.callInThread(inThread)
    reactor.run()

``blockingCallFromThread`` will return the object or raise the exception returned or raised by the function passed to it.
If the function passed to it returns a Deferred, it will return the value the Deferred is called back with or raise the exception it is errbacked with.

Managing the Reactor Thread Pool
--------------------------------

We may want to modify the size of the thread pool, increasing or decreasing the number of threads in use.
We can do this::

    from twisted.internet import reactor

    reactor.suggestThreadPoolSize(30)

The default size of the thread pool depends on the reactor being used; the default reactor uses a minimum size of 0 and a maximum size of 10.

The reactor thread pool is implemented by :api:`twisted.python.threadpool.ThreadPool <ThreadPool>`.
To access methods on this object for more advanced tuning and monitoring (see the API documentation for details) you can get the thread pool with :api:`twisted.internet.interfaces.IReactorThreads.getThreadPool <getThreadPool>`.
