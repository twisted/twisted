from twisted.web.template import Element, renderer, XMLFile
from twisted.python.filepath import FilePath

class ExampleElement(Element):
    loader = XMLFile(FilePath('slots-attributes-1.xml'))

    @renderer
    def person_profile(self, request, tag):
        # Note how convenient it is to pass these attributes in!
        tag.fillSlots(person_name='Luke',
                      profile_image_url='http://example.com/user.png')
        return tag
