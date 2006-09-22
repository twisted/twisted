from twisted.web2 import responsecode
import urlparse

__all__ = ['addLocation']

def addLocation(request, location):
    """
    Add a C{location} header to the response if the response status is
    CREATED.
    @param request: L{IRequest} the request being processed
    @param location: the URI to use in the C{location} header
    """
    def locationFilter(request, response):
        if (response.code == responsecode.CREATED):
            #
            # Check to see whether we have an absolute URI or not.
            # If not, have the request turn it into an absolute URI.
            #
            (scheme, host, path, params, querystring, fragment) = urlparse.urlparse(location)

            if scheme == "":
                uri = request.unparseURL(path=location)
            else:
                uri = location
        
            response.headers.setHeader("location", uri)

        return response

    request.addResponseFilter(locationFilter)
