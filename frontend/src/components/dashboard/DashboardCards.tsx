import { useEffect, useState } from "react";
import { TopPlayersCurrentTagsCard } from "./TopPlayersCurrentTagsCard";
import { MostMainedCharactersCard } from "./MostMainedCharactersCard";
import { MostBattledCharactersCard } from "./MostBattledCharactersCard";
import { LeastAppearancesCharactersCard } from "./LeastAppearancesCharactersCard";
import { UnusedCharactersCard } from "./UnusedCharactersCard";
import { fetchRegionMostMainedCharactersCard, fetchRegionTopPlayersCurrentTagsCard } from "./cardQueries";
import { fetchRegionMostBattledCharactersCard } from "./cardQueries";
import { fetchRegionLeastAppearancesCharactersCard } from "./cardQueries";
import { fetchRegionUnusedCharactersCard } from "./cardQueries";

export type DashboardCardsProps = {
  region: string;
  onAllQueriesComplete: () => void;
};

type DashboardData = {
  topPlayers: Awaited<ReturnType<typeof fetchRegionTopPlayersCurrentTagsCard>>;
  mostMainedCharacters: Awaited<ReturnType<typeof fetchRegionMostMainedCharactersCard>>;
  mostBattledCharacters: Awaited<ReturnType<typeof fetchRegionMostBattledCharactersCard>>;
  leastAppearancesCharacters: Awaited<ReturnType<typeof fetchRegionLeastAppearancesCharactersCard>>;
  unusedCharacters: Awaited<ReturnType<typeof fetchRegionUnusedCharactersCard>>;
};

export function DashboardCards({ region, onAllQueriesComplete }: DashboardCardsProps) {
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setData(null);
      try {
        const [topPlayersResult, mostMainedResult, mostBattledResult, leastAppearancesResult, unusedResult] =
          await Promise.allSettled([
            fetchRegionTopPlayersCurrentTagsCard(region),
            fetchRegionMostMainedCharactersCard(region),
            fetchRegionMostBattledCharactersCard(region),
            fetchRegionLeastAppearancesCharactersCard(region),
            fetchRegionUnusedCharactersCard(region),
          ]);

        const topPlayers =
          topPlayersResult.status === "fulfilled" ? topPlayersResult.value : { topPlayers: [] };
        const mostMainedCharacters =
          mostMainedResult.status === "fulfilled"
            ? mostMainedResult.value
            : { mostMainedCharacters: [] };

        const mostBattledCharacters =
          mostBattledResult.status === "fulfilled"
            ? mostBattledResult.value
            : { mostBattledCharacters: [] };

        const leastAppearancesCharacters =
          leastAppearancesResult.status === "fulfilled"
            ? leastAppearancesResult.value
            : { leastAppearancesCharacters: [] };

        const unusedCharacters =
          unusedResult.status === "fulfilled" ? unusedResult.value : { unusedCharacters: [] };

        if (!cancelled) {
          setData({
            topPlayers,
            mostMainedCharacters,
            mostBattledCharacters,
            leastAppearancesCharacters,
            unusedCharacters,
          });
        }
      } catch {
        // Shouldn't happen because Promise.allSettled doesn't throw, but keep a safe fallback.
        if (!cancelled) {
          setData({
            topPlayers: { topPlayers: [] },
            mostMainedCharacters: { mostMainedCharacters: [] },
            mostBattledCharacters: { mostBattledCharacters: [] },
            leastAppearancesCharacters: { leastAppearancesCharacters: [] },
            unusedCharacters: { unusedCharacters: [] },
          });
        }
      } finally {
        if (!cancelled) {
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
      <MostMainedCharactersCard region={region} data={data.mostMainedCharacters} />
      <MostBattledCharactersCard region={region} data={data.mostBattledCharacters} />
      <LeastAppearancesCharactersCard
        region={region}
        data={data.leastAppearancesCharacters}
      />
      <UnusedCharactersCard region={region} data={data.unusedCharacters} />
    </div>
  );
}
