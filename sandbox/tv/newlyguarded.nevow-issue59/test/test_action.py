from twisted.trial import unittest
from nevow import url
from login import getActionURL

class TestActionURL(unittest.TestCase):
    knownValues = [
        {'root': 'http://127.0.0.1:8081/prefix',
         'testcases':
         [ ('http://127.0.0.1:8081/prefix/secret',
            'http://127.0.0.1:8081/prefix/__login__/secret'),
           ('http://127.0.0.1:8081/prefix/secret/',
            'http://127.0.0.1:8081/prefix/__login__/secret/'),
           ('http://127.0.0.1:8081/prefix/secret/stuff',
            'http://127.0.0.1:8081/prefix/__login__/secret/stuff'),
           ('http://127.0.0.1:8081/prefix/secret/stuff/',
            'http://127.0.0.1:8081/prefix/__login__/secret/stuff/'),
           ('http://127.0.0.1:8081/prefix/secret/stuff/stuff',
            'http://127.0.0.1:8081/prefix/__login__/secret/stuff/stuff'),
           ('http://127.0.0.1:8081/prefix/secret/stuff/stuff/',
            'http://127.0.0.1:8081/prefix/__login__/secret/stuff/stuff/'),
           ],
         },

        {'root': 'http://127.0.0.1:8081/prefix/__session_key__xyzzy',
         'testcases':
         [ ('http://127.0.0.1:8081/prefix/__session_key__xyzzy/secret/stuff/stuff',
            'http://127.0.0.1:8081/prefix/__session_key__xyzzy/__login__/secret/stuff/stuff'),
           ],
         },
        ]

    def test_knownValues(self):
        for data in self.knownValues:
            root = url.URL.fromString(data['root'])
            for before, wanted in data['testcases']:
                before = url.URL.fromString(before)
                wanted = url.URL.fromString(wanted)
                got = getActionURL(before, root)
                self.assertEquals(str(got), str(wanted),
                                  "Wrong login action\nbefore\t%r\nroot\t%r\nwanted\t%r\ngot\t%r" %(
                    str(before),
                    str(root),
                    str(wanted),
                    str(got),
                    ))
