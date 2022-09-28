#!/usr/bin/env python3
from dbus.exceptions import DBusException
from requests.exceptions import ConnectionError
import sqlite3
from multiprocessing import Process
from flask import Flask, request, jsonify
import requests
from getpass import getuser
from subprocess import run
import dbus
import logging
import os
import shlex
import subprocess
import time

# a few globals
debug = False
shutdown_command = 'sudo shutdown -h now'
reboot_command = 'sudo shutdown -r now'
db_file = os.path.expanduser('~/positions.sqlite')

# depending on the current context:
# map KODI RPC actions to either omxplayer keys (https://github.com/popcornmix/omxplayer/blob/master/KeyConfig.h)
# or vifm/tmux keypresses
# https://github.com/xbmc/xbmc/blob/68bf07ee4fab9f844a9bef3ddeeb443be45d9453/xbmc/input/actions/ActionTranslator.cpp
key_action = {'right': (20, 'l'),
              'left': (19, 'h'),
              'up': (22, 'k'),
              'down': (21, 'j'),
              'select': (5, 'enter'),
              'volumeup': (18, ''),
              'volumedown': (17, ''),
              'showosd': (12, ''),
              'playpause': (16, ''),
              'stop': (15, ''),
              'rewind': (1, ''),
              'fastforward': (2, ''),
              'contextmenu': ('', 'f2'),
              }


def store_playback_position():
    ''' regulary store current playback position to sqlite db '''
    con = sqlite3.connect(db_file)
    cur = con.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS positions(name UNIQUE, position)")
    con.commit()
    while True:
        try:
            response = requests.get('http://localhost:8080/pos').json()
        except ConnectionError:
            time.sleep(10)
            continue
        name = response['name']
        position = response['position']
        if name and position > 120:
            cur.execute('INSERT OR REPLACE INTO positions VALUES (?, ?)', (name, position))
            con.commit()
        time.sleep(15)


def tmux_send(action):
    ''' send key to tmux -> vifm '''
    cmd = ['tmux', 'send']
    run(cmd + [action])


def acquire_bus():
    bus_file = f'/tmp/omxplayerdbus.{getuser()}'
    if os.path.exists(bus_file):
        omxplayer_bus = dbus.bus.BusConnection(open(bus_file).read().strip())
    else:
        logging.info('No bus file exists!')
        bus = None
        return None, None

    try:
        obj = omxplayer_bus.get_object('org.mpris.MediaPlayer2.omxplayer',
                                       '/org/mpris/MediaPlayer2',
                                       introspect=False)
        prop = dbus.Interface(obj, 'org.freedesktop.DBus.Properties')
        key = dbus.Interface(obj, 'org.mpris.MediaPlayer2.Player')
    except:
        # there is no bus if we can't connect to it
        bus = None
        return None, None
    return prop, key


def _make_response(req_id, data):
    ''' construct a Kodi-like response '''
    response = {'id': req_id, 'jsonrpc': '2.0', 'result': data}
    logging.debug(f'returning {response}')
    return response


def _send_omxplayer_action(action):
    ''' send dbus event to omxplayer via dbus '''
    app.omxplayer_key.Action(dbus.Int32(key_action[action][0]))


def _send_tmux_action(action):
    ''' send key to tmux '''
    tmux_send(key_action[action][1])


def _seconds_to_hmc(seconds):
    h = int(seconds/3600)
    m = int(seconds % 3600 / 60)
    s = seconds % 60
    return h, m, s


if debug:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.CRITICAL)

# filter out non-critical messages from werkzeug
logging.getLogger('werkzeug').setLevel(logging.CRITICAL)

# create flask app, save dbus objects as its properties
app = Flask(__name__)
app.omxplayer_prop, app.omxplayer_key = acquire_bus()


@app.route("/pos")
def return_current_position():
    if not app.omxplayer_prop and not app.omxplayer_key:
        app.omxplayer_prop, app.omxplayer_key = acquire_bus()
    try:
        position = int(app.omxplayer_prop.Get(dbus.String('org.mpris.MediaPlayer2.Player'), dbus.String('Position')) / 1000000)
        name = str(app.omxplayer_key.GetSource())
    except DBusException:
        app.omxplayer_prop, app.omxplayer_key = acquire_bus()
        if not app.omxplayer_prop:
            return jsonify(name=None, position=None)

        position = int(app.omxplayer_prop.Get(dbus.String('org.mpris.MediaPlayer2.Player'), dbus.String('Position')) / 1000000)
        name = str(app.omxplayer_key.GetSource())
    except Exception as e:
        return jsonify(name=None, position=None)
    return jsonify(name=name, position=position)

