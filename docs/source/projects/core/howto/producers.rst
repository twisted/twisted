
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Producers and Consumers: Efficient High-Volume Streaming
========================================================





The purpose of this guide is to describe the Twisted *producer* and *consumer* system.  The producer system allows applications to stream large amounts of data in a manner which is both memory and CPU efficient, and which does not introduce a source of unacceptable latency into the reactor.

    


Readers should have at least a passing familiarity with the terminology associated with interfaces.

    



Push Producers
--------------


    
A push producer is one which will continue to generate data without external prompting until told to stop; a pull producer will generate one chunk of data at a time in response to an explicit request for more data.

    


The push producer API is defined by the :api:`twisted.internet.interfaces.IPushProducer <IPushProducer>` interface.  It is best to create a push producer when data generation is closedly tied to an event source.  For example, a proxy which forwards incoming bytes from one socket to another outgoing socket might be implemented using a push producer: the :api:`twisted.internet.interfaces.IProtocol.dataReceived <dataReceived>` takes the role of an event source from which the producer generates bytes, and requires no external intervention in order to do so.

    


There are three methods which may be invoked on a push producer at various points in its lifetime: :api:`twisted.internet.interfaces.IPushProducer.pauseProducing <pauseProducing>` , :api:`twisted.internet.interfaces.IPushProducer.resumeProducing <resumeProducing>` , and :api:`twisted.internet.interfaces.IProducer.stopProducing <stopProducing>` .

    



pauseProducing()
~~~~~~~~~~~~~~~~


    
In order to avoid the possibility of using an unbounded amount of memory to buffer produced data which cannot be processed quickly enough, it is necessary to be able to tell a push producer to stop producing data for a while.  This is done using the ``pauseProducing`` method.  Implementers of a push producer should temporarily stop producing data when this method is invoked.

    



resumeProducing()
~~~~~~~~~~~~~~~~~


    
After a push producer has been paused for some time, the excess of data which it produced will have been processed and the producer may again begin producing data.  When the time for this comes, the push producer will have ``resumeProducing`` invoked on it.

    



stopProducing()
~~~~~~~~~~~~~~~


    
Most producers will generate some finite (albeit, perhaps, unknown in advance) amount of data and then stop, having served their intended purpose. However, it is possible that before this happens an event will occur which renders the remaining, unproduced data irrelevant.  In these cases, producing it anyway would be wasteful.  The ``stopProducing`` method will be invoked on the push producer.  The implementation should stop producing data and clean up any resources owned by the producer.

    



Pull Producers
--------------


    
The pull producer API is defined by the :api:`twisted.internet.interfaces.IPullProducer <IPullProducer>` interface.  Pull producers are useful in cases where there is no clear event source involved with the generation of data.  For example, if the data is the result of some algorithmic process that is bound only by CPU time, a pull producer is appropriate.

    


Pull producers are defined in terms of only two methods: :api:`twisted.internet.interfaces.IPullProducer.resumeProducing <resumeProducing>` and :api:`twisted.internet.interfaces.IProducer.stopProducing <stopProducing>` .

    



resumeProducing()
~~~~~~~~~~~~~~~~~


    
Unlike push producers, a pull producer is expected to **only** produce data in response to ``resumeProducing`` being called.  This method will be called whenever more data is required.  How much data to produce in response to this method call depends on various factors: too little data and runtime costs will be dominated by the back-and-forth event notification associated with a buffer becoming empty and requesting more data to process; too much data and memory usage will be driven higher than it needs to be and the latency associated with creating so much data will cause overall performance in the application to suffer.  A good rule of thumb is to generate between 16 and 64 kilobytes of data at a time, but you should experiment with various values to determine what is best for your application.

    



stopProducing()
~~~~~~~~~~~~~~~


    
This method has the same meaning for pull producers as it does for push producers.

    



Consumers
---------


    
This far, I've discussed the various external APIs of the two kinds of producers supported by Twisted.  However, I have not mentioned where the data a producer generates actually goes, nor what entity is responsible for invoking these APIs.  Both of these roles are filled by *consumers* . Consumers are defined by the one interface :api:`twisted.internet.interfaces.IConsumer <IConsumer>` .

    


``IConsumer`` , defines three methods: :api:`twisted.internet.interfaces.IConsumer.registerProducer <registerProducer>` , :api:`twisted.internet.interfaces.IConsumer.unregisterProducer <unregisterProducer>` , and :api:`twisted.internet.interfaces.IConsumer.write <write>` .

    



registerProducer(producer, streaming)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


    
So that a consumer can invoke methods on a producer, the consumer needs to be told about the producer.  This is done with the ``registerProducer`` method.  The first argument is either a ``IPullProducer`` or ``IPushProducer`` provider; the second argument indicates which of these interfaces is provided: ``True`` for push producers, ``False`` for pull producers.

    



unregisterProducer()
~~~~~~~~~~~~~~~~~~~~


    
Eventually a consumer will not longer be interested in a producer.  This could be because the producer has finished generating all its data, or because the consumer is moving on to something else, or any number of other reasons.  In any case, this method reverses the effects of ``registerProducer`` .

    



write(data)
~~~~~~~~~~~


    
As you might guess, this is the method which a producer calls when it has generated some data.  Push producers should call it as frequently as they like as long as they are not paused.  Pull producers should call it once for each time ``resumeProducing`` is called on them.

    



Further Reading
---------------


    
An example push producer application can be found in ``doc/examples/streaming.py`` .

    





- :doc:`Components: Interfaces and Adapters <components>` 
- :api:`twisted.protocols.basic.FileSender <FileSender>` : A Simple Pull Producer


  

