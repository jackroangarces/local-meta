import { useEffect, useState } from "react";
import { TopPlayersCurrentTagsCard } from "./TopPlayersCurrentTagsCard";
import { fetchRegionTopPlayersCurrentTagsCard } from "./cardQueries";

export type DashboardCardsProps = {
  region: string;
  onAllQueriesComplete: () => void;
};

type DashboardData = {
  topPlayers: Awaited<ReturnType<typeof fetchRegionTopPlayersCurrentTagsCard>>;
};

export function DashboardCards({ region, onAllQueriesComplete }: DashboardCardsProps) {
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setData(null);
      try {
        const topPlayers = await fetchRegionTopPlayersCurrentTagsCard(region);
        if (!cancelled) {
          setData({ topPlayers });
          onAllQueriesComplete();
        }
      } catch {
        if (!cancelled) {
          setData({ topPlayers: { topPlayers: [] } });
          onAllQueriesComplete();
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [region, onAllQueriesComplete]);

  if (!data) {
    return null;
  }

  return (
    <div className="home-page__dashboard">
      <TopPlayersCurrentTagsCard region={region} data={data.topPlayers} />
    </div>
  );
}
