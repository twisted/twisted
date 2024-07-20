twisted.web.agent.Agent now allows duplicate Content-Length headers having the same value, per RFC 9110 section 8.6. It is otherwise more strict when parsing Content-Length header values.
