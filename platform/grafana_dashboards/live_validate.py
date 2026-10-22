#!/usr/bin/env python3
"""Supervisor-only scoped Grafana import/query/browser acceptance. No kubectl writes."""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import socket
import signal
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit, parse_qs
from urllib.request import Request, urlopen

from generate import build, health, mesh_query, DEST, DEFAULT_VCC, DEFAULT_FSP

FOLDER='fhs-infra-issue2'

class API:
    def __init__(self):
        self.base=os.environ['GRAFANA_URL'].rstrip('/')
        token=os.environ.get('GRAFANA_TOKEN')
        self.auth='Bearer '+token if token else 'Basic '+base64.b64encode((os.environ['GRAFANA_USER']+':'+os.environ['GRAFANA_PASSWORD']).encode()).decode()
    def call(self,path,data=None,method=None):
        req=Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,headers={'Authorization':self.auth,'Content-Type':'application/json'},method=method)
        try:
            with urlopen(req,timeout=15) as response:return json.load(response)
        except HTTPError as error:
            raise RuntimeError(f'Grafana HTTP {error.code} for {path.split("?")[0]}') from None
    def query(self,expr):
        data=self.call('/api/datasources/proxy/uid/prometheus/api/v1/query?'+urlencode({'query':expr}))
        if data.get('status')!='success':raise RuntimeError('Prometheus query unsuccessful')
        return data['data']['result']



def owned_inventory(api, uids):
    """Bounded global search establishes ownership without a UID GET.

    Known UID GETs can also stall; search does not prove readback health.

    Search must finish before any dashboard write. Absent UIDs are always
    created with overwrite=False, so a race cannot replace another dashboard.
    """
    found={}
    for page in range(1,101):
        rows=api.call('/api/search?'+urlencode({'type':'dash-db','limit':1000,'page':page}))
        if not isinstance(rows,list):raise RuntimeError('Unexpected dashboard search response')
        for row in rows:
            uid=row.get('uid')
            if uid in uids:
                if uid in found:raise RuntimeError('Duplicate dashboard search UID')
                if row.get('folderUid')!=FOLDER:raise RuntimeError('Dashboard UID belongs to another folder: '+uid)
                found[uid]=row
        if len(rows)<1000:return found
    raise RuntimeError('Dashboard ownership search exceeded bounded inventory')


def guarded_route(route, allowed_origin, authorization=None):
    requested=urlsplit(route.request.url)
    if (requested.scheme,requested.netloc)!=(allowed_origin.scheme,allowed_origin.netloc):
        route.abort()
        return
    route.continue_()


