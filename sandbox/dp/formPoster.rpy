


from twisted.python.formmethod import MethodSignature, String, Password, Text, Choice, Integer, Float


import webform


def m(name=None, age=None, gpa=None, password=None, country=None, comments=None):
    print "METHOD CALLED PROPERLY"


def another(**kw):
    print "WE CALLED ANOTHER METHOD"


myForm = MethodSignature(
    String('name', default='Nobody', longDesc='Your name'),
    Integer('age', default='eaqff', longDesc="Your age"),
    Float('gpa', default='asdadf', longDesc="Your grade point average"),
    Password('password', longDesc="Your password"),
#    Choice('country', ['USA', 'Canada', 'Russia'], longDesc="Your country"), # I HATE THE CHOICE SYNTAX HATE
    Text('comments', default="No comment", longDesc="Your comments"),
)


resource = webform.FormPage(
    {
        'form1': myForm.method(m),
        'form2': myForm.method(another)
    },
    templateFile = 'form.html',
    templateDirectory = '.'
)

