import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { SortableContext, arrayMove, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { AnimatePresence } from "framer-motion";
import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Goal, Streak } from "@/types";
import { GoalProgressBar } from "./GoalProgressBar";
import { GoalRow } from "./GoalRow";
import { StreakPill } from "./StreakPill";
import "./TodayGoalsCard.css";

interface Props {
  goals: Goal[];
  streak: Streak | null;
  onCreate: (text: string, target: "today" | "tomorrow") => Promise<void> | void;
  onUpdate: (id: number, patch: Partial<Pick<Goal, "text" | "done" | "queued" | "sort_order">>) => Promise<void> | void;
  onDelete: (id: number) => Promise<void> | void;
  onReorder: (target: "today" | "tomorrow", ordered: Goal[]) => Promise<void> | void;
  onPushRemaining: () => Promise<void> | void;
}

export function TodayGoalsCard({
  goals,
  streak,
  onCreate,
  onUpdate,
  onDelete,
  onReorder,
  onPushRemaining,
}: Props) {
  const [draft, setDraft] = useState("");
  const [polishing, setPolishing] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  const completed = goals.filter((g) => g.done).length;
  const queued = goals.filter((g) => g.queued && !g.done).length;
  const allDone = goals.length > 0 && completed === goals.length;

  const visible = useMemo(() => {
    if (expanded || goals.length <= 5) return goals;
    return goals.slice(0, 5);
  }, [goals, expanded]);

  const submit = async () => {
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    await onCreate(text, "today");
  };

  const polish = async () => {
    if (!draft.trim() || polishing) return;
    setPolishing(true);
    try {
      const res = await api.polish(draft.trim());
      setDraft(res.text);
    } catch {
      // silent — user can still submit raw text
    } finally {
      setPolishing(false);
    }
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIdx = goals.findIndex((g) => g.id === active.id);
    const newIdx = goals.findIndex((g) => g.id === over.id);
    if (oldIdx < 0 || newIdx < 0) return;
    onReorder("today", arrayMove(goals, oldIdx, newIdx));
  };

  const pending = goals.length - completed;

  return (
    <div className={`tgc card ${allDone ? "tgc--good" : ""}`}>
      <div className="tgc__head">
        <div>
          <div className="card__label">Today</div>
          <div className="tgc__count">
            <span className="tgc__count-big">{completed}</span>
            <span className="tgc__count-of">/ {goals.length}</span>
            <span className="tgc__count-label">
              {goals.length === 0
                ? "No goals yet"
                : allDone
                ? "Solid day"
                : `${pending} pending`}
            </span>
          </div>
        </div>
        <div className="tgc__head-right">
          {streak && <StreakPill count={streak.count} />}
        </div>
      </div>

      <GoalProgressBar total={goals.length} completed={completed} queued={queued} />

      <div className="tgc__add">
        <input
          className="tgc__input"
          placeholder={polishing ? "Polishing…" : "Add a goal…"}
          value={draft}
          disabled={polishing}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
          }}
        />
        <button
          className="tgc__polish"
          onClick={polish}
          disabled={!draft.trim() || polishing}
          title="Polish with AI"
        >
          {polishing ? "…" : "Polish"}
        </button>
        <button className="tgc__submit" onClick={submit} disabled={!draft.trim()}>
          Add
        </button>
      </div>

      {goals.length === 0 ? (
        <div className="tgc__empty">Set the day's intent. 3 things you'll be glad you did.</div>
      ) : (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={visible.map((g) => g.id)} strategy={verticalListSortingStrategy}>
            <ul className="tgc__list">
              <AnimatePresence initial={false}>
                {visible.map((g) => (
                  <GoalRow
                    key={g.id}
                    goal={g}
                    onToggleDone={(id, done) => onUpdate(id, { done })}
                    onToggleQueue={(id, queued) => onUpdate(id, { queued })}
                    onEdit={(id, text) => onUpdate(id, { text })}
                    onDelete={(id) => onDelete(id)}
                  />
                ))}
              </AnimatePresence>
            </ul>
          </SortableContext>
        </DndContext>
      )}

      {goals.length > 5 && (
        <button className="tgc__more" onClick={() => setExpanded((v) => !v)}>
          {expanded ? "Show less" : `Show ${goals.length - 5} more`}
        </button>
      )}

      {pending > 0 && (
        <div className="tgc__foot">
          <button className="tgc__push" onClick={() => onPushRemaining()}>
            Push remaining to tomorrow →
          </button>
        </div>
      )}
    </div>
  );
}
