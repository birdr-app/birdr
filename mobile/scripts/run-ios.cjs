#!/usr/bin/env node
/**
 * Xcode 27 Device Hub: Expo's post-build `simctl install/openurl` hangs with no
 * logs. Build a simulator .app without installing, then install/launch ourselves.
 */
const { spawn, spawnSync } = require('child_process');
const fs = require('fs');
const net = require('net');
const os = require('os');
const path = require('path');

const root = path.join(__dirname, '..');
const bundleId = 'pro.birdr.app';
const extra = process.argv.slice(2);
const rebuild = extra.includes('--rebuild');
const expoArgs = extra.filter((arg) => arg !== '--rebuild');

function runNode(script) {
  const result = spawnSync(process.execPath, [path.join(__dirname, script)], {
    cwd: root,
    stdio: 'inherit',
    env: process.env,
  });
  if (result.status) process.exit(result.status);
}

function run(cmd, args, opts = {}) {
  return spawnSync(cmd, args, {
    encoding: 'utf8',
    timeout: 45000,
    killSignal: 'SIGKILL',
    ...opts,
  });
}

function parseDeviceArg(args) {
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--device' || args[i] === '-d') {
      const value = args[i + 1];
      if (!value || value.startsWith('-')) return { present: true, value: null };
      return { present: true, value };
    }
    if (args[i].startsWith('--device=')) {
      return { present: true, value: args[i].slice('--device='.length) };
    }
  }
  return { present: false, value: null };
}

function listSimulatorDevices() {
  const result = run('xcrun', ['simctl', 'list', 'devices', '-j']);
  if (result.status) return [];
  try {
    const data = JSON.parse(result.stdout);
    const devices = [];
    for (const [runtime, list] of Object.entries(data.devices || {})) {
      if (!/iOS/i.test(runtime)) continue;
      for (const device of list) {
        if (!device.udid || device.isAvailable === false) continue;
        devices.push({
          udid: device.udid,
          name: device.name || '',
          state: device.state,
          runtime,
        });
      }
    }
    return devices;
  } catch {
    return [];
  }
}

function pickSimulator(requested) {
  const devices = listSimulatorDevices();
  if (requested) {
    const needle = requested.toLowerCase();
    const match = devices.find(
      (d) => d.udid.toLowerCase() === needle || d.name.toLowerCase() === needle,
    );
    return match || null;
  }
  const bootedPhones = devices.filter((d) => d.state === 'Booted' && /iphone/i.test(d.name));
  if (bootedPhones[0]) return bootedPhones[0];
  const booted = devices.filter((d) => d.state === 'Booted');
  if (booted[0]) return booted[0];
  const phones = devices.filter((d) => /iphone/i.test(d.name));
  return phones[0] || devices[0] || null;
}

