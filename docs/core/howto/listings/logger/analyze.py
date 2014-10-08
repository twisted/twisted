from twisted.logger import extractField

fmt = (
    "message from {log_source} "
    "where a is {log_source.a} and b is {log_source.b}"
)

def analyze(event):
    if event.get("log_format") == fmt:
        a = extractField("log_source.a", event)
        b = extractField("log_source.b", event)
        print("A + B = " + repr(a + b))
