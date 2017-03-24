twisted.web._newclient and HTTPParser always raises ValueError for multiple
Content-Length Headers or for Content-Length Headers with a list of lengths
as the field-value (per RFC7230#section-3.3.2). New behavior is to use first
entry of list if all expected lengths sent are distinct (conflicting
content-length headers/field-values will raise ValueError).
