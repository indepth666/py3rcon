import rconprotocol
import sched
import logging
import threading
import time

class RconMessage():

    def __init__(self, rcon):
        # chat messages
        self.msgList = None
        self.msgInterval = 0
        self.msgIndex = 0

	self.rcon = rcon

	logging.debug('%s() initialized' % self.__class__)

    def setInterval(self, min):
	self.msgInterval = min * 60

    def setMessages(self, messageList):
	self.msgList = messageList

    def OnConnected(self):
	if not (self.msgList is None) and self.msgInterval > 0:
    	    # a separate thread to handle the restart and restart messages
    	    # It is set as daemon to be able to stop it using SystemExit or Ctrl + C
    	    t = threading.Thread(target=self._chatMessageLoop)
	    t.daemon = True
	    t.start()
	    logging.info('OnConnect(): %s ready to send messages every %d seconds' % (self.__class__, self.msgInterval))
	else:
	    logging.info('OnConnect(): %s disabled' % self.__class__)

    def _chatMessageLoop(self):
        _l = len(self.msgList)
        _index = self.msgIndex
        if _l > 0 and not self.msgList[_index] == None:
            self.rcon.sendChat(self.msgList[_index])

        if (_index + 1) >= _l:
            self.msgIndex = 0
        else:
            self.msgIndex += 1

	if not self.rcon.IsAborted():
	    time.sleep(self.msgInterval)
	    self._chatMessageLoop()