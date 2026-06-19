import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import type { Goal } from "@/types";
import "./GoalRow.css";

interface Props {
  goal: Goal;
  readOnly?: boolean;
  onToggleDone?: (id: number, done: boolean) => void;
  onToggleQueue?: (id: number, queued: boolean) => void;
  onEdit?: (id: number, text: string) => void;
  onDelete?: (id: number) => void;
}

export function GoalRow({
  goal,
  readOnly = false,
  onToggleDone,
  onToggleQueue,
  onEdit,
  onDelete,
}: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: goal.id,
  });
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(goal.text);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  useEffect(() => {
    setDraft(goal.text);
  }, [goal.text]);

  const commitEdit = () => {
    const next = draft.trim();
    if (next && next !== goal.text) onEdit?.(goal.id, next);
    else setDraft(goal.text);
    setEditing(false);
  };

  const cancelEdit = () => {
    setDraft(goal.text);
    setEditing(false);
  };

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 20 : 1,
    opacity: isDragging ? 0.85 : 1,
  };

  return (
    <motion.li
      ref={setNodeRef}
      style={style}
      layout
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -8 }}
      transition={{ duration: 0.22, ease: [0.2, 0.8, 0.2, 1] }}
      className={`row-goal ${goal.done ? "row-goal--done" : ""} ${
        goal.queued && !goal.done ? "row-goal--queued" : ""
      }`}
    >
      {!readOnly && (
        <button
          className="row-goal__handle"
          aria-label="Drag"
          {...attributes}
          {...listeners}
        >
          <svg width="10" height="14" viewBox="0 0 10 14" fill="none">
            <circle cx="2" cy="2" r="1.2" fill="currentColor" />
            <circle cx="8" cy="2" r="1.2" fill="currentColor" />
            <circle cx="2" cy="7" r="1.2" fill="currentColor" />
            <circle cx="8" cy="7" r="1.2" fill="currentColor" />
            <circle cx="2" cy="12" r="1.2" fill="currentColor" />
            <circle cx="8" cy="12" r="1.2" fill="currentColor" />
          </svg>
        </button>
      )}

      <button
        className={`row-goal__check ${goal.done ? "row-goal__check--on" : ""}`}
        onClick={() => !readOnly && onToggleDone?.(goal.id, !goal.done)}
        disabled={readOnly}
        aria-label={goal.done ? "Mark incomplete" : "Mark complete"}
      >
        {goal.done && (
          <motion.svg
            width="11"
            height="11"
            viewBox="0 0 11 11"
            initial={{ scale: 0, rotate: -45 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{ type: "spring", stiffness: 600, damping: 16 }}
          >
            <path
              d="M1.5 5.6 L4.2 8.3 L9.5 2.5"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              fill="none"
            />
          </motion.svg>
        )}
      </button>

      <div className="row-goal__main">
        {editing ? (
          <input
            ref={inputRef}
            className="row-goal__input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commitEdit}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitEdit();
              if (e.key === "Escape") cancelEdit();
            }}
          />
        ) : (
          <span
            className="row-goal__text"
            onClick={() => !readOnly && setEditing(true)}
          >
            {goal.text}
          </span>
        )}
      </div>

      {!readOnly && (
        <div className="row-goal__actions">
          <button
            className={`row-goal__queue ${goal.queued ? "row-goal__queue--on" : ""}`}
            onClick={() => onToggleQueue?.(goal.id, !goal.queued)}
            aria-label="Queue for focus window"
            title="Queue for focus window"
          >
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
              <path
                d="M3 2 L10 2 L10 7 L6.5 11 L3 7 Z"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinejoin="round"
                fill="none"
              />
            </svg>
          </button>
          <button
            className="row-goal__delete"
            onClick={() => onDelete?.(goal.id)}
            aria-label="Delete goal"
          >
            <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
              <path
                d="M2 2 L9 9 M9 2 L2 9"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>
      )}
    </motion.li>
  );
}
