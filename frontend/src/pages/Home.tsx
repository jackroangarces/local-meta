import { useCallback, useEffect, useState } from "react";
import { DashboardCards } from "../components/dashboard/DashboardCards";
import LoadingSpinner from "../components/LoadingSpinner";

type RegionsNamesResponse = { names: string[] };
type LatestSnapshotResponse = { snapshot_id: number | null; ranking_date: string | null };

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() || "/api";

export default function Home() {
  const [names, setNames] = useState<string[]>([]);
  const [regionsLoading, setRegionsLoading] = useState(true);
  const [regionsError, setRegionsError] = useState<string | null>(null);
  const [selectedRegion, setSelectedRegion] = useState("");
  const [activeRegion, setActiveRegion] = useState<string | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [dashboardKey, setDashboardKey] = useState(0);
  const [activeRankingDate, setActiveRankingDate] = useState<string | null>(null);

  const onAllQueriesComplete = useCallback(() => {
    setStatsLoading(false);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setRegionsLoading(true);
      setRegionsError(null);
      try {
        const res = await fetch(`${API_BASE}/regions/names`);
        if (!res.ok) {
          throw new Error(`Request failed (${res.status})`);
        }
        const data: RegionsNamesResponse = await res.json();
        if (!cancelled) {
          setNames(data.names ?? []);
          if (data.names?.length) {
            setSelectedRegion(data.names[0]);
          }
        }
      } catch (e) {
        if (!cancelled) {
          setRegionsError(e instanceof Error ? e.message : "Failed to load regions");
          setNames([]);
        }
      } finally {
        if (!cancelled) setRegionsLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleGetStats = () => {
    if (!selectedRegion.trim() || regionsLoading) return;
    setActiveRegion(selectedRegion);
    setStatsLoading(true);
    setDashboardKey((k) => k + 1);
  };

  useEffect(() => {
    let cancelled = false;

    async function loadLatestSnapshotDate() {
      if (!activeRegion) {
        setActiveRankingDate(null);
        return;
      }

      try {
        const params = new URLSearchParams({ region_name: activeRegion });
        const res = await fetch(`${API_BASE}/regions/latest-snapshot?${params.toString()}`);
        if (!res.ok) {
          throw new Error(`Request failed (${res.status})`);
        }
        const data: LatestSnapshotResponse = await res.json();
        if (!cancelled) {
          setActiveRankingDate(data.ranking_date);
        }
      } catch {
        if (!cancelled) {
          setActiveRankingDate(null);
        }
      }
    }

    loadLatestSnapshotDate();
    return () => {
      cancelled = true;
    };
  }, [activeRegion]);

  const formattedRankingDate =
    activeRankingDate != null
      ? new Date(`${activeRankingDate}T00:00:00`).toLocaleDateString("en-US", {
          month: "long",
          day: "numeric",
          year: "numeric",
        })
      : null;

  return (
    <main className="home-page">
      <div className="home-page__controls">
        <label htmlFor="region-select" className="home-page__label">
          Region
        </label>
        <select
          id="region-select"
          className="home-page__select"
          value={selectedRegion}
          onChange={(e) => setSelectedRegion(e.target.value)}
          disabled={regionsLoading || names.length === 0}
        >
          {regionsLoading && <option value="">Loading…</option>}
          {!regionsLoading && names.length === 0 && (
            <option value="">No regions in database</option>
          )}
          {!regionsLoading &&
            names.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
        </select>
        <button
          type="button"
          className="home-page__stats-btn"
          onClick={handleGetStats}
          disabled={regionsLoading || !selectedRegion.trim()}
        >
          Get stats
        </button>
      </div>

      {regionsError && (
        <p className="home-page__error" role="alert">
          {regionsError}
        </p>
      )}

      <p className="home-page__disclaimer">
        {formattedRankingDate == null
          ? "Only offline data within the last 6 months prior to the latest ranking snapshot is considered."
          : `Only offline data within the last 6 months prior to the latest ranking snapshot: ${formattedRankingDate} is considered.`}
      </p>

      <section className="home-page__dashboard-section" aria-label="Region dashboard">
        {activeRegion != null && statsLoading && (
          <div className="home-page__loading-wrap">
            <LoadingSpinner label="Loading stats" />
          </div>
        )}
        {activeRegion != null && (
          <div
            className="home-page__dashboard-mount"
            style={{ display: statsLoading ? "none" : undefined }}
            aria-hidden={statsLoading}
          >
            <DashboardCards
              key={`${activeRegion}-${dashboardKey}`}
              region={activeRegion}
              onAllQueriesComplete={onAllQueriesComplete}
            />
          </div>
        )}
      </section>

      <footer className="home-page__footer">
        rankings from schustats, player data from start.gg, winrates from smashmate via pheasantzelda
        <br />
        created by{" "}
        <a href="https://jrgarces.vercel.app/" target="_blank" rel="noreferrer">
          Jack Garces
        </a>
      </footer>
    </main>
  );
}
