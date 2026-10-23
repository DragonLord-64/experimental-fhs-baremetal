/* Supervisor test dependency only. No browser package is needed to launch the demo. */
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
(async () => {
  const [base, output, phase = 'all'] = process.argv.slice(2);
  if (!/^http:\/\/127\.0\.0\.1:1308[01]$/.test(base)) throw Error('owned loopback test ports only');
  fs.mkdirSync(output, {recursive: true});
  const browser = await chromium.launch({headless: true, ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? {executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE} : {})});
  const page = await browser.newPage({viewport: {width: 1920, height: 1440}, deviceScaleFactor: 1});
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  const visits = phase === 'all' ? [
    ['rack', 'fhs-infra-rack', ''],
    ['fhs', 'fhs-infra-server', '&var-unit=FSPUnit2&var-fhs=FHS1'],
    ['mesh', 'fhs-infra-mesh', '&var-vccu=1&var-fspu=3'],
    ['switch', 'fhs-infra-switch', '&var-switch=VCCUnit1-switch&var-port=1'],
    ['interface', 'fhs-infra-interface', '&var-switch=VCCUnit1-switch&var-interface=eth1%2F1%2F3'],
    ['vlan', 'fhs-infra-vlan', '&var-vlan=55']
  ] : [
    ['rack-'+phase, 'fhs-infra-rack', ''],
    ['fhs-'+phase, 'fhs-infra-server', '&var-unit=FSPUnit2&var-fhs=FHS1'],
    ['mesh-'+phase, 'fhs-infra-mesh', '&var-vccu=1&var-fspu=3'],
    ['switch-'+phase, 'fhs-infra-switch', '&var-switch=VCCUnit1-switch&var-port=1']
  ];
  const evidence = [];
  try {
    for (const [name, uid, variables] of visits) {
      const queries = [];
      const capture = async response => {
        if (response.url().includes('/api/ds/query')) {
          try {
            const json = await response.json();
            for (const [ref, result] of Object.entries(json.results || {})) {
              if (result.error || result.status >= 400) errors.push(`${name}/${ref}: ${result.error || result.status}`);
            }
            queries.push({status: response.status(), results: Object.keys(json.results || {}).length});
          } catch (e) { errors.push(`${name} query response: ${e}`); }
        }
      };
      page.on('response', capture);
      await page.goto(`${base}/d/${uid}?from=now-5m&to=now&refresh=5s${variables}`, {waitUntil:'domcontentloaded',timeout:60000});
      // Allow provisioning, the first rate samples and the two refresh cycles.
      await page.waitForTimeout(18000);
      const text = await page.locator('body').innerText();
      if (text.includes('Dashboard not found') || text.includes('An unexpected error happened')) throw Error(name+': dashboard failed');
      if (!queries.length) throw Error(name+': no real Grafana datasource requests');
      if (name.startsWith('fhs') && !text.includes(['ok', 'port-independent'].includes(phase) ? 'ok' : 'fault')) throw Error(name+': scenario status absent');
      if (name.startsWith('mesh') && !text.includes(['ok', 'port-independent'].includes(phase) ? 'ok' : 'fault')) throw Error(name+': link state absent');
      if (name.startsWith('rack')) {
        // Native Canvas field mappings include the switch identity and status.
        for (const [unit, expected] of [
          ['vccu1', phase === 'ok' ? 'ok' : 'fault'],
          ['fspu3', ['ok', 'port-independent'].includes(phase) ? 'ok' : 'fault']
        ]) {
          if (!new RegExp(`${unit}-switch\\s*[·:]?\\s*${expected}`, 'i').test(text)) throw Error(`${name}: ${unit} operational ${expected} absent`);
        }
      }
      if (name.startsWith('mesh')) {
        if (!/available capacity.*%/i.test(text)) throw Error(name+': percent capacity label absent');
        for (const value of [87, 50, ['ok', 'port-independent'].includes(phase) ? 45 : 0]) {
          if (!new RegExp(`\\b${value}\\s*%`).test(text)) throw Error(`${name}: visible ${value}% absent`);
        }
      }
      if (phase === 'port-independent' && name.startsWith('switch') && (!text.includes('fault') || !text.includes('ok'))) throw Error(name+': independent port fault and healthy hardware/link states absent');
      if (/unavailable|observed throughput|observed status/i.test(text)) throw Error(name+': stale provenance prose');
      if (name === 'mesh') {
        if (!/ok\s+647\s+fault\s+1\s+unknown\s+0\s+notdeployed\s+0/.test(text)) throw Error('mesh counts must render numeric 647/1/0/0');
      }
      await page.screenshot({path:path.join(output,name+'.png'),fullPage:true,timeout:60000});
      fs.writeFileSync(path.join(output,name+'.txt'),text);
      evidence.push({name,uid,queries});
      page.off('response',capture);
    }
    if (errors.length) throw Error(errors.join('\n'));
    fs.writeFileSync(path.join(output,'browser-'+phase+'.json'),JSON.stringify({evidence,errors},null,2));
  } finally { await browser.close(); }
})().catch(e => {console.error(e);process.exit(1)});
