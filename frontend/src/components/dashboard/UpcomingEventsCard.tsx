type Props = {
  region: string;
  data: {
    tournaments: Array<{
      id: number | null;
      name: string;
      city: string | null;
      addr_state: string | null;
      start_at: number | null;
      slug: string | null;
      url: string | null;
    }>;
  };
};

function formatStartDate(unixSeconds: number | null): string {
  if (unixSeconds == null) return "Date TBD";
  return new Date(unixSeconds * 1000).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatLocation(city: string | null, state: string | null): string {
  if (city && state) return `${city}, ${state}`;
  if (city) return city;
  if (state) return state;
  return "Location TBD";
}

export function UpcomingEventsCard({ region, data }: Props) {
  const events = data.tournaments ?? [];

  return (
    <article className="dashboard-card">
      <h2 className="dashboard-card__title">Upcoming Events</h2>
      <p className="dashboard-card__meta">Start.gg events near {region}</p>

      <ol className="dashboard-card__list dashboard-card__list--scroll">
        {events.length === 0 ? (
          <li>No data yet</li>
        ) : (
          events.map((event, idx) => (
            <li key={`${event.id ?? "none"}-${event.slug ?? event.name}-${idx}`}>
              {event.url ? (
                <a href={event.url} target="_blank" rel="noreferrer">
                  {event.name}
                </a>
              ) : (
                <span>{event.name}</span>
              )}{" "}
              - {formatStartDate(event.start_at)} ({formatLocation(event.city, event.addr_state)})
            </li>
          ))
        )}
      </ol>
    </article>
  );
}

