from twisted.python.components import registerAdapter
from twisted.web.resource import IResource
from twisted.web.test import FunkyForm

from BlogPost import BlogPost

from twisted.web.domtemplate import DOMTemplate


class BlogPostResourceAdapter(DOMTemplate):
    """
    An adapter for rendering a blog post in a browser.
    """
    templateFile = 'BlogPost.html'
    
    def getTemplateMethods(self):
        return [{'class': 'Title', 'method': self.title},
                    {'class': 'Contents', 'method': self.body},
                    {'class': 'Foo', 'method': self.funky},
                  ]

    def title(self, request, node):
        node.childNodes=[self.d.createTextNode(self.model.topic)]

    def body(self, request, node):
        h=self.d.createElement('h3')
        h.appendChild(self.d.createTextNode(self.model.topic))
        node.childNodes=[h]
        node.appendChild(self.d.createTextNode(self.model.body))

    def funky(self, request, node):
        return FunkyForm()

from BlogPost import BlogPost

# Register our adapter
# This tells twisted that BlogPostResourceAdapter knows how to 
# implement IResource for instances of BlogPost
registerAdapter(BlogPostResourceAdapter, BlogPost, IResource)




