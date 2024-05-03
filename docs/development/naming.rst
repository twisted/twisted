
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Naming Conventions
==================





While this may sound like a small detail, clear method naming is important to provide an API that developers familiar with event-based programming can pick up quickly.




Since the idea of a method call maps very neatly onto that of a received event, all event handlers are simply methods named after past-tense verbs. All class names are descriptive nouns, designed to mirror the is-a relationship of the abstractions they implement. All requests for notification or transmission are present-tense imperative verbs.




Here are some examples of this naming scheme:





- An event notification of data received from peer:``dataReceived(data)`` 
- A request to send data: ``write(data)`` 
- A class that implements a protocol: ``Protocol`` 





The naming is platform neutral. This means that the names are equally appropriate in a wide variety of environments, as long as they can publish the required events.




It is self-consistent. Things that deal with TCP use the acronym TCP, and it is always capitalized. Dropping, losing, terminating, and closing the connection are all referred to as "losing" the connection. This symmetrical naming allows developers to easily locate other API calls if they have learned a few related to what they want to do.




It is semantically clear. The semantics of dataReceived are simple: there are some bytes available for processing. This remains true even if the lower-level machinery to get the data is highly complex.



