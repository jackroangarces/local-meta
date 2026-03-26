type Props = {
  region: string;
  data: {
    topPlayers: Array<{
      current_tag: string;
      supermajor_player_id: number;
      main_character_name: string | null;
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

export function TopPlayersCurrentTagsCard({ region, data }: Props) {
  const topPlayers = data.topPlayers ?? [];

  return (
    <article className="dashboard-card">
      <h2 className="dashboard-card__title">Top Players</h2>
      <p className="dashboard-card__meta">Based on SchuStats power ratings in {region}</p>

      <ol className="dashboard-card__list dashboard-card__list--wide-padding dashboard-card__list--scroll">
        {topPlayers.length === 0 ? (
          <li>No data yet</li>
        ) : (
          topPlayers.map((player, idx) => (
            <li key={`${player.current_tag}-${player.supermajor_player_id}-${idx}`}>
              <div className="dashboard-card__char-row">
                <a
                  className="dashboard-card__char-text"
                  href={`https://www.supermajor.gg/ultimate/player/${encodeURIComponent(
                    player.current_tag,
                  )}?id=S${player.supermajor_player_id}&offline`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {player.current_tag}
                </a>
                {player.main_character_name ? (
                  (() => {
                    const iconSrc = resolveCharacterIconSrc(player.main_character_name ?? "");
                    if (!iconSrc) return null;
                    return (
                      <img
                        className="dashboard-card__char-icon"
                        src={iconSrc}
                        alt={`${player.main_character_name} icon`}
                      />
                    );
                  })()
                ) : null}
              </div>
            </li>
          ))
        )}
      </ol>
    </article>
  );
}

