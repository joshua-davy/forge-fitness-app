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
import { useState } from "react";
import type { Goal } from "@/types";
import { GoalRow } from "./GoalRow";
import "./TomorrowGoalsCard.css";

interface Props {
  goals: Goal[];
  onCreate: (text: string, target: "today" | "tomorrow") => Promise<void> | void;
  onUpdate: (id: number, patch: Partial<Pick<Goal, "text" | "queued" | "sort_order">>) => Promise<void> | void;
  onDelete: (id: number) => Promise<void> | void;
  onReorder: (target: "today" | "tomorrow", ordered: Goal[]) => Promise<void> | void;
}

export function TomorrowGoalsCard({ goals, onCreate, onUpdate, onDelete, onReorder }: Props) {
  const [draft, setDraft] = useState("");
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  const submit = async () => {
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    await onCreate(text, "tomorrow");
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIdx = goals.findIndex((g) => g.id === active.id);
    const newIdx = goals.findIndex((g) => g.id === over.id);
    if (oldIdx < 0 || newIdx < 0) return;
    onReorder("tomorrow", arrayMove(goals, oldIdx, newIdx));
  };

  return (
    <div className="tmc card">
      <div className="tmc__head">
        <div>
          <div className="card__label">Plan tomorrow</div>
          <div className="tmc__title">
            <span className="tmc__title-big">{goals.length}</span>
            <span className="tmc__title-label">
              {goals.length === 0 ? "Nothing planned" : `planned for tomorrow`}
            </span>
          </div>
        </div>
      </div>

      <div className="tmc__add">
        <input
          className="tmc__input"
          placeholder="What does tomorrow need?"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
          }}
        />
        <button className="tmc__submit" onClick={submit} disabled={!draft.trim()}>
          Add
        </button>
      </div>

      {goals.length === 0 ? (
        <div className="tmc__empty">
          Plan the next day before energy fades. Future-you will thank present-you.
        </div>
      ) : (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={goals.map((g) => g.id)} strategy={verticalListSortingStrategy}>
            <ul className="tmc__list">
              <AnimatePresence initial={false}>
                {goals.map((g) => (
                  <GoalRow
                    key={g.id}
                    goal={g}
                    onEdit={(id, text) => onUpdate(id, { text })}
                    onDelete={(id) => onDelete(id)}
                    onToggleQueue={(id, queued) => onUpdate(id, { queued })}
                  />
                ))}
              </AnimatePresence>
            </ul>
          </SortableContext>
        </DndContext>
      )}
    </div>
  );
}
