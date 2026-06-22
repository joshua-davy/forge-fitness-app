import "./Header.css";

interface Props {
  date: string; // ISO yyyy-mm-dd
  greetingName?: string | null;
  onPreviousDay?: () => void;
  onNextDay?: () => void;
  onToday?: () => void;
  nextDisabled?: boolean;
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function pretty(iso: string): string {
  try {
    const d = new Date(iso + "T00:00:00");
    return `${WEEKDAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}`;
  } catch {
    return iso;
  }
}

export function Header({ date, greetingName, onPreviousDay, onNextDay, onToday, nextDisabled }: Props) {
  return (
    <header className="forge-header">
      <div className="forge-header__brand">
        <div className="forge-header__mark">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <path
              d="M11 1 L20 6 V16 L11 21 L2 16 V6 Z"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinejoin="round"
              fill="rgba(107,227,164,0.05)"
            />
            <path
              d="M11 6 V11 L15 13"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
            />
          </svg>
        </div>
        <div>
          <div className="forge-header__eyebrow">DAILY COMMAND CENTRE</div>
          <h1 className="forge-header__title">FORGE</h1>
          {greetingName && <div className="forge-header__greeting">Welcome back, {greetingName}.</div>}
        </div>
      </div>
      <div className="forge-header__date">
        <div className="forge-header__date-label">ACTIVE DATE</div>
        <div className="forge-header__date-value">{pretty(date)}</div>
        <div className="forge-header__nav">
          <button onClick={onPreviousDay} aria-label="Previous day">Prev day</button>
          <button onClick={onToday}>Today</button>
          <button onClick={onNextDay} disabled={nextDisabled} aria-label="Next day">Next day</button>
        </div>
      </div>
    </header>
  );
}
