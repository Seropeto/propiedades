const { useCurrentFrame, interpolate, AbsoluteFill } = require('remotion');

const ContactScreen = ({ nombre, telefono, email, ciudad, estado }) => {
  const frame = useCurrentFrame();

  const opacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const slideUp = interpolate(frame, [0, 20], [40, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill
      style={{
        background: 'linear-gradient(160deg, #0f1923 0%, #1a2e44 100%)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: 'Arial, sans-serif',
        opacity,
      }}
    >
      {/* Logo */}
      <div
        style={{
          transform: `translateY(${slideUp}px)`,
          textAlign: 'center',
          marginBottom: 60,
        }}
      >
        <div style={{ fontSize: 36, color: '#94a3b8', letterSpacing: 4, marginBottom: 8 }}>
          TOXIRO
        </div>
        <div style={{ fontSize: 56, fontWeight: 900, color: '#ffffff', letterSpacing: 2 }}>
          PROPIEDADES
        </div>
        <div
          style={{
            width: 80,
            height: 4,
            background: '#3b82f6',
            margin: '20px auto 0',
            borderRadius: 2,
          }}
        />
      </div>

      {/* Datos agente */}
      <div
        style={{
          transform: `translateY(${slideUp}px)`,
          textAlign: 'center',
          color: '#ffffff',
        }}
      >
        <div style={{ fontSize: 42, fontWeight: 700, marginBottom: 20 }}>{nombre}</div>
        <div style={{ fontSize: 34, color: '#94a3b8', marginBottom: 14 }}>📞 {telefono}</div>
        <div style={{ fontSize: 30, color: '#94a3b8', marginBottom: 40 }}>✉️ {email}</div>
        <div style={{ fontSize: 28, color: '#3b82f6' }}>{ciudad}, {estado}</div>
      </div>
    </AbsoluteFill>
  );
};

module.exports = { ContactScreen };
