import os
import rconprotocol
import logging
import threading
import time
import re
import json

class RconCommandItem():
    
    def __init__(self, regMatch, mode, command):
	self.regMatch = regMatch
	self.mode = mode.lower()
	self.command = command
        self.__parsed = False

    def Match(self, message):
	m = re.match("^" + re.escape(self.regMatch), message )

	if m: self.__parse(m.groups)

	return m

    def __parse(self, groups):
	if self.__parsed: return
	
	self.command = self.command % tuple(groups)
	self.__parsed = True

    def Command(self):
	return self.command

    def Mode(self):
	return self.mode
    

class RconCommand():

    def __init__(self, rcon):
	self.configFile = None
        self.adminList = []
	self.cmdList = []

	self.rcon = rcon

	logging.debug('%s: initialized' % self.__class__)

    def setConfig(self, configFile):
	self.configFile = configFile
    
    def loadConfig(self):
	if self.configFile is None:
	    logging.error('%s: No command config specified' % (self.__class__))
	    return False

	if not os.path.isfile(self.configFile):
	    logging.error('%s: Command list file "%s" not found' % (self.__class__, self.configFile))
	    return False

	with open(self.configFile) as json_config: 
	    config = json.load(json_config)
	
	self.setAdmins(config['admins'])
	self.setCommands(config['commands'])
	return True
	
    def setAdmins(self, playerUids):
	self.adminList = playerUids

    def setCommands(self, commandList):
	self.cmdList = []
	if len(commandList) > 0:
	    for c in commandList:
		self.cmdList.append( RconCommandItem( c[0], c[1], c[2] ) )

    def OnConnected(self):
	if self.loadConfig():
	    logging.info('OnConnect(): %s configured (%d commands %d admins)' % (self.__class__, len(self.cmdList), len(self.adminList)))
	else:
	    logging.info('OnConnect(): %s disabled' % self.__class__)

    def OnPlayerConnect(self):
	# do some action when player connects
	logging.debug('OnPlayerConnect(): %s' % self.__class__)

    def OnPlayerDisconnect(self):
	# do some action when player disconnects
	logging.debug('OnPlayerDisconnect(): %s' % self.__class__)

    def OnChat(self, message):
	# do some action when player sends a chat message
	for c in cmdList:
	    if c.Match(message):
		if c.Mode() == 'int':
		    eval(c.Command())
		else:
		    rconprotocol.sendCommand( c.Command() )