function findApp(dir) {
  const derived = path.join(os.homedir(), 'Library/Developer/Xcode/DerivedData');
  const derivedApps = [];
  try {
    for (const name of fs.readdirSync(derived)) {
      if (!name.startsWith('Birdr-')) continue;
      const candidate = path.join(
        derived,
        name,
        'Build/Products/Debug-iphonesimulator/Birdr.app',
      );
      if (fs.existsSync(candidate)) derivedApps.push(candidate);
    }
  } catch {
    /* ignore */
  }
  derivedApps.sort((a, b) => {
    try {
      return fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs;
    } catch {
      return 0;
    }
  });
  if (derivedApps[0]) return derivedApps[0];

  const stack = [dir];
  while (stack.length) {
    const current = stack.pop();
    let entries = [];
    try {
      entries = fs.readdirSync(current, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      const full = path.join(current, entry.name);
      if (entry.name === 'Birdr.app') return full;
      if (entry.isDirectory() && entry.name !== 'node_modules') stack.push(full);
    }
  }
  return null;
}

function metroListening() {
  return new Promise((resolve) => {
    const socket = net.connect({ port: 8081, host: '127.0.0.1' }, () => {
      socket.end();
      resolve(true);
    });
    socket.setTimeout(400, () => {
      socket.destroy();
      resolve(false);
    });
    socket.on('error', () => resolve(false));
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function deviceRoot(udid) {
  return path.join(
    os.homedir(),
    'Library/Developer/CoreSimulator/Devices',
    udid,
  );
}

function installedAppPath(udid) {
  const appDir = path.join(deviceRoot(udid), 'data/Containers/Bundle/Application');
  const stack = [appDir];
  while (stack.length) {
    const current = stack.pop();
    let entries = [];
    try {
      entries = fs.readdirSync(current, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      const full = path.join(current, entry.name);
      if (entry.name === 'Birdr.app') {
        try {
          if (fs.statSync(path.join(full, 'Birdr')).size > 0) return full;
        } catch {
          /* still copying */
        }
        continue;
      }
      if (entry.isDirectory()) stack.push(full);
    }
  }
  return null;
}

function listBirdrHostProcesses(udid) {
  const result = spawnSync('ps', ['-axo', 'pid=,ppid=,command='], { encoding: 'utf8' });
  if (result.status) return [];
  const processes = [];
  for (const line of result.stdout.split('\n')) {
    const match = line.match(/^\s*(\d+)\s+(\d+)\s+(.*)$/);
    if (!match) continue;
    const pid = Number(match[1]);
    const ppid = Number(match[2]);
    const command = match[3];
    const isBirdr =
      command.includes('Birdr.app/Birdr') && (!udid || command.includes(udid));
    const isDebugserver = /debugserver/.test(command);
    const isStuckSimctl =
      /simctl (install|launch|get_app_container|openurl|listapps)/.test(command) &&
      (!udid || command.includes(udid));
    if (isBirdr || isStuckSimctl) processes.push({ pid, ppid, command, isBirdr, isDebugserver });
    else if (isDebugserver) processes.push({ pid, ppid, command, isBirdr: false, isDebugserver: true });
  }
  return processes;
}

function forceQuitBirdr(udid) {
  const processes = listBirdrHostProcesses(udid);
  const birdr = processes.filter((p) => p.isBirdr);
  const debugServers = processes.filter(
    (p) => p.isDebugserver && birdr.some((b) => b.ppid === p.pid || b.pid === p.pid),
  );
  const stuck = processes.filter((p) => /simctl /.test(p.command));
  const pids = [...birdr, ...debugServers, ...stuck].map((p) => p.pid);
  if (!pids.length) return;
  spawnSync('kill', ['-9', ...pids.map(String)], { stdio: 'ignore' });
}

async function waitForInstall(udid, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const installed = installedAppPath(udid);
    if (installed) return installed;
    await sleep(500);
  }
  return null;
}

function bootDevice(device) {
  spawnSync('open', [`devices://device/open?id=${device.udid}`], { stdio: 'inherit' });
  if (device.state === 'Booted') return;
  console.log(`ios: booting ${device.name}…`);
  run('xcrun', ['simctl', 'boot', device.udid], { stdio: 'inherit', timeout: 20000 });
  run('xcrun', ['simctl', 'bootstatus', device.udid, '-b'], {
    stdio: 'inherit',
    timeout: 120000,
  });
  device.state = 'Booted';
}

function rebootDevice(device) {
  console.log(`ios: rebooting ${device.name} to clear a stuck Birdr install…`);
  run('xcrun', ['simctl', 'shutdown', device.udid], { stdio: 'inherit', timeout: 30000 });
  device.state = 'Shutdown';
  bootDevice(device);
}

function startInstall(appPath, udid) {
  return spawn('xcrun', ['simctl', 'install', udid, appPath], {
    stdio: ['ignore', 'pipe', 'pipe'],
  });
}

async function installApp(appPath, device) {
  forceQuitBirdr(device.udid);
  bootDevice(device);

  console.log(`ios: installing Birdr on ${device.name}…`);
  let child = startInstall(appPath, device.udid);
  let installed = await waitForInstall(device.udid, 25000);

  if (!installed) {
    child.kill('SIGKILL');
    forceQuitBirdr(device.udid);
    rebootDevice(device);
    console.log(`ios: retrying install on ${device.name}…`);
    child = startInstall(appPath, device.udid);
    installed = await waitForInstall(device.udid, 60000);
  }

  if (!installed) {
    child.kill('SIGKILL');
    const stderr = child.stderr ? child.stderr.read() : null;
    console.error('ios: install did not copy Birdr.app onto the simulator.');
    if (stderr) console.error(String(stderr));
    process.exit(1);
  }

  console.log(`ios: Birdr is on ${device.name}.`);
  return installed;
}

function launchApp(device) {
  console.log(`ios: launching Birdr on ${device.name}…`);
  const viaDeviceCtl = spawn(
    'xcrun',
    [
      'devicectl',
      'device',
      'process',
      'launch',
      '--device',
      device.udid,
      '--terminate-existing',
      '--activate',
      bundleId,
    ],
    { stdio: 'ignore', detached: true },
  );
  viaDeviceCtl.unref();
}

async function ensureMetro() {
  if (await metroListening()) {
    console.log('ios: Metro already on 8081.');
    return null;
  }
  console.log('ios: starting Metro on 8081…');
  const metro = spawn('npx', ['expo', 'start', '--port', '8081'], {
    cwd: root,
    env: process.env,
    stdio: 'inherit',
  });
  for (let i = 0; i < 60; i++) {
    await sleep(500);
    if (await metroListening()) return metro;
    if (metro.exitCode != null) {
      console.error('ios: Metro exited before it was ready.');
      process.exit(metro.exitCode || 1);
    }
  }
  console.error('ios: Metro did not come up on 8081.');
  return metro;
}

runNode('sync-release-info-plist.cjs');
runNode('fix-pbxproj-shellscript.cjs');

if (rebuild) {
  fs.rmSync(path.join(root, 'ios/build'), { recursive: true, force: true });
  const pods = spawnSync('pod', ['install'], {
    cwd: path.join(root, 'ios'),
    stdio: 'inherit',
    env: process.env,
  });
  if (pods.status) process.exit(pods.status);
}

const deviceArg = parseDeviceArg(expoArgs);
const simulatorTarget = pickSimulator(deviceArg.value);
const usePhysicalDevice =
  deviceArg.present && deviceArg.value && !simulatorTarget && deviceArg.value !== 'generic';

if (usePhysicalDevice) {
  console.log('ios: physical device — running expo@latest run:ios…\n');
  const child = spawn('npx', ['--yes', 'expo@latest', 'run:ios', ...expoArgs], {
    cwd: root,
    env: process.env,
    stdio: 'inherit',
  });
  child.on('close', (status) => process.exit(status || 0));
} else {
  const outputDir = fs.mkdtempSync(path.join(os.tmpdir(), 'birdr-ios-'));
  const buildArgs = [
    '--yes',
    'expo@latest',
    'run:ios',
    '--device',
    'generic',
    '--output',
    outputDir,
    '--no-bundler',
    ...expoArgs.filter((arg, i, arr) => {
      if (arg === '--device' || arg === '-d') return false;
      if (arr[i - 1] === '--device' || arr[i - 1] === '-d') return false;
      if (arg.startsWith('--device=')) return false;
      if (arg === '--no-bundler') return false;
      return true;
    }),
  ];

  console.log('ios: building simulator app (install/launch handled after xcodebuild)…\n');
  const build = spawnSync('npx', buildArgs, {
    cwd: root,
    env: process.env,
    stdio: 'inherit',
  });
  if (build.status) process.exit(build.status);

  const appPath = findApp(outputDir);
  if (!appPath) {
    console.error(`ios: built OK but could not find Birdr.app under ${outputDir}`);
    process.exit(1);
  }

  const device = simulatorTarget || pickSimulator(null);
  if (!device) {
    console.error('ios: no iOS simulator available. Open Device Hub and create one.');
    process.exit(1);
  }

  ensureMetro()
    .then(async (metro) => {
      await installApp(appPath, device);
      launchApp(device);
      if (!metro) {
        console.log('\nios: Birdr should be on the simulator home screen. Tap it if it did not come to the foreground.\n');
        process.exit(0);
      }
      metro.on('close', (status) => process.exit(status || 0));
    })
    .catch((error) => {
      console.error(error);
      process.exit(1);
    });
}
