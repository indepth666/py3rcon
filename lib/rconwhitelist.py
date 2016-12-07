import sys, os, sched, logging, threading, time, json
import lib.rconprotocol
from lib.rconprotocol import Player

class RconWhitelist(object):

    Interval = 30 # interval how often the whitelist.json should be saved (default: every 30 seconds)

    def __init__(self, rcon, configFile, GUI=False):
        self.configFile = configFile
        self.rcon = rcon
        self.whitelist = []
        self.changed = False
        self.modified = None
        self.GUI = GUI

        if not(os.path.isfile(self.configFile)):
            open(self.configFile, 'a').close()

        logging.info("[WHITELIST] Loading whitelist...")
        self.loadConfig()

        if self.GUI: return

        # thread to save whitelist.json every X 
        self.saveConfigAsync()

        # thread to watch for file changes
        t = threading.Thread(target=self.watchConfig)
        t.daemon = True
        t.start()
         
    """
    public: (Re)Load the commands configuration file
    """
    def loadConfig(self):
        with open(self.configFile) as json_config:
            try:
                config = json.load(json_config)
            except ValueError:
                config = []

        self.whitelist = []
        for x in config:
            self.whitelist.append( Player.fromJSON(x) )
        
        self.modified = os.path.getmtime(self.configFile)
    
    def watchConfig(self):
        if not(os.path.isfile(self.configFile)): return
        time.sleep(10)

        mtime = os.path.getmtime(self.configFile)
        if self.modified != mtime:
            self.loadConfig()
            self.fetchPlayers()

        self.watchConfig()

    def saveConfigAsync(self):
        t = threading.Thread(target=self.saveConfig)
        t.daemon = True
        t.start()

    def saveConfig(self):
        if self.changed or self.GUI:
            with open(self.configFile, 'w') as outfile:
                json.dump([ob.__dict__ for ob in self.whitelist], outfile, indent=4, sort_keys=True)
        
        if self.GUI: return

        self.changed = False
        time.sleep(self.Interval)
        self.saveConfig()

    def fetchPlayers(self):
        self.rcon.sendCommand('players')

    def checkPlayer(self, player):
        if player.allowed:
            logging.info('[WHITELIST] Player %s with ID %s IS WHITELISTED' % (player.name, player.guid))
            return

        logging.info('[WHITELIST] Player %s IS NOT WHITELISTED - Kick in progress' % (player.name))
        self.rcon.sendCommand('kick {}'.format(player.number))

    def OnPlayers(self, playerList):
        for x in playerList:
            found = [a for a in self.whitelist if a.guid == x.guid]
            if len(found) <= 0: break

            self.checkPlayer(found[0])

    def OnPlayerConnect(self, player):
        found = [x for x in self.whitelist if x.guid == player.guid]

        # add the connecting player into the whitelist
        if len(found) <= 0:
            self.whitelist.append(player)
            self.changed = True
            found.append( player )

        self.checkPlayer(found[0])
    