def scalar(api,expr,expected):
    result=api.query(expr)
    values=[float(x['value'][1]) for x in result]
    assert values==expected,(expr,values,expected)
    return {'query':expr,'values':values}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--navigation-only',action='store_true',help='Read-only native navigation/capture on already imported owned dashboards; no scenario acceptance');parser.add_argument('--visual-only',action='store_true',help='Import/capture without query or navigation assertions');parser.add_argument('--import-owned',action='store_true');parser.add_argument('--browser',action='store_true');parser.add_argument('--diagnose-api',action='store_true');parser.add_argument('--capture-existing',action='store_true',help='Read-only rack screenshot attempt before API/query acceptance');parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if (args.capture_existing or args.diagnose_api) and (args.visual_only or args.import_owned or args.browser or (args.capture_existing and args.diagnose_api)):parser.error('Capture and diagnosis are separate read-only operations')
    if args.navigation_only and (args.visual_only or args.import_owned or args.browser or args.capture_existing or args.diagnose_api):parser.error('Navigation-only is a separate read-only operation')
    args.output.mkdir(parents=True,exist_ok=True);os.chmod(args.output,0o700)
    report={'host':socket.gethostname(),'timestamp':time.time(),'queries':[],'browser':[],'limitations':['Hardware behavior is emulated. No traffic generation or historical replay claimed. Physical rack positions are not discovered.']}
    api=API();dashboards=build()
    def save(): (args.output/'evidence.json').write_text(json.dumps(report,indent=2)+'\n')
    try:
        if args.diagnose_api:
            diagnose_api(api,report);save();return
        if args.capture_existing:
            capture_existing(api,args.output,report);save();return
        report['grafana']=api.call('/api/health')
        if report['grafana'].get('version')!='13.2.3':raise RuntimeError('Requires preserved Grafana 13.2.3')
        # Read-only discovery; no datasource modification.
        assert api.call('/api/datasources/uid/prometheus')['type']=='prometheus'
        jobs={}
        if not args.visual_only:
            for variable,metric in [('job','sts_psu1_fan'),('node_job','node_network_info'),('switch_job','nexus_interfaces_vdcId')]:
                observed=sorted({x['metric']['job'] for x in api.query(metric)})
                if len(observed)!=1:raise RuntimeError('Select an unambiguous lab '+variable+' before validation')
                jobs[variable]=observed[0]
        report['jobs']=jobs
        if args.navigation_only:
            owned=owned_inventory(api,{d['uid'] for d in dashboards.values()})
            if set(owned)!={d['uid'] for d in dashboards.values()}:raise RuntimeError('Navigation requires all six owned dashboards already imported')
            browser_check(api,args.output,jobs,report)
            report['status']='navigation passed; scenario/query/visual acceptance remains separate'
            save();return
        if args.import_owned:
            try:folder=api.call('/api/folders/'+FOLDER)
            except RuntimeError as error:
                if 'HTTP 404' not in str(error):raise
                folder=api.call('/api/folders',{'uid':FOLDER,'title':'FHS infrastructure issue 2'})
            inventory=owned_inventory(api,{d['uid'] for d in dashboards.values()})
            report['ownership_discovery']='bounded global dashboard search completed'
            for key,d in dashboards.items():
                exists=d['uid'] in inventory
                if exists:
                    current=api.call('/api/dashboards/uid/'+d['uid'])
                    if current['meta'].get('folderUid')!=FOLDER:raise RuntimeError('Dashboard UID ownership changed')
                    d={**d,'id':current['dashboard']['id'],'version':current['dashboard']['version']}
                # Classic schema is generated explicitly; never POST v2 captures here.
                result=api.call('/api/dashboards/db',{'dashboard':d,'folderUid':FOLDER,'overwrite':False,'message':'Scoped infrastructure dashboard validation'})
                assert result['uid']==d['uid']
                readback=api.call('/api/dashboards/uid/'+d['uid'])
                assert readback['meta']['folderUid']==FOLDER
            report['import']='owned folder only; classic API write and readback passed'
        if args.visual_only:
            visual_capture(api,args.output,report)
            report['status']='captured; independent visual review required'
            save();return
        def expand(expr,unit='FSPUnit2',fhs='FHS1',switch='VCCUnit1-switch',interface='eth1/1/3'):
            values={**jobs,'unit':unit,'fhs':fhs,'switch':switch,'interface':interface,'instance':'.*','node_instance':'.*','__rate_interval':'5m','vccu':'1','fspu':'3','port':'1','vlan':'55'}
            for key in sorted(values,key=len,reverse=True):expr=expr.replace('$'+key,values[key])
            return expr
        report['queries'].append(scalar(api,'count(up{fhs_name!="",unit="FSPUnit1"} == 0)',[4]))
        for fhs in range(1,5):
            report['queries'].append(scalar(api,expand(health('FSPUnit1',f'FHS{fhs}')),[]))
            report['queries'].append(scalar(api,f'count({{unit="FSPUnit1",fhs="FHS{fhs}",__name__=~"sts_.*|node_.*|.*temperature.*"}})',[]))
        report['queries'].append(scalar(api,expand(health('FSPUnit2')),[1]))
        report['queries'].append(scalar(api,expand('sts_psu1_fan{job="$job",unit="FSPUnit2",fhs="FHS1"}'),[1]))
        report['queries'].append(scalar(api,expand('count(sts_psu1_fan{job="$job"} != 0)'),[1]))
        report['queries'].append(scalar(api,expand('count(sts_psu2_fan{job="$job"} != 0)'),[]))
        report['queries'].append(scalar(api,expand('count(count by(unit,fhs) (sts_psu1_fan{job="$job"}))'),[12]))
        report['queries'].append(scalar(api,expand('count(count by(source) (nexus_interfaces_vdcId{job="$switch_job"}))'),[7]))
        report['queries'].append(scalar(api,expand('count(nexus_lldp_id{job="$switch_job"})'),[56]))
        for role,count in [('VCC',DEFAULT_VCC),('FSP',DEFAULT_FSP)]:
            for number in range(1,count+1):
                unit=f'{role}Unit{number}'
                expected=[] if unit=='FSPUnit1' else ([1] if unit=='FSPUnit2' else [0])
                report['queries'].append(scalar(api,expand(health(unit)),expected))
        mesh=api.query(expand(mesh_query()))
        assert len(mesh)==12,len(mesh)
        broken=[x['metric'] for x in mesh if float(x['value'][1])==0]
        assert broken==[{'vcc':'VCCUnit1','fsp':'FSPUnit3'}],broken
        assert all(float(x['value'][1]) in (0,1) for x in mesh)
        report['mesh']={'links':len(mesh),'broken':broken}
        down=api.query(expand('nexus_interfaces_vdcId{job="$switch_job",operSt="down"}'))
        assert {(x['metric']['source'],x['metric']['interface']) for x in down}=={('VCCUnit1-switch','eth1/1/3'),('FSPUnit3-switch','eth1/1/1')}
        for source,interface,peer,remote in [('VCCUnit1-switch','eth1/1/3','FSPUnit3-switch','eth1/1/1'),('FSPUnit3-switch','eth1/1/1','VCCUnit1-switch','eth1/1/3')]:
            report['queries'].append(scalar(api,f'nexus_lldp_id{{source="{source}",interface="{interface}",sysName="{peer}",portIdV="{remote}"}}',[1]))
        # Execute every generated panel query, including query syntax and response envelope.
        for d in dashboards.values():
            for p in d['panels']:
                for t in p.get('targets',[]):api.query(expand(t['expr']))
        report['all_panel_queries']='executed successfully (nonempty not required for missing hosts)'
        save()
        if args.browser:browser_check(api,args.output,jobs,report)
        report['status']='passed';save()
    except Exception as error:
        # Never include response bodies, headers, cookies or credential-bearing URLs.
        report['status']='failed';report['error_type']=type(error).__name__;save();raise


