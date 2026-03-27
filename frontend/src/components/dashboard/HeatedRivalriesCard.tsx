type Props = {
  region: string;
  data: {
    heatedRivalries: Array<{
      player1_id: number;
      player1_tag: string;
      player1_rank: number;
      player1_wins: number;
      player2_id: number;
      player2_tag: string;
      player2_rank: number;
      player2_wins: number;
      total_sets: number;
      heated_score: number;
    }>;
  };
};

export function HeatedRivalriesCard({ region, data }: Props) {
  const rows = data.heatedRivalries ?? [];

  return (
    <article className="dashboard-card">
      <h2 className="dashboard-card__title">Fiercest Rivalries</h2>
      <p className="dashboard-card__meta">Close and frequent ranked sets in {region} (based on last 100 sets)</p>

      <ol className="dashboard-card__list dashboard-card__list--scroll">
        {rows.length === 0 ? (
          <li>No data yet</li>
        ) : (
          rows.map((r, idx) => (
            <li key={`${r.player1_id}-${r.player2_id}-${idx}`}>
              <span className="dashboard-card__char-text">
                {r.player1_tag} (#{r.player1_rank}) {r.player1_wins} - {r.player2_wins}{" "}
                {r.player2_tag} (#{r.player2_rank})
              </span>
            </li>
          ))
        )}
      </ol>
    </article>
  );
}

