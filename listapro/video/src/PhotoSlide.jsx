const { useCurrentFrame, useVideoConfig, interpolate, Easing, Img, AbsoluteFill } = require('remotion');

const PhotoSlide = ({ src, startFrame, duration }) => {
  const frame = useCurrentFrame();
  const local = frame - startFrame;

  // Ken Burns: zoom lento del 100% al 110%
  const scale = interpolate(local, [0, duration], [1, 1.1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.linear,
  });

  // Fade in/out
  const opacity = interpolate(
    local,
    [0, 15, duration - 15, duration],
    [0, 1, 1, 0],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
  );

  return (
    <AbsoluteFill style={{ opacity }}>
      <AbsoluteFill
        style={{
          transform: `scale(${scale})`,
          transformOrigin: 'center center',
        }}
      >
        <Img
          src={src}
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
      </AbsoluteFill>
      {/* Gradiente oscuro abajo */}
      <AbsoluteFill
        style={{
          background: 'linear-gradient(to top, rgba(0,0,0,0.75) 0%, transparent 50%)',
        }}
      />
    </AbsoluteFill>
  );
};

module.exports = { PhotoSlide };
