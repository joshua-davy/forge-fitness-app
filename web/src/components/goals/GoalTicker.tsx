import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import type { Goal } from "@/types";
import "./GoalTicker.css";

interface Props {
  goals: Goal[];
}

export function GoalTicker({ goals }: Props) {
  const pending = useMemo(() => goals.filter((g) => !g.done), [goals]);
  const done = goals.length - pending.length;
  const [idx, setIdx] = useState(0);

  // Reset index when pending list shrinks
  useEffect(() => {
    if (idx >= pending.length) setIdx(0);
  }, [pending.length, idx]);

  // Rotate every 5s
  useEffect(() => {
    if (pending.length < 2) return;
    const id = window.setInterval(() => {
      setIdx((i) => (i + 1) % pending.length);
    }, 5000);
    return () => window.clearInterval(id);
  }, [pending.length]);

  const empty = goals.length === 0;
  const allDone = !empty && pending.length === 0;
  const current = pending[idx];

  let body: React.ReactNode;
  if (empty) {
    body = (
      <span className="ticker__text ticker__text--muted">
        No goals set for today — add one to get rolling.
      </span>
    );
  } else if (allDone) {
    body = (
      <span className="ticker__text ticker__text--good">
        ✓ All goals done — solid day.
      </span>
    );
  } else {
    body = (
      <AnimatePresence mode="wait">
        <motion.span
          key={current?.id ?? idx}
          className="ticker__text"
          initial={{ y: 14, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -14, opacity: 0 }}
          transition={{ duration: 0.32, ease: [0.2, 0.8, 0.2, 1] }}
        >
          {current?.text}
        </motion.span>
      </AnimatePresence>
    );
  }

  return (
    <div className={`ticker ${allDone ? "ticker--good" : ""}`}>
      <div className="ticker__led" aria-hidden />
      <span className="ticker__label">GOALS</span>
      <div className="ticker__body">{body}</div>
      <span className={`ticker__count ${allDone ? "ticker__count--good" : ""}`}>
        {done}/{goals.length}
      </span>
      <div className="ticker__scan" aria-hidden />
    </div>
  );
}
