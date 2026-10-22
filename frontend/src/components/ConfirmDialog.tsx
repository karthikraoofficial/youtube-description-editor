import { useEffect, useId, useRef } from "react";

type Props = {
  open: boolean;
  title: string;
  children: React.ReactNode;
  confirmLabel: string;
  /** Label for the button that closes without doing anything. */
  cancelLabel?: string;
  tone?: "danger" | "accent";
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

/** A modal question. Escape or the backdrop cancels; focus starts on Cancel so Enter never confirms by accident. */
export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  cancelLabel = "Cancel",
  tone = "accent",
  busy,
  onConfirm,
  onCancel,
}: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const bodyId = useId();

  useEffect(() => {
    const el = dialog.current;
    if (!el) return;
    if (open && !el.open) {
      el.showModal();
      cancel.current?.focus();
    } else if (!open && el.open) el.close();
  }, [open]);

  return (
    <dialog
      ref={dialog}
      onCancel={(e) => {
        e.preventDefault();
        onCancel();
      }}
      onClick={(e) => {
        if (e.target === dialog.current) onCancel();
      }}
      aria-labelledby={titleId}
      aria-describedby={bodyId}
      className="m-auto w-[min(92vw,480px)] rounded-xl border border-line bg-surface p-0 text-fg shadow-xl backdrop:bg-black/50"
    >
      <div className="p-6">
        <h2 id={titleId} className="mb-3 text-lg font-semibold">
          {title}
        </h2>
        <div id={bodyId} className="space-y-2 text-sm text-muted">
          {children}
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button
            ref={cancel}
            type="button"
            onClick={onCancel}
            className="rounded-md border border-line px-4 py-2 text-sm hover:bg-line/50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className={`rounded-md px-4 py-2 text-sm font-medium text-on-accent hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-60 ${
              tone === "danger" ? "bg-danger focus-visible:outline-danger" : "bg-accent focus-visible:outline-accent"
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </dialog>
  );
}
