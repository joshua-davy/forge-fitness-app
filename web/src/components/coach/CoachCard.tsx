import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import type { CoachPayload } from "@/types";
import "./CoachCard.css";

interface Props { data: CoachPayload | null; onRefresh?: () => void; loadError?: Error | null; }

export function CoachCard({ data, onRefresh, loadError }: Props) {
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generate = async () => {
    setGenerating(true); setError(null);
    try {
      await api.coachGenerate();
      onRefresh?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setGenerating(false);
    }
  };

  if (!data) return (
    <div className="coach card">
      <div className="coach__head"><div className="card__label">Coach</div></div>
      <div className={loadError ? "coach__error" : "coach__loading"}>
        {loadError ? `Coach failed to load: ${loadError.message}` : "Reading your data..."}
      </div>
      {loadError && <button className="coach__gen" onClick={onRefresh}>Retry</button>}
    </div>
  );

  const toneClass = (t: string) => t === "good" ? "good" : t === "warn" ? "warn" : t === "bad" ? "bad" : "neutral";
  const groups = [
    { tone: "bad", label: "Needs attention", help: "Red", items: data.observations.filter((o) => o.tone === "bad") },
    { tone: "warn", label: "Watch", help: "Yellow", items: data.observations.filter((o) => o.tone === "warn") },
    { tone: "good", label: "Working well", help: "Green", items: data.observations.filter((o) => o.tone === "good") },
    { tone: "neutral", label: "Context", help: "Blue", items: data.observations.filter((o) => o.tone === "neutral") },
  ].filter((group) => group.items.length > 0);

  return (
    <div className="coach card">
      <div className="coach__head">
        <div className="card__label">Coach {data.used_ai && <span className="coach__ai-badge">AI</span>}</div>
        <div className="coach__meta-row">
          <span className="meta">Confidence {Math.round(data.confidence * 100)}%</span>
          <button className="coach__gen" onClick={generate} disabled={generating}>
            {generating ? "Generating…" : "↻ Generate"}
          </button>
        </div>
      </div>

      <div className="coach__headline">{data.headline}</div>

      <div className="coach__legend" aria-label="Coach colour legend">
        <span><i className="coach__legend-dot coach__legend-dot--bad" /> Red: act now</span>
        <span><i className="coach__legend-dot coach__legend-dot--warn" /> Yellow: watch</span>
        <span><i className="coach__legend-dot coach__legend-dot--good" /> Green: strength</span>
        <span><i className="coach__legend-dot coach__legend-dot--neutral" /> Blue: context</span>
      </div>

      {data.observations.length > 0 && (
        <div className="coach__groups">
          {groups.map((group) => (
            <section key={group.tone} className={`coach__group coach__group--${group.tone}`}>
              <div className="coach__group-label">{group.label} <span>{group.help}</span></div>
              <ul className="coach__list">
                <AnimatePresence initial={false}>
                  {group.items.map((o, i) => (
                    <motion.li key={o.kind + i} className={`coach__item coach__item--${toneClass(o.tone)}`}
                      initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.28, delay: i * 0.04 }}>
                      <div className="coach__body">{o.text}</div>
                    </motion.li>
                  ))}
                </AnimatePresence>
              </ul>
            </section>
          ))}
        </div>
      )}

      {data.actions.length > 0 && (
        <div className="coach__section">
          <div className="coach__section-label">ACTIONS</div>
          {data.actions.map((a, i) => (
            <div key={i} className={`coach__action coach__action--${a.priority}`}>
              <span className="coach__action-dot" />
              {a.text}
            </div>
          ))}
        </div>
      )}

      {data.risks.length > 0 && (
        <div className="coach__section">
          <div className="coach__section-label">RISKS</div>
          {data.risks.map((r, i) => (
            <div key={i} className="coach__risk">⚠ {r.text}</div>
          ))}
        </div>
      )}

      {error && <div className="coach__error">{error}</div>}
      {data.warning && <div className="coach__warning">{data.warning}</div>}
    </div>
  );
}
