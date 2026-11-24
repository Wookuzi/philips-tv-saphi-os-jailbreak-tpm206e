#!/usr/bin/env python3
"""Local bridge between the custom TV Home and a Gira X1 (Gira IoT REST API v2).

    python gira_bridge.py register --gira 192.168.1.30 --user YOUR-GIRA-USER
        Asks for the Gira password (not echoed, never stored), registers this
        computer as an API client and saves only the access token in
        build/gira.json (ignored by Git).
    python gira_bridge.py list
        Shows the switchable functions your Gira user can see, with the
        datapoint IDs to put in home-app/config.local.js.
    python gira_bridge.py serve --tv 192.168.1.50 --host 192.168.1.20
        Runs the local HTTP bridge (default port 8770). Only the TV, this
        computer and localhost may use it. It can switch/dim lights and move
        blinds (OnOff, Brightness, Position, Slat-Position, Up-Down,
        Step-Up-Down) and only READ temperatures (Current, Set-Point).
    python gira_bridge.py unregister
        Revokes the token on the Gira X1 and deletes build/gira.json.

Standard library only. The X1 uses a self-signed HTTPS certificate, so TLS
verification is disabled for requests to the configured Gira address only.
"""
import argparse
import base64
import getpass
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
STORE = ROOT / 'build' / 'gira.json'
CLIENT_ID = 'io.github.saphi-custom-home.tvbridge'
CONTROL_DATAPOINTS = ('OnOff', 'Brightness')
# Datapoints the TV may change, with their allowed range. Anything else
# (for example a thermostat Set-Point) is read-only through this bridge.
WRITABLE = {'OnOff': (0, 1), 'Brightness': (0, 100), 'Position': (0, 100),
            'Slat-Position': (0, 100), 'Up-Down': (0, 1), 'Step-Up-Down': (0, 1)}
READ_ONLY = ('Current', 'Set-Point')


def load():
    if not STORE.exists():
        sys.exit('Not registered yet. Run: python gira_bridge.py register --gira <X1-IP> --user <name>')
    return json.loads(STORE.read_text(encoding='utf-8'))


class Gira:
    def __init__(self, host, token=None):
        self.base = 'https://' + host + '/api/v2'
        self.token = token
        self.tls = ssl.create_default_context()
        self.tls.check_hostname = False
        self.tls.verify_mode = ssl.CERT_NONE  # X1 ships a self-signed certificate.
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                                urllib.request.HTTPSHandler(context=self.tls))

    def call(self, method, path, body=None, auth=None, token=True):
        url = self.base + path
        if token and self.token:
            url += ('&' if '?' in url else '?') + 'token=' + urllib.parse.quote(self.token)
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header('Content-Type', 'application/json')
        if auth:
            request.add_header('Authorization', 'Basic ' + base64.b64encode(auth.encode()).decode())
        try:
            with self.http.open(request, timeout=8) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors='replace')[:300]
            raise RuntimeError(f'Gira X1 answered {error.code} for {method} {path}: {detail}') from None

    def info(self):
        return self.call('GET', '/', token=False)

    def register(self, user, password):
        return self.call('POST', '/clients', {'client': CLIENT_ID}, auth=user + ':' + password, token=False)['token']

    def unregister(self):
        self.call('DELETE', '/clients/' + urllib.parse.quote(self.token), token=False)

    def uiconfig(self):
        return self.call('GET', '/uiconfig')

    def get(self, uid):
        values = self.call('GET', '/values/' + urllib.parse.quote(uid)).get('values') or []
        return values[0].get('value') if values else None

    def set(self, uid, value):
        self.call('PUT', '/values/' + urllib.parse.quote(uid), {'value': value})


def functions(config, names=CONTROL_DATAPOINTS):
    """Yield (function, {datapointName: uid}) for every function with one of the given datapoints."""
    for function in config.get('functions', []):
        points = {p.get('name'): p.get('uid') for p in function.get('dataPoints', []) if p.get('uid')}
        if any(name in points for name in names):
            yield function, points


def as_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def locations(config):
    """Map function uid -> room name, from the nested location tree."""
    names = {}
    def walk(node, label):
        here = node.get('displayName') or label
        for uid in node.get('functions', []):
            names[uid] = here
        for child in node.get('locations', []):
            walk(child, here)
    for location in config.get('locations', []):
        walk(location, '')
    return names


def cmd_register(args):
    gira = Gira(args.gira)
    info = gira.info()
    if info.get('info') != 'GDS-REST-API':
        sys.exit('That address does not look like a Gira IoT REST API: ' + json.dumps(info))
    print('Found ' + str(info.get('deviceName')) + ' (firmware ' + str(info.get('deviceVersion')) + ').')
    password = getpass.getpass('Gira password for user "' + args.user + '" (not shown, not saved): ')
    token = gira.register(args.user, password)
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps({'gira': args.gira, 'token': token}, indent=2), encoding='utf-8')
    try:
        STORE.chmod(0o600)
    except OSError:
        pass
    print('Registered. Token saved to ' + str(STORE) + ' (ignored by Git). Next: python gira_bridge.py list')


