import { useEffect, useState } from "react";
import "./App.css";
import { TripPlaybackSection } from "./components/TripPlaybackSection";
import { TripSelector } from "./components/TripSelector";
import { DEFAULT_TRIP_ID, TRIP_OPTIONS } from "./config/tripOptions";
import type { DemoTrip } from "./types/telemetry";
import { formatVehicleName } from "./utils/telemetry";

function App() {
  const [selectedTripId, setSelectedTripId] = useState(DEFAULT_TRIP_ID);
  const [trip, setTrip] = useState<DemoTrip | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const option =
      TRIP_OPTIONS.find((candidate) => candidate.id === selectedTripId) ??
      TRIP_OPTIONS[0];

    fetch(`${import.meta.env.BASE_URL}trips/${option.file}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error("Demo trip data could not be loaded.");
        }

        return response.json() as Promise<unknown>;
      })
      .then((data) => {
        if (!cancelled) {
          setTrip(data as DemoTrip);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError("Unable to load the recorded trip for this demo.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedTripId]);

  // Clearing the previous trip lives in this event handler (not an
  // effect, not a render-phase ref diff) — the ordinary, unrestricted
  // place to fire multiple state updates together. It drops `trip` to
  // null immediately, which hides/unmounts the keyed TripPlaybackSection
  // below until the newly selected trip's data has actually loaded, so
  // that component is only ever mounted once per trip with its final
  // data — never handed a different trip mid-lifetime.
  function handleTripChange(id: string) {
    setSelectedTripId(id);
    setTrip(null);
    setLoadError(null);
  }

  const vehicleName = formatVehicleName(trip?.metadata.vehicle);

  return (
    <main className="telemetry-demo">
      <header className="demo-header">
        <div>
          <p className="eyebrow">Vehicle Telemetry Platform</p>
          <h1>Recorded Telemetry Demo</h1>
          <p className="subtitle">
            Playback interface for a real-world OBD-II trip recorded by this
            project{trip ? ` from a ${vehicleName}` : ""}.
          </p>
        </div>

        <div className="recorded-badge">Recorded Real-World Telemetry</div>
      </header>

      <section className="vehicle-panel">
        <div>
          <p className="panel-label">Vehicle</p>
          <h2>{vehicleName}</h2>
        </div>

        <div className="trip-meta">
          <div>
            <span>Trip</span>
            <TripSelector
              options={TRIP_OPTIONS}
              selectedId={selectedTripId}
              onChange={handleTripChange}
            />
          </div>

          <div>
            <span>Source</span>
            <strong>OBDLink EX</strong>
          </div>

          <div>
            <span>Mode</span>
            <strong>Playback</strong>
          </div>
        </div>
      </section>

      {loadError && <div className="empty-state">{loadError}</div>}

      {!trip && !loadError && (
        <div className="empty-state">Loading recorded trip…</div>
      )}

      {trip && <TripPlaybackSection key={selectedTripId} trip={trip} />}

      <footer className="demo-footer">
        <p>
          This demo replays recorded telemetry sessions through a browser-based
          playback interface.
        </p>

        <a
          href="https://github.com/richardrhanly-us/vehicle-telemetry-platform"
          target="_blank"
          rel="noreferrer"
        >
          View Source Code
        </a>
      </footer>
    </main>
  );
}

export default App;
