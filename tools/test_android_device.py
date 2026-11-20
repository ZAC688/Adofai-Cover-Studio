"""Run native tests and process-restart persistence on the isolated debug emulator."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.request import build_opener, ProxyHandler, Request
import uuid

ROOT = Path(__file__).resolve().parents[1]
APP = 'com.zac688.adofaicoverstudio.debug'
EXPECTED_NATIVE = {
    ('RuntimeSmokeTest', name) for name in (
        'nativeDependenciesAndActualOfflineWebViewBoot',
        'nativeMemoryPagesBlasFontAndJpegActuallyWork',
        'actualThreeJsAndPixiChangeFullResolutionAndroidPixels',
        'actualEmbeddedChartFramePreviewsNativeGoldTrack',
        'javaOnnxRuntimeMatchesTheOriginalModelReference',
        'allNineApprovedSamplesKeepTheOriginalNinetyPercentIouGate',
        'sqliteSaveSurvivesOpeningAnotherStoreConnection',
    )
} | {('SystemFileTest', name) for name in (
    'realSystemSaveWritesAReadableFullPng',
    'realSystemCancelDoesNotReportSavedOrCloseTheEditor',
)}


def verify_instrumentation(output):
    match = re.search(r'OK \((\d+) tests?\)', output)
    if not match or int(match[1]) < len(EXPECTED_NATIVE) or any(word in output for word in ('FAILURES!!!', 'INSTRUMENTATION_FAILED', 'INSTRUMENTATION_ABORTED')):
        raise AssertionError('Native instrumentation did not pass; inspect instrumentation.log')
    passed = set()
    current = {}
    for line in output.splitlines():
        if line.startswith('INSTRUMENTATION_STATUS: class='):
            current['class'] = line.split('=', 1)[1].rsplit('.', 1)[-1]
        elif line.startswith('INSTRUMENTATION_STATUS: test='):
            current['test'] = line.split('=', 1)[1]
        elif line.startswith('INSTRUMENTATION_STATUS_CODE:'):
            code = int(line.split(':', 1)[1])
            if code not in (0, 1):
                raise AssertionError('A native test failed, was skipped or was aborted; inspect instrumentation.log')
            if code == 0:
                passed.add((current.get('class'), current.get('test')))
            current = {}
    if not EXPECTED_NATIVE <= passed:
        raise AssertionError('Required native tests did not all report success; inspect instrumentation.log')
    return len(passed)


class Device:
    def __init__(self, serial):
        if not re.fullmatch(r'emulator-\d+', serial):
            raise ValueError('Only an isolated emulator is allowed; physical phones are not modified')
        self.serial = serial
        self.base = [str(ROOT/'tools/android-sdk/platform-tools/adb.exe'), '-s', serial]
        self.http = build_opener(ProxyHandler({}))
        self.forward = None

    def adb(self, *arguments, timeout=60):
        result = subprocess.run([*self.base, *arguments], capture_output=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError('ADB operation failed: '+result.stderr.decode(errors='replace')[:500])
        return result.stdout.decode('utf-8', errors='replace').strip()

    def validate(self, expected_page_size=None):
        if self.adb('get-state') != 'device':
            raise RuntimeError('The emulator has not booted; native tests were not run')
        if self.adb('shell', 'getprop', 'ro.kernel.qemu') != '1':
            raise ValueError('Not an isolated Android emulator')
        if self.adb('shell', 'getprop', 'sys.boot_completed') != '1':
            raise RuntimeError('Android boot is incomplete')
        page_size = int(self.adb('shell', 'getconf', 'PAGE_SIZE'))
        if expected_page_size is not None and page_size != expected_page_size:
            raise ValueError(f'Required {expected_page_size}-byte Android pages, got {page_size}; tests were not run')
        return {'pageSize': page_size, 'sdk': self.adb('shell', 'getprop', 'ro.build.version.sdk'),
                'abi': self.adb('shell', 'getprop', 'ro.product.cpu.abi')}

    def ready(self):
        self.adb('shell', 'am', 'start', '-W', '-n', APP+'/com.zac688.adofaicoverstudio.MainActivity')
        deadline = time.monotonic()+150
        while time.monotonic() < deadline:
            try:
                pid = int(self.adb('shell', 'pidof', APP))
                ready = json.loads(self.adb('shell', 'run-as', APP, 'cat', 'cache/runtime-ready.json'))
                if ready['pid'] == pid:
                    self.device_port = int(ready['port'])
                    if self.forward:
                        self.adb('forward', '--remove', 'tcp:'+str(self.forward))
                    self.forward = int(self.adb('forward', 'tcp:0', 'tcp:'+str(self.device_port)))
                    self.token = self.request('/api/session')['token']
                    return pid
            except (RuntimeError, ValueError, OSError):
                pass
            time.sleep(.25)
        raise RuntimeError('Embedded Android runtime did not become ready after opening the debug app')

    def request(self, path, body=None):
        headers = {'Host': f'127.0.0.1:{self.device_port}'}
        payload = None
        if body is not None:
            headers.update({'Content-Type': 'application/json', 'x-editor-token': self.token,
                            'Origin': f'http://127.0.0.1:{self.device_port}'})
            payload = json.dumps(body).encode()
        request = Request(f'http://127.0.0.1:{self.forward}'+path, data=payload, headers=headers,
                          method='PUT' if body is not None else 'GET')
        with self.http.open(request, timeout=30) as response:
            return json.load(response)

    def persistence(self):
        old_pid = self.ready()
        initial = self.request('/api/project')
        changed = deepcopy(initial['project'])
        marker = 'native-restart-'+uuid.uuid4().hex
        changed['name'] = marker
        saved = self.request('/api/project', {'baseRevision': initial['revision'], 'project': changed})
        try:
            self.adb('shell', 'am', 'force-stop', APP)
            new_pid = self.ready()
            assert new_pid != old_pid, 'The original process was not actually replaced'
            actual = self.request('/api/project')
            assert actual['revision'] == saved['revision']
            assert actual['project'] == changed, 'Saved work changed or was lost across real Android process restart'
            return {'passed': True, 'newProcess': True, 'revisionPreserved': True}
        finally:
            current = self.request('/api/project')
            self.request('/api/project', {'baseRevision': current['revision'], 'project': initial['project']})

    def close(self):
        if self.forward:
            self.adb('forward', '--remove', 'tcp:'+str(self.forward))

    def stability(self, duration=90):
        """Observe the real WebView after restart, not just the HTTP ready flag."""
        from playwright.sync_api import sync_playwright
        pid = self.ready()
        port = self.adb('forward', 'tcp:0', 'localabstract:webview_devtools_remote_'+str(pid))
        initial = self.request('/api/project')
        checks = 0
        try:
            with sync_playwright() as playwright:
                # WebView exposes page targets but not Chrome's browser-context
                # download manager. Leave its native system file handling intact.
                browser = playwright.chromium.connect_over_cdp('http://127.0.0.1:'+port, no_defaults=True, timeout=60_000)
                try:
                    page = next(page for context in browser.contexts for page in context.pages if page.url.startswith('http://127.0.0.1:'))
                    page.locator('.mobile-tabs').wait_for(state='visible', timeout=60_000)
                    page.wait_for_function("document.querySelector('canvas[aria-label=封面画布]')?.getAttribute('aria-busy')==='false'", timeout=60_000)
                    deadline = time.monotonic()+duration
                    while time.monotonic()<deadline:
                        assert int(self.adb('shell','pidof',APP))==pid, 'The app process crashed or restarted after readiness'
                        page.locator('.mobile-tabs button').nth(checks % 4).click(timeout=10_000)
                        assert page.locator('canvas[aria-label=封面画布]').evaluate('(canvas)=>canvas.width>0&&canvas.height>0')
                        assert self.request('/api/project')==initial, 'Switching panels changed the saved work'
                        checks += 1
                        time.sleep(5)
                finally:
                    browser.close()
        finally:
            self.adb('forward','--remove','tcp:'+port)
        return {'passed':True, 'seconds':duration, 'responsiveChecks':checks, 'sameProcess':True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--page-size', type=int, choices=[4096, 16384])
    parser.add_argument('--report-dir', type=Path, default=ROOT/'artifacts/android/native')
    args = parser.parse_args()
    report_root = args.report_dir
    report_root.mkdir(parents=True, exist_ok=True)
    report = {'nativePassed': False, 'processRestartPassed': False}
    device = Device(args.serial)
    try:
        report['device'] = device.validate(args.page_size)
        for relative in ('debug/app-debug.apk', 'androidTest/debug/app-debug-androidTest.apk'):
            path = ROOT/'android/app/build/outputs/apk'/relative
            if not path.is_file():
                raise FileNotFoundError('Build debug and AndroidTest APKs first')
            device.adb('install', '-r', str(path), timeout=180)
        output = device.adb('shell', 'am', 'instrument', '-w', '-r', APP+'.test/androidx.test.runner.AndroidJUnitRunner', timeout=900)
        (report_root/'instrumentation.log').write_text(output, encoding='utf-8')
        report.update(nativePassed=True, nativeTests=verify_instrumentation(output))
        report['restart'] = device.persistence()
        report['processRestartPassed'] = True
        report['stability'] = device.stability()
        print('Native Android tests and actual process-restart persistence passed')
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        device.close()
        (report_root/'results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
