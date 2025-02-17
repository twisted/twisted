ipv6 = False

if ipv6:
    interface = "::"
    group = "ff03::1"
else:
    interface = "0.0.0.0"
    group = "228.0.0.5"

port = 9999
