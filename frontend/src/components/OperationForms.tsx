import type { AppendOp, FindReplaceOp, Operation, PrependOp, Separator } from "../api/preview";
import { metaOf } from "../lib/operations";

const input =
  "w-full rounded-md border border-line bg-bg px-3 py-2 font-mono text-sm focus-visible:outline-2 focus-visible:outline-accent";

export function OperationForm({ op, onChange }: { op: Operation; onChange: (op: Operation) => void }) {
  switch (op.type) {
    case "find_replace":
      return <FindReplaceForm op={op} onChange={onChange} />;
    case "append":
    case "prepend":
      return <AddTextForm op={op} onChange={onChange} />;
  }
}

function FindReplaceForm({ op, onChange }: { op: FindReplaceOp; onChange: (op: FindReplaceOp) => void }) {
  const set = <K extends keyof FindReplaceOp>(k: K, v: FindReplaceOp[K]) => onChange({ ...op, [k]: v });
  return (
    <div className="space-y-4">
      <label className="block">
        <span className="mb-1 block text-sm font-medium">Find</span>
        <textarea rows={3} value={op.find} onChange={(e) => set("find", e.target.value)} className={input} />
      </label>
      <label className="block">
        <span className="mb-1 block text-sm font-medium">Replace with</span>
        <textarea
          rows={3}
          value={op.replace}
          onChange={(e) => set("replace", e.target.value)}
          placeholder="Leave empty to delete the matches"
          className={input}
        />
      </label>
      <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={op.case_sensitive} onChange={(e) => set("case_sensitive", e.target.checked)} />
          Match case
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={op.regex} onChange={(e) => set("regex", e.target.checked)} />
          Regular expression
        </label>
      </div>
      {op.regex && (
        <p className="text-xs text-muted">
          Python-style regex. <code>^</code> and <code>$</code> match at each line; use <code>\1</code> or{" "}
          <code>\g&lt;name&gt;</code> in the replacement for captured groups.
        </p>
      )}
    </div>
  );
}

const SEPARATORS: { value: Separator; label: string }[] = [
  { value: "blank_line", label: "Blank line" },
  { value: "newline", label: "New line" },
  { value: "none", label: "Nothing" },
];

function AddTextForm<T extends AppendOp | PrependOp>({ op, onChange }: { op: T; onChange: (op: T) => void }) {
  const set = <K extends keyof T>(k: K, v: T[K]) => onChange({ ...op, [k]: v });
  const { at: where, placeholder } = metaOf(op.type).adds!;
  return (
    <div className="space-y-4">
      <label className="block">
        <span className="mb-1 block text-sm font-medium">
          Text to add at the {where} of each description
        </span>
        <textarea
          rows={7}
          value={op.text}
          onChange={(e) => set("text", e.target.value as T["text"])}
          placeholder={placeholder}
          className={input}
        />
      </label>
      <fieldset>
        <legend className="mb-1.5 text-sm font-medium">
          Separate it from the existing description with
        </legend>
        <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
          {SEPARATORS.map((s) => (
            <label key={s.value} className="flex items-center gap-2">
              <input
                type="radio"
                name={`${op.type}-separator`}
                checked={op.separator === s.value}
                onChange={() => set("separator", s.value as T["separator"])}
              />
              {s.label}
            </label>
          ))}
        </div>
      </fieldset>
      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          className="mt-0.5"
          checked={op.skip_if_present}
          onChange={(e) => set("skip_if_present", e.target.checked as T["skip_if_present"])}
        />
        <span>
          Skip videos that already {where} with this text
          <span className="block text-xs text-muted">So running it twice never adds it twice. Skipped videos cost no quota.</span>
        </span>
      </label>
      <p className="text-xs text-muted">
        Spaces and blank lines at the {where} of the existing description are tidied up first, and blank lines around
        your text are removed. Everything else stays exactly as it is.
      </p>
    </div>
  );
}
