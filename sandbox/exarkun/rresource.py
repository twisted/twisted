
class RestrictedResource(resource.Resource):
    default = True
    
    def __init__(self, wrapped, rules):
        resource.Resource.__init__(self)
        self.wrapped = wrapped
        self.rules = rules

    def getChild(self, name, request):
        if self.checkRequest(request):
            return self.wrapped.getChild(name, request)
        else:
            return error.ForbiddenResource("Access denied")

    def render(self, request):
        if self.checkRequest(request, self.rules):
            return self.wrapped.render(request)
        else:
            request.setResponseCode(403)
            return 'Access denied'

    def checkRequest(self, request, rules):
        for (condition, rule) in rules:
            if condition.check(self, request):
                try:
                    c = rule.check
                except AttributeError:
                    b = self.checkRequest(request, rule)
                else:
                    b = c(self, request)
                if b is not None:
                    return b
        return self.default

def main():
    from twisted.web import server
    from twisted.web import static
    
    from predicates import Contradiction, Tautology
    from predicates import Address, MonthDay, UniqueHosts, Connections
    rules = [
        # Localhost can always connect
        (Address == '127.0.0.1/255.255.255.255')(Tautology),
        (Month == 10)(
            # Oct 29th no one else can connect
            (MonthDay == 29)(Contradiction),
            (MonthDay == 30)(
                # Oct 30th anyone on 10.x.x.x can connect, as long as there
                # are 512 or fewer unique IPs connected.
                (Address == '10.0.0.0/255.0.0.0')(UniqueHosts <= 512)
            )
        ),
        # Any other connection is allowed, as long as they are from a host with
        # less than 10 existing connections.
        (Tautology)(Connections < 10)
    ]
    site = server.Site(RestrictedResource(static.File('.'), rules))
    
