import type { TripOption } from "../config/tripOptions";

interface TripSelectorProps {
  options: TripOption[];
  selectedId: string;
  onChange: (id: string) => void;
}

export function TripSelector({
  options,
  selectedId,
  onChange,
}: TripSelectorProps) {
  return (
    <select
      className="trip-select"
      value={selectedId}
      onChange={(event) => onChange(event.target.value)}
      aria-label="Select recorded trip"
    >
      {options.map((option) => (
        <option key={option.id} value={option.id}>
          {option.label}
        </option>
      ))}
    </select>
  );
}
