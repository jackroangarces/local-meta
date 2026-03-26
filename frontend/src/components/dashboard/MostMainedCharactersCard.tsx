type Props = {
  region: string;
  data: {
    mostMainedCharacters: Array<{
      character_id: number;
      character_name: string;
      main_count: number;
      mains_players: Array<{
        player_id: number;
        current_tag: string;
        rank: number | null;
      }>;
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

      <ol className="dashboard-card__list dashboard-card__list--scroll">
        {characters.length === 0 ? (
          <li>No data yet</li>
        ) : (
          characters.map((c, idx) => (
            <li key={`${c.character_id}-${c.character_name}-${idx}`}>
              <div className="dashboard-card__char-row">
                <span className="dashboard-card__char-hover-wrap">
                  <span className="dashboard-card__char-text">{c.character_name}</span>{" "}
                  <span className="dashboard-card__char-main-count">({c.main_count})</span>
                  <span className="dashboard-card__hover-panel" role="tooltip">
                    <div className="dashboard-card__hover-panel-title">
                      {c.character_name} Players:
                    </div>
                    {c.mains_players?.length ? (
                      <ul className="dashboard-card__hover-panel-list">
                        {c.mains_players.map((p, pIdx) => (
                          <li key={`${p.player_id}-${p.current_tag}-${pIdx}`}>
                            {p.current_tag}
                            {p.rank != null ? ` (#${p.rank})` : ""}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <div className="dashboard-card__hover-panel-empty">No data yet</div>
                    )}
                  </span>
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

