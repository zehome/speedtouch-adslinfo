#!/usr/bin/env python

# This script will connect to SpeedTouch 546v6 and get
# bandwidth available (ADSL sync)

import os
import sys
import signal
import traceback
import socket
import daemon
import BaseHTTPServer
import telnetlib
from SocketServer import ThreadingMixIn


MODEM_HOST="10.0.0.138"
MODEM_USER="Administrator"
MODEM_PASSWORD=""

def get_synchro_sth():
    vi = sys.version_info
    if vi[0] == 2 and vi[1] >= 6:
        tn = telnetlib.Telnet(MODEM_HOST, timeout=5)
    else:
        socket.setdefaulttimeout(5)
        tn = telnetlib.Telnet(MODEM_HOST)
    tn.read_until("Username : ")
    tn.write(MODEM_USER+"\r\n")
    tn.read_until("Password : ")
    tn.write(MODEM_PASSWORD+"\r\n")
    data = tn.read_until("{%s}=>" % (MODEM_USER,))
    if "6.1.19.0" in data:
       return get_synchro_6119(tn)
    elif "7.4.3.2" in data:
       return get_synchro_7432(tn)

    # Unsupported
    return None

def get_synchro_6119(tn):
    tn.write("adsl info\r\n")
    tn.write("exit\r\n")
    data = tn.read_all()
    synchro=["0","0"]
    ok=False
    for line in data.split("\n"):
        if line.startswith("Available Bandwidth"):
            ok = True

        if ok and line.startswith("  Downstream"):
            synchro[0] = line.split()[3]
	if ok and line.startswith("  Upstream"):
            synchro[1] = line.split()[3]
    return synchro

def get_synchro_7432(tn):
    tn.write("adsl info\r\n")
    tn.write("exit\r\n")
    data = tn.read_all()
    synchro=None
    for line in data.split("\n"):
        if line.startswith("Bandwidth"):
            synchro = line.split(" ")[6]
            synchro = synchro and synchro.strip() or synchro
    return synchro.split("/")

class ST546HTTPHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            synchro = get_synchro_sth()
        except:
            self.send_response(500)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write("%s" % (traceback.format_exc(),))
            traceback.print_exc()
            return
        
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write("%s/%s\n" % (synchro[0], synchro[1]))

class ADSLSyncHTTPServer(ThreadingMixIn, BaseHTTPServer.HTTPServer): pass

if __name__ == "__main__":
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option("--port",
            type="int",
            dest="port",
            help="HTTP Server port (default = 7980)",
            default=7980)
    parser.add_option("--host",
            type="string",
            dest="host",
            help="HTTP Server listen address (default = *)",
            default='')
    parser.add_option("--pidfile",
            type="string",
            dest="pidfile",
            help="Daemon pidfile (default = /var/run/adslsync.pid)",
            default='/var/run/adslsync.pid')
    parser.add_option("--daemon",
            action="store_true",
            dest="daemon",
            help="Daemonize (default = False)",
            default=False)

    values, args = parser.parse_args()

    # Overwrite defaults using env
    MODEM_HOST=os.environ.get("STH_HOST", MODEM_HOST)
    MODEM_USER=os.environ.get("STH_USER", MODEM_USER)
    MODEM_PASSWORD=os.environ.get("STH_PASS", MODEM_PASSWORD)

    if "oneshot" in args:
        print "Synchro [Down, Up]: %s" % (get_synchro_sth(),)
        sys.exit(0)

    if "start" not in args and "stop" not in args:
        parser.print_help()
        sys.exit(0)
    
    if "stop" in args:
        ## Search pid, then kill the daemon
        try:
            f = open(values.pidfile, "r")
            pid=int(f.read())
            os.kill(pid, signal.SIGTERM)
            f.close()
        except:
            print "Invalid pidfile %s." % (values.pidfile,)
            sys.exit(1)
        else:
            print "Killed pid %s" % (pid, )
            sys.exit(0)


    def handleSignal(*args, **kw):
        try:
            os.unlink(values.pidfile)
        except:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, handleSignal)
    signal.signal(signal.SIGTERM, handleSignal)

    print "Will serve forever on port %s" % (values.port, )
    server = ADSLSyncHTTPServer((values.host, values.port), ST546HTTPHandler)
    
    if values.daemon:
        daemon.daemonize()
    
    ## Write pidfile
    try:
        pid = os.getpid()
        f = open(values.pidfile, "wb+")
        f.write("%s" % (pid, ))
        f.close()
    except (OSError, IOError):
        print "Unable to write pidfile %s" % (values.pidfile, )

    server.serve_forever()

    self.handleSignal()
