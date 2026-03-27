type Props = {
  region: string;
  data: {
    risingStars: Array<{
      player_id: number;
      current_tag: string;
      rank: number;
      upset_score: number;
      upset_wins: number;
      upsets: Array<{
        defeated_player_id: number;
        defeated_tag: string;
        defeated_rank: number;
        upset_factor: number;
        upset_sets: number;
      }>;
    }>;
  };
};

export function RisingStarsCard({ region, data }: Props) {
  const rows = data.risingStars ?? [];

  return (
    <article className="dashboard-card">
      <h2 className="dashboard-card__title">Rising Stars</h2>
      <p className="dashboard-card__meta">
        Upset score determined from last 100 sets vs top 100 players in {region}
      </p>

      <ol className="dashboard-card__list dashboard-card__list--scroll">
        {rows.length === 0 ? (
          <li>No data yet</li>
        ) : (
          rows.map((row, idx) => (
            <li key={`${row.player_id}-${row.current_tag}-${idx}`}>
              <span className="dashboard-card__char-hover-wrap">
                <span className="dashboard-card__char-text">
                  {row.current_tag} (#{row.rank})
                  <br />
                  Score: {row.upset_score} ({row.upset_wins} upsets)
                </span>
                <span className="dashboard-card__hover-panel" role="tooltip">
                  <div className="dashboard-card__hover-panel-title">{row.current_tag} upset victims:</div>
                  {row.upsets?.length ? (
                    <ul className="dashboard-card__hover-panel-list">
                      {row.upsets.map((u, uIdx) => (
                        <li key={`${u.defeated_player_id}-${u.defeated_tag}-${uIdx}`}>
                          {u.defeated_tag} (#{u.defeated_rank})
                          {u.upset_sets && u.upset_sets > 1 ? ` (x${u.upset_sets})` : ""}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="dashboard-card__hover-panel-empty">No cached upsets yet</div>
                  )}
                </span>
              </span>
            </li>
          ))
        )}
      </ol>
    </article>
  );
}

