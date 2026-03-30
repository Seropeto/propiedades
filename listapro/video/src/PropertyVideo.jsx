const { useCurrentFrame, useVideoConfig, interpolate, AbsoluteFill, Audio } = require('remotion');
const { PhotoSlide } = require('./PhotoSlide');
const { ContactScreen } = require('./ContactScreen');

const PHOTO_DURATION = 90;    // 3 seg a 30fps
const CONTACT_DURATION = 90;  // 3 seg pantalla final

const PropertyVideo = ({ photos, precio, ciudad, estado, recamaras, banos, metros, operacion, nombre, telefono, email, musicSrc }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const totalPhotos = photos.length;
  const contactStart = totalPhotos * PHOTO_DURATION;

  // Texto overlay: fade in en foto 1
  const textOpacity = interpolate(frame, [15, 35], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const textSlide = interpolate(frame, [15, 35], [30, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const isContactScreen = frame >= contactStart;

  const stats = [
    recamaras ? `🛏 ${recamaras} Dorm.` : null,
    banos     ? `🚿 ${banos} Baños` : null,
    metros    ? `📐 ${metros} m²` : null,
  ].filter(Boolean).join('   |   ');

  return (
    <AbsoluteFill style={{ background: '#000', fontFamily: 'Arial, sans-serif' }}>

      {/* Música de fondo */}
      {musicSrc && (
        <Audio src={musicSrc} volume={0.4} />
      )}

      {/* Slides de fotos */}
      {photos.map((src, i) => {
        const start = i * PHOTO_DURATION;
        const end = start + PHOTO_DURATION;
        if (frame < start - 10 || frame > end + 10) return null;
        return (
          <PhotoSlide key={i} src={src} startFrame={start} duration={PHOTO_DURATION} />
        );
      })}

      {/* Pantalla de contacto final */}
      {isContactScreen && (
        <ContactScreen
          nombre={nombre}
          telefono={telefono}
          email={email}
          ciudad={ciudad}
          estado={estado}
        />
      )}

      {/* Overlay de texto (solo en fotos, no en contacto) */}
      {!isContactScreen && (
        <AbsoluteFill
          style={{
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'flex-end',
            padding: '0 60px 120px',
            opacity: textOpacity,
            transform: `translateY(${textSlide}px)`,
          }}
        >
          {/* Badge operacion */}
          <div
            style={{
              display: 'inline-block',
              alignSelf: 'flex-start',
              background: operacion === 'Venta' ? '#3b82f6' : '#16a34a',
              color: '#fff',
              fontSize: 28,
              fontWeight: 700,
              padding: '8px 24px',
              borderRadius: 6,
              marginBottom: 20,
              letterSpacing: 1,
            }}
          >
            En {operacion}
          </div>

          {/* Precio */}
          <div
            style={{
              fontSize: 86,
              fontWeight: 900,
              color: '#facc15',
              lineHeight: 1,
              marginBottom: 16,
              textShadow: '0 2px 8px rgba(0,0,0,0.6)',
            }}
          >
            {precio}
          </div>

          {/* Ciudad */}
          <div style={{ fontSize: 42, color: '#ffffff', fontWeight: 600, marginBottom: 14 }}>
            {ciudad}, {estado}
          </div>

          {/* Stats */}
          {stats && (
            <div style={{ fontSize: 32, color: '#e2e8f0' }}>{stats}</div>
          )}
        </AbsoluteFill>
      )}

      {/* Logo top-right */}
      {!isContactScreen && (
        <div
          style={{
            position: 'absolute',
            top: 50,
            right: 50,
            color: 'rgba(255,255,255,0.85)',
            fontSize: 26,
            fontWeight: 700,
            letterSpacing: 2,
            textShadow: '0 1px 4px rgba(0,0,0,0.5)',
          }}
        >
          ToxiroPropiedades
        </div>
      )}
    </AbsoluteFill>
  );
};

module.exports = { PropertyVideo, PHOTO_DURATION, CONTACT_DURATION };
