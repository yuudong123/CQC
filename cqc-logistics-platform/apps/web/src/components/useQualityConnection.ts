"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { DEMO_INPUT_INTERVAL_MS, initialRuntime, nextPollDelay, step, classifyResult } from "@/lib/quality-runtime";
import {
  getSnapshot,
  parseSnapshot,
  qualityRequest,
  saveReview,
  type QualitySnapshot,
  type SimulatorChange,
} from "@/lib/quality-api";
import {
  DemoFaultImageStore,
  loadQualityPoll,
  parseFaultImages,
  type FaultImage,
} from "@/lib/quality-fault-images";
import type { MisclassificationType } from "@/lib/quality-contract";

const REQUEST_TIMEOUT_MS = 7000;

async function fetchFaultImages(signal: AbortSignal) {
  return parseFaultImages(
    await (await qualityRequest("fault-images", { signal })).json(),
  );
}

export function useQualityConnection(mode: "demo" | "api") {
  const imageStore = useRef(new DemoFaultImageStore());
  const demoState = useRef(initialRuntime());
  const [faultImages, setFaultImages] = useState<FaultImage[]>([]);
  const [faultImageError, setFaultImageError] = useState("");
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
      // 라인 속도가 바뀌면 다음 투입부터 새 간격을 쓰도록 매번 다시 예약한다.
      const interval = () => demoState.current.intervalMs ?? DEMO_INPUT_INTERVAL_MS;
      let timer: ReturnType<typeof setTimeout>;
      const tick = () => {
        const previous = demoState.current;
        const next = step(previous, Date.now(), interval(), true);
        imageStore.current.advance(previous, next);
        demoState.current = next; update(next);
        setFaultImages([...imageStore.current.items]);
        timer = setTimeout(tick, interval());
      };
      timer = setTimeout(tick, interval());
      return () => {
        mounted.current = false;
        clearTimeout(timer);
        clearInterval(clockTimer);
      };
    }
    async function poll() {
      const startedAt = Date.now();
      controller = new AbortController();
      const version = generation.current;
      try {
        const signal = controller.signal;
        const result = await loadQualityPoll(
          () =>
            getSnapshot(
              AbortSignal.any([signal, AbortSignal.timeout(REQUEST_TIMEOUT_MS)]),
            ),
          () =>
            fetchFaultImages(
              AbortSignal.any([signal, AbortSignal.timeout(REQUEST_TIMEOUT_MS)]),
            ),
        );
        if (!disposed && version === generation.current && !busy.current) {
          if (result.images) setFaultImages(result.images);
          setFaultImageError(result.imageError);
          accept(result.snapshot);
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
        // 응답 후 1초가 아니라 시작 기준 1초마다 조회한다. snapshot이 0.5~0.8초 걸리면
        // 실제 주기가 1.7초쯤 돼서 2초 간격 사과를 덩어리로 놓쳤다.
        if (!disposed) pollTimer = setTimeout(poll, nextPollDelay(Date.now() - startedAt));
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
        demoState.current = { ...demoState.current, ...change };
        update(demoState.current);
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
        demoState.current = classifyResult(demoState.current, id, value);
        update(demoState.current);
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
        imageStore.current.remove(ids);
        setFaultImages([...imageStore.current.items]);
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
        if (mounted.current) {
          setFaultImages((current) =>
            current.filter((row) => !result.deletedIds.includes(row.id)),
          );
          const fresh = await loadQualityPoll(
            () => getSnapshot(signal),
            () => fetchFaultImages(signal),
          );
          if (mounted.current) {
            accept(fresh.snapshot);
            if (fresh.images) setFaultImages(fresh.images);
            setFaultImageError(fresh.imageError);
          }
          if (fresh.images?.some((row) => ids.includes(row.id)))
            throw new Error(
              "일부 이미지가 삭제되지 않았습니다. 남은 목록을 확인하고 다시 시도하세요.",
            );
        }
      });
    },
    [mode, run, accept],
  );
  return {
    faultImages,
    faultImageError: mode === "api" ? faultImageError : "",
    faultImageSource: (id: string) => imageStore.current.source(id),
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
