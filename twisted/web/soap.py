"""SOAP support for twisted.web.

Requires SOAPpy.

API Stability: unstable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org}

Future plans:
SOAPContext support of some kind.
Pluggable method lookup policies.
Figure out why None doesn't work, and write tests.
"""

# SOAPpy
import SOAP

# twisted imports
from twisted.web import server, resource
from twisted.internet import defer
from twisted.python import log, failure


class SOAPPublisher(resource.Resource):
    """Publish methods beginning with 'soap_'.

    If the method has an attribute 'useKeywords', it well get the
    arguments passed as keyword args.
    """

    isLeaf = 1
    
    # override to change the encoding used for responses
    encoding = "UTF-8"
    
    def render(self, request):
        """Handle a SOAP command."""
        data = request.content.read()

        p, header, body, attrs = SOAP.parseSOAPRPC(data, 1, 1, 1)

        method, args, kwargs, ns = p._name, p._aslist, p._asdict, p._ns
        function = getattr(self, "soap_%s" % method, None)
        
        if not function:
            self._methodNotFound(request, method)
            return server.NOT_DONE_YET
        else:
            try:
                if hasattr(function, "useKeywords"):
                    keywords = {}
                    for k, v in kwargs.items():
                        keywords[str(k)] = v
                    result = function(**keywords)
                else:
                    result = function(*args)
            except:
                f = failure.Failure()
                log.err(f)
                self._gotError(f, request, method)
                return server.NOT_DONE_YET

        if isinstance(result, defer.Deferred):
            result.addCallback(self._gotResult, request, method)
            result.addErrback(self._gotError, request, method)
        else:
            self._gotResult(result, request, method)
        return server.NOT_DONE_YET

    def _methodNotFound(self, request, methodName):
        response = SOAP.buildSOAP(SOAP.faultType("%s:Client" % SOAP.NS.ENV_T,
                                                 "Method %s not found" % methodName),
                                  encoding=self.encoding)
        self._sendResponse(request, response, status=500)
    
    def _gotResult(self, result, request, methodName):
        response = SOAP.buildSOAP(kw={'%sResponse' % methodName: result},
                                  encoding=self.encoding)
        self._sendResponse(request, response)

    def _gotError(self, failure, request, methodName):
        e = failure.value
        if isinstance(e, SOAP.faultType):
            fault = e
        else:
            fault = SOAP.faultType("%s:Server" % SOAP.NS.ENV_T, "Method %s failed." % methodName)
        response = SOAP.buildSOAP(fault, encoding=self.encoding)
        self._sendResponse(request, response, status=500)

    def _sendResponse(self, request, response, status=200):
        request.setResponseCode(status)

        if self.encoding is not None:
            mimeType = 'text/xml; charset="%s"' % self.encoding
        else:
            mimeType = "text/xml"
        request.setHeader("Content-type", mimeType)
        request.setHeader("Content-length", str(len(response)))
        request.write(response)
        request.finish()
