#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Bottle based Server Module
Based on the restserver module using Flask
'''

import json
from threading import Thread
from wsgiref.simple_server import make_server
from bottle import Bottle, response
from MAVProxy.modules.lib import mp_module


def mavlink_to_json(msg):
    '''Translate mavlink python messages in json string'''
    ret = '\"%s\": {' % msg._type
    for fieldname in msg._fieldnames:
        data = getattr(msg, fieldname)
        ret += '\"%s\" : \"%s\", ' % (fieldname, data)
    ret = ret[0:-2] + '}'
    return ret


def mpstatus_to_json(status):
    '''Translate MPStatus in json string'''
    msg_keys = list(status.msgs.keys())
    data = '{'
    for key in msg_keys[:-1]:
        data += mavlink_to_json(status.msgs[key]) + ','
    data += mavlink_to_json(status.msgs[msg_keys[-1]])
    data += '}'
    return data


class BottleServer:
    '''Bottle based REST server'''
    def __init__(self):
        # Server variables
        self.app = None
        self.run_thread = None
        self.address = 'localhost'
        self.port = 5000

        # Save status
        self.status = None
        self.server = None

    def update_dict(self, mpstate):
        '''Update MP state reference'''
        self.status = mpstate.status

    def set_ip_port(self, ip, port):
        '''set ip and port'''
        self.address = ip
        self.port = port
        self.stop()
        self.start()

    def start(self):
        '''Start server'''
        self.app = Bottle()
        self.add_routes()
        self.run_thread = Thread(target=self.run)
        self.run_thread.start()

    def running(self):
        '''If app is valid, thread and server are running'''
        return self.app is not None

    def stop(self):
        '''Stop server'''
        self.app = None
        if self.server:
            self.server.shutdown()
            self.server = None
        if self.run_thread:
            self.run_thread = None

    def run(self):
        '''Start app'''
        self.server = make_server(self.address, self.port, self.app)
        self.server.serve_forever()

    def request(self, arg=''):
        '''Deal with requests'''
        response.content_type = 'application/json'
        if not self.status:
            return json.dumps({"result": "No message"})

        try:
            status_dict = json.loads(mpstatus_to_json(self.status))
        except Exception as e:
            print(e)
            return json.dumps({})

        # If no key, send the entire json
        if not arg:
            return json.dumps(status_dict)

        # Get item from path
        new_dict = status_dict
        args = arg.split('/')
        for key in args:
            if key in new_dict:
                new_dict = new_dict[key]
            else:
                return json.dumps({"key": key, "last_dict": new_dict})

        return json.dumps(new_dict)

    def add_routes(self):
        '''Set routes'''
        self.app.route('/rest/mavlink/<arg:path>', method='GET')(self.request)
        self.app.route('/rest/mavlink/', method='GET')(self.request)


class ServerModule(mp_module.MPModule):
    ''' Server Module '''
    def __init__(self, mpstate):
        super(ServerModule, self).__init__(mpstate, "bottleserver", "bottleserver module")
        self.rest_server = BottleServer()

        self.add_command('bottleserver', self.cmds,
            "bottleserver module", ['start', 'stop', 'address 127.0.0.1:4777'])

    def usage(self):
        '''show help on command line options'''
        return "Usage: bottleserver <address|stop|start>"

    def cmds(self, args):
        '''control behaviour of the module'''
        if not args or len(args) < 1:
            print(self.usage())
            return

        if args[0] == "start":
            if self.rest_server.running():
                print("Bottle server already running.")
                return
            self.rest_server.start()
            print("Bottle server running: %s:%s" %
                  (self.rest_server.address, self.rest_server.port))

        elif args[0] == "stop":
            if not self.rest_server.running():
                print("Bottle server is not running.")
                return
            self.rest_server.stop()

        elif args[0] == "address":
            # Check if have necessary amount of arguments
            if len(args) != 2:
                print("usage: bottleserver address <ip:port>")
                return

            address = args[1].split(':')
            # Check if argument is correct
            if len(address) == 2:
                self.rest_server.set_ip_port(address[0], int(address[1]))
                return

        else:
            print(self.usage())

    def idle_task(self):
        '''called rapidly by mavproxy'''
        # Update server with last mpstate
        self.rest_server.update_dict(self.mpstate)

    def unload(self):
        '''Stop and kill everything before finishing'''
        self.rest_server.stop()


def init(mpstate):
    '''initialise module'''
    return ServerModule(mpstate)