@app.route("/jsonrpc", methods = ['POST', 'GET'])
def handle():
    if request.method == 'GET':
        return {"description": "JSON-RPC API of XBMC",
                "id": "http://xbmc.org/jsonrpc/ServiceDescription.json",
                "methods": {},
                "version": "10.3.0"}
    else:
        logging.debug(f'Request: {request.json}')
        req_id = request.json.get('id')
        method = request.json.get('method')

        if method == 'Application.GetProperties':
            return _make_response(req_id,
                                  {'name':'Kodi',
                                  'version':{'major':18,
                                             'minor':9,
                                             'revision':'20201126-nogitfound',
                                             'tag':'stable'}})
        elif method == 'Player.GetActivePlayers':
            try:
                status = str(app.omxplayer_prop.Get(dbus.String('org.mpris.MediaPlayer2.Player'),
                                                    dbus.String('PlaybackStatus')))
            except (DBusException, AttributeError):
                # try to reacquire the bus connection
                app.omxplayer_prop, app.omxplayer_key = acquire_bus()
                return _make_response(req_id, [])
            # if omxplayer dbus is available it means we're playing something
            return _make_response(req_id, [{'playerid': 1,
                                            'playertype': 'internal',
                                            'type': 'video'}])
        elif method == 'GUI.GetProperties':
            # let's pretend Kodi interface is always active
            return _make_response(req_id, {'currentwindow': {'id': 10025,
                                                             'label': 'Videos'},
                                           'fullscreen': False})
        elif method == 'Player.GetItem':
            if app.omxplayer_prop:
                name = str(app.omxplayer_key.GetSource())
                return _make_response(req_id, {'item': {'label': f'{name}'}})
 
            else:
                return _make_response(req_id, {'currentwindow': {'id': 10025, 'label': 'Videos'},
                                               'fullscreen': False})
        elif method == 'System.Shutdown':
            subprocess.call(shlex.split(shutdown_command))

        elif method == 'System.Reboot':
            subprocess.call(shlex.split(reboot_command))

        elif method == 'Player.PlayPause':
            logging.debug('Sending play/pause')
            _send_omxplayer_action('playpause')

        elif method == 'Input.ShowOSD':
            logging.debug('Sending ShowOSD (toggle subtitles)')
            _send_omxplayer_action('showosd')

        elif method == 'Player.Stop':
            logging.debug('Sending stop (exit)')
            _send_omxplayer_action('stop')

        elif method == 'Player.GetProperties':
            position = int(app.omxplayer_prop.Get(dbus.String('org.mpris.MediaPlayer2.Player'), dbus.String('Position')) / 1000000)
            duration = int(app.omxplayer_prop.Get(dbus.String('org.mpris.MediaPlayer2.Player'), dbus.String('Duration')) / 1000000)
            status = str(app.omxplayer_prop.Get(dbus.String('org.mpris.MediaPlayer2.Player'), dbus.String('PlaybackStatus')))
            if 'Playing' in status:
                speed = 1
            else:
                speed = 0
            logging.debug(f'position/duration: {position}/{duration}')
            h, m, s = _seconds_to_hmc(position)
            H, M, S = _seconds_to_hmc(duration)
          
            ''' we will fake the file properties - mediainfo is rather slow '''
            return _make_response(req_id,
                  {'audiostreams': [{'bitrate': 120000,
                                     'channels': 2,
                                     'codec': 'aac',
                                     'index': 0,
                                     'language': 'und',
                                     'name': 'AAC stereo'}],
                   'currentaudiostream': {'bitrate': 120000,
                                          'channels': 2,
                                          'codec': 'aac',
                                          'index': 0,
                                          'language': 'und',
                                          'name': 'AAC stereo'},
                   'currentvideostream': {'codec': 'h264',
                                          'height': 854,
                                          'index': 0,
                                          'language': 'und',
                                          'name': '',
                                          'width': 480},
                   'currentsubtitle': {},
                   'canseek': True,
                   'partymode': False,
                   'playlistid': 1,
                   'position': 0,
                   'repeat': 'off',
                   'shuffled': False,
                   'speed': speed,
                   'subtitleenabled': True,
                   'subtitles': [],
                   'time': {'hours': h, 'milliseconds': 0, 'minutes': m, 'seconds': s},
                   'totaltime': {'hours': H, 'milliseconds': 0, 'minutes': M, 'seconds': S},
                   'type': 'video',
                   'videostreams': [{'codec': 'h264',
                                     'height': 854,
                                     'index': 0,
                                     'language': 'und',
                                     'name': '',
                                     'width': 480}]
                  })

        if method == 'Input.ExecuteAction':
            kodi_action = request.json.get('params', {}).get('action')
            resolved_action = key_action.get(kodi_action)
            if resolved_action:
                logging.debug(f'caught action {resolved_action}')
                # if omxplayer bus is available, use that. otherwise send keys to vifm/tmux
                if app.omxplayer_key:
                    _send_omxplayer_action(kodi_action)
                else:
                    _send_tmux_action(kodi_action)
            else:
                logging.debug(f'detected unresolved action {kodi_action}')

        return '{}'


if __name__ == "__main__":
    p = Process(target=store_playback_position)
    p.start()
    app.run(debug=debug, host="0.0.0.0", use_reloader=False, port=8080)
    # p.join()
