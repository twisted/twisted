from twisted.web2.test.test_server import BaseCase

class TestNevowCompat(BaseCase):
    try:
        import nevow
    except ImportError:
        skip = "can't run w/o nevow"

    def testSimpleNevowResource(self):
        from nevow import rend
        class Foo(rend.Page):
            def renderHTTP(self, ctx):
                return "Foo"

        self.assertResponse((Foo(), "http://localhost/"),
                            (200, {}, 'Foo'))


try:
    from twisted.web import resource

    class OldWebResource(resource.Resource):
        def __init__(self, message, *args, **kwargs):
            self.message = message
            resource.Resource.__init__(self, *args, **kwargs)
            
        isLeaf = True
        
        def render(self, req):
            return self.message
    
except ImportError:
    OldWebCompat.skip = "can't run w/o twisted.web"

class OldWebCompat(BaseCase):
    try:
        import twisted.web
    except ImportError:
        skip = "can't run w/o twisted.web"

    def testOldWebResource(self):
        ow = OldWebResource('I am an OldWebResource')
        
        self.assertResponse((ow, "http://localhost/"),
                            (200, {}, 'I am an OldWebResource'))

    def testOldWebResourceNotLeaf(self):
        ow = OldWebResource('I am not a leaf')
        ow.isLeaf = False

        self.assertResponse((ow, "http://localhost/"),
                            (200, {}, 'I am not a leaf'))

    def testOldWebResourceWithChildren(self):
            
        ow = OldWebResource('I am an OldWebResource with a child')
        
        ow.isLeaf = False

        ow.putChild('child',
                    OldWebResource('I am a child of an OldWebResource'))

        self.assertResponse((ow, "http://localhost/"),
                            (200, {},
                             'I am an OldWebResource with a child'))

        self.assertResponse((ow, "http://localhost/child"),
                            (200, {},
                             'I am a child of an OldWebResource'))

        
