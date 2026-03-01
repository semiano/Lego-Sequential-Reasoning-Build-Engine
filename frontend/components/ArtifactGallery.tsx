type ArtifactItem = {
  url: string;
  title: string;
};

export function ArtifactGallery({ items }: { items: ArtifactItem[] }) {
  if (!items.length) {
    return null;
  }

  return (
    <div style={{ border: "1px solid #2e3540", borderRadius: 8, padding: 10, background: "#161b22" }}>
      <h3 style={{ marginTop: 0 }}>Artifact Gallery</h3>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))", gap: 8 }}>
        {items.map((item) => (
          <a key={item.url} href={item.url} target="_blank" rel="noreferrer" style={{ textDecoration: "none", color: "inherit" }}>
            <img src={item.url} alt={item.title} style={{ width: "100%", height: 100, objectFit: "cover", borderRadius: 6 }} />
            <div style={{ fontSize: 12, marginTop: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.title}</div>
          </a>
        ))}
      </div>
    </div>
  );
}
