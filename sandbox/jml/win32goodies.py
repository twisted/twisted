import win32api, win32con, pywintypes

class RegistryKey:
    def __init__(self, parent, name=None):
        if name is None:
            self.key = parent
        else:
            self.key = win32api.RegOpenKey(parent.key, name)

    def queryKeys(self):
        subkeys, _, _ = win32api.RegQueryInfoKey(self.key)
        for i in range(subkeys):
            yield win32api.RegEnumKey(self.key, i)

    def queryChildren(self):
        for name in self.queryKeys():
            key = self.getChild(name)
            yield key
            key.close()

    def queryValues(self):
        _, values, _ = win32api.RegQueryInfoKey(self.key)
        for i in range(values):
            yield win32api.RegEnumValue(self.key, i)

    def getChild(self, name):
        return RegistryKey(self, name)

    def close(self):
        win32api.RegCloseKey(self.key)

    def getValue(self, name=None):
        if name is not None:
            try:
                return win32api.RegQueryValueEx(self.key, name)
            except pywintypes.error:
                raise KeyError, "No registry value with name: %s" % (name,)
        else:
            return win32api.RegQueryValue(self.key)

    def __getitem__(self, name):
        return self.getValue(name)


LOCAL_MACHINE = RegistryKey(win32con.HKEY_LOCAL_MACHINE)

def getSystemShares():
    key = LOCAL_MACHINE.getChild(r"SYSTEM\ControlSet001\Services\lanmanserver\Shares")
    shares = {}
    for name, obj, typ in key.queryValues():
        path = obj[2]
        shares[name] = path.split('=')[1]
    key.close()
    return shares

def getNetworkInterfaces():
    nicsKey = LOCAL_MACHINE.getChild(r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\NetworkCards")
    interfaces = []
    for nic in nicsKey.queryChildren():
        serviceKey = r"SYSTEM\CurrentControlSet\Services\%s\Parameters\TcpIp" % nic['ServiceName'][0]
        serviceKey = LOCAL_MACHINE.getChild(serviceKey)

        defaultGateway = None
        try:
            defaultGateway = serviceKey['DefaultGateway'][0]
            if defaultGateway:
                defaultGateway = defaultGateway[0]
                ipAddress = serviceKey['IPAddress'][0]
                netmask = serviceKey['SubnetMask'][0]
        except KeyError:
            pass

        try:
            defaultGateway = serviceKey['DhcpDefaultGateway'][0]
            if defaultGateway:
                defaultGateway = defaultGateway[0]
                ipAddress = serviceKey['DhcpIPAddress'][0]
                netmask = serviceKey['DhcpSubnetMask'][0]
        except KeyError:
            pass

        if defaultGateway:
            interfaces.append((defaultGateway, ipAddress, netmask))

        serviceKey.close()
    nicsKey.close()
    return interfaces


if __name__ == '__main__':
    print getSystemShares()
    print getNetworkInterfaces()
