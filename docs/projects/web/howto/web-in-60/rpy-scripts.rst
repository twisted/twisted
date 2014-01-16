
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

rpy scripts (or, how to save yourself some typing)
==================================================





The goal of this installment is to show you another way to run a Twisted Web
server with a custom resource which doesn't require as much code as the previous
examples.




The feature in question is called an ``rpy script`` . An rpy script
is a Python source file which defines a resource and can be loaded into a
Twisted Web server. The advantages of this approach are that you don't have to
write code to create the site or set up a listening port with the reactor. That
means fewer lines of code that aren't dedicated to the task you're trying to
accomplish.




There are some disadvantages, though. An rpy script must have the
extension ``.rpy`` . This means you can't import it using the
usual Python import statement. This means it's hard to re-use code in
an rpy script. This also means you can't easily unit test it. The code
in an rpy script is evaluated in an unusual context. So, while rpy
scripts may be useful for testing out ideas, they're not recommend for
much more than that.




Okay, with that warning out of the way, let's dive in. First, as mentioned,
rpy scripts are Python source files with the ``.rpy`` extension. So,
open up an appropriately named file (for example, ``example.rpy`` ) and
put this code in it:





.. code-block:: python

    
    import time
    
    from twisted.web.resource import Resource
    
    class ClockPage(Resource):
        isLeaf = True
        def render_GET(self, request):
            return "<html><body>%s</body></html>" % (time.ctime(),)
    
    resource = ClockPage()




You may recognize this as the resource from
the :doc:`first dynamic rendering example <dynamic-content>` . What's different is what you don't see: we didn't
import ``reactor`` or ``Site`` . There are no calls
to ``listenTCP`` or ``run`` . Instead, and this is
the core idea for rpy scripts, we just bound the
name ``resource`` to the resource we want the script to
serve. Every rpy script must bind this name, and this name is the only
thing Twisted Web will pay attention to in an rpy script.




All that's left is to drop this rpy script into a Twisted Web server. There
are a few ways to do this. The simplest way is with ``twistd`` :





.. code-block:: console

    
    $ twistd -n web --path .




Hit `http://localhost:8080/example.rpy <http://localhost:8080/example.rpy>`_ 
to see it run. You can pass other arguments here too. ``twistd web`` 
has options for specifying which port number to bind, whether to set up an HTTPS
server, and plenty more. Other options you can pass to ``twistd`` allow
you to configure logging to work differently, to select a different reactor,
etc. For a full list of options, see ``twistd --help`` and ``twistd web --help`` .



