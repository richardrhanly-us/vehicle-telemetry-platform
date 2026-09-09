import type { AlarmEvent } from "../types/telemetry";
import {
  type AlarmGroup,
  computeElapsedLabel,
  formatFieldValueWithUnit,
  getFieldMeta,
  pairAlarmEvents,
} from "../utils/telemetry";

interface AlarmTimelineProps {
  events: AlarmEvent[];
  tripStartTime: string | null;
}

export function AlarmTimeline({ events, tripStartTime }: AlarmTimelineProps) {
  if (!events.length) {
    return (
      <div className="empty-state">
        No recorded alarm events for this trip.
      </div>
    );
  }

  const groups = pairAlarmEvents(events);

  return (
    <div className="alarm-list">
      {groups.map((group, index) => (
        <AlarmGroupCard
          key={`${group.rule}-${index}`}
          group={group}
          tripStartTime={tripStartTime}
        />
      ))}
    </div>
  );
}

function AlarmGroupCard({
  group,
  tripStartTime,
}: {
  group: AlarmGroup;
  tripStartTime: string | null;
}) {
  const primary = group.triggered ?? group.cleared;

  if (!primary) {
    return null;
  }

  const severity = (primary.severity || "warning").toLowerCase();
  const badgeClass = severity === "critical" ? "critical" : "warning";
  const containerClass = group.cleared ? "cleared" : "triggered";

  return (
    <div className={`alarm-event ${containerClass}`}>
      <div className="alarm-event-top">
        <span className="alarm-event-title">{group.rule}</span>
        <span className={`alarm-badge ${badgeClass}`}>{severity}</span>
      </div>

      <div className="alarm-event-meta">
        {group.triggered && (
          <TriggeredPhase
            event={group.triggered}
            tripStartTime={tripStartTime}
          />
        )}

        {group.cleared ? (
          <ClearedPhase event={group.cleared} tripStartTime={tripStartTime} />
        ) : group.triggered ? (
          <div className="alarm-event-phase">
            <span className="alarm-event-phase-label">Still active</span>{" "}
            at end of trip
          </div>
        ) : null}
      </div>
    </div>
  );
}

function TriggeredPhase({
  event,
  tripStartTime,
}: {
  event: AlarmEvent;
  tripStartTime: string | null;
}) {
  const elapsed = computeElapsedLabel(event.timestamp, tripStartTime);
  const meta = getFieldMeta(event.field);
  const requirement = event.duration_requirement_seconds;

  return (
    <div className="alarm-event-phase">
      <span className="alarm-event-phase-label">Triggered</span>
      {elapsed ? ` at ${elapsed}` : ""}
      <br />
      {meta ? meta.label : event.field}:{" "}
      {formatFieldValueWithUnit(event.field, event.value)} (
      {event.operator ?? ""}
      {formatFieldValueWithUnit(event.field, event.threshold)})
      {requirement !== null && requirement !== undefined ? (
        <>
          <br />
          Duration requirement: {requirement} sec
        </>
      ) : null}
    </div>
  );
}

function ClearedPhase({
  event,
  tripStartTime,
}: {
  event: AlarmEvent;
  tripStartTime: string | null;
}) {
  const elapsed = computeElapsedLabel(event.timestamp, tripStartTime);

  return (
    <div className="alarm-event-phase">
      <span className="alarm-event-phase-label">Cleared</span>
      {elapsed ? ` at ${elapsed}` : ""}
      <br />
      Active: {event.duration_seconds.toFixed(1)} sec
    </div>
  );
}
