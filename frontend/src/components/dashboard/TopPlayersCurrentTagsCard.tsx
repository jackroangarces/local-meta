type Props = {
  region: string;
  data: {
    topPlayers: Array<{ current_tag: string; supermajor_player_id: number }>;
  };
};

export function TopPlayersCurrentTagsCard({ region, data }: Props) {
  const topPlayers = data.topPlayers ?? [];

  return (
    <article className="dashboard-card">
      <h2 className="dashboard-card__title">Top Players</h2>
      <p className="dashboard-card__meta">Based on SchuStats power ratings in {region}</p>

      <ol className="dashboard-card__list dashboard-card__list--scroll">
        {topPlayers.length === 0 ? (
          <li>No data yet</li>
        ) : (
          topPlayers.map((player, idx) => (
            <li key={`${player.current_tag}-${player.supermajor_player_id}-${idx}`}>
              <a
                href={`https://www.supermajor.gg/ultimate/player/${encodeURIComponent(
                  player.current_tag,
                )}?id=S${player.supermajor_player_id}`}
                target="_blank"
                rel="noreferrer"
              >
                {player.current_tag}
              </a>
            </li>
          ))
        )}
      </ol>
    </article>
  );
}

