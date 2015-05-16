
zone = [
    SOA(
        # For whom we are the authority
        'example-domain.com',

        # This nameserver's name
        mname = "ns1.example-domain.com",
        
        # Mailbox of individual who handles this
        rname = "root.example-domain.com",

        # Unique serial identifying this SOA data
        serial = 2003010601,        

        # Time interval before zone should be refreshed
        refresh = "1H",             

        # Interval before failed refresh should be retried
        retry = "1H",               

        # Upper limit on time interval before expiry
        expire = "1H",              

        # Minimum TTL
        minimum = "1H"              
    ),

    A('example-domain.com', '127.0.0.1'),
    NS('example-domain.com', 'ns1.example-domain.com'),

    CNAME('www.example-domain.com', 'example-domain.com'),
    CNAME('ftp.example-domain.com', 'example-domain.com'),

    MX('example-domain.com', 0, 'mail.example-domain.com'),
    A('mail.example-domain.com', '123.0.16.43')
]
