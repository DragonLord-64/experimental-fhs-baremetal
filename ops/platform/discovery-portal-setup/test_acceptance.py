"""Safety and preservation regressions for supervised live acceptance."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('live_acceptance',Path(__file__).with_name('acceptance.py'))
live=importlib.util.module_from_spec(spec);spec.loader.exec_module(live)


class AcceptanceTest(unittest.TestCase):
    def test_production_contexts_and_namespaces_are_rejected(self):
        live.validate_scope('fhs-test','fhs-discovery-portal-test')
        for context,namespace in [('monitoring','fhs-discovery-portal-test'),('fhs-test','hw-management'),('fhs-test','default')]:
            with self.assertRaises(ValueError):live.validate_scope(context,namespace)

    def test_inventory_comparison_ignores_only_forwarded_origin(self):
        before={'serial':'physical-123','status':'stored','url':'http://127.0.0.1:40001/mid-cbf-hw/netbox/api/plugins/inventory/assets/5/',
                'nested':[{'url':'http://127.0.0.1:40001/mid-cbf-hw/netbox/api/dcim/devices/2/'}]}
        after=json.loads(json.dumps(before).replace('40001','45002'))
        self.assertEqual(live.digest(live.stable_api(before)),live.digest(live.stable_api(after)))
        for field,value in [('serial','different-identity'),('status','faulty')]:
            changed=dict(after,**{field:value})
            self.assertNotEqual(live.digest(live.stable_api(before)),live.digest(live.stable_api(changed)))
        self.assertEqual('https://example.invalid/asset/5',live.stable_api('https://example.invalid/asset/5'))

    def test_bootstrap_secret_is_stdin_only(self):
        acceptance=object.__new__(live.Acceptance)
        acceptance.credentials={'api_token':'fixture-secret-do-not-put-in-process-arguments'}
        acceptance.evidence={};calls=[]
        acceptance.kubectl=lambda *args,**kwargs:calls.append((args,kwargs))
        acceptance.ensure_admin_api()
        self.assertEqual(1,len(calls))
        args,kwargs=calls[0]
        self.assertNotIn(acceptance.credentials['api_token'],str(args))
        self.assertEqual({'token':acceptance.credentials['api_token']},kwargs['obj'])

    def test_a_successful_or_foreign_report_cannot_authorize_resume(self):
        for status,context in [('passed','fhs-test'),('failed','monitoring')]:
            with tempfile.TemporaryDirectory() as folder:
                acceptance=object.__new__(live.Acceptance)
                acceptance.path=Path(folder)/'report.json'
                acceptance.path.write_text(json.dumps({'status':status,'context':context,
                    'namespace':'fhs-discovery-portal-test','checks':{'baseline':{}}}))
                acceptance.kubectl=lambda *a,**k:self.fail('Kubernetes must not be contacted')
                with self.assertRaises(AssertionError):acceptance.execute(resume=True)

    def test_routes_resolve_relative_assets_against_the_application_base(self):
        from contextlib import contextmanager
        acceptance=object.__new__(live.Acceptance)
        captured={};fetched=[]
        @contextmanager
        def forward(service,port):
            yield 'http://'+service+':'+str(port)
        def request(url,**kwargs):
            fetched.append(url)
            if url.startswith('http://127.0.0.1'):return '<html>Ingress</html>'
            if 'hw-landing' in url:
                return ''.join('<a href="'+live.PREFIX+'/'+p+'/">'+p+'</a>' for p in ('netbox','grafana','mid-cbf-kibana'))
            for app in ('netbox','grafana','mid-cbf-kibana'):
                if url.endswith('/'+app+'/'):
                    return '<base href="'+live.PREFIX+'/'+app+'/"><script src="public/app.js"></script>'
            return 'Asset body'
        acceptance.forward=forward
        acceptance.record=lambda name,details:captured.update({name:details})
        with patch.object(live,'run',return_value=b'127.0.0.1'),patch.object(live,'request',side_effect=request):
            acceptance.routes()
        expected=live.PREFIX+'/grafana/public/app.js'
        self.assertEqual(expected,captured['routes']['grafana']['asset_fetched'])
        self.assertIn('http://fhs-grafana:80'+expected,fetched)

    def test_elastic_requests_accept_prefixed_and_relative_paths(self):
        acceptance=object.__new__(live.Acceptance)
        acceptance.credentials={'elastic-password':'synthetic-only'}
        with patch.object(live,'request',return_value={}) as request:
            for path in ('_ilm/policy/filebeat',live.PREFIX+'/mid-cbf-kibana/api/data_views'):
                acceptance.elastic('http://fixture:5601',path)
                self.assertEqual('http://fixture:5601/'+path.lstrip('/'),request.call_args.args[0])

    def test_private_site_values_cannot_enter_transfer_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);chart=root/'platform/charts/fhs-platform';chart.mkdir(parents=True)
            (chart/'site-values.yaml').write_text('private_fixture: do-not-transfer\n')
            evidence=root/'ops/platform/discovery-portal-setup/source-evidence.json'
            evidence.parent.mkdir(parents=True);evidence.write_text('{"archives":[]}')
            with patch.object(live,'ROOT',root),self.assertRaises(AssertionError):
                live.bundle(root/'archive.tgz')


if __name__=='__main__':unittest.main()
