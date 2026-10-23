import { useQuery } from "@tanstack/react-query";
import type { FieldInfo } from "../lib/fields";
import { api } from "./client";
import type { Field } from "./preview";

/** The Fields the app can edit and what each allows, from the backend's registry (ADR-0022). */
export const useFields = () =>
  useQuery({ queryKey: ["fields"], queryFn: () => api<FieldInfo[]>("/fields"), staleTime: Infinity });

/** One Field's description, once loaded. */
export function useFieldInfo(field: Field): FieldInfo | undefined {
  return useFields().data?.find((f) => f.field === field);
}
