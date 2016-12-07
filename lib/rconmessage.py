import lib.rconprotocol
import sched
import logging
import threading
import time

"""
RconMessage class used to repeatedly sent server info messages
"""
class RconMessage(object):
    def __init__(self, rcon, config):
        # chat messages
        self.msgList = None
        self.msgInterval = 0
        self.msgIndex = 0

        self.rcon = rcon

        self.setInterval(config['interval'] )
        self.setMessages(config['messages'] )

        logging.debug('%s() initialized' % type(self).__name__)

    """
    public: set the interval in minutes on how often a message should appear
    @parama integer min - minute
    """
    def setInterval(self, min):
        self.msgInterval = min * 60

    """
    public: set the messages to be send every interval - check out the setInterval(<min>) method
    @param List messageList - list of messages as string
    """
    def setMessages(self, messageList):
        self.msgList = messageList

    """
    Event: Called by Rcon.OnConnected() when connection is established and authenticated
    Used to initialize the chat thread
    """
    def OnConnected(self):
        if not (self.msgList is None) and self.msgInterval > 0:
            # a separate thread to handle the restart and restart messages
            # It is set as daemon to be able to stop it using SystemExit or Ctrl + C
            t = threading.Thread(target=self._chatMessageLoop)
            t.daemon = True
            t.start()
            logging.info('OnConnect(): %s ready to send messages every %d seconds' % (type(self).__name__, self.msgInterval))
        else:
            logging.info('OnConnect(): %s disabled' % type(self).__name__)

    """
    private: The actual message chat loop.
    This thread will send the chat message to everyone and sleeps for interval configured by setInterval(<min>) method
    """
    def _chatMessageLoop(self):
        time.sleep(self.msgInterval)

        _l = len(self.msgList)
        _index = self.msgIndex
        if _l > 0 and not self.msgList[_index] == None:
            self.rcon.sendChat(self.msgList[_index])

        if (_index + 1) >= _l:
            self.msgIndex = 0
        else:
            self.msgIndex += 1

        if not self.rcon.isExit:           
            self._chatMessageLoop()
