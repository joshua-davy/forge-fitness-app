import "./GoalProgressBar.css";

interface Props {
  total: number;
  completed: number;
  queued?: number;
}

export function GoalProgressBar({ total, completed, queued = 0 }: Props) {
  if (total === 0) {
    return (
      <div className="gpb gpb--empty">
        <div className="gpb__track" />
        <span className="gpb__label">No goals yet</span>
      </div>
    );
  }
  const allDone = completed === total;
  return (
    <div className={`gpb ${allDone ? "gpb--good" : ""}`}>
      <div className="gpb__track">
        <div
          className="gpb__fill"
          style={{ width: `${(completed / total) * 100}%` }}
        />
        {queued > 0 && !allDone && (
          <div
            className="gpb__queued"
            style={{
              left: `${(completed / total) * 100}%`,
              width: `${(queued / total) * 100}%`,
            }}
          />
        )}
        <div className="gpb__segments">
          {Array.from({ length: total - 1 }).map((_, i) => (
            <div
              key={i}
              className="gpb__seg"
              style={{ left: `${((i + 1) / total) * 100}%` }}
            />
          ))}
        </div>
      </div>
      <span className="gpb__label">
        {allDone ? "All done — solid day" : `${completed}/${total} complete`}
      </span>
    </div>
  );
}