def diagnose_api(api, report):
    """Bounded read-only comparison; never retain API bodies or exception messages."""
    report['grafana']=api.call('/api/health')
    if report['grafana'].get('version')!='13.2.3':
        raise RuntimeError('Diagnosis requires exact Grafana 13.2.3')
    uid=DEST['rack'][1]
    if uid not in owned_inventory(api,{uid}):
        raise RuntimeError('Existing owned rack not found; no UID probes attempted')
    report['api_probes']=[]
    for suffix in ('','?apiVersion=v1'):
        started=time.monotonic()
        probe={'route':'owned rack legacy GET'+suffix}
        try:
            data=api.call('/api/dashboards/uid/'+uid+suffix)
            probe['valid_owned_dashboard']=(data.get('dashboard',{}).get('uid')==uid and data.get('meta',{}).get('folderUid')==FOLDER)
        except Exception as error:
            probe['error_type']=type(error).__name__
        probe['elapsed_seconds']=round(time.monotonic()-started,3)
        report['api_probes'].append(probe)
    report['status']='diagnosed; no import or acceptance'


def cookie_login(context, api):
    if not os.environ.get('GRAFANA_USER') or not os.environ.get('GRAFANA_PASSWORD'):
        raise RuntimeError('Browser capture requires cookie login credentials')
    response=context.request.post(api.base+'/login',data={'user':os.environ['GRAFANA_USER'],'password':os.environ['GRAFANA_PASSWORD']},max_redirects=0,timeout=15000)
    if not response.ok: raise RuntimeError('Cookie login failed')


