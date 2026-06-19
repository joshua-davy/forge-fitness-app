import { Component, type ReactNode } from "react";
import { DashboardScreen } from "@/screens/Dashboard";

export default function App() {
  return (
    <AppErrorBoundary>
      <DashboardScreen />
    </AppErrorBoundary>
  );
}

class AppErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <main className="app">
          <div className="card" style={{ marginTop: 40 }}>
            <div className="card__label">Forge recovered from a screen error</div>
            <p style={{ color: "var(--text-2)", lineHeight: 1.5 }}>
              {this.state.error.message}
            </p>
            <button className="dash-syncbar__btn" style={{ marginTop: 16 }} onClick={() => window.location.reload()}>
              Reload Forge
            </button>
          </div>
        </main>
      );
    }
    return this.props.children;
  }
}
