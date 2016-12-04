import os, sys, logging, threading, time, curses
from curses import panel
from curses import textpad

class RconGUI(object):
    def __init__(self, rcon, config):
        self.rcon = rcon
        self.logFile = None
        self.logThread = None
        self.cancelCommand = False

        self.setLogfile(config['logfile'])

        self.navigation = {
            'menu': self.showMenu,
            'playermenu': self.showPlayerMenu,
            'player': self.showPlayers,
            'missionmenu': self.showMissionMenu,
            'command': self.showCommandLine
        }
        self.mainmenu = [
            ('Refresh Players', self.fetchPlayers),
            ('Manage Whitelist', self.manageWhitelist),
            ('Restart Mission...', self.fetchMissions),
            ('Kick All', self.rcon.kickAll),
            ('Shutdown Server', self.shutdownServer),
            ('Restart Server (v1.65)', self.restartServer),
            ('Exit', None)
        ]

        self.playermenu = []
        self.missionmenu = []
        self.backMenu = [('Main Menu', self.getMainMenu)]

        self.__navigation = self.getMainMenu()
        self.__prevnav = None
        # menu cursor position
        self.position = 0
        # is whitelist
        self.isWhitelist = False
        # player cursor position
        self.playerpos = 0
        self.players = []

        self.posAndSize = {
            # height, width, ypos, xpos
            'menu':     [27, 30, 1, 1],
            'log':      [8, 131, 31, 1],
            'cmd':      [3, 131, 28, 1],
            'cmdTextbox':[1, 120, 29, 3],
            'player':   [27, 100, 1, 32]
        }

        try:
            self.screen = curses.initscr()

            if not self.checkMaxSize():
                curses.endwin()
                print('THE TERMINAL WINDOW IS TO SMALL (width/height)')
                return

            self.initColors()

            curses.cbreak()
            curses.noecho()
            curses.curs_set(0)
           
            self.menuWnd = self.screen.subwin(*self.posAndSize['menu'])
            self.menuWnd.keypad(1)

            self.logWnd = self.screen.subwin(*self.posAndSize['log'])

            self.cmdWnd = self.screen.subwin(*self.posAndSize['cmd'])
            self.cmdTextbox = self.screen.subwin(*self.posAndSize['cmdTextbox'])

            self.playerWnd = self.screen.subwin(*self.posAndSize['player'])

        except:
            curses.endwin()
            raise

    def getMainMenu(self):
        return 'menu'

    def setLogfile(self, filename):
        self.logFile = filename
        if not self.logThread:
            self.logThread = threading.Thread(target=self.updateLog)
            self.logThread.daemon = True
            self.logThread.start()

    def initColors(self):
        curses.start_color()
        # pair one is used for menu selection
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
        # pair for command line
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)

    def OnPlayers(self, playerList):
        self.players = playerList
        self.isWhitelist = False
        self.showPlayers()

    def OnMissions(self, missionList):
        self.missionmenu = missionList
        self.missionmenu.append("Back")
        self.showMissionMenu()
        
    def OnAbort(self):
        logging.debug("Quit GUI")
        curses.endwin()

    def shutdownServer(self):
        self.rcon.sendCommand('#shutdown')

    def restartServer(self):
        self.rcon.sendCommand('#restartserver')

    def restartMission(self):
        m = self.missionmenu[self.position]
        if m != 'Back':
            self.rcon.sendCommand('#mission %s' % m)
        return self.getMainMenu()

    def kickPlayer(self):
        player = self.players[self.playerpos]
        logging.debug("Kicking player '%s'" % player.name)

        self.rcon.sendCommand('kick %s' % player.number)
        return self.getMainMenu()

    def fetchPlayers(self):
        self.isWhitelist = False
        self.players = []
        self.showPlayers()
        self.rcon.sendCommand('players')

    def fetchMissions(self):
        self.rcon.sendCommand('missions')

    def manageWhitelist(self):
        clsWhitelist = self.rcon.loadmodule('rconwhitelist', 'RconWhitelist')
        self.players = clsWhitelist.whitelist
        self.isWhitelist = True
        self.showPlayers()
    
    def removePlayerWhitelist(self):
        player = self.players[self.playerpos]
        player.allowed = False

        clsWhitelist = self.rcon.loadmodule('rconwhitelist', 'RconWhitelist')
        clsWhitelist.saveConfigAsync()

        logging.info('Player removed from WHITELIST')
        self.showPlayers()
        return 'playermenu'

    def addPlayerWhitelist(self):
        player = self.players[self.playerpos]
        player.allowed = True

        clsWhitelist = self.rcon.loadmodule('rconwhitelist', 'RconWhitelist')
        clsWhitelist.saveConfigAsync()

        logging.info('Player removed from WHITELIST')
        self.showPlayers()
        return 'playermenu'

    def OnConnected(self):
        try:
            t = threading.Thread(target=self._menuThread)
            t.daemon = True
            t.start()
        except:
            logging.error(sys.exc_info())

    def _menuThread(self):
        try:
            self.fetchPlayers()
            self.display()
        except:
            logging.error(sys.exc_info())

        self.rcon.Abort()

    def checkMaxSize(self):
        _res = True
        my = self.screen.getmaxyx()[0]
        mx = self.screen.getmaxyx()[1]

        overlap = list(filter(lambda v: v[0] + v[2] > my, self.posAndSize.values()))
        if len(overlap) > 0:
            _res = False

        overlap = list(filter(lambda v: v[1] + v[3] > mx, self.posAndSize.values()))
        if len(overlap) > 0:
            _res = False

        return _res

    """
    Switch between player and menu navigation
    """
    def switchNavigation(self):
        if not (self.__prevnav is None) and self.__prevnav != self.__navigation:
            self.navigation[self.__prevnav]()

        self.navigation[self.__navigation]()
        self.__prevnav = self.__navigation

        res = ''
        # clean up the menu window because other menus might have less info than the other
        if self.__navigation == 'menu' or self.__navigation == 'playermenu' or self.__navigation == 'missionmenu':
            res = self.inputMenu()
        elif self.__navigation == 'player':
            res = self.inputMenu()
        elif self.__navigation == 'command':
            res = self.inputCommand()

        self.__navigation = res

    def navigate(self, n):
        if self.__navigation == 'menu' or self.__navigation == 'playermenu' or self.__navigation == 'missionmenu':
            _length = len(self.mainmenu)
            if self.__navigation == 'playermenu':
                _length = len(self.playermenu)
            elif self.__navigation == 'missionmenu':
                _length = len(self.missionmenu)

            if (self.position + n) < 0:
                self.position = 0
            elif (self.position + n) >= _length:
                self.position = _length - 1
            else:
                self.position += n
        elif self.__navigation == 'player':
            if (self.playerpos + n) < 0:
                self.playerpos = 0
            elif (self.playerpos + n) >= len(self.players):
                self.playerpos = len(self.players) - 1
            else:
                self.playerpos += n
    
    """
    Thread to update the log file using N last lines (calculated)
    """
    def updateLog(self):
        time.sleep(2)

        if self.rcon.isExit:
            return

        if not hasattr(self, 'logWnd'):
            return

        self.logWnd.clear()
        self.logWnd.border("|", "|", "-", "-", "#", "#", "#", "#")

        maxW = self.posAndSize['log'][1] - self.posAndSize['log'][3] - 2
        maxH = self.posAndSize['log'][0] - 1

        fp = open(self.logFile)
        fp.seek(0, 2)
        file_size = fp.tell()
        
        offset = file_size - 500
        if offset < 0:
            offset = 0

        fp.seek(offset, 0)

        lines = []
        for chunk in iter(lambda: fp.readline(), ''):
            lines.append( chunk )
        
        lines = lines[maxH * -1:]

        i = 1
        while(i < maxH and len(lines)):
            curLine = lines.pop()
            maxH - i

            if len(curLine) >= maxW:
                self.logWnd.addstr(maxH - i, 2, curLine[maxW:].rstrip())
                i += 1
                curLine = curLine[:maxW]
                if i >= maxH:
                    break

            self.logWnd.addstr(maxH - i, 2, curLine.rstrip())
            i += 1

        self.logWnd.refresh()
        self.updateLog()

    """
    Display the main menu
    """
    def showMenu(self):
        self.menuWnd.clear()
        self.menuWnd.border("|", "|", "-", "-", "#", "#", "#", "#")

        for index, item in enumerate(self.mainmenu):
            mode = curses.A_NORMAL
            if index == self.position and self.__navigation == 'menu':
                mode = curses.color_pair(1)
            msg = ' %s' % item[0]
            self.menuWnd.addstr(1+index, 1, msg, mode)

        self.menuWnd.refresh()

    def showMissionMenu(self):
        self.menuWnd.clear()
        self.menuWnd.border("|", "|", "-", "-", "#", "#", "#", "#")

        for index, item in enumerate(self.missionmenu):
            mode = curses.A_NORMAL
            if index == self.position and self.__navigation == 'missionmenu':
                mode = curses.color_pair(1)
            self.menuWnd.addstr(1+index, 1, item, mode)

        self.menuWnd.refresh()

    """
    Display the player menu, when player is selected
    """
    def showPlayerMenu(self):
        self.menuWnd.clear()
        self.menuWnd.border("|", "|", "-", "-", "#", "#", "#", "#")

        self.playermenu = list(self.backMenu)

        if len(self.players) > 0:
            player = self.players[self.playerpos]
            self.playermenu.append( ('Kick %s' % player.name, self.kickPlayer) )
            if player.allowed:
                self.playermenu.append( ('Remove from Whitelist', self.removePlayerWhitelist) )
            else:
                self.playermenu.append( ('Add To Whitelist', self.addPlayerWhitelist) )
            

        for index, item in enumerate(self.playermenu):
            mode = curses.A_NORMAL
            if index == self.position and self.__navigation == 'playermenu':
                mode = curses.color_pair(1)
            msg = ' %s' % item[0]
            self.menuWnd.addstr(1+index, 1, msg, mode)

        self.menuWnd.refresh()

    """
    Display the list of all players available on the server
    """
    def showPlayers(self):
        self.playerWnd.clear()
        self.playerWnd.border("|", "|", "-", "-", "#", "#", "#", "#")
        _row = 0
        _col = 0
        for index,player in enumerate(self.players):
            if not _row == 0 and _row%25 == 0:
                _col += 1
                _row = 0

            _offsetX = _col * 24 + 2
            _m = curses.A_NORMAL

            if index == self.playerpos and self.__navigation == 'player':
                _m = curses.color_pair(1)
            
            if self.isWhitelist:
                allowed = '[Y]' if player.allowed else '[N]'
                self.playerWnd.addstr(1 + _row , _offsetX, "%s %s" % (allowed, player.name), _m)
            else:
                self.playerWnd.addstr(1 + _row , _offsetX, "%s #%d" % (player.name, index), _m)
            _row += 1
        self.playerWnd.refresh()

    """
    Display the command bar
    """
    def showCommandLine(self):
        self.cmdWnd.clear()
        self.cmdWnd.border("|", "|", "-", "-", "#", "#", "#", "#")
        
        _color = curses.A_NORMAL
        if self.__navigation == 'command':
            _color = curses.color_pair(1)

        self.cmdWnd.addstr(0, 2, "  Enter command ", _color)
        self.cmdWnd.refresh()
        
    def cmdValidate(self, ch):
        if ch == 9:
            self.cancelCommand = True
            ch = curses.ascii.BEL
        return ch

    """
    Command input when focused
    """
    def inputCommand(self):
        self.cmdTextbox.move(0,0)

        tb = textpad.Textbox(self.cmdTextbox)
        text = tb.edit(self.cmdValidate)

        if not self.cancelCommand:
            self.rcon.sendCommand(text.strip())

        self.cancelCommand = False

        return self.getMainMenu()

    """
    Keyboard input for the menu, when focused
    """
    def inputMenu(self):
        _result = self.__navigation

        key = self.menuWnd.getch()

        if key in [curses.KEY_ENTER, ord('\n')]:
            time.sleep(0.5)
            if self.__navigation == 'menu':
                if self.position == len(self.mainmenu)-1:
                    _result = ''
                    return
                elif self.position == 2:
                    self.mainmenu[self.position][1]()
                    _result = 'missionmenu'
                else:
                    self.mainmenu[self.position][1]()
            elif self.__navigation == 'playermenu':
                _result = self.playermenu[self.position][1]()
            elif self.__navigation == 'player':
                self.position = 0
                _result = 'playermenu'
            elif self.__navigation == 'missionmenu':
                _result = self.restartMission()
                self.position = 0

        elif key == curses.KEY_UP:
            self.navigate( -1 )
        elif key == curses.KEY_DOWN:
            self.navigate(1)
        elif key == curses.KEY_RIGHT:
            self.navigate(25)
        elif key == curses.KEY_LEFT:
            self.navigate(-25)

        elif key == 9:
            if self.__navigation == 'menu':
                _result = 'player'
            elif self.__navigation == 'player':
                _result = 'command'
            else:
                _result = self.getMainMenu()

        return _result

    def display(self):
        try:
            for k, v in self.navigation.items():
                if k != self.__navigation:
                    v()

            while self.__navigation:
                self.switchNavigation()

        except (KeyboardInterrupt, SystemExit):
            logging.error(sys.exc_info())
        except:
            logging.error(sys.exc_info())
