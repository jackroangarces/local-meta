import { useCallback, useEffect, useState } from "react";
import { DashboardCards } from "../components/dashboard/DashboardCards";
import LoadingSpinner from "../components/LoadingSpinner";

type RegionsNamesResponse = { names: string[] };

const API_BASE = "/api";

export default function Home() {
  const [names, setNames] = useState<string[]>([]);
  const [regionsLoading, setRegionsLoading] = useState(true);
  const [regionsError, setRegionsError] = useState<string | null>(null);
  const [selectedRegion, setSelectedRegion] = useState("");
  const [activeRegion, setActiveRegion] = useState<string | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [dashboardKey, setDashboardKey] = useState(0);

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

  return (
    <main className="home-page">
      <h1 className="home-page__title">Local Meta</h1>
      <p className="home-page__lead">Select your region to see stats. It's time to stop going 0-2.</p>

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
        rankings from schustats, player data from start.gg
      </footer>
    </main>
  );
}
