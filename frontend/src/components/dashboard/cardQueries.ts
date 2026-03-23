/**
 * One async function per dashboard card. Replace placeholders with real API calls.
 * DashboardCards awaits Promise.all(...) so the UI stays in loading until every query settles.
 */

export async function fetchRegionOverviewCard(region: string): Promise<{ headline: string }> {
  await new Promise((r) => setTimeout(r, 400 + Math.random() * 200));
  return { headline: `Overview for ${region}` };
}

export async function fetchRegionActivityCard(region: string): Promise<{ items: number }> {
  await new Promise((r) => setTimeout(r, 500 + Math.random() * 200));
  // Placeholder: tie to region so the param is used; replace with real metrics later.
  return { items: 12 + (region.length % 5) };
}

export async function fetchRegionTopPlayersCurrentTagsCard(
  region: string,
): Promise<{
  topPlayers: Array<{ current_tag: string; supermajor_player_id: number }>;
}> {
  const API_BASE = "/api";
  const params = new URLSearchParams({ region_name: region });
  const res = await fetch(`${API_BASE}/regions/top-players/current-tags?${params.toString()}`);
  if (!res.ok) {
    throw new Error(`Request failed (${res.status})`);
  }
  const data: { top_players: Array<{ current_tag: string; supermajor_player_id: number }> } = await res.json();
  return { topPlayers: data.top_players ?? [] };
}

export async function fetchRegionMostMainedCharactersCard(
  region: string,
): Promise<{
  mostMainedCharacters: Array<{
    character_id: number;
    character_name: string;
    main_count: number;
  }>;
}> {
  const API_BASE = "/api";
  const params = new URLSearchParams({ region_name: region });
  const res = await fetch(`${API_BASE}/regions/most-mained-characters?${params.toString()}`);
  if (!res.ok) {
    throw new Error(`Request failed (${res.status})`);
  }

  const data: {
    most_mained_characters: Array<{ character_id: number; character_name: string; main_count: number }>;
  } = await res.json();

  return { mostMainedCharacters: data.most_mained_characters ?? [] };
}

export async function fetchRegionMostBattledCharactersCard(
  region: string,
): Promise<{
  mostBattledCharacters: Array<{
    character_id: number;
    character_name: string;
    games_played_sum: number;
  }>;
}> {
  const API_BASE = "/api";
  const params = new URLSearchParams({ region_name: region });
  const res = await fetch(`${API_BASE}/regions/most-battled-characters?${params.toString()}`);
  if (!res.ok) {
    throw new Error(`Request failed (${res.status})`);
  }

  const data: {
    most_battled_characters: Array<{
      character_id: number;
      character_name: string;
      games_played_sum: number;
    }>;
  } = await res.json();

  return { mostBattledCharacters: data.most_battled_characters ?? [] };
}

export async function fetchRegionLeastAppearancesCharactersCard(
  region: string,
): Promise<{
  leastAppearancesCharacters: Array<{
    character_id: number;
    character_name: string;
    games_played_sum: number;
  }>;
}> {
  const API_BASE = "/api";
  const params = new URLSearchParams({ region_name: region });
  const res = await fetch(
    `${API_BASE}/regions/least-appearances-characters?${params.toString()}`,
  );
  if (!res.ok) {
    throw new Error(`Request failed (${res.status})`);
  }

  const data: {
    least_appearances_characters: Array<{
      character_id: number;
      character_name: string;
      games_played_sum: number;
    }>;
  } = await res.json();

  return { leastAppearancesCharacters: data.least_appearances_characters ?? [] };
}

export async function fetchRegionUnusedCharactersCard(
  region: string,
): Promise<{
  unusedCharacters: Array<{
    character_id: number;
    character_name: string;
  }>;
}> {
  const API_BASE = "/api";
  const params = new URLSearchParams({ region_name: region });
  const res = await fetch(`${API_BASE}/regions/unused-characters?${params.toString()}`);
  if (!res.ok) {
    throw new Error(`Request failed (${res.status})`);
  }

  const data: {
    unused_characters: Array<{ character_id: number; character_name: string }>;
  } = await res.json();

  return { unusedCharacters: data.unused_characters ?? [] };
}
