def getsockinfo(sock):
    s = `sock`
    sp = s[1:-1].split(",")[1:]
    d = {}
    for i in sp:
        exec(i.strip(), None, d)
    return (d["family"], d["type"], d["protocol"])

