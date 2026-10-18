/**
 * Render mobile/birdr-new.png (round logo on transparent) into every app icon:
 *   assets/icon.png                       1024, opaque, logo on the cream icon background
 *   assets/adaptive-icon.png              1024 adaptive foreground, logo inside the safe zone, transparent
 *   ios/.../AppIcon.appiconset/*          every size listed in its Contents.json, opaque
 *   android/.../mipmap-<dpi>/ic_launcher(.webp|_round|_foreground)
 *
 * Run from mobile/: node scripts/generate-app-icons.cjs
 * Uses sharp; falls back to macOS `sips` (PNG output, no webp) when sharp is unavailable.
 */
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = path.join(__dirname, '..');
const SRC = path.join(ROOT, 'birdr-new.png');
const BACKGROUND = '#F8EEDC'; // matches app.json adaptiveIcon.backgroundColor / @color/iconBackground
const ICON_LOGO_SCALE = 0.86; // logo diameter on full (iOS / legacy) icons
// Adaptive icons: 108dp layer, launchers show at most the centre 72dp (66dp guaranteed).
const ADAPTIVE_LOGO_SCALE = 0.62;
const IOS_SET = path.join(ROOT, 'ios/Birdr/Images.xcassets/AppIcon.appiconset');
const ANDROID_RES = path.join(ROOT, 'android/app/src/main/res');
const DENSITIES = { mdpi: 1, hdpi: 1.5, xhdpi: 2, xxhdpi: 3, xxxhdpi: 4 };

function iosIconSizes() {
  const contents = JSON.parse(fs.readFileSync(path.join(IOS_SET, 'Contents.json'), 'utf8'));
  return contents.images
    .filter((img) => img.filename && img.size)
    .map((img) => {
      const points = parseFloat(img.size.split('x')[0]);
      const scale = parseFloat((img.scale || '1x').replace('x', ''));
      return { file: img.filename, px: Math.round(points * scale) };
    });
}

function androidTargets(ext) {
  const out = [];
  for (const [dpi, mult] of Object.entries(DENSITIES)) {
    const dir = path.join(ANDROID_RES, `mipmap-${dpi}`);
    out.push({ file: path.join(dir, `ic_launcher.${ext}`), px: 48 * mult, kind: 'square' });
    out.push({ file: path.join(dir, `ic_launcher_round.${ext}`), px: 48 * mult, kind: 'round' });
    out.push({ file: path.join(dir, `ic_launcher_foreground.${ext}`), px: 108 * mult, kind: 'foreground' });
  }
  return out;
}

async function withSharp(sharp) {
  // Trim the transparent border and square the logo so it is centred exactly.
  const trimmed = await sharp(SRC).trim().png().toBuffer();
  const meta = await sharp(trimmed).metadata();
  const side = Math.max(meta.width, meta.height);
  const logo = await sharp(trimmed)
    .extend({
      top: Math.floor((side - meta.height) / 2),
      bottom: Math.ceil((side - meta.height) / 2),
      left: Math.floor((side - meta.width) / 2),
      right: Math.ceil((side - meta.width) / 2),
      background: { r: 0, g: 0, b: 0, alpha: 0 },
    })
    .png()
    .toBuffer();

  async function render(px, { scale, background, circle }) {
    const inner = Math.round(px * scale);
    const logoPx = await sharp(logo).resize(inner, inner).png().toBuffer();
    let img = sharp({
      create: { width: px, height: px, channels: 4, background: background || { r: 0, g: 0, b: 0, alpha: 0 } },
    }).composite([{ input: logoPx, gravity: 'centre' }]);
    if (circle) {
      const mask = Buffer.from(
        `<svg width="${px}" height="${px}"><circle cx="${px / 2}" cy="${px / 2}" r="${px / 2}"/></svg>`
      );
      img = sharp(await img.png().toBuffer()).composite([{ input: mask, blend: 'dest-in' }]);
    }
    return img;
  }

  const write = async (pipeline, file, { opaque } = {}) => {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    let p = sharp(await pipeline.png().toBuffer());
    if (opaque) p = p.flatten({ background: BACKGROUND }).removeAlpha();
    if (file.endsWith('.webp')) await p.webp({ lossless: true }).toFile(file);
    else await p.png().toFile(file);
    console.log('wrote', path.relative(ROOT, file));
  };

  await write(await render(1024, { scale: ICON_LOGO_SCALE, background: BACKGROUND }), path.join(ROOT, 'assets/icon.png'), { opaque: true });
  await write(await render(1024, { scale: ADAPTIVE_LOGO_SCALE }), path.join(ROOT, 'assets/adaptive-icon.png'));

  for (const { file, px } of iosIconSizes()) {
    // App Store rejects icons with an alpha channel.
    await write(await render(px, { scale: ICON_LOGO_SCALE, background: BACKGROUND }), path.join(IOS_SET, file), { opaque: true });
  }

  for (const t of androidTargets('webp')) {
    if (t.kind === 'foreground') await write(await render(t.px, { scale: ADAPTIVE_LOGO_SCALE }), t.file);
    else if (t.kind === 'round') await write(await render(t.px, { scale: ICON_LOGO_SCALE, background: BACKGROUND, circle: true }), t.file);
    else await write(await render(t.px, { scale: ICON_LOGO_SCALE, background: BACKGROUND }), t.file);
  }
}

function withSips() {
  console.warn('sharp not available: using sips (PNG only, no trim/round mask).');
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'birdr-icons-'));
  const bg = BACKGROUND.replace('#', '');
  const render = (px, scale, file, padColor) => {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    const inner = Math.round(px * scale);
    const step = path.join(tmp, 'step.png');
    execFileSync('sips', ['-s', 'format', 'png', '-z', String(inner), String(inner), SRC, '--out', step], { stdio: 'ignore' });
    const args = ['--padToHeightWidth', String(px), String(px)];
    if (padColor) args.push('--padColor', padColor);
    execFileSync('sips', [...args, step, '--out', file], { stdio: 'ignore' });
    console.log('wrote', path.relative(ROOT, file));
  };
  render(1024, ICON_LOGO_SCALE, path.join(ROOT, 'assets/icon.png'), bg);
  render(1024, ADAPTIVE_LOGO_SCALE, path.join(ROOT, 'assets/adaptive-icon.png'));
  for (const { file, px } of iosIconSizes()) render(px, ICON_LOGO_SCALE, path.join(IOS_SET, file), bg);
  for (const t of androidTargets('png')) {
    const webp = t.file.replace(/\.png$/, '.webp');
    if (fs.existsSync(webp)) fs.unlinkSync(webp); // avoid duplicate resources
    render(t.px, t.kind === 'foreground' ? ADAPTIVE_LOGO_SCALE : ICON_LOGO_SCALE, t.file, t.kind === 'foreground' ? null : bg);
  }
}

async function main() {
  if (!fs.existsSync(SRC)) {
    console.error('Source not found:', SRC);
    process.exit(1);
  }
  let sharp = null;
  try {
    sharp = require('sharp');
  } catch {
    sharp = null;
  }
  if (sharp) await withSharp(sharp);
  else withSips();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
