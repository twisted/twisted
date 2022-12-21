
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Glossary
========





This glossary is very incomplete.  Contributions are
welcome.

    




      
.. _web-howto-glossary-resource:

resource




      
  
  An object accessible via HTTP at one or more URIs.  In Twisted Web,
  a resource is represented by an object which provides :py:class:`twisted.web.resource.IResource` and most often is
  a subclass of :py:class:`twisted.web.resource.Resource` .  For example, here
  is a resource which represents a simple HTML greeting.
  
  
  .. code-block:: python
  
      
      from twisted.web.resource import Resource
      
      class Greeting(Resource):
          def render_GET(self, request):
              return "


  

