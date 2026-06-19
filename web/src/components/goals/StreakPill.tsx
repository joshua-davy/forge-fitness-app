import "./StreakPill.css";

interface Props {
  count: number;
}

export function StreakPill({ count }: Props) {
  return (
    <div className={`streak ${count > 0 ? "streak--on" : ""}`}>
      <svg width="12" height="14" viewBox="0 0 12 14" fill="none" aria-hidden>
        <path
          d="M6 0 C 7 3, 11 4, 11 8 a 5 5 0 1 1 -10 0 C 1 5, 3 4, 4 1 C 4 3, 5 4, 6 5 Z"
          fill="currentColor"
        />
      </svg>
      <span className="streak__count">{count}</span>
      <span className="streak__label">day{count === 1 ? "" : "s"}</span>
    </div>
  );
}
