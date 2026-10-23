import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "./Button";

/** "Back to …" above a screen's title. */
export function BackLink({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <Button variant="link" size="sm" onClick={onClick} icon={<ArrowLeft aria-hidden className="size-4" />} className="-ml-3">
      {children}
    </Button>
  );
}
