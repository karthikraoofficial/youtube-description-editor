import { useRef } from "react";
import {
  type AppendOp,
  type FindReplaceOp,
  type Operation,
  type PrependOp,
  type Separator,
  type TemplateOp,
  useTemplateVariables,
} from "../api/preview";
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
    case "template":
      return <TemplateForm op={op} onChange={onChange} />;
  }
}

const variableToken = (name: string) => `{${name}}`;

function TemplateForm({ op, onChange }: { op: TemplateOp; onChange: (op: TemplateOp) => void }) {
  const variables = useTemplateVariables();
  const box = useRef<HTMLTextAreaElement>(null);

  function insert(name: string) {
    const el = box.current;
    const token = variableToken(name);
    const start = el?.selectionStart ?? op.template.length;
    const end = el?.selectionEnd ?? op.template.length;
    onChange({ ...op, template: op.template.slice(0, start) + token + op.template.slice(end) });
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(start + token.length, start + token.length);
    });
  }

  return (
    <div className="space-y-4">
      <label className="block">
        <span className="mb-1 block text-sm font-medium">Template for the whole description</span>
        <textarea
          ref={box}
          rows={9}
          value={op.template}
          onChange={(e) => onChange({ ...op, template: e.target.value })}
          placeholder={"{description}\n\nWatch the full video: {video_url}"}
          className={input}
        />
      </label>
      <p className="text-xs text-muted">
        The result replaces the whole description. Include <code>{"{description}"}</code> to keep the current text.
      </p>
      <div>
        <span className="mb-1.5 block text-sm font-medium">Insert a variable</span>
        <div className="flex flex-wrap gap-1.5">
          {variables.data?.map((v) => (
            <button
              key={v.name}
              type="button"
              onClick={() => insert(v.name)}
              title={v.help}
              className="rounded border border-line bg-bg px-2 py-0.5 font-mono text-xs hover:border-accent hover:text-accent"
            >
              {variableToken(v.name)}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-muted">
          Hover a variable to see what it inserts. Write <code>{"{{"}</code> or <code>{"}}"}</code> for a literal brace.
        </p>
      </div>
    </div>
  );
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
