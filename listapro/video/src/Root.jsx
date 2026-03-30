const { Composition, registerRoot } = require('remotion');
const { PropertyVideo, PHOTO_DURATION, CONTACT_DURATION } = require('./PropertyVideo');

// Props por defecto para preview en Remotion Studio
const defaultProps = {
  photos: ['http://localhost:8000/uploads/demo/portada.jpg'],
  precio: '$400.000',
  ciudad: 'Santiago',
  estado: 'Las Condes',
  recamaras: '4',
  banos: '2',
  metros: '180',
  operacion: 'Venta',
  nombre: 'María González',
  telefono: '33 1234 5678',
  email: 'maria@toxiro.com',
  musicSrc: null,
};

const RemotionRoot = () => {
  const photoCount = defaultProps.photos.length;
  const durationInFrames = photoCount * PHOTO_DURATION + CONTACT_DURATION;

  return (
    <Composition
      id="PropertyVideo"
      component={PropertyVideo}
      durationInFrames={durationInFrames}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={defaultProps}
      calculateMetadata={({ props }) => {
        const count = (props.photos || []).length || 1;
        return { durationInFrames: count * PHOTO_DURATION + CONTACT_DURATION };
      }}
    />
  );
};

module.exports = { RemotionRoot };

registerRoot(RemotionRoot);
