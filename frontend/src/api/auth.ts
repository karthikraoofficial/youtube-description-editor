import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { ApiError, SIGNED_OUT_EVENT, api } from "./client";

/** "signed_out": the deployed app needs the Owner's session first (any API call answered 401). */
export type AuthState = "signed_out" | "no_client_secret" | "disconnected" | "expired" | "connected";
export type ChannelInfo = { id: string; title: string; avatar_url: string | null };
export type AuthStatus = { state: AuthState; channel: ChannelInfo | null };

const KEY = ["auth", "status"];

async function fetchStatus(): Promise<AuthStatus> {
  try {
    return await api<AuthStatus>("/auth/status");
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return { state: "signed_out", channel: null };
    throw e;
  }
}

export function useAuthStatus() {
  const qc = useQueryClient();
  // Any request refused for want of a session (it expired mid-use) sends the app back to sign-in.
  useEffect(() => {
    const signedOut = () => qc.invalidateQueries({ queryKey: KEY });
    window.addEventListener(SIGNED_OUT_EVENT, signedOut);
    return () => window.removeEventListener(SIGNED_OUT_EVENT, signedOut);
  }, [qc]);
  return useQuery({ queryKey: KEY, queryFn: fetchStatus });
}

/** Signing in is a full-page trip to Google and back (ADR-0019). */
export const startSignIn = () => window.location.assign("/api/auth/login");

function useAuthMutation(path: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<AuthStatus>(path, { method: "POST" }),
    onSuccess: (status) => qc.setQueryData(KEY, status),
  });
}

export const useDisconnect = () => useAuthMutation("/auth/disconnect");
