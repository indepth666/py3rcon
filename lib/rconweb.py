import os, sys, logging, threading, time, re
import json
import urllib
import http.server as server
import socketserver
import lib.rconprotocol
from lib.rconprotocol import Player

PORT = 8000


class RconWEB(object):
    Action = {}
    DocRoot = '{}/web'.format( os.getcwd() )

    def __init__(self, rcon, config):
        self.rcon = rcon
        self.logFile = None
        self.players = [Player(1, "123-123-123", "test player 1"), Player(2, "223-123-123", "player 2")]

        self.addActions()

    def addActions(self):
        RconWEB.Action['/action/kickall'] = self.Web_kickAll
        RconWEB.Action['/action/kickplayer'] = self.Web_kickPlayer
        RconWEB.Action['/action/players'] = self.Web_refreshPlayers
        RconWEB.Action['/action/getplayers'] = self.Web_getPlayers

    def OnConnected(self):
        #self.Web_refreshPlayers()

        httpd = socketserver.TCPServer(("", PORT), Handler)
        print("serving at port %s" % (PORT))
        
        httpd.serve_forever()

    def Web_kickAll(self):
        self.rcon.kickAll()
        return json.dumps(True)

    def Web_kickPlayer(self, **args):
        self.rcon.sendCommand('kick %s' % (args['id'][0]))
        return json.dumps(True)

    def Web_refreshPlayers(self):
        self.rcon.sendCommand('players')
        return json.dumps(True)

    def Web_getPlayers(self):
        result = "["
        for x in self.players:
            result += x.toJSON() + ","
        result = result[:-1]
        result += "]"
        
        return result
        

    """
    Event: is called whenever the players command is send
    """
    def OnPlayers(self, playerList):
        self.players = playerList
        


class Handler(server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in RconWEB.Action.keys():
            self.do_JSON( RconWEB.Action[self.path] )
            return

        os.chdir(RconWEB.DocRoot)
        server.SimpleHTTPRequestHandler.do_GET(self)

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