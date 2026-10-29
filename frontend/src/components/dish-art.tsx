// Deterministic, honest placeholder art: an illustrated plate tinted from the dish's hue.
// It is labelled as an illustration wherever provenance is shown; owners replace it with real photos.
export function DishArt({ hue = 30, kind = "plate", size = 88, rounded = 18, label }: { hue?: number; kind?: string; size?: number; rounded?: number; label?: string }) {
  const bg = `hsl(${hue} 55% 88%)`;
  const rim = `hsl(${hue} 45% 78%)`;
  const food = `hsl(${hue} 70% 52%)`;
  const food2 = `hsl(${(hue + 40) % 360} 60% 42%)`;
  const leaf = `hsl(${(hue + 110) % 360} 45% 38%)`;
  return (
    <svg className="dish-art" width={size} height={size} viewBox="0 0 100 100" role="img" aria-label={label ?? "Illustration of the dish"} style={{ borderRadius: rounded, background: bg, flex: "none" }}>
      <circle cx="50" cy="52" r="38" fill="#fff" />
      <circle cx="50" cy="52" r="38" fill="none" stroke={rim} strokeWidth="3" />
      <circle cx="50" cy="52" r="27" fill="none" stroke={rim} strokeWidth="1.5" strokeDasharray="2 4" />
      <path d="M30 56c2-14 14-22 24-20 12 2 18 12 16 22-2 8-12 12-22 10-12-1-19-4-18-12z" fill={food} />
      <circle cx="44" cy="48" r="5" fill={food2} />
      <circle cx="58" cy="55" r="4" fill={food2} opacity=".85" />
      <path d="M44 30c-3-5 3-7 0-12" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" fill="none" style={{ animation: "steam 2.8s ease-out infinite" }} />
      <path d="M56 30c-3-5 3-7 0-12" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" fill="none" style={{ animation: "steam 2.8s ease-out 1.1s infinite" }} />
      <path d="M62 38c6-8 14-8 16-4-6 1-10 4-14 8z" fill={leaf} />
      <path d="M36 38c-6-6-12-5-13-1 5 0 9 2 12 5z" fill={leaf} opacity=".85" />
    </svg>
  );
}

/** The dish's real photo when the restaurant uploaded one, otherwise the generated illustration. */
export function DishImage({ image, size = 88, rounded = 18, label }: { image?: { url?: string; hue?: number } | null; size?: number; rounded?: number; label?: string }) {
  if (image?.url) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={image.url} alt={label ?? "Photo of the dish"} width={size} height={size} loading="lazy" className="dish-art shrink-0 object-cover" style={{ width: size, height: size, borderRadius: rounded }} />;
  }
  return <DishArt hue={image?.hue ?? 30} size={size} rounded={rounded} label={label} />;
}
