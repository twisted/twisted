def getsockinfo(sock):
    s = `sock._sock`
    sp = s[1:-1].split(",")[1:]
    g = {}
    d = {}
    for i in sp:
        exec i.strip() in g, d
    return (d["family"], d["type"], d["protocol"])

if __name__ == "__main__":
    from socket import socket, AF_INET, SOCK_DGRAM
    print getsockinfo(socket(AF_INET, SOCK_DGRAM))

