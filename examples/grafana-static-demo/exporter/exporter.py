"""Static demo adapter. Every request validates a fresh file; no observation cache."""
import argparse
import json
import math
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

STATES = {name: n for n, name in enumerate(('ok', 'degraded', 'fault', 'unknown', 'notdeployed'))}
CATALOG = json.loads(Path(__file__).with_name('components.json').read_text())
COMPONENTS = {c['title'].lower().replace(' ', ''): c for c in CATALOG}
SERVERS = {f'{role}{n}-fhs{f}' for role, count, members in [('vccu',24,1),('fspu',27,4)] for n in range(1,count+1) for f in range(1,members+1)}
SWITCHES = {f'{role}{n}-switch' for role,count in [('vccu',24),('fspu',27)] for n in range(1,count+1)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(value, required, optional=()):
    require(isinstance(value, dict), 'expected object')
    require(set(required) <= value.keys() and value.keys() <= set(required) | set(optional), 'missing or unsupported keys: ' + ','.join(value))


def state(value):
    require(isinstance(value,str) and value in STATES, 'status must be ok/degraded/fault/unknown/notdeployed')
    return STATES[value]


def raw_unit(name):
    role, number = re.fullmatch(r'(vccu|fspu)(\d+)', name).groups()
    return ('VCCUnit' if role == 'vccu' else 'FSPUnit') + number


def endpoint(value):
    keys(value, ('switch','interface'))
    require(value['switch'] in SWITCHES, 'unknown switch')
    require(isinstance(value['interface'],str) and re.fullmatch(r'eth1/(?:[1-9]|[12]\d|3[0-2])/[1-4]', value['interface']), 'invalid interface')
    return value['switch'], value['interface']


def render(data):
    keys(data, ('version','provenance','defaults','servers','links','physical_ports','transceivers'),
         ('readings','interfaces','switches'))
    require(type(data['version']) is int and data['version'] == 1, 'unsupported version')
    require(data['provenance'] == 'STATIC DEMO: synthetic mock readings and synthetic peer inventory; not observed hardware', 'explicit STATIC DEMO provenance required')
    defaults = data['defaults']
    keys(defaults, ('status','mock_readings','provenance'))
    normal = state(defaults['status'])
    require(type(defaults['mock_readings']) is bool, 'mock_readings must be boolean')
    require(defaults['provenance'] == 'synthetic demo', 'default readings need synthetic demo provenance')
    mock = defaults['mock_readings']
    require(isinstance(data['servers'],dict) and data['servers'].keys() <= SERVERS, 'unknown server')
    lines = ['# STATIC DEMO: synthetic values and peers, NOT hardware observations. Status 0 ok, 1 degraded, 2 fault, 3 unknown, 4 notdeployed.']

    def emit(metric, labels, value):
        lines.append(metric + '{' + ','.join(k+'='+json.dumps(str(v), ensure_ascii=True) for k,v in sorted(labels.items())) + '} ' + str(value))

    overrides = {}
    require(isinstance(data.get('readings',[]),list), 'readings must be an array')
    for reading in data.get('readings',[]):
        keys(reading, ('server','component','metric','value','provenance'))
        require(reading['server'] in SERVERS and reading['component'] in COMPONENTS, 'invalid reading identity')
        require(reading['metric'] in {r['name'] for r in COMPONENTS[reading['component']]['readings']}, 'unsupported native reading')
        require(reading['provenance'] == 'synthetic demo', 'reading provenance must be synthetic demo')
        require(type(reading['value']) in (int,float) and math.isfinite(reading['value']), 'finite numeric reading required')
        identity = (reading['server'],reading['component'],reading['metric'])
        require(identity not in overrides, 'duplicate reading')
        overrides[identity] = reading['value']

    for name in sorted(SERVERS):
        server = data['servers'].get(name, {})
        keys(server, (), ('status','provenance','components'))
        require(server.get('provenance','synthetic demo') in ('static replay','synthetic demo'), 'invalid server provenance')
        require(isinstance(server.get('components',{}),dict) and server.get('components',{}).keys() <= COMPONENTS.keys(), 'unknown component')
        unit, fhs = name.split('-')
        labels = {'unit':raw_unit(unit), 'fhs':fhs.upper(), 'provenance':server.get('provenance','synthetic demo')}
        health = state(server.get('status', defaults['status']))
        emit('demo_server_status', labels, health)
        reading_seen = set()
        for component, catalog in COMPONENTS.items():
            status = state(server.get('components',{}).get(component, 'unknown' if health == 3 else defaults['status']))
            emit('demo_component_status', {**labels,'component':component}, status)
            for reading in catalog['readings']:
                identity = (name,component,reading['name'])
                if identity not in overrides and (not mock or status >= 3 or health >= 3):
                    continue
                native = {'unit':raw_unit(unit),'fhs':fhs.upper(),'provenance':'synthetic demo'}
                if reading.get('node_job'):
                    native.update(dict(re.findall(r'(\w+)="([^"]*)"',reading.get('extra',''))))
                    if reading['name'] == 'node_nvme_info':
                        native['state'] = 'live'
                else:
                    native['source'] = catalog['source']
                # Shared FAN controller and NVMe hottest-sensor queries address one series.
                key = (reading['name'],tuple(sorted(native.items())))
                if key in reading_seen:
                    continue
                reading_seen.add(key)
                metric = reading['name']
                value = (40 if 'temp' in metric else 4500 if metric.endswith('_rpm') else
                         12 if '12v' in metric else 3.3 if '3v' in metric else
                         150 if metric.endswith('_watts') else 1 if metric == 'node_nvme_info' else 0)
                emit(metric,native,overrides.get(identity,value))
        if mock and health < 3:
            emit('node_network_info',{'unit':raw_unit(unit),'fhs':fhs.upper(),'device':'demo0','operstate':'up','provenance':'synthetic demo'},1)

    def status_map(field, interface=False):
        values = data.get(field,{})
        require(isinstance(values,dict) and values.keys() <= SWITCHES, 'invalid '+field)
        result = {}
        for switch, members in values.items():
            require(isinstance(members,dict),'expected status object')
            for member,status in members.items():
                if interface:
                    endpoint({'switch':switch,'interface':member})
                else:
                    require(member in map(str,range(1,33)), 'physical port must be 1..32')
                result[switch,member] = state(status)
        return result

    ports = status_map('physical_ports')
    optics = status_map('transceivers')
    interfaces = status_map('interfaces',True)
    require(isinstance(data.get('switches',{}),dict) and data.get('switches',{}).keys() <= SWITCHES,'unknown switch')
    switches = {k:state(v) for k,v in data.get('switches',{}).items()}
    require(isinstance(data['links'],list),'links must be an array')
    links, ids = {}, set()
    for link in data['links']:
        keys(link, ('id','status','ends'), ('rate_bps','capacity_bps','available_capacity_percent'))
        capacity = link.get('capacity_bps',100000000000)
        rate = link.get('rate_bps',1000000000)
        require(type(capacity) in (int,float) and math.isfinite(capacity) and capacity > 0, 'positive finite capacity_bps required')
        require(type(rate) in (int,float) and math.isfinite(rate) and 0 <= rate <= capacity, 'rate_bps must be finite and within capacity')
        available = link.get('available_capacity_percent')
        if 'available_capacity_percent' in link:
            require(type(available) in (int,float) and math.isfinite(available) and 0 <= available <= 100,
                    'available_capacity_percent must be finite and within 0..100')
        require(isinstance(link['id'],str) and re.fullmatch('[a-z0-9-]+',link['id']) and link['id'] not in ids, 'invalid or duplicate link id')
        ids.add(link['id'])
        require(isinstance(link['ends'],list) and len(link['ends']) == 2,'one link needs two ends')
        ends = [endpoint(e) for e in link['ends']]
        require(ends[0][0].startswith('vccu') and ends[1][0].startswith('fspu'),'ends must be vccu then fspu')
        pair = tuple(e[0].removesuffix('-switch') for e in ends)
        require(pair not in links,'duplicate mesh pair')
        links[pair] = (ends,state(link['status']),rate,capacity,available)
    # One deterministic synthetic peer inventory fills the mesh. Overrides replace
    # the pair's definition, never add an unrelated second interface health source.
    peers, seen = {}, set()
    for v in range(1,25):
        for f in range(1,28):
            pair = ('vccu'+str(v),'fspu'+str(f))
            slot = lambda n: 'eth1/'+str((n-1)//4+1)+'/'+str((n-1)%4+1)
            ends,value,rate,capacity,available = links.get(pair, ([(pair[0]+'-switch',slot(f)),(pair[1]+'-switch',slot(v))],normal,1000000000,100000000000,None))
            edits = {interfaces[e] for e in ends if e in interfaces}
            require(len(edits) <= 1,'conflicting logical endpoint overrides')
            if edits:
                value = edits.pop()
            emit('demo_mesh_status',{'vcc':raw_unit(pair[0]),'fsp':raw_unit(pair[1])},value)
            if mock:
                emit('demo_mesh_capacity_bps',{'vcc':raw_unit(pair[0]),'fsp':raw_unit(pair[1])},capacity)
                # Synthetic available headroom is distinct from configured line rate
                # and traffic. A down link has no available capacity; missing states
                # must never look like a measured zero or a healthy percentage.
                if value < 3:
                    healthy = available if available is not None else 45 + ((v-1)*17 + (f-1)*23) % 56
                    emit('demo_mesh_available_capacity_percent',{'vcc':raw_unit(pair[0]),'fsp':raw_unit(pair[1])},0 if value == 2 else healthy)
            for e,peer in (ends,ends[::-1]):
                require(e not in seen,'duplicate interface endpoint')
                seen.add(e)
                peers[e] = (peer,value,rate,capacity)
    # Explicit mock gauges avoid counter resets or invented traffic history.
    lines.extend(["# TYPE demo_interface_rate_bytes_per_second gauge", "# TYPE demo_interface_errors_per_second gauge", "# TYPE demo_interface_drops_per_second gauge"])
    for switch in sorted(SWITCHES):
        source = raw_unit(switch.removesuffix('-switch'))+'-switch'
        emit('demo_switch_status',{'source':source},switches.get(switch,normal))
        member_statuses = [switches.get(switch,normal)]
        if mock:
            emit('nexus_ch_tempValue',{'source':source,'sensor':'synthetic chassis','provenance':'synthetic demo'},35)
            emit('nexus_ch_volt',{'source':source,'sensor':'synthetic psu','provenance':'synthetic demo'},12)
            emit('demo_switch_fan_rpm',{'source':source,'provenance':'synthetic demo'},4000)
        for port in range(1,33):
            hardware = {'source':source,'port':str(port)}
            emit('demo_port_status',hardware,ports.get((switch,str(port)),normal))
            emit('demo_transceiver_status',hardware,optics.get((switch,str(port)),normal))
            member_statuses.extend((ports.get((switch,str(port)),normal),optics.get((switch,str(port)),normal)))
            if mock:
                for metric,value in [('demo_optic_temperature_celsius',32),('demo_optic_voltage_volts',3.3),('demo_optic_rx_dbm',-2),('demo_optic_tx_dbm',-1)]:
                    emit(metric,{**hardware,'provenance':'synthetic demo'},value)
            for lane in range(1,5):
                interface = f'eth1/{port}/{lane}'
                peer,value,rate,capacity = peers.get((switch,interface), ((f'demo-peer-{switch}-{port}-{lane}','demo0'),interfaces.get((switch,interface),normal),1000000000,100000000000))
                labels = {'source':source,'interface':interface}
                emit('demo_interface_status',labels,value)
                member_statuses.append(value)
                emit('nexus_interfaces_vdcId',{**labels,'operSt':'up' if value < 2 else 'down' if value == 2 else 'unknown','provenance':'synthetic demo'},1)
                peer_switch = raw_unit(peer[0].removesuffix('-switch'))+'-switch' if peer[0] in SWITCHES else peer[0]
                emit('nexus_lldp_id',{**labels,'sysName':peer_switch,'portId':peer[1],'provenance':'synthetic demo'},1)
                if mock:
                    for direction in ('In','Out'):
                        emit('demo_interface_rate_bytes_per_second',{**labels,'dn':'sys/demo/dbgIfHC'+direction,'provenance':'synthetic demo'},rate/8 if value < 2 else 0)
                    for metric in ('demo_interface_errors_per_second','demo_interface_drops_per_second'):
                        emit(metric,{**labels,'provenance':'synthetic demo'},0)
                    emit('demo_interface_capacity_bps',{**labels,'provenance':'synthetic demo'},capacity)
                emit('demo_vlan_membership',{'Unit':switch.removesuffix('-switch'),'interface':interface,'vlan':'55','Deployment':'ok','Allowed_VLANs':'55 (synthetic demo)','provenance':'synthetic demo'},1)
        # Known failures take priority over missing telemetry. Keep the independent
        # chassis/port/QSFP metrics intact while the rack summarizes operations.
        overall = next(s for s in (2,1,3,4,0) if s in member_statuses)
        emit('demo_switch_operational_status',{'source':source},overall)
    if mock:
        for switch in sorted(SWITCHES):
            emit('demo_vlan_translation',{'Unit':switch.removesuffix('-switch'),'vlan':'55','From':'55','To':'155','Provenance':'synthetic demo'},1)
    return '\n'.join(lines)+'\n'


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/metrics':
            self.send_error(404)
            return
        try:
            # Bounded file size and single HTTP worker keep invalid/slow edits bounded.
            with self.server.source.open('rb') as source:
                raw = source.read(2_000_001)
            require(len(raw) <= 2_000_000, 'source exceeds 2MB')
            def unique(pairs):
                obj = {}
                for key,value in pairs:
                    require(key not in obj, 'duplicate JSON key')
                    obj[key] = value
                return obj
            payload = render(json.loads(raw, object_pairs_hook=unique)).encode()
            code = 200
        except (ValueError, TypeError, KeyError, OSError, AttributeError, OverflowError) as exc:
            payload = ('invalid scenarios.json: '+str(exc)+'\n').encode()
            code = 503
        self.send_response(code)
        self.send_header('Content-Type','text/plain; version=0.0.4; charset=utf-8')
        self.send_header('Content-Length',str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=Path('/data/scenarios.json'))
    parser.add_argument('--port',type=int,default=9100)
    args = parser.parse_args()
    server = HTTPServer(('0.0.0.0',args.port),Handler)
    server.source = args.source
    server.serve_forever()

if __name__ == '__main__':
    main()
