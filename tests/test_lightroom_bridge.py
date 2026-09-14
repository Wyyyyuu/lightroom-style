"""Lua 5.1 behavior with a minimal fake SDK; this is NOT Lightroom integration QA."""
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from lupa.lua51 import LuaRuntime


PLUGIN = Path(__file__).resolve().parents[1] / "lightroom-bridge" / "PhotoStyleBridge.lrplugin"
CLIENT = PLUGIN.parent / "bridge_probe.py"


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.plugin = self.root / 'PhotoStyleBridge.lrplugin'
        shutil.copytree(PLUGIN, self.plugin, ignore=shutil.ignore_patterns('*.log'))
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.globals().pluginPath = str(self.plugin).replace("\\", "/")
        self.lua.globals().statePath = str(self.root).replace("\\", "/")
        self.lua.globals().pathExists = lambda path: "file" if Path(path).is_file() else ("directory" if Path(path).is_dir() else None)
        self.lua.globals().makeDirectories = lambda path: Path(path).mkdir(parents=True, exist_ok=True)
        self.lua.globals().deleteRequest = self.delete_request
        self.lua.execute('''
            _PLUGIN = {path = pluginPath}
            mocks = {}
            mocks.LrPathUtils = {child = function(p,c) return p .. '/' .. c end,
                                getStandardFilePath = function(which) assert(which == 'appData'); return statePath end}
            mocks.LrFileUtils = {exists = function(p) return pathExists(p) end,
                                files = function() return function() return nil end end,
                                createAllDirectories = function(p) makeDirectories(p); return true end,
                                delete = function(p) return deleteRequest(p) end}
            taskStarts = 0
            mocks.LrTasks = {pcall = pcall,
                startAsyncTask = function(f) taskStarts = taskStarts + 1; pendingTask = f end,
                sleep = function() photoStyleBridgeStop = true end}
            selected = {
                localIdentifier = 42,
                getFormattedMetadata = function(self,k) assert(k == 'fileName'); return 'example.cr3' end,
                getRawMetadata = function(self,k) assert(k == 'isVirtualCopy'); return false end,
                getDevelopSettings = function() return {Exposure2012=0.5, Temperature=5200, PrivateUnexpectedField='excluded'} end,
                applyDevelopSettings = function() error('A read-only diagnostic attempted a write') end,
            }
            catalog = {
                getPath = function() return 'test-catalog.lrcat' end,
                getTargetPhoto = function() return selected end,
                findPhotoByPath = function() error('Unexpected photo lookup') end,
                createVirtualCopies = function() error('Unexpected mutation') end,
            }
            mocks.LrApplication = {versionString = function() return '13.0.2' end,
                                  activeCatalog = function() return catalog end}
            mocks.LrApplicationView = {getCurrentModuleName = function() return 'develop' end}
            import = function(name) assert(mocks[name], 'Unexpected SDK import'); return mocks[name] end
            bridge = dofile(pluginPath .. '/Bridge.lua')
        ''')

    def tearDown(self):
        self.directory.cleanup()

    def delete_request(self, path):
        target = Path(path)
        self.assertEqual(target.name, "refresh.request")
        self.assertTrue(target.resolve().is_relative_to(self.root.resolve()))
        target.unlink()
        return True

    def responses(self, prefix):
        return [json.loads(path.read_text(encoding="utf-8")) for path in (self.root / "PhotoStyleMatchBridge").glob(prefix + "-*.json") if Path(str(path) + ".ready").is_file()]

    def test_lua51_syntax_and_json_roundtrip(self):
        compiler = self.lua.eval("function(s,n) return assert(loadstring(s,n)) end")
        for path in PLUGIN.glob("*.lua"):
            compiler(path.read_text(encoding="utf-8"), str(path))
        encode = self.lua.execute("return dofile(pluginPath .. '/Json.lua').encode")
        value = {"文字": 'newline\nquote" tab\t slash\\ NUL\0', "number": 0.5, "boolean": True}
        self.assertEqual(json.loads(encode(self.lua.table_from(value))), value)

    def test_diagnostic_reads_selected_settings_without_mutation(self):
        self.lua.execute("bridge.diagnose()")
        result = self.responses("diagnostic")[0]
        self.assertTrue(result["capabilities"]["catalog"]["ok"])
        target = result["capabilities"]["catalog"]["value"]["target"]
        self.assertEqual(target["local_identifier"], 42)
        self.assertEqual(target["settings"], {"Exposure2012": 0.5, "Temperature": 5200})

    def test_empty_catalog_and_independent_api_error(self):
        self.lua.execute("selected = nil; mocks.LrApplicationView.getCurrentModuleName = function() error('module unavailable') end; bridge.diagnose()")
        result = self.responses("diagnostic")[0]["capabilities"]
        self.assertFalse(result["active_module"]["ok"])
        self.assertTrue(result["catalog"]["ok"])
        self.assertFalse(result["catalog"]["value"]["has_target_photo"])

    def test_start_idempotent_and_refresh_protocol(self):
        state = self.root / "PhotoStyleMatchBridge"
        state.mkdir()
        (state / "refresh.request").write_text("refresh")
        self.lua.execute("bridge.start(); bridge.start(); assert(taskStarts == 1); pendingTask()")
        self.assertEqual(len(self.responses("loaded")), 1)
        self.assertEqual(len(self.responses("diagnostic")), 2)
        self.assertFalse((state / "refresh.request").exists())

    def test_reloading_module_does_not_overwrite_responses(self):
        self.lua.execute("bridge.diagnose(); dofile(pluginPath .. '/Bridge.lua').diagnose(); bridge.diagnose()")
        self.assertEqual(len(self.responses("diagnostic")), 3)

    def test_worker_failure_remains_visible_when_receipt_directory_fails(self):
        self.lua.execute("mocks.LrFileUtils.createAllDirectories = function() return false, 'simulated permission error' end; bridge.start()")
        with self.assertRaisesRegex(Exception, 'simulated permission error'):
            self.lua.execute('pendingTask()')
        self.assertIn('simulated permission error', (self.plugin / 'bridge-startup.log').read_text())
        self.assertFalse(self.lua.globals().photoStyleBridgeRunning)

    def test_bootstrap_logs_before_worker_load_failure(self):
        (self.plugin / 'Bridge.lua').write_text("error('simulated bootstrap failure')", encoding='utf-8')
        self.lua.execute("dofile(pluginPath .. '/Init.lua')")
        with self.assertRaisesRegex(Exception, 'simulated bootstrap failure'):
            self.lua.execute('pendingTask()')
        log = (self.plugin / 'bridge-startup.log').read_text()
        self.assertIn('Init entered', log)
        self.assertIn('simulated bootstrap failure', log)

    def test_manual_menu_starts_worker_and_produces_diagnostic(self):
        self.lua.execute("dofile(pluginPath .. '/Diagnostics.lua'); pendingTask()")
        self.assertEqual(len(self.responses('diagnostic')), 1)
        self.assertTrue(self.lua.globals().photoStyleBridgeRunning)
        self.assertIn('Manual diagnostics menu selected', (self.plugin / 'bridge-startup.log').read_text())

    def manager_button(self):
        self.lua.execute('''
            mocks.LrView = {bind = function(key) return key end}
            provider = dofile(pluginPath .. '/PluginInfoProvider.lua')
            properties = {}
            provider.startDialog(properties)
            factory = {push_button = function(self, spec) return spec end,
                       static_text = function(self, spec) return spec end}
            sections = provider.sectionsForTopOfDialog(factory, properties)
            managerButton = sections[1][1]
        ''')
        return self.lua.globals().managerButton

    def test_manager_button_runs_without_menu_or_auto_init(self):
        button = self.manager_button()
        button['action']()
        self.lua.execute('pendingTask()')
        self.assertEqual(len(self.responses('diagnostic')), 1)
        self.assertIn('SDK', self.lua.globals().properties['bridgeStatus'])
        self.assertFalse(self.lua.globals().properties['bridgeBusy'])

    def test_manager_button_displays_real_bootstrap_error(self):
        button = self.manager_button()
        (self.plugin / 'Bridge.lua').write_text("error('specific SDK load error')", encoding='utf-8')
        button['action']()
        self.lua.execute('pendingTask()')
        self.assertIn('specific SDK load error', self.lua.globals().properties['bridgeStatus'])
        self.assertFalse(self.lua.globals().properties['bridgeBusy'])

    def test_client_rejects_stale_response(self):
        self.lua.execute("bridge.diagnose()")
        (self.plugin / 'bridge-startup.log').write_text('Worker error: simulated startup failure\n', encoding='utf-8')
        result = subprocess.run([sys.executable, str(CLIENT), "--state-dir", str(self.root / "PhotoStyleMatchBridge"), "--plugin-dir", str(self.plugin), "--timeout", "1"], text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)["connected"])
        self.assertIn('simulated startup failure', json.loads(result.stdout)['startup_log_tail'][0])

    def test_client_waits_for_new_ready_marker(self):
        state = self.root / "PhotoStyleMatchBridge"
        state.mkdir()
        def fake_response():
            deadline = time.monotonic() + 3
            while not (state / "refresh.request").is_file() and time.monotonic() < deadline:
                time.sleep(0.02)
            response = state / "diagnostic-fresh.json"
            response.write_text('{"schema_version":1,"capabilities":{}}', encoding="utf-8")
            time.sleep(0.1)
            Path(str(response) + ".ready").write_text("ready")
        worker = threading.Thread(target=fake_response)
        worker.start()
        result = subprocess.run([sys.executable, str(CLIENT), "--state-dir", str(state), "--timeout", "3"], text=True, capture_output=True)
        worker.join()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["connected"])


if __name__ == "__main__":
    unittest.main()
