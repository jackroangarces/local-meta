type Props = {
  region: string;
  data: {
    mostMainedCharacters: Array<{
      character_id: number;
      character_name: string;
      main_count: number;
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

export function MostMainedCharactersCard({ region, data }: Props) {
  const characters = data.mostMainedCharacters ?? [];

  return (
    <article className="dashboard-card">
      <h2 className="dashboard-card__title">Most Mained</h2>
      <p className="dashboard-card__meta">
        Based on each player's highest play % in {region}
      </p>

      <ol className="dashboard-card__list">
        {characters.length === 0 ? (
          <li>No data yet</li>
        ) : (
          characters.map((c, idx) => (
            <li key={`${c.character_id}-${c.character_name}-${idx}`}>
              <div className="dashboard-card__char-row">
                <span className="dashboard-card__char-text">
                  {c.character_name} ({c.main_count})
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

