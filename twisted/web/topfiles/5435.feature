The new attribute twisted.web.iweb.IClientRequest.absoluteURI contains the absolute URI made for an Agent request; while the new attribute twisted.web.iweb.IResponse.request contains a reference to the related request. It is now also possible to inspect redirect history with twisted.web.iweb.IResponse.previousResponse.

