#!/usr/bin/python

import os, signal, sys, argparse, threading, rconprotocol, json

def restart_program():
    print 'Restarting program'
    python = sys.executable
    os.execl(python, python, * sys.argv)

def signal_term_handler(signal, frame):
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_term_handler)

pid = str(os.getpid())

parser = argparse.ArgumentParser(description='Python Rcon cmdlet for ARMA3 Servers')
parser.add_argument('configfile', help='configuration file in JSON')

args = parser.parse_args()

if not os.path.isfile(args.configfile):
    print ''
    print ' -- Configuration not found: "{}" --\n'.format(args.configfile)
    exit(1)

with open(args.configfile) as json_config:
    config = json.load(json_config)

_bstr = os.path.basename(args.configfile)
_n = 48 - len(_bstr)

print 'PyRcon for ARMA3 CLI v0.1'
print ''
print '#'.ljust(71, '#')
print '# Configuration file: {}{}#'.format(_bstr , ''.ljust(_n, ' '))
print '#'.ljust(71, '#')
print '# DO NOT FORGET TO SETUP THE beserver.cfg LOCATED IN battleye/ FOLDER #'
print '#'.ljust(71, '#')
print ''

pidfile = '/tmp/pyrcon.{}.run'.format(config['server']['port'])

if os.path.isfile(pidfile):
    print 'pyrcon is already running for {}:{}'.format(config['server']['host'], config['server']['port'])
    exit()

open(pidfile, 'w').write(pid)

rcon = rconprotocol.Rcon(config['server']['host'], config['server']['rcon_password'], config['server']['port'])

# Display messages to all players ever X interval (sequencial)
# Usage: rcon.messengers(<List of Messages>, <delay in minutes>)

rcon.messengers( config['repeatMessage']['messages'], config['repeatMessage']['interval'])

# Define a shutdown interval (requires the server be started under WATCHDOG - FOR RESTART)
# Usage: rcon.shutdown(<time in minutes>, <List of RestartMessage objects>)
rcon.shutdown(1, [
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
# and restart the program
#restart_program()
