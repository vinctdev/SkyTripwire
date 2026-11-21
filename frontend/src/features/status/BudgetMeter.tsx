// Requests used in the rolling 24 h window against the daily budget. The fill carries the state
// (normal, near limit, limit reached) on a neutral track, and the state is always written out as
// text as well.

const LEVELS = {
  normal: { fill: "bg-accent", label: null },
  near: { fill: "bg-meter-warning", label: "Near limit" },
  full: { fill: "bg-meter-danger", label: "Limit reached" },
} as const;

export function budgetLevel(used: number, budget: number): keyof typeof LEVELS {
  if (budget <= 0 || used >= budget) return "full";
  return used / budget >= 0.8 ? "near" : "normal";
}

export function BudgetMeter({
  used,
  budget,
  label,
}: {
  used: number;
  budget: number;
  label: string;
}) {
  const level = LEVELS[budgetLevel(used, budget)];
  const percent = budget > 0 ? Math.min(100, Math.round((used / budget) * 100)) : 100;
  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-baseline justify-between gap-2 tabular-nums">
        <span>
          {used.toLocaleString("en-US")} of {budget.toLocaleString("en-US")} requests (
          {String(percent)}%)
        </span>
        {level.label && <span className="text-sm font-semibold">{level.label}</span>}
      </div>
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={budget}
        aria-valuenow={Math.min(used, budget)}
        aria-valuetext={`${String(used)} of ${String(budget)} requests${level.label ? `, ${level.label.toLowerCase()}` : ""}`}
        className="h-2.5 w-full overflow-hidden rounded-full bg-meter-track"
      >
        <div
          className={`h-full rounded-full ${level.fill}`}
          style={{ width: `${String(percent)}%` }}
        />
      </div>
    </div>
  );
}
