import { useState } from "react";
import { api } from "@/lib/api";
import "./Onboarding.css";

interface Props {
  garminConfigured: boolean;
  onSynced: () => void;
}

export function Onboarding({ garminConfigured, onSynced }: Props) {
  const [syncing, setSyncing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const syncToday = async () => {
    setSyncing(true); setError(null);
    try {
      await api.syncGarmin();
      setResult("Today synced successfully.");
      onSynced();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  const importHistory = async () => {
    setImporting(true); setError(null);
    try {
      const r = await api.syncGarminHistory(365);
      setResult(`Imported ${r.synced} days. ${r.failed} failed, ${r.skipped} skipped.`);
      onSynced();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Import failed");
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="onboarding">
      <div className="onboarding__mark">
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
          <path d="M20 2 L37 11 V29 L20 38 L3 29 V11 Z" stroke="#6BE3A4" strokeWidth="1.5" strokeLinejoin="round" fill="rgba(107,227,164,0.06)" />
          <path d="M20 11 V20 L27 24" stroke="#6BE3A4" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      </div>
      <h1 className="onboarding__title">Welcome to Forge</h1>
      <p className="onboarding__sub">
        Connect your Garmin to unlock your full health intelligence dashboard.
      </p>

      <div className="onboarding__what">
        <div className="onboarding__what-label">FORGE WILL CALCULATE</div>
        <div className="onboarding__chips">
          {["Sleep Score","Recovery","Strain","HRV","Resting HR","Body Battery",
            "Stress","SpO2","Fitness Age","Biological Age","VO2 Max","AI Coaching"].map(m => (
            <span key={m} className="onboarding__chip">{m}</span>
          ))}
        </div>
      </div>

      {!garminConfigured ? (
        <div className="onboarding__setup">
          <div className="onboarding__setup-title">Setup required</div>
          <p className="onboarding__setup-body">
            Add your Garmin credentials to the <code>.env</code> file in the <code>backend/</code> folder:
          </p>
          <pre className="onboarding__code">{`GARMIN_EMAIL=your@email.com\nGARMIN_PASSWORD=yourpassword\nUSER_BIRTH_YEAR=1990`}</pre>
          <p className="onboarding__setup-body">Then restart the backend and refresh this page.</p>
        </div>
      ) : (
        <div className="onboarding__actions">
          <button
            className="onboarding__btn onboarding__btn--primary"
            onClick={syncToday}
            disabled={syncing || importing}
          >
            {syncing ? "Syncing today…" : "Sync Today"}
          </button>
          <button
            className="onboarding__btn onboarding__btn--secondary"
            onClick={importHistory}
            disabled={importing || syncing}
          >
            {importing ? "Importing 365 days… (this takes a while)" : "Import Last 365 Days"}
          </button>
        </div>
      )}

      {result && <div className="onboarding__result">{result}</div>}
      {error && <div className="onboarding__error">{error}</div>}
    </div>
  );
}
