
from javax.swing import JFrame, JTable, JScrollPane, JPanel, JLabel, \
     JComboBox, JButton, JCheckBox, JTextField, BoxLayout
from javax.swing.border import TitledBorder
from java.awt import BorderLayout, GridLayout
from java.awt.event import ActionListener

### utilities

def newframe():
    f = JFrame()
    f.setSize(300, 300)
    f.setLocation(100,100)
    f.setTitle("Zing!")
    f.show()
    return f, f.getContentPane()

def formFromList(l):
    p = JPanel()
    rv = [p]
    p.setLayout(GridLayout(len(l), 2))
    for ltext, widget in l:
        p.add(JLabel(ltext))
        rv.append(widget)
        p.add(widget)
    return tuple(rv)

class _TempListener(ActionListener):
    def __init__(self, callable):
        self.callable = callable
    def actionPerformed(self, ae):
        self.callable(ae)

def actionListen(widget, callable):
    widget.addActionListener(_TempListener(callable))
    return widget

def titlePane(title):
    b = TitledBorder(title)
    p = JPanel()
    p.setBorder(b)
    return p

### Dialogs

class NewAccount:
    def __init__(self):
        self.buildFrame()
    def buildFrame(self):
        f, jp = newframe()
        jp.setLayout(BoxLayout(jp, BoxLayout.Y_AXIS))
        jp2 = JPanel()
        jp2.add(JLabel("Gateway"), BorderLayout.WEST)
        jcomb = JComboBox()
        jcomb.getModel().addElement("Hello!")
        jp2.add(jcomb)
        jp.add(jp2)
        gwopt = titlePane("Gateway Options")
        stdopt = titlePane("Standard Options")
        # gwopt.add(JButton("Nothing Here Yet"))
        gwopt.add(PBAccountForm().widget)
        jp.add(gwopt)
        stdopt.setLayout(GridLayout(2, 2))
        stdopt.add(JLabel("Auto Login"))
        stdopt.add(JCheckBox("Automatically Log In"))
        stdopt.add(JLabel("Account Name"))
        stdopt.add(JTextField())
        jp.add(stdopt)
        jp3 = JPanel()
        jp3.setLayout(BoxLayout(jp3, BoxLayout.X_AXIS))
        jp3.add(JButton("OK"))
        jp3.add(JButton("Cancel"))
        jp.add(jp3)


class PBAccountForm:
    def __init__(self):
        self.widget = self.buildPanel()

    def buildPanel(self):
        p, self.identityField, self.passwordField, self.hostField,\
           self.portField, self.serviceField, self.perspectiveField = \
           formFromList(
            [['Identity Name', JTextField()],
             ['Password', JTextField()],
             ['Hostname', JTextField()],
             ['Port Number', JTextField()],
             ['Service Name', JTextField()],
             ['Perspective Name', JTextField()]])
        return p



class AccountManager:

    def buildFrame(self):
        f, jp = newframe()
        jt = JTable([], ["Account Name", "Online",
                         "Auto Login", "Gateway Type"])
        js = JScrollPane(jt)
        jp.add(js)
        jp.add(actionListen(JButton("New Account"),
                            self.newAccountClicked),
               BorderLayout.SOUTH)
        return f

    def newAccountClicked(self, ae):
        print "clicked"
        NewAccount()
        return

    def __init__(self):
        self.frame = self.buildFrame()
