import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";

export type AuthState = "no_client_secret" | "disconnected" | "expired" | "connected";
export type ChannelInfo = { id: string; title: string; avatar_url: string | null };
export type AuthStatus = { state: AuthState; channel: ChannelInfo | null };

const KEY = ["auth", "status"];

export function useAuthStatus() {
  return useQuery({ queryKey: KEY, queryFn: () => api<AuthStatus>("/auth/status") });
}

function useAuthMutation(path: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<AuthStatus>(path, { method: "POST" }),
    onSuccess: (status) => qc.setQueryData(KEY, status),
  });
}

export const useConnect = () => useAuthMutation("/auth/connect");
export const useDisconnect = () => useAuthMutation("/auth/disconnect");
