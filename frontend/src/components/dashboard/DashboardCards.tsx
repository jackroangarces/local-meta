import { useEffect, useState } from "react";
import { TopPlayersCurrentTagsCard } from "./TopPlayersCurrentTagsCard";
import { MostMainedCharactersCard } from "./MostMainedCharactersCard";
import { MostBattledCharactersCard } from "./MostBattledCharactersCard";
import { LeastAppearancesCharactersCard } from "./LeastAppearancesCharactersCard";
import { UpcomingEventsCard } from "./UpcomingEventsCard";
import { BestMatchupsCard } from "./BestMatchupsCard";
import { RisingStarsCard } from "./RisingStarsCard";
import { fetchRegionMostMainedCharactersCard, fetchRegionTopPlayersCurrentTagsCard } from "./cardQueries";
import { fetchRegionMostBattledCharactersCard } from "./cardQueries";
import { fetchRegionLeastAppearancesCharactersCard } from "./cardQueries";
import { fetchRegionUpcomingEventsCard } from "./cardQueries";
import { fetchRegionBestMatchupsCard } from "./cardQueries";
import { fetchRegionRisingStarsCard } from "./cardQueries";

export type DashboardCardsProps = {
  region: string;
  onAllQueriesComplete: () => void;
};

type DashboardData = {
  topPlayers: Awaited<ReturnType<typeof fetchRegionTopPlayersCurrentTagsCard>>;
  mostMainedCharacters: Awaited<ReturnType<typeof fetchRegionMostMainedCharactersCard>>;
  mostBattledCharacters: Awaited<ReturnType<typeof fetchRegionMostBattledCharactersCard>>;
  leastAppearancesCharacters: Awaited<ReturnType<typeof fetchRegionLeastAppearancesCharactersCard>>;
  upcomingEvents: Awaited<ReturnType<typeof fetchRegionUpcomingEventsCard>>;
  bestMatchups: Awaited<ReturnType<typeof fetchRegionBestMatchupsCard>>;
  risingStars: Awaited<ReturnType<typeof fetchRegionRisingStarsCard>>;
};

export function DashboardCards({ region, onAllQueriesComplete }: DashboardCardsProps) {
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setData(null);
      try {
        const [topPlayersResult, mostMainedResult, mostBattledResult, leastAppearancesResult, upcomingEventsResult, bestMatchupsResult, risingStarsResult] =
          await Promise.allSettled([
            fetchRegionTopPlayersCurrentTagsCard(region),
            fetchRegionMostMainedCharactersCard(region),
            fetchRegionMostBattledCharactersCard(region),
            fetchRegionLeastAppearancesCharactersCard(region),
            fetchRegionUpcomingEventsCard(region),
            fetchRegionBestMatchupsCard(region),
            fetchRegionRisingStarsCard(region),
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
        const upcomingEvents =
          upcomingEventsResult.status === "fulfilled" ? upcomingEventsResult.value : { tournaments: [] };
        const bestMatchups =
          bestMatchupsResult.status === "fulfilled" ? bestMatchupsResult.value : { bestMatchups: [] };
        const risingStars =
          risingStarsResult.status === "fulfilled" ? risingStarsResult.value : { risingStars: [] };

        if (!cancelled) {
          setData({
            topPlayers,
            mostMainedCharacters,
            mostBattledCharacters,
            leastAppearancesCharacters,
            upcomingEvents,
            bestMatchups,
            risingStars,
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
            upcomingEvents: { tournaments: [] },
            bestMatchups: { bestMatchups: [] },
            risingStars: { risingStars: [] },
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
      <UpcomingEventsCard region={region} data={data.upcomingEvents} />
      <TopPlayersCurrentTagsCard region={region} data={data.topPlayers} />
      <RisingStarsCard region={region} data={data.risingStars} />
      <MostMainedCharactersCard region={region} data={data.mostMainedCharacters} />
      <BestMatchupsCard region={region} data={data.bestMatchups} />
      <MostBattledCharactersCard region={region} data={data.mostBattledCharacters} />
      <LeastAppearancesCharactersCard
        region={region}
        data={data.leastAppearancesCharacters}
      />
    </div>
  );
}
