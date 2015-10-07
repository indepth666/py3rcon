import os
import sys
import curses
from curses import panel
import lib.rconprotocol
import logging
import threading
import time

class RconGUI(object):
    def __init__(self, rcon):
        self.rcon = rcon
        self.logFile = None
        self.logThread = None

        self.mainmenu = [
            ('Send Hello', self.sayHello),
            ('Kick All', self.rcon.kickAll),
            ('Shutdown (immediately)', self.shutdownServer),
            ('Exit','exit')
        ]

        self.backMenu = [('Main Menu', self.switchNavigation)]
        self.playermenu = []

        self.__navigation = 'menu'
        # menu cursor position
        self.position = 0
        # player cursor position
        self.playerpos = 0
        self.players = []

        self.posAndSize = {
            # height, width, ypos, xpos
            'menu':     [27, 30, 1, 1],
            'log':      [8, 131, 33, 1],
            'cmdlabel': [3, 131, 28, 1],
            'cmd':      [3, 131, 30, 1],
            'player':   [27, 100, 1, 32]
        }

        self.cmdText = ""

        try:
            self.screen = curses.initscr()
            if self.checkMaxSize():
                self.menuWnd = self.screen.subwin(*self.posAndSize['menu'])
                self.menuWnd.keypad(1)

                self.logWnd = self.screen.subwin(*self.posAndSize['log'])

                self.titleWnd = self.screen.subwin(*self.posAndSize['cmdlabel'])
                self.cmdWnd = self.screen.subwin(*self.posAndSize['cmd'])

                self.playerWnd = self.screen.subwin(*self.posAndSize['player'])

            else:
                curses.endwin()

        except:
            curses.endwin()
            raise

    def setLogfile(self, filename):
        self.logFile = filename
        if not self.logThread:
            self.logThread = threading.Thread(target=self.updateLog)
            self.logThread.daemon = True
            self.logThread.start()


    def OnPlayers(self, playerList):
        self.players = playerList

    def OnAbort(self):
	    logging.debug("Quit GUI")
	    self.exitCurses()

    def shutdownServer(self):
        self.rcon.sendCommand('#shutdown')

    def kickPlayer(self):
        logging.debug("Kicking player")

    def fetchPlayers(self):
        self.rcon.sendCommand('players')

    def sayHello(self):
        self.rcon.sendChat("Hello World!")

    def callCommand(self):
        self.rcon.sendCommand(self.cmdText)
        self.cmdText = ""
        self.titleWnd.addstr(1, 80, "Command executed", curses.A_REVERSE)
        self.cmdWnd.clear()

    def OnConnected(self):
        try:
            t = threading.Thread(target=self._menuThread)
            t.daemon = True
            t.start()

            time.sleep(3)
            self.fetchPlayers()
        except:
            logging.error(sys.exc_info())

    def _menuThread(self):
        try:
            self.display()
        except:
            logging.error(sys.exc_info())

        self.rcon.Abort()

    def exitCurses(self):
        curses.nocbreak(); self.screen.keypad(0); curses.echo();
        curses.endwin()

    def checkMaxSize(self):
        _res = True
        my = self.screen.getmaxyx()[0]
        mx = self.screen.getmaxyx()[1]

        overlap = list(filter(lambda v: v[0] + v[2] > my, self.posAndSize.values()))
        if len(overlap) > 0:
            _res = False
            print('--- TERMINAL WINDOW HEIGHT TOO SMALL ---')

        overlap = list(filter(lambda v: v[1] + v[3] > mx, self.posAndSize.values()))
        if len(overlap) > 0:
            _res = False
            print('--- TERMINAL WINDOW WEIGHT TOO SMALL ---')

        return _res

    """
    Switch between player and menu navigation
    """
    def switchNavigation(self, toNav = 'menu'):
        self.position = 0
        self.__navigation = toNav

        # clean up the menu window because other menus might have less info than the other
        if self.__navigation == 'menu' or self.__navigation == 'playermenu':
            self.menuWnd.clear()
        elif self.__navigation == 'player':
            self.playerWnd.clear()

        logging.debug("Switching to %s Position %d" % (self.__navigation, self.position))

    def getPlayerMenu(self):
        playerObj = self.players[self.playerpos]
        self.playermenu = [("Kick %s" % playerObj.name, self.kickPlayer) ] + self.backMenu
        return self.playermenu

    def navigate(self, n):
        if self.__navigation == 'menu' or self.__navigation == 'playermenu':
            _items = self.mainmenu
            if self.__navigation == 'playermenu':
                _items = self.playermenu
            self.position += n
            if self.position < 0:
                self.position = 0
            elif self.position >= len(_items):
                self.position = len(_items) - 1
        elif self.__navigation == 'player':
            if (self.playerpos + n) < 0:
                self.playerpos = 0
            elif (self.playerpos + n) >= len(self.players):
                self.playerpos = len(self.players) - 1
            else:
                self.playerpos += n


    def updateLog(self):
        time.sleep(2)

        if self.rcon.IsAborted():
            return

        self.logWnd.clear()
        self.logWnd.border("|", "|", "-", "-", "#", "#", "#", "#")

        maxW = self.posAndSize['log'][1] - self.posAndSize['log'][3] - 1
        maxH = self.posAndSize['log'][0] - 1

        lastlines = os.popen("tail -n %d %s" % (maxH, self.logFile)).read()
        lines = lastlines.splitlines()

        i = 1
        while(i < maxH and len(lines)):
            curLine = lines.pop()
            maxH - i

            if len(curLine) > maxW:
                self.logWnd.addstr(maxH - i, 1, curLine[maxW:])
                i += 1
                curLine = curLine[:maxW]
                if i >= maxH:
                    break

            self.logWnd.addstr(maxH - i, 1, curLine)
            i += 1

        self.logWnd.refresh()
        self.updateLog()

    def updateMenu(self, items):
        self.menuWnd.clear()
        self.menuWnd.border("|", "|", "-", "-", "#", "#", "#", "#")

        for index, item in enumerate(items):
            mode = curses.A_NORMAL
            if index == self.position and (self.__navigation == 'menu' or self.__navigation == 'playermenu'):
                mode = curses.A_REVERSE
            msg = ' %s' % item[0]
            self.menuWnd.addstr(1+index, 1, msg, mode)

        self.menuWnd.refresh()

    def updatePlayer(self):
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
                _m = curses.A_REVERSE
            self.playerWnd.addstr(1 + _row , _offsetX, "%s #%d" % (player.name, index), _m)
            _row += 1
        self.playerWnd.refresh()

    def updateCommandLine(self):
        self.titleWnd.addstr(1, 2, "Type any valid server command below", curses.A_NORMAL)
        self.cmdWnd.border("|", "|", "-", "-", "#", "#", "#", "#")
        self.cmdWnd.addstr(1, 2, self.cmdText, curses.A_REVERSE)
        self.cmdWnd.refresh()
        self.titleWnd.refresh()

    def display(self):
        try:
            while True:
                curses.curs_set(0)
                self.updateCommandLine()
                self.updatePlayer()

                if self.__navigation == 'playermenu':
                    self.updateMenu( self.getPlayerMenu() )
                else:
                    self.updateMenu(self.mainmenu)

                key = self.menuWnd.getch()

                if key in [curses.KEY_ENTER, ord('\n')]:
                    if len(self.cmdText) > 0:
                        self.callCommand()
                    elif self.__navigation == 'menu':
                        if self.position == len(self.mainmenu)-1:
                            break
                        else:
                            self.mainmenu[self.position][1]()
                    elif self.__navigation == 'playermenu':
                        self.playermenu[self.position][1]()
                    elif self.__navigation == 'player':
                        self.switchNavigation('playermenu')
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
                        self.switchNavigation('player')
                    else:
                        self.switchNavigation('menu')
                elif key > 32 and key < 126:
                    self.position = -1
                    self.cmdText += chr(key)
                elif key == curses.KEY_BACKSPACE:
                    self.cmdText = self.cmdText[:-1]
                    self.cmdWnd.clear()

        except (KeyboardInterrupt, SystemExit):
            logging.error(sys.exc_info())
        except:
            logging.error(sys.exc_info())
