from twisted.web import vhost, static, script

default = static.Data('text/html', '')
default.putChild('vhost', vhost.VHostMonsterResource())
resource = vhost.NameVirtualHost()
resource.default = default
file = static.File('static')
file.processors = {'.rpy': script.ResourceScript}
resource.addHost('twistedmatrix.com', file)