def visual_capture(api, output, report):
    """Six actual browser captures; no query, data or rename gates."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        try:
            context=browser.new_context(viewport={'width':1920,'height':1200},service_workers='block')
            context.route('**/*',lambda route: guarded_route(route,urlsplit(api.base),None))
            cookie_login(context,api)
            page=context.new_page()
            page.set_default_timeout(15000)
            for key,(_,uid) in DEST.items():
                entry={'view':key,'navigation':'domcontentloaded','review':'pending'}
                try:
                    page.goto(api.base+'/d/'+uid+'?'+urlencode({'var-ds':'prometheus','var-unit':'FSPUnit2','var-fhs':'FHS1','var-switch':'VCCUnit1-switch','var-interface':'eth1/1/3','var-instance':'All','var-node_instance':'All'}),wait_until='domcontentloaded',timeout=20000)
                except Exception:
                    entry['navigation']='incomplete; inspect loading/error state'
                page.wait_for_timeout(3000)
                try:
                    page.screenshot(path=str(output/(key+'.png')),timeout=15000,full_page=True)
                    entry['capture']='actual browser page'
                except Exception as error:
                    entry['capture']='failed';entry['error_type']=type(error).__name__
                entry['login_screen']='/login' in page.url
                report['browser'].append(entry)
                (output/'evidence.json').write_text(json.dumps(report,indent=2)+'\n')
                sections={'rack':[('Rack 7 · 42U front','rack-lower')],'fhs':[('PSU 1 · readings','fhs-psu1'),('PSU 2 · readings','fhs-psu2')],
                          'switch':[('Chassis temperature','switch-hardware'),('Last-known LLDP neighbors','switch-lldp')],
                          'interface':[('LLDP diagnostics','interface-lldp-diagnostics')]}
                for title,filename in sections.get(key,[]):
                    section={'view':key,'section':title,'review':'pending'}
                    try:
                        page.get_by_text(title,exact=True).first.scroll_into_view_if_needed(timeout=5000)
                        page.wait_for_timeout(1000)
                        page.screenshot(path=str(output/(filename+'.png')),timeout=10000)
                        section['capture']='actual viewport'
                    except Exception as error:
                        section['capture']='failed';section['error_type']=type(error).__name__
                    report['browser'].append(section)

        finally:
            browser.close()
    report['screenshots']='Actual Grafana browser captures; NoData allowed; loading/error/login is not a rendering pass'


def capture_existing(api, output, report):
    """Capture the existing rack, including a loading/error state; no acceptance claim."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        try:
            context=browser.new_context(viewport={'width':1920,'height':1200},service_workers='block')
            context.route('**/*',lambda route: guarded_route(route,urlsplit(api.base),api.auth))
            cookie_login(context,api)
            page=context.new_page()
            page.set_default_timeout(15000)
            report['navigation']='domcontentloaded'
            try:
                page.goto(api.base+'/d/'+DEST['rack'][1],wait_until='domcontentloaded',timeout=20000)
            except Exception:
                report['navigation']='incomplete; capture may show a loading/error state'
            page.wait_for_timeout(5000)
            page.screenshot(path=str(output/'existing-rack-before-acceptance.png'),timeout=15000)
            report['status']='captured_before_acceptance'
            report['screenshots']='Existing rack browser state only; inspect image, no query or rendering acceptance'
        finally:
            browser.close()


