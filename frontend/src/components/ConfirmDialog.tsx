import { useEffect, useId, useRef } from "react";
import { Button } from "./ui/Button";

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
      className="m-auto w-[min(92vw,480px)] rounded-2xl border border-line bg-surface p-0 text-fg shadow-xl backdrop:bg-black/40 backdrop:backdrop-blur-[2px]"
    >
      <div className="p-5 sm:p-6">
        <h2 id={titleId} className="mb-3 text-lg font-semibold">
          {title}
        </h2>
        <div id={bodyId} className="space-y-2 text-sm text-muted">
          {children}
        </div>
        <div className="mt-6 flex flex-wrap justify-end gap-2">
          <Button ref={cancel} variant="outline" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button
            variant={tone === "danger" ? "danger" : "primary"}
            onClick={onConfirm}
            disabled={busy}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </dialog>
  );
}
