from twisted.im.baseaccount import AccountManager
from twisted.im.pbsupport import PBAccount
from twisted.im.tocsupport import TOCAccount
from twisted.im.ircsupport import IRCAccount

from java.awt import GridLayout, FlowLayout, BorderLayout, Container
import sys
from java.awt.event import ActionListener
from javax.swing import JTextField, JPasswordField, JComboBox, JPanel, JLabel,\
     JCheckBox, JFrame, JButton, BoxLayout, JTable, JScrollPane, \
     ListSelectionModel
from javax.swing.border import TitledBorder
from javax.swing.table import DefaultTableModel

doublebuffered = 0
stype = "twisted.words"

gateways = { "Twisted" : [["Identity Name", JTextField()],
                          ["Password", JPasswordField()],
                          ["Host", JTextField("twistedmatrix.com")],
                          ["Port", JTextField("8787")],
                          #["Service Type", JComboBox(twistedServices)],
                          ["Service Name", JTextField("twisted.words")],
                          ["Perspective Name", JTextField()]],
             "AIM"     : [["Screen Name", JTextField()],
                          ["Password", JPasswordField()],
                          ["Host", JTextField("toc.oscar.aol.com")],
                          ["Port", JTextField("9898")]],
             "IRC"     : [["Nickname", JTextField()],
                          ["Password", JPasswordField()],
                          ["Host", JTextField()],
                          ["Port", JTextField("6667")],
                          ["Channels", JTextField()]]
             }

def makeGWDict():
    gatedict = {}
    for key in gateways.keys():
        gatedict[key] = {}
        for value in gateways[key]:
            gatedict[key][value[0]] = value[1]
    return gatedict

gatedict = makeGWDict()

class _Listener(ActionListener):
    def __init__(self, callable):
        self.callable = callable
    def actionPerformed(self, ae):
        self.callable(ae)

def actionWidget(widget, callable):
    widget.addActionListener(_Listener(callable))
    return widget

class NewAccountGUI:
    def __init__(self, amgui):
        self.amgui = amgui
        self.am = amgui.acctmanager

        self.autologin = JCheckBox("Automatically Log In")
        self.acctname = JTextField()
        self.gwoptions = JPanel(doublebuffered)
        self.gwoptions.setBorder(TitledBorder("Gateway Options"))

        self.mainframe = JFrame("New Account Window")
        self.buildpane("Twisted")

    def changeGWOptions(self, newgateway):
        self.gwoptions.removeAll()
        self.gwoptions.setLayout(GridLayout(len(gateways[newgateway]), 2))
        for item in gateways[newgateway]:
            self.gwoptions.add(JLabel(item[0]))
            self.gwoptions.add(item[1])
    
    def buildpane(self, gateway):
        gw = JPanel(GridLayout(1, 2), doublebuffered)
        gw.add(JLabel("Gateway"))
        self.gwlist = actionWidget(JComboBox(gateways.keys()), self.changegw)
        self.gwlist.setSelectedItem(gateway)
        gw.add(self.gwlist)

        stdoptions = JPanel(GridLayout(2, 2), doublebuffered)
        stdoptions.setBorder(TitledBorder("Standard Options"))
        stdoptions.add(JLabel())
        stdoptions.add(self.autologin)
        stdoptions.add(JLabel("Account Name"))
        stdoptions.add(self.acctname)

        buttons = JPanel(FlowLayout(), doublebuffered)
        buttons.add(actionWidget(JButton("OK"), self.addaccount))
        buttons.add(actionWidget(JButton("Cancel"), self.cancel))

        mainpane = self.mainframe.getContentPane()
        mainpane.setLayout(BoxLayout(mainpane, BoxLayout.Y_AXIS))
        mainpane.add(gw)
        self.changeGWOptions(gateway)
        mainpane.add(self.gwoptions)
        mainpane.add(stdoptions)
        mainpane.add(buttons)

    def show(self):
        self.mainframe.setLocation(100, 100)
        self.mainframe.pack()
        self.mainframe.show()

    #actionlisteners
    def changegw(self, ae):
        gwselection = self.gwlist.getSelectedItem()
        self.changeGWOptions(gwselection)
        self.mainframe.pack()
        self.mainframe.show()

    def addaccount(self, ae):
        gwselection = self.gwlist.getSelectedItem()
        components = gatedict[gwselection]
        host = components["Host"].getText()
        port = int(components["Port"].getText())
        passwd = components["Password"].getText()
        autologin = self.autologin.isSelected()
        acctname = self.acctname.getText()

        if gwselection == "Twisted":
            name = components["Identity Name"].getText()
            sname = components["Service Name"].getText()
            perspective = components["Perspective Name"].getText()
            self.am.addAccount(PBAccount(acctname, autologin, host, port, name,
                                         passwd,[[stype, sname, perspective]]))
        elif gwselection == "AIM":
            name = components["Screen Name"].getText()
            self.am.addAccount(TOCAccount(acctname, autologin, name, passwd,
                                          host, port))

        elif gwselection == "IRC":
            name = components["Nickname"].getText()
            channels = components["Channels"].getText()
            self.am.addAccount(IRCAccount(acctname, autologin, name,
                                          passwd, channels, host, port))
                
        self.amgui.update()
        print "Added new account"
        self.mainframe.dispose()
     
    def cancel(self, ae):
        print "Cancelling new account creation"
        self.mainframe.dispose()


