"""
This is an ultra-minimal copy of bits of the Tag class from nevow's stan.py.

Usage:
from tag import tagmaker as T
T.a(href="foo.html")["text"]
"""

class TagMaker(object):
    def __getattr__(self, name):
        return Tag(name)
tagmaker = TagMaker()

class Tag(object):
    def __init__(self, tagName):
        self.tagName = tagName
        self.attributes = {}
        self.children = []
            
    def __call__(self, **kw):
        """Change attributes of this tag.         
        If the attribute is a python keyword, such as 'class', you can
        add an underscore to the name, like 'class_'.
        """
        for k, v in kw.iteritems():
            if k[-1] == u'_':
                k = k[:-1]
            self.attributes[k] = v
        return self

    def __getitem__(self, children):
        """Add children to this tag. Multiple children may be added by
        passing a tuple or a list. Children may be other tag instances
        or strings.
        """
        if not isinstance(children, (list, tuple)):
            children = [children]
        self.children.extend(children)
        return self

    def __repr__(self):
        return "Tag(%r, attributes=%r, children=%r)" % (
            self.tagName, self.attributes, self.children)


class xml(object):
    """XML content marker.
    
    xml contains content that is already correct XML and should not be escaped
    to make it XML-safe. 
    """
    __slots__ = ['content']
    
    def __init__(self, content):
        self.content = content
        
    def __repr__(self):
        return '<xml %r>' % self.content

allowSingleton = (u'img', u'br', u'hr', u'base', u'meta', u'link', u'param', u'area',
                  u'input', u'col', u'basefont', u'isindex', u'frame')

def serialize(obj):
    buf = []
    serialize_into(obj, buf)
    return u''.join(buf)

def serialize_into(obj, buf):
    if isinstance(obj, (list, tuple)):
        for subobj in obj:
            serialize_into(subobj, buf)
    elif isinstance(obj, unicode):
        serialize_string(obj, buf)
    elif isinstance(obj, str):
        serialize_string(unicode(obj), buf)
    elif isinstance(obj, xml):
        serialize_xml(obj, buf)
    elif isinstance(obj, Tag):
        serialize_tag(obj, buf)
    else:
        raise Exception("serialize: Unknown object %r" % obj)

def serialize_xml(s, buf):
    buf.append(s.content)

def serialize_string(s, buf):
    buf.append(s.replace(u"&", u"&amp;").replace(u"<", u"&lt;")
               .replace(u">", u"&gt;").replace(u'"', u"&quot;"))

def serialize_tag(tag, buf):
    buf.append(u'<%s' % tag.tagName)
    for (k, v) in tag.attributes.iteritems():
        if v is not None:
            buf.append(u' %s="' % k)
            serialize_into(v, buf)
            buf.append(u'"')
    if not tag.children and tag.tagName in allowSingleton:
        buf.append(u' />')
    else:
        buf.append(u'>')
        for child in tag.children:
            serialize_into(child, buf)
        buf.append(u'</%s>' % tag.tagName)
