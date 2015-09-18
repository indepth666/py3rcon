#!/usr/bin/python

import os, signal, sys, argparse, threading, rconprotocol

def signal_term_handler(signal, frame):
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_term_handler)

pid = str(os.getpid())

parser = argparse.ArgumentParser(description='Python Rcon cmdlet for ARMA3 Servers')
parser.add_argument('host', help='server host')
parser.add_argument('port', help='server port')
parser.add_argument('password', help='admin rcon password')

args = parser.parse_args()

print ''
print '#######################################################################'
print '# DO NOT FORGET TO SETUP THE beserver.cfg LOCATED IN battleye/ FOLDER #'
print '#######################################################################'
print ''

pidfile = '/tmp/pyrcon.{}.run'.format(args.port)

if os.path.isfile(pidfile):
    print 'pyrcon is already running for {}:{}'.format(args.host, args.port)
    exit()

open(pidfile, 'w').write(pid)

rcon = rconprotocol.Rcon(args.host,args.password, args.port)

# Display messages to all players ever X interval (sequencial)
# Usage: rcon.messengers(<List of Messages>, <delay in minutes>)
rcon.messengers(['','Besucht uns auf: www.die-bluiescreen-crew.de','Du befindest die auf dem D.B.C. Exile Esseker Server', 'Unser Teamspeak: www.die-bluecreen-crew.de'], 20)

# Define a shutdown interval (requires the server be started under WATCHDOG - FOR RESTART)
# Usage: rcon.shutdown(<time in minutes>, <List of RestartMessage objects>)
rcon.shutdown(240, [
                        rconprotocol.RestartMessage(15, 'RESTART IN 15 MINUTES'),
                        rconprotocol.RestartMessage(10, 'RESTART IN 10 MINUTES'),
                        rconprotocol.RestartMessage( 5, 'RESTART IN 5 MINUTES'),
                        rconprotocol.RestartMessage( 3, 'RESTART IN 3 MINUTES'),
                        rconprotocol.RestartMessage( 1, 'RESTART IN 1 MINUTE'),
                ])

# Establish the RCON connection
rcon.connect()

# remove PID
os.unlink(pidfile)