class UneditableTableModel(DefaultTableModel):
    def isCellEditable(self, x, y):
        return 0

class AccountManagementGUI:
    def __init__(self):
        self.acctmanager = AccountManager()
        self.mainframe = JFrame("Account Manager")
        self.headers = ["Account Name", "Status", "Autologin", "Gateway"]
        self.data = UneditableTableModel([], self.headers)
        self.table = JTable(self.data)
        self.table.setColumnSelectionAllowed(0)   #cannot select columns
        self.table.setSelectionMode(ListSelectionModel.SINGLE_SELECTION)

        self.connectbutton = actionWidget(JButton("Connect"), self.connect)
        self.dconnbutton = actionWidget(JButton("Disconnect"), self.disconnect)
        self.deletebutton = actionWidget(JButton("Delete"), self.deleteAccount)
        self.buildpane()
        self.mainframe.pack()
        self.mainframe.show()
        
    def buildpane(self):
        buttons = JPanel(FlowLayout(), doublebuffered)
        buttons.add(self.connectbutton)
        buttons.add(self.dconnbutton)
        buttons.add(actionWidget(JButton("New"), self.addNewAccount))
        buttons.add(self.deletebutton)
        buttons.add(actionWidget(JButton("Quit"), self.quit))
        
        mainpane = self.mainframe.getContentPane()
        mainpane.setLayout(BoxLayout(mainpane, BoxLayout.Y_AXIS))
        mainpane.add(JScrollPane(self.table))
        mainpane.add(buttons)
        self.update()

    def update(self):
        self.data.setDataVector(self.acctmanager.getSnapShot(), self.headers)
        if self.acctmanager.isEmpty():
            self.deletebutton.setEnabled(0)
            self.connectbutton.setEnabled(0)
            self.dconnbutton.setEnabled(0)
        else:
            self.deletebutton.setEnabled(1)
            if not 1 in self.acctmanager.getConnectionInfo(): #all disconnected
                self.dconnbutton.setEnabled(0)
                self.connectbutton.setEnabled(1)
            elif not 0 in self.acctmanager.getConnectionInfo():  #all connected
                self.dconnbutton.setEnabled(1)
                self.connectbutton.setEnabled(0)
            else:
                self.dconnbutton.setEnabled(1)
                self.connectbutton.setEnabled(1)

    #callable button actions
    def connect(self, ae):
        print "Trying to connect"
        row = self.table.getSelectedRow()
        if row < 0:
            print "Trying to connect to an account but no account selected"
        else:
            acctname = self.data.getValueAt(row, 0)
            self.acctmanager.connect(acctname)
            self.update()

    def disconnect(self, ae):
        print "Trying to disconnect"
        row = self.table.getSelectedRow()
        if row < 0:
            print "Trying to logoff an account but no account was selected."
        else:
            acctname = self.data.getValueAt(row, 0)
            self.acctmanager.disconnect(acctname)
            self.update()
    
    def addNewAccount(self, ae):
        print "Starting new account creation"
        NewAccountGUI(self).show()

    def deleteAccount(self, ae):
        print "Deleting account"
        row = self.table.getSelectedRow()
        if row < 0:
            print "Trying to delete an account but no account selected"
        else:
            acctname = self.data.getValueAt(row, 0)
            self.acctmanager.delAccount(acctname)
            self.update()

    def quit(self, ae):
        self.acctmanager.quit()
        sys.exit()

if __name__ == "__main__":
    n = AccountManagementGUI()
