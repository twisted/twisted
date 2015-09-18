
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Overview of Twisted Web
=======================






Introduction
------------


    
Twisted Web is a web application server written in pure
Python, with APIs at multiple levels of abstraction to
facilitate different kinds of web programming.


    



Twisted Web's Structure
-----------------------


        


.. image:: ../img/web-overview.png



        


When
the Web Server receives a request from a Client, it creates
a Request object and passes it on to the Resource system.
The Resource system dispatches to the appropriate Resource
object based on what path was requested by the client. The
Resource is asked to render itself, and the result is
returned to the client.

    



Resources
---------


    
Resources are the lowest-level abstraction for applications
in the Twisted web server. Each Resource is a 1:1 mapping with
a path that is requested: you can think of a Resource as a
single "page" to be rendered. The interface for making
Resources is very simple; they must have a method named
``render`` which takes a single argument, which is the
Request object (an instance of :api:`twisted.web.server.Request <twisted.web.server.Request>` ). This render
method must return a string, which will be returned to the web
browser making the request. Alternatively, they can return a
special constant, :api:`twisted.web.server.NOT_DONE_YET <twisted.web.server.NOT_DONE_YET>` , which tells
the web server not to close the connection; you must then use
``request.write(data)`` to render the
page, and call ``request.finish()`` 
whenever you're done.


    



Web programming with Twisted Web
--------------------------------


    

Web programmers seeking a higher level abstraction than the Resource system
should look at `Nevow <https://launchpad.net/nevow>`_ .
Nevow is based on ideas previously developed in Twisted, but is now maintained
outside of Twisted to easy development and release cycle pressures.

  

