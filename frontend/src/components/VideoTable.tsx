import {
  type ColumnDef,
  type Row,
  type RowData,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { memo, useCallback, useEffect, useRef, useState } from "react";
import type { Video } from "../api/videos";
import { descriptionPreview, formatDate, formatDuration } from "../lib/format";
import type { Selection } from "../lib/selection";

declare module "@tanstack/react-table" {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface TableMeta<TData extends RowData> {
    selected: Selection;
    onToggle: (id: string) => void;
    onSetMany: (ids: string[], select: boolean) => void;
    onOverrideShort: (id: string, isShort: boolean) => void;
  }
}

type Props = {
  videos: Video[]; // already filtered
  selected: Selection;
  onToggle: (id: string) => void;
  onSetMany: (ids: string[], select: boolean) => void;
  onOverrideShort: (id: string, isShort: boolean) => void;
};

/** Short is tri-state: unknown until classified. One sort key and one label for it. */
const shortRank = (v: Video) => (v.is_short === null ? -1 : v.is_short ? 1 : 0);

// Columns never change; per-render state (selection) arrives through table meta.
const columns: ColumnDef<Video>[] = [
  {
    id: "select",
    enableSorting: false,
    header: ({ table }) => {
      const { selected, onSetMany } = table.options.meta!;
      const ids = table.getCoreRowModel().rows.map((r) => r.id);
      const all = ids.length > 0 && ids.every((id) => selected.has(id));
      const some = !all && ids.some((id) => selected.has(id));
      return (
        <Checkbox
          checked={all}
          indeterminate={some}
          label={all ? "Deselect the matching videos" : "Select all matching videos"}
          onChange={() => onSetMany(ids, !all)}
        />
      );
    },
    cell: ({ row, table }) => (
      <Checkbox
        checked={table.options.meta!.selected.has(row.id)}
        label={`Select ${row.original.title}`}
        onChange={() => table.options.meta!.onToggle(row.id)}
        tabIndex={-1}
      />
    ),
  },
  {
    id: "thumbnail",
    enableSorting: false,
    header: () => <span className="sr-only">Thumbnail</span>,
    cell: ({ row }) =>
      row.original.thumbnail_url ? (
        <img src={row.original.thumbnail_url} alt="" loading="lazy" className="h-10 w-[72px] rounded object-cover" />
      ) : (
        <span className="block h-10 w-[72px] rounded bg-line" aria-hidden />
      ),
  },
  {
    accessorKey: "title",
    header: "Title",
    cell: ({ getValue }) => (
      <span className="line-clamp-2 font-medium" title={getValue<string>()}>
        {getValue<string>()}
      </span>
    ),
  },
  {
    accessorKey: "published_at",
    header: "Published",
    cell: ({ getValue }) => <span className="whitespace-nowrap text-muted">{formatDate(getValue<string>())}</span>,
  },
  {
    accessorKey: "duration_s",
    header: "Length",
    cell: ({ getValue }) => <span className="tabular-nums text-muted">{formatDuration(getValue<number>())}</span>,
  },
  {
    id: "is_short",
    header: "Short",
    accessorFn: shortRank,
    cell: ({ row, table }) => <ShortCell video={row.original} onOverride={table.options.meta!.onOverrideShort} />,
  },
  {
    id: "description",
    header: "Description",
    accessorFn: (v) => descriptionPreview(v.description),
    cell: ({ getValue }) => (
      <span className="line-clamp-2 text-muted" title={getValue<string>()}>
        {getValue<string>() || <em className="opacity-60">Empty</em>}
      </span>
    ),
  },
  {
    accessorKey: "edited",
    header: "Status",
    cell: ({ getValue }) =>
      getValue<boolean>() ? (
        <span className="rounded-full bg-ok/15 px-2 py-0.5 text-xs font-medium text-ok">Edited</span>
      ) : null,
  },
];

const MOVE_KEYS: Record<string, (i: number, last: number) => number> = {
  ArrowDown: (i) => i + 1,
  ArrowUp: (i) => i - 1,
  Home: () => 0,
  End: (_i, last) => last,
  PageDown: (i) => i + 10,
  PageUp: (i) => i - 10,
};

export function VideoTable({ videos, selected, onToggle, onSetMany, onOverrideShort }: Props) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "published_at", desc: true }]);
  // Roving focus follows the Video, not the row position, so sorting/filtering keeps your place.
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const rowRefs = useRef(new Map<string, HTMLTableRowElement>());

  const table = useReactTable({
    data: videos,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getRowId: (v) => v.id,
    meta: { selected, onToggle, onSetMany, onOverrideShort },
  });
  const rows = table.getRowModel().rows;
  const tabStopId = rows.some((r) => r.id === focusedId) ? focusedId : (rows[0]?.id ?? null);

  useEffect(() => {
    const live = new Set(rows.map((r) => r.id));
    for (const id of rowRefs.current.keys()) if (!live.has(id)) rowRefs.current.delete(id);
  }, [rows]);

  // Stable handlers (reading the latest rows through a ref) let unchanged rows skip re-rendering.
  const rowsRef = useRef(rows);
  rowsRef.current = rows;
  const onKeyDown = useCallback(
    (e: React.KeyboardEvent, id: string) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const all = rowsRef.current;
      const move = MOVE_KEYS[e.key];
      if (move) {
        e.preventDefault();
        const index = all.findIndex((r) => r.id === id);
        const next = all[Math.min(Math.max(move(index, all.length - 1), 0), all.length - 1)];
        setFocusedId(next.id);
        rowRefs.current.get(next.id)?.focus();
      } else if (e.key === " " && !e.shiftKey && (e.target as HTMLElement).tagName !== "INPUT") {
        // A focused checkbox handles Space natively; only the row itself toggles here.
        e.preventDefault();
        onToggle(id);
      } else if (e.key === "s" || e.key === "S") {
        // Keyboard path to correct the Short label (the cell button is outside the tab order).
        const video = all.find((r) => r.id === id)?.original;
        if (video) {
          e.preventDefault();
          onOverrideShort(id, video.is_short !== true);
        }
      }
    },
    [onToggle, onOverrideShort],
  );
  const setRowRef = useCallback((id: string, el: HTMLTableRowElement | null) => {
    if (el) rowRefs.current.set(id, el);
  }, []);

  return (
    <div className="max-h-[calc(100vh-280px)] min-h-64 overflow-auto rounded-xl border border-line bg-surface">
      <table className="w-full min-w-[880px] table-fixed border-collapse text-sm">
        <colgroup>
          <col className="w-11" />
          <col className="w-[88px]" />
          <col />
          <col className="w-28" />
          <col className="w-20" />
          <col className="w-20" />
          <col className="w-[28%]" />
          <col className="w-20" />
        </colgroup>
        <thead className="sticky top-0 z-10 bg-surface shadow-[0_1px_0_var(--color-line)]">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((h) => {
                const canSort = h.column.getCanSort();
                const sorted = h.column.getIsSorted();
                return (
                  <th
                    key={h.id}
                    scope="col"
                    aria-sort={!canSort ? undefined : sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : "none"}
                    className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-muted"
                  >
                    {canSort ? (
                      <button
                        type="button"
                        onClick={h.column.getToggleSortingHandler()}
                        className="inline-flex items-center gap-1 rounded hover:text-fg focus-visible:outline-2 focus-visible:outline-accent"
                      >
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        <span aria-hidden className="w-3 text-[10px]">
                          {sorted === "asc" ? "▲" : sorted === "desc" ? "▼" : ""}
                        </span>
                      </button>
                    ) : (
                      flexRender(h.column.columnDef.header, h.getContext())
                    )}
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {rows.map((row) => (
            <VideoRow
              key={row.id}
              row={row}
              isSelected={selected.has(row.id)}
              isTabStop={row.id === tabStopId}
              setRowRef={setRowRef}
              onFocusRow={setFocusedId}
              onKeyDown={onKeyDown}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

type RowProps = {
  row: Row<Video>;
  isSelected: boolean;
  isTabStop: boolean;
  setRowRef: (id: string, el: HTMLTableRowElement | null) => void;
  onFocusRow: (id: string) => void;
  onKeyDown: (e: React.KeyboardEvent, id: string) => void;
};

// Re-render a row only when its own Video, selection or tab stop changes (not on every toggle).
const VideoRow = memo(
  function VideoRow({ row, isSelected, isTabStop, setRowRef, onFocusRow, onKeyDown }: RowProps) {
    return (
      <tr
        ref={(el) => setRowRef(row.id, el)}
        tabIndex={isTabStop ? 0 : -1}
        onFocus={() => onFocusRow(row.id)}
        onKeyDown={(e) => onKeyDown(e, row.id)}
        className={`border-t border-line outline-none focus-visible:bg-accent/10 focus-visible:shadow-[inset_3px_0_0_var(--color-accent)] ${
          isSelected ? "bg-accent/5" : "hover:bg-line/40"
        }`}
      >
        {row.getVisibleCells().map((cell) => (
          <td key={cell.id} className="px-3 py-2 align-middle">
            {flexRender(cell.column.columnDef.cell, cell.getContext())}
          </td>
        ))}
      </tr>
    );
  },
  (a, b) =>
    a.row.original === b.row.original &&
    a.isSelected === b.isSelected &&
    a.isTabStop === b.isTabStop &&
    a.onKeyDown === b.onKeyDown,
);

const SOURCE_HINT = {
  probe: "Detected from YouTube",
  duration: "Guessed from length (YouTube didn't answer); will be re-checked on next Sync",
  manual: "Set by you",
} as const;

function ShortCell({ video, onOverride }: { video: Video; onOverride: (id: string, isShort: boolean) => void }) {
  const label = video.is_short === null ? "—" : video.is_short ? "Yes" : "No";
  const next = video.is_short !== true;
  const hint = video.short_source ? SOURCE_HINT[video.short_source] : "Not classified yet";
  return (
    <button
      type="button"
      tabIndex={-1}
      onClick={() => onOverride(video.id, next)}
      title={`${hint}. Click to mark as ${next ? "a Short" : "not a Short"}.`}
      aria-label={`Short: ${label}. ${hint}. Mark as ${next ? "a Short" : "not a Short"}`}
      className={`rounded px-1.5 py-0.5 hover:bg-line/60 ${video.is_short ? "font-medium" : "text-muted"}`}
    >
      {label}
      {video.short_source === "duration" && <span aria-hidden className="ml-0.5 text-warn">≈</span>}
      {video.short_source === "manual" && <span aria-hidden className="ml-0.5 text-accent">✎</span>}
    </button>
  );
}

function Checkbox({
  checked,
  indeterminate = false,
  label,
  onChange,
  tabIndex,
}: {
  checked: boolean;
  indeterminate?: boolean;
  label: string;
  onChange: () => void;
  tabIndex?: number;
}) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate;
  }, [indeterminate]);
  return (
    <input
      ref={ref}
      type="checkbox"
      checked={checked}
      onChange={onChange}
      aria-label={label}
      tabIndex={tabIndex}
      className="h-4 w-4 cursor-pointer accent-[var(--color-accent)]"
    />
  );
}
