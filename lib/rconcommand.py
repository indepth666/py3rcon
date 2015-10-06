import os
import lib.rconprotocol
import logging
import threading
import time
import re
import json

"""
RconCommand class used to read admin commands sent through normal chat messages.
Check out the commands.json for a command list available for admins
"""
class RconCommand(object):
    def __init__(self, rcon):
        self.configFile = None
        self.adminList = []
        self.cmdList = []
        self.players = []

        self.rcon = rcon

        logging.debug('%s: initialized' % type(self).__name__)

    """
    public: Set the destinaiton path of the commands configuration file
    @param string configFile - absolute path of the configuration file
    """

    def setConfig(self, configFile):
        self.configFile = configFile

    """
    public: (Re)Load the commands configuration file
    """

    def loadConfig(self):
        if self.configFile is None:
            logging.error('%s: No command config specified' % (type(self).__name__))
            return False

        if not os.path.isfile(self.configFile):
            logging.error('%s: Command list file "%s" not found' % (type(self).__name__, self.configFile))
            return False

        with open(self.configFile) as json_config:
            config = json.load(json_config)

        self.setAdmins(config['admins'])
        self.setCommands(config['commands'])
        return True

    """
    public: set a list of battleye GUID to make them admin
    This method is usually called by loadConfig
    """
    def setAdmins(self, playerUids):
        self.adminList = playerUids

    """
    public: set a list of command available for admins
    This method is usually called by loadConfig
    """
    def setCommands(self, commandList):
        self.cmdList = []
        if len(commandList) > 0:
            for c in commandList:
                self.cmdList.append( RconCommandItem( c[0], c[1] ) )

    """
            Event: Called by Rcon.OnConnected()
            Used to load the configuration being set by setConfig(<file>)
            """
    def OnConnected(self):
        if self.loadConfig():
            logging.info('OnConnect(): %s configured (%d commands %d admins)' % (type(self).__name__, len(self.cmdList), len(self.adminList)))
        else:
            logging.info('OnConnect(): %s disabled' % type(self).__name__)

    """
            Event: Called by Rcon.OnPlayerConnect(Player)
            Used manage adminstrator when they login (plus a info message)
            """
    def OnPlayerConnect(self, player):
        # do some action when player connects
        logging.debug('OnPlayerConnect(): %s - Player: %s' % ( type(self).__name__, player.name))

        if player.guid in self.adminList:
            self.rcon.sendChat("Admin '%s' connected" % player.name)

        self.players.append(player)

    def OnPlayerDisconnect(self, player):
        # do some action when player disconnects
        logging.debug('OnPlayerDisconnect(): %s - Player: %s' % (type(self).__name__, player.name))

        found = list(filter(lambda x: x.number == player.number, self.players))
        if(len(found) > 0):
            self.players.remove(found[0])

    """
            Event: Called by Rcon.OnChat(ChatMessage)
            Used to validate and Execute the admin commands
            """
    def OnChat(self, obj):
        # do some action when player sends a chat message
        logging.info("RconCommand: %s - %s" % (obj.channel, obj.message))
        try:
            found = list(filter(lambda x: x.name == obj.sender, self.players))
            if (len(found) > 0) and found[0].guid in self.adminList:
                for c in self.cmdList:
                    logging.info(c)
                if c.Match(obj.message):
                    c.Execute(self.rcon)
        except:
            logging.warning("Error in message: %s" % obj.message)
            logging.exception("Stack Trace:")


class RconCommandItem():

    def __init__(self, regMatch, command):
        self.regMatch = regMatch
        self.command = command

    def Match(self, message):
        m = re.match(re.escape(self.regMatch), message )
        return m

    def Execute(self, rcon):
        param = self.command.split(':')
        # run a usual server side command
        if len(param) <= 1:
            rcon.sendCommand(self.command)
        # run commands from core Rcon class
        elif len(param) <= 2:
            getattr(rcon, param[1])()
        elif len(param) >= 3:
            clsObj = rcon.loadmodule( param[0], param[1] )
            getattr(clsObj, param[2])()
        else:
            logging.warning("Command '%s' matching '%s' is misconfigured (length: %d)" % (self.command, self.regMatch, len(param)))
