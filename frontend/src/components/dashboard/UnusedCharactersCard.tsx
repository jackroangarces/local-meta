type Props = {
  region: string;
  data: {
    unusedCharacters: Array<{
      character_id: number;
      character_name: string;
    }>;
  };
};

const charIconModules = import.meta.glob("../../assets/char_icons/*iconssbupng.png", {
  eager: true,
  import: "default",
}) as Record<string, string>;

function toCharacterIconFilename(characterName: string): string {
  const slug = characterName
    .toLowerCase()
    .replace(/&/g, "and")
    .replace(/[.\s\/]/g, "");

  return `${slug}iconssbupng.png`;
}

function resolveCharacterIconSrc(characterName: string): string | undefined {
  const filename = toCharacterIconFilename(characterName);
  const entry = Object.entries(charIconModules).find(([path]) => path.endsWith(`/${filename}`));
  return entry?.[1];
}

export function UnusedCharactersCard({ region, data }: Props) {
  const characters = data.unusedCharacters ?? [];

  return (
    <article className="dashboard-card">
      <h2 className="dashboard-card__title">Unused</h2>
      <p className="dashboard-card__meta">Zero uses in matches in {region}</p>

      <ol className="dashboard-card__list dashboard-card__list--scroll">
        {characters.length === 0 ? (
          <li>No data yet</li>
        ) : (
          characters.map((c, idx) => (
            <li key={`${c.character_id}-${c.character_name}-${idx}`}>
              <div className="dashboard-card__char-row">
                <span className="dashboard-card__char-text">
                  {c.character_name} (0)
                </span>
                {(() => {
                  const iconSrc = resolveCharacterIconSrc(c.character_name);
                  if (!iconSrc) return null;
                  return (
                    <img
                      className="dashboard-card__char-icon"
                      src={iconSrc}
                      alt={`${c.character_name} icon`}
                    />
                  );
                })()}
              </div>
            </li>
          ))
        )}
      </ol>
    </article>
  );
}

