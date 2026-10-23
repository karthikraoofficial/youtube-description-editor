import { useRef, useState } from "react";
import {
  type AddTagsOp,
  type AppendOp,
  type FindReplaceOp,
  type Operation,
  type PrependOp,
  type RemoveTagsOp,
  type SectionOp,
  type TemplateOp,
  useTemplateVariables,
} from "../api/preview";
import { type FieldInfo, SEPARATOR_LABELS } from "../lib/fields";
import { metaOf } from "../lib/operations";
import { parseTags } from "../lib/tags";

const input =
  "w-full rounded-md border border-line bg-bg px-3 py-2 font-mono text-sm";

export function OperationForm({ op, field, onChange }: { op: Operation; field: FieldInfo; onChange: (op: Operation) => void }) {
  switch (op.type) {
    case "find_replace":
      return <FindReplaceForm op={op} onChange={onChange} />;
    case "append":
    case "prepend":
      return <AddTextForm op={op} field={field} onChange={onChange} />;
    case "template":
      return <TemplateForm op={op} onChange={onChange} />;
    case "section":
      return <SectionForm op={op} onChange={onChange} />;
    case "add_tags":
    case "remove_tags":
      return <TagsForm op={op} field={field} onChange={onChange} />;
  }
}

function TagsForm<T extends AddTagsOp | RemoveTagsOp>({
  op,
  field,
  onChange,
}: {
  op: T;
  field: FieldInfo;
  onChange: (op: T) => void;
}) {
  // Keep what was typed (commas and all); the Operation gets the parsed list.
  const [text, setText] = useState(() => op.tags.join(", "));
  const adding = op.type === "add_tags";
  return (
    <div className="space-y-4">
      <label className="block">
        <span className="mb-1 block text-sm font-medium">Tags to {adding ? "add" : "remove"}</span>
        <textarea
          rows={4}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            onChange({ ...op, tags: parseTags(e.target.value) });
          }}
          placeholder={adding ? "e.g. guitar lesson, late night" : "e.g. tour 2019"}
          className={input}
        />
      </label>
      <p className="text-xs text-muted">
        Separate tags with commas or put each on its own line. Upper and lower case don't matter when matching
        {adding ? " tags a video already has" : ""}. YouTube allows {field.max_size} {field.size_unit} of tags per
        video.
      </p>
    </div>
  );
}

const IF_MISSING: { value: SectionOp["if_missing"]; label: string }[] = [
  { value: "append", label: "Add it at the end" },
  { value: "prepend", label: "Add it at the start" },
  { value: "skip", label: "Leave the video alone" },
];

function SectionForm({ op, onChange }: { op: SectionOp; onChange: (op: SectionOp) => void }) {
  const set = <K extends keyof SectionOp>(k: K, v: SectionOp[K]) => onChange({ ...op, [k]: v });
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-sm font-medium">Start marker</span>
          <input
            value={op.start_marker}
            onChange={(e) => set("start_marker", e.target.value)}
            placeholder="e.g. [LINKS]"
            className={input}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-medium">End marker</span>
          <input
            value={op.end_marker}
            onChange={(e) => set("end_marker", e.target.value)}
            placeholder="e.g. [/LINKS]"
            className={input}
          />
        </label>
      </div>
      <label className="block">
        <span className="mb-1 block text-sm font-medium">Content between the markers</span>
        <textarea rows={7} value={op.content} onChange={(e) => set("content", e.target.value)} className={input} />
      </label>
      <fieldset>
        <legend className="mb-1.5 text-sm font-medium">If a video has no markers yet</legend>
        <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
          {IF_MISSING.map((o) => (
            <label key={o.value} className="flex items-center gap-2">
              <input
                type="radio"
                name="section-if-missing"
                checked={op.if_missing === o.value}
                onChange={() => set("if_missing", o.value)}
              />
              {o.label}
            </label>
          ))}
        </div>
      </fieldset>
      <p className="text-xs text-muted">
        The markers stay in the description; only what's between them changes. Markers can't contain &lt; or &gt;
        (YouTube doesn't allow them). Videos where the markers are broken, for example a start without an end, are
        blocked rather than guessed at.
      </p>
    </div>
  );
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

function AddTextForm<T extends AppendOp | PrependOp>({
  op,
  field,
  onChange,
}: {
  op: T;
  field: FieldInfo;
  onChange: (op: T) => void;
}) {
  const set = <K extends keyof T>(k: K, v: T[K]) => onChange({ ...op, [k]: v });
  const { at: where, placeholder, oneLinePlaceholder } = metaOf(op.type).adds!;
  const meta = field;
  // A one-line Field (a title) gets a one-line text box.
  const oneLine = field.one_line;
  return (
    <div className="space-y-4">
      <label className="block">
        <span className="mb-1 block text-sm font-medium">
          Text to add at the {where} of each {meta.singular}
        </span>
        {oneLine ? (
          <input
            value={op.text}
            onChange={(e) => set("text", e.target.value as T["text"])}
            placeholder={oneLinePlaceholder}
            className={input}
          />
        ) : (
          <textarea
            rows={7}
            value={op.text}
            onChange={(e) => set("text", e.target.value as T["text"])}
            placeholder={placeholder}
            className={input}
          />
        )}
      </label>
      <fieldset>
        <legend className="mb-1.5 text-sm font-medium">
          Separate it from the existing {meta.singular} with
        </legend>
        <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
          {meta.separators.map((s) => (
            <label key={s} className="flex items-center gap-2">
              <input
                type="radio"
                name={`${op.type}-separator`}
                checked={op.separator === s}
                onChange={() => set("separator", s as T["separator"])}
              />
              {SEPARATOR_LABELS[s]}
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
        Spaces {oneLine ? "" : "and blank lines "}at the {where} of the existing {meta.singular} are tidied up first
        {oneLine ? "" : ", and blank lines around your text are removed"}. Everything else stays exactly as it is.
      </p>
    </div>
  );
}
