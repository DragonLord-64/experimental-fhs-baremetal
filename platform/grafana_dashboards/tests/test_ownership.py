"""Safety checks for bounded ownership discovery before Grafana writes."""
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from live_validate import owned_inventory, FOLDER

class Ownership(TestCase):
    def test_unknown_uid_never_uses_get(self):
        api=Mock();api.call.return_value=[]
        self.assertEqual({},owned_inventory(api,{'candidate'}))
        self.assertEqual('/api/search?type=dash-db&limit=1000&page=1',api.call.call_args.args[0])

    def test_unrelated_owner_aborts(self):
        api=Mock();api.call.return_value=[{'uid':'candidate','folderUid':'other'}]
        with self.assertRaises(RuntimeError):owned_inventory(api,{'candidate'})

    def test_global_pagination_and_owned_uid(self):
        api=Mock();api.call.side_effect=[[{'uid':str(i)} for i in range(1000)], [{'uid':'candidate','folderUid':FOLDER}]]
        self.assertIn('candidate',owned_inventory(api,{'candidate'}))
        self.assertEqual(2,api.call.call_count)

    def test_incomplete_search_fails_closed(self):
        api=Mock();api.call.return_value=[{'uid':'other'}]*1000
        with self.assertRaises(RuntimeError):owned_inventory(api,{'candidate'})
        self.assertEqual(100,api.call.call_count)

class ImportSafety(TestCase):
    def test_first_import_is_nonoverwriting_and_read_back(self):
        import tempfile
        from unittest.mock import patch
        import live_validate as validator
        from generate import build
        dashboards=build(1,3)
        api=Mock()
        api.query.side_effect=[
            [{'metric':{'job':'fhs'}}],
            [{'metric':{'job':'node'}}],
            [{'metric':{'job':'switch'}}],
            RuntimeError('stop after import for offline test'),
        ]
        created=set()
        def call(path,data=None):
            if path=='/api/health':return {'version':'13.2.3'}
            if path=='/api/datasources/uid/prometheus':return {'type':'prometheus'}
            if path=='/api/folders/'+FOLDER:return {'uid':FOLDER}
            if path.startswith('/api/search?'):return []
            if path=='/api/dashboards/db':
                self.assertFalse(data['overwrite'])
                self.assertEqual(FOLDER,data['folderUid'])
                uid=data['dashboard']['uid'];created.add(uid)
                return {'uid':uid}
            if path.startswith('/api/dashboards/uid/'):
                uid=path.rsplit('/',1)[1]
                self.assertIn(uid,created,'GET must follow successful creation for an absent UID')
                return {'meta':{'folderUid':FOLDER}}
            self.fail('Unexpected endpoint '+path)
        api.call.side_effect=call
        with tempfile.TemporaryDirectory() as output:
            with patch.object(validator,'API',return_value=api),patch.object(validator,'build',return_value=dashboards),patch.object(sys,'argv',['live_validate','--import-owned','--output',output]):
                with self.assertRaisesRegex(RuntimeError,'stop after import'):
                    validator.main()
        self.assertEqual({d['uid'] for d in dashboards.values()},created)


class DiagnosisSafety(TestCase):
    def test_known_uid_timeout_is_recorded_and_version_probe_is_read_only(self):
        from live_validate import diagnose_api
        api=Mock()
        api.call.side_effect=[{'version':'13.2.3'},
            [{'uid':'fhs-infra-rack','folderUid':FOLDER}],
            TimeoutError('private response must never appear'),
            {'dashboard':{'uid':'fhs-infra-rack'},'meta':{'folderUid':FOLDER}}]
        report={};diagnose_api(api,report)
        self.assertEqual('TimeoutError',report['api_probes'][0]['error_type'])
        self.assertTrue(report['api_probes'][1]['valid_owned_dashboard'])
        self.assertNotIn('private response',str(report))
        self.assertTrue(all(len(c.args)==1 and not c.kwargs for c in api.call.call_args_list))
        self.assertEqual('/api/dashboards/uid/fhs-infra-rack?apiVersion=v1',api.call.call_args.args[0])

class VisualOnlySafety(TestCase):
    def test_owned_visual_import_skips_all_queries_and_acceptance(self):
        import tempfile
        from unittest.mock import patch
        import live_validate as validator
        from generate import build
        dashboards=build()
        api=Mock()
        def call(path,data=None):
            if path=='/api/health':return {'version':'13.2.3'}
            if path=='/api/datasources/uid/prometheus':return {'type':'prometheus'}
            if path=='/api/folders/'+FOLDER:return {'uid':FOLDER}
            if path.startswith('/api/search?'):
                return [{'uid':d['uid'],'folderUid':FOLDER} for d in dashboards.values()]
            if path.startswith('/api/dashboards/uid/'):
                return {'meta':{'folderUid':FOLDER},'dashboard':{'id':12,'version':7}}
            if path=='/api/dashboards/db':
                self.assertFalse(data['overwrite'])
                self.assertEqual(7,data['dashboard']['version'])
                self.assertEqual(12,data['dashboard']['id'])
                self.assertEqual(FOLDER,data['folderUid'])
                self.assertNotIn('rename',data['dashboard']['title'].lower())
                return {'uid':data['dashboard']['uid']}
            self.fail('Unexpected endpoint '+path)
        api.call.side_effect=call
        with tempfile.TemporaryDirectory() as output:
            with patch.object(validator,'API',return_value=api),patch.object(validator,'visual_capture') as capture,patch.object(validator,'browser_check') as acceptance,patch.object(sys,'argv',['live_validate','--visual-only','--import-owned','--output',output]):
                validator.main()
                capture.assert_called_once()
                acceptance.assert_not_called()
        api.query.assert_not_called()
        self.assertEqual(6,sum(c.args[0]=='/api/dashboards/db' for c in api.call.call_args_list))
