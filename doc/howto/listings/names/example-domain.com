
zone = [
    SOA(
        'example-domain.com',           # For whom we are the authority

        mname = "ns1.example-domain.com",  # This nameserver's name
        rname = "root.example-domain.com", # Mailbox of individual who handles this

        serial = 2003010601,        # Unique serial identifying this SOA data
        refresh = "1H",             # Time interval before zone should be 

        retry = "1H",               # Interval before failed refresh should be

        expire = "1H",              # Upper limit on time interval before

        minimum = "1H"              # Minimum TTL
    ),

    A('example-domain.com', '127.0.0.1'),
    NS('ns1.example-domain.com', 'example-domain.com'),

    CNAME('www.example-domain.com', 'example-domain.com'),
    CNAME('ftp.example-domain.com', 'example-domain.com'),

    MX('example-domain.com', 0, 'mail.example-domain.com'),
    A('mail.example-domain.com', '123.0.16.43')
]
