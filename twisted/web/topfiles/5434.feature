twisted.web.client.BrowserLikeRedirectAgent, a new redirect agent, treats HTTP 301 and 302 like HTTP 303 on non-HEAD/GET requests, changing the method to GET before proceeding.
