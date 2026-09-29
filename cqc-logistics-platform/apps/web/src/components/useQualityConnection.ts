"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { initialRuntime, step, classifyResult } from "@/lib/quality-runtime";
import {
  getSnapshot,
  parseSnapshot,
  qualityRequest,
  saveReview,
  type QualitySnapshot,
  type SimulatorChange,
} from "@/lib/quality-api";
import type { MisclassificationType } from "@/lib/quality-contract";

export function useQualityConnection(mode: "demo" | "api") {
  const [state, update] = useState(initialRuntime);
  const [snapshot, setSnapshot] = useState<QualitySnapshot | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [connectedAt, setConnectedAt] = useState<number | null>(null);
  const [clock, setClock] = useState(0);
  const latest = useRef<QualitySnapshot | null>(null);
  const generation = useRef(0),
    busy = useRef(false),
    mounted = useRef(true);
  const mutation = useRef<AbortController | null>(null);
  const accept = useCallback((value: QualitySnapshot) => {
    latest.current = value;
    setSnapshot(value);
    update(value.state);
    setConnectedAt(Date.now());
  }, []);
  useEffect(() => {
    mounted.current = true;
    let disposed = false,
      pollTimer: ReturnType<typeof setTimeout>;
    let controller: AbortController | undefined;
    const clockTimer = setInterval(() => setClock(Date.now()), 1000);
    if (mode === "demo") {
      const timer = setInterval(
        () => update((current) => step(current, Date.now())),
        1000,
      );
      return () => {
        mounted.current = false;
        clearInterval(timer);
        clearInterval(clockTimer);
      };
    }
    async function poll() {
      controller = new AbortController();
      const version = generation.current;
      try {
        const value = await getSnapshot(
          AbortSignal.any([controller.signal, AbortSignal.timeout(7000)]),
        );
        if (!disposed && version === generation.current && !busy.current) {
          accept(value);
          setError("");
        }
      } catch (cause) {
        if (!disposed && version === generation.current)
          setError(
            cause instanceof Error
              ? cause.message
              : "관제 상태를 읽지 못했습니다.",
          );
      } finally {
        if (!disposed) pollTimer = setTimeout(poll, 1000);
      }
    }
    void poll();
    return () => {
      disposed = true;
      mounted.current = false;
      controller?.abort();
      mutation.current?.abort();
      clearTimeout(pollTimer);
      clearInterval(clockTimer);
    };
  }, [mode, accept]);
  const run = useCallback(
    async (operation: (signal: AbortSignal) => Promise<void>) => {
      if (busy.current) throw new Error("이전 요청을 처리 중입니다.");
      busy.current = true;
      generation.current++;
      setPending(true);
      const controller = new AbortController();
      mutation.current = controller;
      try {
        await operation(
          AbortSignal.any([controller.signal, AbortSignal.timeout(8000)]),
        );
      } finally {
        busy.current = false;
        if (mounted.current) setPending(false);
      }
    },
    [],
  );
  const configure = useCallback(
    async (change: SimulatorChange) => {
      if (mode === "demo") {
        update((current) => ({ ...current, ...change }));
        return;
      }
      await run(async (signal) => {
        if (!latest.current)
          throw new Error("서버 상태 확인 후 조작할 수 있습니다.");
        const value = await (
          await qualityRequest("simulator", {
            method: "PUT",
            body: JSON.stringify({
              expectedRevision: latest.current.revision,
              ...change,
            }),
            signal,
          })
        ).json();
        if (mounted.current) accept(parseSnapshot(value));
      });
    },
    [mode, run, accept],
  );
  const classify = useCallback(
    async (id: string, value: MisclassificationType) => {
      if (mode === "demo") {
        update((current) => classifyResult(current, id, value));
        return;
      }
      await run(async (signal) => {
        await saveReview(id, value, signal);
        if (mounted.current)
          update((current) => classifyResult(current, id, value));
      });
    },
    [mode, run],
  );
  const removeImages = useCallback(
    async (ids: string[]) => {
      if (mode === "demo") {
        update((current) => ({
          ...current,
          images: current.images.filter((row) => !ids.includes(row.id)),
        }));
        return;
      }
      await run(async (signal) => {
        const response = await qualityRequest("fault-images", {
          method: "DELETE",
          body: JSON.stringify({ ids }),
          signal,
        });
        const result = await response.json();
        if (
          !result ||
          !Array.isArray(result.deletedIds) ||
          result.deletedIds.some(
            (id: unknown) => typeof id !== "string" || !ids.includes(id),
          )
        )
          throw new Error(
            "삭제 응답이 올바르지 않습니다. 목록에서 결과를 확인하세요.",
          );
        if (mounted.current)
          update((current) => ({
            ...current,
            images: current.images.filter((row) => !ids.includes(row.id)),
          }));
      });
    },
    [mode, run],
  );
  return {
    state,
    snapshot,
    error,
    pending,
    connectedAt,
    stale:
      mode === "api" && (!connectedAt || clock - connectedAt > 5000 || !!error),
    configure,
    classify,
    removeImages,
  };
}
