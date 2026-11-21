import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "./client";
import type { components } from "./schema";

export type Channel = components["schemas"]["ChannelOut"];
export type ChannelCreate = components["schemas"]["ChannelIn"];
export type ChannelUpdate = components["schemas"]["ChannelUpdate"];
export type ChannelTestInput = components["schemas"]["ChannelTest"];
export type ChannelTestResult = components["schemas"]["ChannelTestResult"];
export type FilterItem = components["schemas"]["FilterOut"];
export type FilterInput = components["schemas"]["FilterIn"];
export type AppConfig = components["schemas"]["ConfigOut"];
export type Alert = components["schemas"]["AlertOut"];
export type Status = components["schemas"]["StatusOut"];
export type ProviderStatus = components["schemas"]["ProviderStatus"];

export const queryKeys = {
  health: ["health"] as const,
  channels: ["channels"] as const,
  channel: (id: number) => ["channels", id] as const,
  // Filters list their channels, so channel changes invalidate them too.
  filters: ["filters"] as const,
  filter: (id: number) => ["filters", id] as const,
  config: ["config"] as const,
  status: ["status"] as const,
  alerts: ["alerts"] as const,
};

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: () => unwrap(api.GET("/api/health")),
    staleTime: 5 * 60_000,
  });
}

/** Static backend configuration (providers, FR24 on/off, category labels). */
export function useConfig() {
  return useQuery({
    queryKey: queryKeys.config,
    queryFn: () => unwrap(api.GET("/api/config")),
    staleTime: Infinity,
  });
}

// Channels

export function useChannels() {
  return useQuery({
    queryKey: queryKeys.channels,
    queryFn: () => unwrap(api.GET("/api/channels")),
  });
}

export function useChannel(id: number) {
  return useQuery({
    queryKey: queryKeys.channel(id),
    queryFn: () =>
      unwrap(api.GET("/api/channels/{channel_id}", { params: { path: { channel_id: id } } })),
  });
}

export function useCreateChannel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ChannelCreate) => unwrap(api.POST("/api/channels", { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.channels }),
  });
}

export function useUpdateChannel(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ChannelUpdate) =>
      unwrap(api.PUT("/api/channels/{channel_id}", { params: { path: { channel_id: id } }, body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.channels }),
  });
}

export function useDeleteChannel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      unwrap(api.DELETE("/api/channels/{channel_id}", { params: { path: { channel_id: id } } })),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.channels }),
        queryClient.invalidateQueries({ queryKey: queryKeys.filters }),
      ]),
  });
}

/** Test message to a stored channel (`id`) or to credentials that are not saved yet. */
export function useTestChannel() {
  return useMutation({
    mutationFn: (target: { id: number } | ChannelTestInput) =>
      "id" in target
        ? unwrap(
            api.POST("/api/channels/{channel_id}/test", {
              params: { path: { channel_id: target.id } },
            }),
          )
        : unwrap(api.POST("/api/channels/test", { body: target })),
  });
}

// Filters

function useInvalidateFilters() {
  const queryClient = useQueryClient();
  // Channels list the filters using them, the status shows the planned requests.
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.filters }),
      queryClient.invalidateQueries({ queryKey: queryKeys.channels }),
      queryClient.invalidateQueries({ queryKey: queryKeys.status }),
    ]);
}

export function useFilters() {
  return useQuery({
    queryKey: queryKeys.filters,
    queryFn: () => unwrap(api.GET("/api/filters")),
  });
}

export function useFilter(id: number) {
  return useQuery({
    queryKey: queryKeys.filter(id),
    queryFn: () =>
      unwrap(api.GET("/api/filters/{filter_id}", { params: { path: { filter_id: id } } })),
  });
}

export function useCreateFilter() {
  const invalidate = useInvalidateFilters();
  return useMutation({
    mutationFn: (body: FilterInput) => unwrap(api.POST("/api/filters", { body })),
    onSuccess: invalidate,
  });
}

export function useUpdateFilter() {
  const invalidate = useInvalidateFilters();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: FilterInput }) =>
      unwrap(api.PUT("/api/filters/{filter_id}", { params: { path: { filter_id: id } }, body })),
    onSuccess: invalidate,
  });
}

export function useDeleteFilter() {
  const invalidate = useInvalidateFilters();
  return useMutation({
    mutationFn: (id: number) =>
      unwrap(api.DELETE("/api/filters/{filter_id}", { params: { path: { filter_id: id } } })),
    onSuccess: invalidate,
  });
}

// Alerts

export const ALERTS_PAGE_SIZE = 50;

/** Alert history, newest first, paged by id. `filterId` narrows it to one filter. */
export function useAlerts(filterId: number | undefined) {
  return useInfiniteQuery({
    queryKey: [...queryKeys.alerts, filterId ?? "all"],
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/alerts", {
          params: {
            query: {
              limit: ALERTS_PAGE_SIZE,
              ...(pageParam === undefined ? {} : { before_id: pageParam }),
              ...(filterId === undefined ? {} : { filter_id: filterId }),
            },
          },
        }),
      ),
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (lastPage) =>
      lastPage.length < ALERTS_PAGE_SIZE ? undefined : Math.min(...lastPage.map((a) => a.id)),
    refetchInterval: 30_000,
  });
}

export function useClearAlerts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.DELETE("/api/alerts")),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.alerts }),
  });
}

// Status

export function useStatus() {
  return useQuery({
    queryKey: queryKeys.status,
    queryFn: () => unwrap(api.GET("/api/status")),
    refetchInterval: 10_000,
  });
}
