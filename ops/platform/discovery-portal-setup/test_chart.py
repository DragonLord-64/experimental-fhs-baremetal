"""Offline chart contracts. Runtime acceptance remains a separate supervisor check."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
import yaml

ROOT = Path(__file__).resolve().parents[3]
CHART = ROOT / 'platform/charts/fhs-platform'


def render(prefix='', discovery=False, chart=CHART, extra=()):
    result = subprocess.run(['helm', 'template', 'discovery', str(chart), '--namespace',
        'fhs-discovery-portal-test', '--set-string', 'global.urlPrefix='+prefix,
        '--set', 'global.discovery.enabled='+str(discovery).lower(), *extra],
        text=True, capture_output=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return [o for o in yaml.safe_load_all(result.stdout) if o]


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.external=[]
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag == 'a': self.links.append(attrs['href'])
        for attr in ('src', 'href'):
            if attrs.get(attr, '').startswith(('http:', 'https:', '//')):
                self.external.append(attrs[attr])


class ChartTest(unittest.TestCase):
    def test_landing_paths_local_assets_and_accessible_content(self):
        for prefix in ('', '/mid-cbf-hw', '/nested/hw/', '/nested/hw'):
            objects=render(prefix)
            cm=next(o for o in objects if o['kind']=='ConfigMap' and 'config.json' in o.get('data',{}))
            import importlib.util
            spec=importlib.util.spec_from_file_location('landing', CHART/'files/landing/server.py')
            runtime=importlib.util.module_from_spec(spec); spec.loader.exec_module(runtime)
            html=runtime.page(json.loads(cm['data']['config.json'])).decode(); parser=Links(); parser.feed(html)
            clean=prefix.rstrip('/')
            self.assertEqual([clean+'/'+p+'/' for p in ('netbox','grafana','mid-cbf-kibana')], parser.links)
            self.assertEqual([],parser.external)
            self.assertIn('lang="en"',html); self.assertIn('aria-label=',html)
            self.assertIn('focus-visible',html); self.assertNotIn('password',html.lower())
            ingress=next(o for o in objects if o['kind']=='Ingress')
            paths=ingress['spec']['rules'][0]['http']['paths']
            self.assertEqual(clean+'/',paths[-1]['path'])
            self.assertTrue(paths[-1]['backend']['service']['name'].endswith('-hw-landing'))

    def test_discovery_filtered_authenticated_and_labels_survive(self):
        objects=render('/nested/hw/',True)
        cm=next(o for o in objects if o['kind']=='ConfigMap' and o['metadata']['name']=='fhs-prometheus')
        config=yaml.safe_load(cm['data']['prometheus.yml'])
        jobs={j['job_name']:j for j in config['scrape_configs']}
        for name,port,choice in [('node-netbox',9100,'node'),('fhs-netbox',9110,'fhs')]:
            job=jobs[name]; sd=job['http_sd_configs'][0]
            self.assertIn('/nested/hw/netbox/api/plugins/prometheus-sd/devices/?status=active&cf_prometheus_exporters='+choice,sd['url'])
            self.assertEqual({'type':'Token','credentials_file':'/etc/netbox-discovery/token'},sd['authorization'])
            from urllib.parse import urlsplit
            netbox_config="\n".join(value for o in objects if o["kind"]=="ConfigMap" and o["metadata"]["name"].startswith("fhs-netbox") for value in o.get("data",{}).values())
            self.assertTrue(urlsplit(sd["url"]).hostname in netbox_config, 'NetBox must permit the discovery service hostname')
            rules=job['relabel_configs']
            self.assertIn({'source_labels':['__meta_netbox_status'],'regex':'active','action':'keep'},rules)
            self.assertTrue(any(r.get('target_label')=='__address__' and r['replacement']=='${1}:'+str(port) for r in rules))
            self.assertTrue({'node_name','device','site','role'} <= {r.get('target_label') for r in rules})
        off=render(discovery=False)
        cm=next(o for o in off if o['kind']=='ConfigMap' and o['metadata']['name']=='fhs-prometheus')
        self.assertNotIn('http_sd_configs',cm['data']['prometheus.yml'])
        self.assertIn('192.168.8.31:9100',cm['data']['prometheus.yml'])

    def test_tag_selection_remains_available(self):
        objects=render('/hw',True,extra=('--set','global.discovery.selector=tags'))
        cm=next(o for o in objects if o['kind']=='ConfigMap' and o['metadata']['name']=='fhs-prometheus')
        config=cm['data']['prometheus.yml']
        self.assertIn('status=active&tag=node-exporter',config)
        self.assertIn('status=active&tag=fhs-exporter',config)
        self.assertNotIn('cf_prometheus_exporters',config)

    def test_setup_only_job_and_preserve_existing_objects(self):
        objects=render(extra=('--set', 'logging.filebeatSetup.enabled=true'))
        job=next(o for o in objects if o['kind']=='Job' and '-filebeat-setup-' in o['metadata']['name'])
        self.assertEqual(900,job['spec']['activeDeadlineSeconds'])
        pod=job['spec']['template']['spec']; self.assertEqual('Never',pod['restartPolicy'])
        beat=next(c for c in pod['initContainers'] if c['name']=='filebeat-setup')
        self.assertTrue(beat['image'].endswith(':9.5.5'))
        self.assertEqual('setup',beat['args'][0]); self.assertIn('--pipelines',beat['args'])
        self.assertTrue(all('hostPath' not in v for v in pod['volumes']))
        for o in objects:
            if o['kind'] in ('Deployment','DaemonSet','StatefulSet'):
                self.assertNotIn('beats/filebeat',json.dumps(o))
        cm=next(o for o in objects if o['kind']=='ConfigMap' and 'filebeat.yml' in o.get('data',{}))
        cfg=yaml.safe_load(cm['data']['filebeat.yml'])
        self.assertEqual([],cfg['filebeat.inputs'])
        self.assertFalse(cfg['setup.template.overwrite']); self.assertFalse(cfg['setup.ilm.overwrite'])
        self.assertEqual('${ELASTIC_PASSWORD}',cfg['output.elasticsearch']['password'])
        self.assertIn('"override":false',pod['containers'][0]['args'][0])

    def test_portable_copy_and_standalone_opt_in(self):
        with tempfile.TemporaryDirectory() as folder:
            copied=Path(folder)/'platform'; shutil.copytree(CHART,copied)
            first=render('/hw',True,copied)
            def page_checksum(objects):
                return next(o['spec']['template']['metadata']['annotations']['checksum/page'] for o in objects if o['kind']=='Deployment' and o['metadata']['name'].endswith('-hw-landing'))
            content=copied/'files/landing/server.py'
            content.write_text(content.read_text().replace('<h1>HW management</h1>','<h1>Updated hardware home</h1>'))
            self.assertNotEqual(page_checksum(first),page_checksum(render('/hw',True,copied)))
        p=subprocess.run(['helm','template','logs',str(ROOT/'platform/charts/elasticsearch-kibana')],capture_output=True,text=True,check=True)
        self.assertNotIn('beats/filebeat',p.stdout)
        defaults=render()
        self.assertFalse(any('-filebeat-setup' in o['metadata']['name'] for o in defaults))
        self.assertNotIn('beats/filebeat',json.dumps(defaults))

    def test_discovery_enable_does_not_change_unrelated_templates(self):
        before=render('/hw'); after=render('/hw',True)
        def templates(objects):
            return {o['metadata']['name']:o['spec']['template'] for o in objects if o['kind'] in ('Deployment','StatefulSet')}
        self.assertEqual(templates(before),templates(after))