def browser_check(api,output,jobs,report):
    """Real native clicks; fail closed when destination/context is not preserved."""
    import re
    from playwright.sync_api import sync_playwright
    common={'var-ds':'prometheus','var-instance':'All','var-node_instance':'All',**{'var-'+k:v for k,v in jobs.items()},'var-unit':'FSPUnit2','var-fhs':'FHS1','var-switch':'VCCUnit1-switch','var-interface':'eth1/1/3','var-vccu':'1','var-fspu':'3','from':'now-15m','to':'now'}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        try:
            context=browser.new_context(viewport={'width':1440,'height':1000},service_workers='block')
            context.route('**/*',lambda route:guarded_route(route,urlsplit(api.base)))
            cookie_login(context,api);page=context.new_page()

            def check(view, selected=None):
                def destination(url):
                    params=parse_qs(urlsplit(url).query)
                    return '/d/'+DEST[view][1] in url and all(params.get(k)==[v] for k,v in (selected or {}).items())
                page.wait_for_url(destination,timeout=10000)
                actual=parse_qs(urlsplit(page.url).query)
                for key,value in {'var-ds':'prometheus','from':'now-15m','to':'now',**{'var-'+k:v for k,v in jobs.items()},**(selected or {})}.items():
                    assert actual.get(key)==[value], 'Navigation context mismatch: '+key
                page.wait_for_timeout(2000)

            def open_view(view, **selected):
                page.goto(api.base+'/d/'+DEST[view][1]+'?'+urlencode({**common,**selected}),wait_until='domcontentloaded')
                check(view,selected)

            def click(locator,view,selected,label,menu=None):
                locator.click(timeout=8000)
                if menu:
                    try:
                        page.wait_for_url(lambda url: '/d/'+DEST[view][1] in url and all(parse_qs(urlsplit(url).query).get(k)==[v] for k,v in selected.items()),timeout=1500)
                    except Exception:
                        page.get_by_text(menu,exact=True).last.click(timeout=8000)
                check(view,selected)
                page.screenshot(path=str(output/(label+'.png')))
                report['browser'].append({'path':label,'passed':True})

            def back(view,selected,label):
                page.go_back(wait_until='domcontentloaded');check(view,selected)
                report['browser'].append({'path':label,'passed':True})

            open_view('rack')
            click(page.get_by_text(re.compile(r'^fspu2-fhs1 · ')).first,'fhs',{'var-unit':'FSPUnit2','var-fhs':'FHS1'},'rack-to-fhs')
            back('rack',{},'fhs-return-rack')
            click(page.get_by_text(re.compile(r'^vccu1-switch · ')).first,'switch',{'var-switch':'VCCUnit1-switch'},'rack-to-switch')
            back('rack',{},'switch-return-rack')

            open_view('mesh')
            click(page.get_by_role('link',name='Open selected vccu switch',exact=True),'switch',{'var-switch':'VCCUnit1-switch','var-unit':'VCCUnit1'},'mesh-destination')
            back('mesh',{},'switch-return-mesh')

            open_view('switch')
            # Separate visible lane identity survives compact status mappings.
            click(page.get_by_text('L3',exact=True).first,'interface',{'var-interface':'eth1/1/3','var-switch':'VCCUnit1-switch'},'switch-to-interface')
            click(page.locator('a[data-testid="data-testid Data link"]').filter(has_text=re.compile(r'^fspu3-switch$')).first,'interface',{'var-switch':'FSPUnit3-switch','var-interface':'eth1/1/1','var-unit':'FSPUnit3'},'peer-opposite-endpoint',menu='Open Last-known peer')
            back('interface',{'var-switch':'VCCUnit1-switch','var-interface':'eth1/1/3'},'peer-return-interface')
            back('switch',{'var-switch':'VCCUnit1-switch'},'interface-return-switch')

            captures=[(view,{},view) for view in DEST]
            captures += [('switch',{'var-switch':'FSPUnit3-switch'},'switch-fspu3-fault'),('switch',{'var-switch':'VCCUnit1-switch'},'switch-vccu1-fault'),('fhs',{'var-unit':'FSPUnit1','var-fhs':'FHS1'},'fspu1-missing'),('fhs',{'var-unit':'FSPUnit2','var-fhs':'FHS1'},'fspu2-degraded')]
            for view,selected,name in captures:
                open_view(view,**selected)
                page.screenshot(path=str(output/(name+'.png')),full_page=True)
                report['browser'].append({'path':'capture '+name,'passed':True})
        finally:browser.close()


if __name__=='__main__':
    def deadline(signum, frame):
        raise SystemExit('Bounded supervisor deadline reached')
    signal.signal(signal.SIGALRM,deadline)
    signal.alarm(540)
    try:
        main()
    except Exception as error:
        # Keep credential-bearing Playwright request logs out of stdout/stderr.
        print('Validation failed: '+type(error).__name__+'; inspect nonsecret evidence.json status')
        raise SystemExit(1) from None
