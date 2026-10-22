#!/usr/bin/env python3
"""Bounded supervisor runner. Never invoked by the sandboxed implementation worker.

Only three unique owned Compose projects, relative portable mounts, no image deletion.
Browser tooling is supplied by the supervisor via NODE_PATH, not by demo launch.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import time
import urllib.parse
import urllib.request
import zipfile

SOURCE = Path(__file__).resolve().parents[1]


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--operation', required=True)
    parser.add_argument('--artifacts', type=Path, required=True)
    args = parser.parse_args()
    assert re.fullmatch(r'[a-z0-9]{8,20}', args.operation), 'unique operation token required'
    output = args.artifacts.resolve()
    assert output == Path('/tmp') / ('fhs-static-accept-'+args.operation), 'owned artifact path required'
    assert not output.exists(), 'do not overwrite previous evidence'
    output.mkdir()
    start = time.monotonic()
    report = {'operation':args.operation,'source_sha256':hashes(SOURCE),'checks':{}}
    owned = []
    log = (output/'commands.log').open('w')

    def run(argv, cwd=None, env=None, timeout=180, check=True):
        assert time.monotonic()-start < 1700, 'runner deadline exceeded'
        log.write(json.dumps(argv)+'\n');log.flush()
        result = subprocess.run(argv,cwd=cwd,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
        log.write(result.stdout+'\n');log.flush()
        if check and result.returncode:
            raise AssertionError(f'command failed ({result.returncode}): {argv[0:4]}: {result.stdout[-2000:]}')
        return result

    def compose(folder, project, *argv, check=True):
        env = {**os.environ,'COMPOSE_PROJECT_NAME':project,'GRAFANA_PORT':str(13081 if project.endswith('-zip') else 13080)}
        return run(['docker','compose','-p',project,'-f',str(folder/'compose.yaml'),*argv],cwd=folder,env=env,check=check)

    def fresh(folder, suffix):
        project = 'fhs-static-accept-'+args.operation+'-'+suffix
        assert not run(['docker','ps','-aq','--filter','label=com.docker.compose.project='+project]).stdout.strip(), 'preexisting project'
        assert not run(['docker','volume','ls','-q','--filter','label=com.docker.compose.project='+project]).stdout.strip(), 'preexisting project volumes'
        owned.append((folder,project))
        return project

    def launch(folder, project, expected=True):
        env = {**os.environ,'COMPOSE_PROJECT_NAME':project,'GRAFANA_PORT':str(13081 if project.endswith('-zip') else 13080)}
        result = run(['sh','./launch.sh'],cwd=folder,env=env,timeout=420,check=expected)
        if not expected:
            assert result.returncode and 'port' in result.stdout.lower(), 'occupied-port explanation missing'
        return result

    def http(base, path):
        with urllib.request.urlopen(base+path,timeout=30) as response:
            return json.load(response)

    def query(base, expr):
        value = http(base,'/api/datasources/proxy/uid/prometheus/api/v1/query?'+urllib.parse.urlencode({'query':expr}))
        assert value['status']=='success', value
        return value['data']['result']

    def number(base, expr, expected):
        result = query(base,expr)
        assert len(result)==1 and float(result[0]['value'][1])==expected, (expr,result,expected)

    def wait_number(base,expr,expected):
        deadline=time.monotonic()+45
        while True:
            result=query(base,expr)
            if len(result)==1 and float(result[0]['value'][1])==expected:
                return
            assert time.monotonic()<deadline,(expr,result,expected)
            time.sleep(2)

    def identity(folder,project):
        ids=compose(folder,project,'ps','-q').stdout.split()
        assert len(ids)==3,ids
        info=json.loads(run(['docker','inspect',*ids]).stdout)
        assert all(c['Config']['Labels']['com.docker.compose.project']==project for c in info)
        return {c['Id']:(c['State']['StartedAt'],c['RestartCount']) for c in info}

    def browser(base, phase):
        run(['node',str(SOURCE/'tests/browser_check.cjs'),base,str(output/'screenshots'),phase],timeout=360)

    before=set(run(['docker','ps','-q']).stdout.split())
    try:
        copy=output/'outside-checkout'/'grafana-static-demo'
        shutil.copytree(SOURCE,copy,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        assert hashes(copy)==hashes(SOURCE)
        project=fresh(copy,'copy')
        config=json.loads(compose(copy,project,'config','--format','json').stdout)
        services=config['services']
        assert set(services)=={'grafana','prometheus','exporter'}
        assert services['grafana']['image']=='grafana/grafana:13.2.3'
        assert services['prometheus']['image']=='prom/prometheus:v3.15.0'
        for name,limit in [('grafana',768),('prometheus',256),('exporter',64)]:
            service=services[name]
            assert int(service['mem_limit'])==limit*1024*1024
            assert not service.get('privileged') and service.get('network_mode')!='host'
            assert not service.get('devices')
            if name!='grafana': assert not service.get('ports')
            for volume in service.get('volumes',[]):
                assert 'docker.sock' not in volume['target']
                if volume['type']=='bind':assert Path(volume['source']).resolve().is_relative_to(copy)
        assert services['grafana']['ports'][0]['host_ip']=='127.0.0.1'
        report['checks']['compose_config_passed']=True
        launch(copy,project)
        base='http://127.0.0.1:13080'
        assert http(base,'/api/health')['database']=='ok'
        original_identity=identity(copy,project)
        report['checks']['compose_build_up_ready']=True
        # Allow initial scrapes; query every target using real PromQL.
        time.sleep(12)
        dashboard_evidence=[]
        for file in sorted((copy/'grafana/dashboards').glob('*.json')):
            expected=json.loads(file.read_text())
            actual=http(base,'/api/dashboards/uid/'+expected['uid'])['dashboard']
            for key in ('uid','title','links','panels','templating'):
                assert actual[key]==expected[key],(file.name,key)
            variables={v['name']:v['current']['value'] for v in expected['templating']['list']}
            variables.update({'__rate_interval':'30s','node_instance':'.*','instance':'.*'})
            queried=[]
            for panel in actual['panels']:
                for target in panel.get('targets',[]):
                    expr=target.get('expr','')
                    for key in sorted(variables,key=len,reverse=True):
                        expr=expr.replace('${'+key+'}',str(variables[key])).replace('$'+key,str(variables[key]))
                    assert '$' not in re.sub(r'"[^"\n]*"','""',expr),expr
                    result=query(base,expr)
                    queried.append({'panel':panel['id'],'refId':target['refId'],'expr':expr,'series':len(result)})
                    # The source FSPU2 view and all switch/mesh/VLAN defaults must have data.
                    assert result,(file.name,panel['id'],expr)
            dashboard_evidence.append({'uid':actual['uid'],'targets':queried})
        (output/'dashboard-queries.json').write_text(json.dumps(dashboard_evidence,indent=2))
        report['checks']['six_dashboards_passed']=True
        for metric,count in [('demo_server_status',132),('demo_component_status',2772),('demo_switch_status',51),('demo_mesh_status',648),('demo_interface_status',6528),('demo_port_status',1632),('demo_transceiver_status',1632)]:
            number(base,'count('+metric+')',count)
        number(base,'count(demo_server_status == 3)',4)
        number(base,'count(demo_component_status == 3)',84)
        for metric in ('demo_switch_status','demo_mesh_status','demo_interface_status','demo_port_status','demo_transceiver_status'):
            number(base,'count('+metric+' >= 3) or vector(0)',0)
        mesh='demo_mesh_status{vcc="VCCUnit1",fsp="FSPUnit3"}'
        left='demo_interface_status{source="VCCUnit1-switch",interface="eth1/1/3"}'
        right='demo_interface_status{source="FSPUnit3-switch",interface="eth1/1/1"}'
        server='demo_server_status{unit="FSPUnit2",fhs="FHS1"}'
        psu='demo_component_status{unit="FSPUnit2",fhs="FHS1",component="psu1"}'
        port='demo_port_status{source="VCCUnit1-switch",port="1"}'
        optic='demo_transceiver_status{source="VCCUnit1-switch",port="1"}'
        for expr,value in [(mesh,2),(left,2),(right,2),(server,1),(psu,2),(port,0),(optic,0)]:number(base,expr,value)
        number(base,'count(cpu_temperature_celcius)',128)
        for status,count in [(0,647),(2,1),(3,0),(4,0)]:
            number(base,f'count(demo_mesh_status == {status}) or vector(0)',count)
        number(base,'count(demo_vlan_translation)',51)
        number(base,'max(demo_interface_capacity_bps) / 1e9',100)
        number(base,'max(demo_optic_temperature_celsius)',32)
        number(base,'max(demo_optic_voltage_volts)',3.3)
        def bounded_rates(expected):
            for source,interface in [('VCCUnit1-switch','eth1/1/3'),('FSPUnit3-switch','eth1/1/1')]:
                selector='{source="'+source+'",interface="'+interface+'"}'
                wait_number(base,'max(demo_interface_rate_bytes_per_second'+selector+') * 8',expected)
            number(base,'count((demo_interface_rate_bytes_per_second * 8) > on(source,interface) group_left demo_interface_capacity_bps) or vector(0)',0)
        bounded_rates(0)
        report['checks']['numeric_counts_units_and_bounded_rates_passed']=True
        report['checks']['scenario_queries_passed']=True
        browser(base,'all')
        report['checks']['browser_screenshots_passed']=True
        source=copy/'scenarios.json';original=source.read_text();data=json.loads(original)
        def save(value):
            temporary=source.with_suffix('.next');temporary.write_text(json.dumps(value));temporary.replace(source)
        data['servers']['fspu2-fhs1']['status']='ok'
        data['servers']['fspu2-fhs1']['components']['psu1']='ok'
        data['links'][2]['status']='ok'
        save(data)
        for expr in (server,psu,mesh,left,right):wait_number(base,expr,0)
        bounded_rates(1000000000)
        browser(base,'ok')
        # Fault the parent hardware while the logical link and QSFP stay healthy.
        data['physical_ports']={'vccu1-switch':{'1':'fault'}};save(data)
        wait_number(base,port,2);number(base,optic,0);number(base,left,0);number(base,mesh,0)
        browser(base,'port-independent')
        source.write_text(original)
        for expr,value in [(server,1),(psu,2),(mesh,2),(left,2),(right,2),(port,0)]:wait_number(base,expr,value)
        bounded_rates(0)
        browser(base,'back')
        assert identity(copy,project)==original_identity,'edit caused restart/recreation'
        report['checks']['edit_roundtrip_passed']=True
        source.write_text('{')
        exporter_http=compose(copy,project,'exec','-T','exporter','python','-c',
            'import urllib.request,urllib.error;\ntry: urllib.request.urlopen("http://127.0.0.1:9100/metrics")\nexcept urllib.error.HTTPError as e: print(e.code,e.read().decode()); assert e.code==503\nelse: raise AssertionError("invalid source accepted")').stdout
        assert '503 invalid scenarios.json:' in exporter_http
        wait_number(base,'up{job="static-demo"}',0)
        assert not query(base,psu),'stale data after failed scrape'
        source.write_text(original)
        wait_number(base,'up{job="static-demo"}',1);wait_number(base,psu,2)
        assert identity(copy,project)==original_identity
        report['checks']['invalid_config_recovery_passed']=True
        launch(copy,project)
        assert identity(copy,project)==original_identity
        report['checks']['launch_idempotence_passed']=True
        report['checks']['outside_copy_passed']=True
        # A separate owned project fails on the first project's occupied port.
        collision=fresh(copy,'collision')
        launch(copy,collision,expected=False)
        assert http(base,'/api/health')['database']=='ok'
        assert identity(copy,project)==original_identity
        report['checks']['occupied_port_isolation_passed']=True
        compose(copy,collision,'down','--volumes',check=True)
        archive=output/'grafana-static-demo.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for name in hashes(copy):z.write(copy/name,'grafana-static-demo/'+name)
        extracted=output/'zip-extracted'
        with zipfile.ZipFile(archive) as z:z.extractall(extracted)
        folder=extracted/'grafana-static-demo'
        # Python zipfile does not restore executable modes; ordinary unzip does.
        with zipfile.ZipFile(archive) as z:
            for entry in z.infolist():
                if entry.external_attr>>16: (extracted/entry.filename).chmod(entry.external_attr>>16)
        assert os.access(folder/'launch.sh',os.X_OK)
        assert hashes(folder)==hashes(SOURCE)
        zipped=fresh(folder,'zip');launch(folder,zipped)
        zipbase='http://127.0.0.1:13081'
        time.sleep(10);number(zipbase,mesh,2);number(zipbase,psu,2)
        assert len(http(zipbase,'/api/search?type=dash-db'))==6
        report['checks']['zip_extract_launch_passed']=True
        report['zip']={'path':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
    finally:
        cleaned=True
        for folder,project in reversed(owned):
            try:
                compose(folder,project,'logs','--no-color','--tail','80',check=False)
                compose(folder,project,'down','--volumes')
                assert not run(['docker','ps','-aq','--filter','label=com.docker.compose.project='+project]).stdout.strip()
                assert not run(['docker','volume','ls','-q','--filter','label=com.docker.compose.project='+project]).stdout.strip()
                assert not run(['docker','network','ls','-q','--filter','label=com.docker.compose.project='+project]).stdout.strip()
            except Exception as error:
                cleaned=False;log.write('cleanup: '+str(error)+'\n')
        assert before <= set(run(['docker','ps','-q']).stdout.split()),'preexisting service stopped'
        report['checks']['owned_cleanup_passed']=cleaned
        report['elapsed_seconds']=round(time.monotonic()-start,2)
        (output/'runtime-evidence.json').write_text(json.dumps(report,indent=2))
        log.close()
        assert cleaned,'owned cleanup failed'
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