def cmd_list(args):
    store = load()
    gira = Gira(store['gira'], store['token'])
    config = gira.uiconfig()
    rooms = locations(config)
    found = False
    for function, points in functions(config, tuple(WRITABLE) + READ_ONLY):
        found = True
        room = rooms.get(function.get('uid'), '')
        print('- ' + str(function.get('displayName')) + (' [' + room + ']' if room else ''))
        for name in tuple(WRITABLE) + READ_ONLY:
            if name in points:
                try:
                    value = gira.get(points[name])
                except Exception:
                    value = '?'
                print('    ' + name + ' datapoint: ' + points[name] + '  (now ' + str(value) + ')')
    if not found:
        print('No switchable functions are visible to this Gira user.')
    print('\nPut the OnOff datapoint of each light into home-app/config.local.js (smartHome.lights).')


def cmd_unregister(args):
    store = load()
    try:
        Gira(store['gira'], store['token']).unregister()
        print('Token revoked on the Gira X1.')
    except Exception as error:
        print('Could not revoke on the X1 (' + str(error) + '); deleting the local token anyway.')
    STORE.unlink()


def cmd_serve(args):
    store = load()
    gira = Gira(store['gira'], store['token'])
    allowed = {}
    lock = threading.Lock()

    def refresh_allowed():
        config = gira.uiconfig()
        fresh = {}
        for function, points in functions(config, tuple(WRITABLE) + READ_ONLY):
            for name in tuple(WRITABLE) + READ_ONLY:
                if name in points:
                    fresh[points[name]] = (name, function.get('displayName'))
        with lock:
            allowed.clear()
            allowed.update(fresh)
        return len(fresh)

    print('Gira X1 at ' + store['gira'] + ': ' + str(refresh_allowed()) + ' usable datapoints.', flush=True)
    clients = {args.tv, args.host, '127.0.0.1'}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, status, payload):
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            if self.client_address[0] not in clients:
                self.reply(403, {'error': 'not allowed'}); return
            url = urllib.parse.urlsplit(self.path)
            query = urllib.parse.parse_qs(url.query)
            if url.path == '/health':
                self.reply(200, {'ok': True}); return
            if url.path not in ('/state', '/set', '/toggle'):
                self.reply(404, {'error': 'unknown path'}); return
            uids = [u for u in (query.get('dp') or [''])[0].split(',') if u][:20]
            with lock:
                known = {u: allowed.get(u) for u in uids}
            if not uids or not all(known.values()):
                self.reply(400, {'error': 'unknown datapoint'}); return
            try:
                if url.path == '/state':
                    values = {}
                    for u in uids:
                        try:
                            values[u] = as_number(gira.get(u))
                        except Exception:
                            values[u] = None
                    self.reply(200, {'values': values}); return
                if len(uids) != 1:
                    raise ValueError()
                dp = uids[0]
                kind, label = known[dp]
                if kind not in WRITABLE:
                    self.reply(403, {'error': 'read-only datapoint'}); return
                low, high = WRITABLE[kind]
                if url.path == '/toggle':
                    if kind != 'OnOff':
                        raise ValueError()
                    value = 0 if (as_number(gira.get(dp)) or 0) > 0 else 1
                else:
                    value = float((query.get('value') or [''])[0])
                    if not low <= value <= high or (high == 1 and value not in (0, 1)):
                        raise ValueError()
                    value = int(value) if value == int(value) else value
                gira.set(dp, value)
                print(time.strftime('%H:%M:%S') + ' ' + str(label) + ' ' + kind + ' -> ' + str(value), flush=True)
                # Report the value just written: an immediate read-back can still
                # return the old state while KNX is updating.
                self.reply(200, {'values': {dp: float(value)}})
            except ValueError:
                self.reply(400, {'error': 'bad value'})
            except Exception as error:
                print('Gira error: ' + str(error), flush=True)
                self.reply(502, {'error': 'gira unavailable'})

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print('Light bridge on http://' + args.host + ':' + str(args.port) + ' (allowed: ' + ', '.join(sorted(clients)) + '). Ctrl+C to stop.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
    finally:
        server.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('register'); p.add_argument('--gira', required=True, help='Gira X1 LAN address'); p.add_argument('--user', required=True)
    sub.add_parser('list')
    sub.add_parser('unregister')
    p = sub.add_parser('serve')
    p.add_argument('--tv', required=True, help='TV LAN address (only this TV may call the bridge)')
    p.add_argument('--host', required=True, help='This computer\'s LAN address to listen on')
    p.add_argument('--port', type=int, default=8770)
    args = parser.parse_args()
    {'register': cmd_register, 'list': cmd_list, 'serve': cmd_serve, 'unregister': cmd_unregister}[args.action](args)
