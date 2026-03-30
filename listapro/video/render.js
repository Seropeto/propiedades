const { bundle } = require('@remotion/bundler');
const { renderMedia, selectComposition } = require('@remotion/renderer');
const path = require('path');

async function main() {
  const args = JSON.parse(process.argv[2]);
  const {
    photos,
    precio,
    ciudad,
    estado,
    recamaras,
    banos,
    metros,
    operacion,
    nombre,
    telefono,
    email,
    musicSrc,
    outputPath,
    PHOTO_DURATION,
    CONTACT_DURATION,
  } = args;

  const entryPoint = path.resolve(__dirname, 'src/Root.jsx');

  process.stderr.write('Bundling...\n');
  const bundled = await bundle({ entryPoint });

  const inputProps = {
    photos,
    precio,
    ciudad,
    estado,
    recamaras,
    banos,
    metros,
    operacion,
    nombre,
    telefono,
    email,
    musicSrc: musicSrc || null,
  };

  const photoCount = photos.length;
  const durationInFrames = photoCount * (PHOTO_DURATION || 90) + (CONTACT_DURATION || 90);

  process.stderr.write('Selecting composition...\n');
  const composition = await selectComposition({
    serveUrl: bundled,
    id: 'PropertyVideo',
    inputProps,
  });

  composition.durationInFrames = durationInFrames;

  process.stderr.write('Rendering...\n');
  await renderMedia({
    composition,
    serveUrl: bundled,
    codec: 'h264',
    outputLocation: outputPath,
    inputProps,
    onProgress: ({ progress }) => {
      process.stderr.write(`progress:${Math.round(progress * 100)}\n`);
    },
  });

  process.stdout.write(JSON.stringify({ success: true, output: outputPath }));
}

main().catch(err => {
  process.stderr.write('ERROR: ' + err.message + '\n');
  process.stdout.write(JSON.stringify({ success: false, error: err.message }));
  process.exit(1);
});
