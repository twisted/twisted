import os.path, time
from twisted.web2 import server, http, resource, channel
from twisted.web2 import static, http_headers, responsecode

class Child(resource.Resource):
  creation_time = time.time()
  text = 'Yo Ho Ho and a bottle of rum.'
  content_type = http_headers.MimeType('text', 'plain')

  def render(self, ctx):
    return http.Response(
      responsecode.OK,
      {'last-modified': self.creation_time,
      'etag': http_headers.ETag(str(hash(self.text))),
      'content-type': self.content_type},
      self.text)

class Toplevel(resource.Resource):
  addSlash = True
  child_monkey = static.File(os.path.dirname(static.__file__)+'/static.py')
  child_elephant = Child()

  def render(self, ctx):
    return http.Response(
      200, 
      {'content-type': http_headers.MimeType('text', 'html')},
      """<html><body>
      <a href="monkey">The source code of twisted.web2.static</a><br>
      <a href="elephant">A defined child</a></body></html>""")

site = server.Site(Toplevel())

# Standard twisted application Boilerplate
from twisted.application import service, strports
application = service.Application("demoserver")
s = strports.service('tcp:8080', channel.HTTPFactory(site))
s.setServiceParent(application)
