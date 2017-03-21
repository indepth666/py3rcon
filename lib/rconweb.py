import os, sys, logging, threading, time, re
import json
import urllib
import http.server as server
import socketserver
import lib.rconprotocol
from lib.rconprotocol import Player
import queue as Queue

PORT = 8000


class RconWEB(object):
    Action = {}
    DocRoot = '{}/web'.format( os.getcwd() )

    def __init__(self, rcon, config):
        self.rcon = rcon
        self.logFile = config['logfile']
        self.players = [Player(1, "123-123-123", "test player 1"), Player(2, "223-123-123", "player 2")]

        self.isAsync = False

        self.addActions()

    def addActions(self):
        RconWEB.Action['/action/kickall'] = self.Web_kickAll
        RconWEB.Action['/action/kickplayer'] = self.Web_kickPlayer
        RconWEB.Action['/action/shutdown'] = self.Web_shutdownServer
        RconWEB.Action['/action/restart'] = self.Web_restartServer
        RconWEB.Action['/action/players'] = self.Web_refreshPlayers
        RconWEB.Action['/action/log'] = self.Web_logUpdate

    def OnConnected(self):
        t = threading.Thread(target=self._initHTTP)
        t.daemon = True
        t.start()

        logging.info('OnConnect(): Serving HTTPd on port %s ' % (PORT))
        print('Serving HTTPd on port %s' % (PORT))
    
    def _initHTTP(self):
        self.Web_refreshPlayers()

        httpd = socketserver.TCPServer(("", PORT), Handler)
        httpd.serve_forever()

    def Web_kickAll(self):
        self.rcon.kickAll()
        return json.dumps(True)

    def Web_kickPlayer(self, **args):
        if 'ban' in args:
            self.rcon.sendCommand('ban {}'.format(args['id'][0]))
        else:
            self.rcon.sendCommand('kick {}'.format(args['id'][0]))

        return json.dumps(True)

    def Web_logUpdate(self):
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

        return json.dumps(lines)

    def Web_shutdownServer(self):
        self.rcon.sendCommand('#shutdown')
        return json.dumps(True)

    def Web_restartServer(self):
        self.rcon.sendCommand('#restartserver')
        return json.dumps(True)

    def Web_refreshPlayers(self):
        self.isAsync = True
        self.rcon.sendCommand('players')
        
        timeout = time.time() + 15

        while time.time() < timeout:
            if not self.isAsync: break
            time.sleep(1)

        result = "["
        for x in self.players:
            result += x.toJSON() + ","
        if len(self.players) > 0:
            result = result[:-1]
        result += "]"

        return result

    """
    Event: is called whenever the players command is send
    """
    def OnPlayers(self, playerList):
        self.players = playerList
        self.isAsync = False
    """
    Event: when no players are available
    """
    def OnNoPlayers(self):
        self.players = []
        self.isAsync = False

class Handler(server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in RconWEB.Action.keys():
            self.do_JSON( RconWEB.Action[self.path] )
            return

        os.chdir(RconWEB.DocRoot)
        server.SimpleHTTPRequestHandler.do_GET(self)
        os.chdir('../')

    def do_POST(self):
        if self.path in RconWEB.Action.keys():
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            content_len = int(self.headers['content-length'])
            post_body = self.rfile.read(content_len).decode('utf-8')
            parsed = urllib.parse.parse_qs(post_body)
            call = RconWEB.Action[self.path]
            result = str.encode( call(**parsed))
            self.wfile.write( result )


    def do_JSON(self, call):
        self.send_response(200)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        result = call()

        self.wfile.write(str.encode(result))