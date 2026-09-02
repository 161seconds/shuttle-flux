"use client";

import { useEffect, useMemo, useState } from "react";
import { Activity, Cpu, Server, Zap } from "lucide-react";
import { getRuntimeStatus, RuntimeStatus } from "../lib/api";

const LABELS: Record<string, string> = {
  python: "Python",
  pytorch: "PyTorch",
  ultralytics_yolo: "YOLO",
  sam3: "SAM 3",
  onnx: "ONNX",
  tensorrt: "TensorRT",
  cuda: "CUDA",
  opencv: "OpenCV",
  deep_eiou: "Deep-EIoU",
  osnet_reid: "OSNet ReID",
  ocr: "OCR",
  homography: "Homography",
  flask: "Flask",
  javascript: "JavaScript",
  ffmpeg: "FFmpeg",
};

export function RuntimeStack() {
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getRuntimeStatus()
      .then((result) => {
        if (!cancelled) setRuntime(result);
      })
      .catch(() => {
        if (!cancelled) setOffline(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const displayedRuntime = useMemo(() => {
    if (!runtime?.inference_service?.runtime) return runtime;
    const remote = runtime.inference_service.runtime;
    const componentKeys = new Set([
      ...Object.keys(runtime.components),
      ...Object.keys(remote.components),
    ]);
    const components = Object.fromEntries(
      Array.from(componentKeys).map((key) => {
        const localComponent = runtime.components[key];
        const remoteComponent = remote.components[key];
        return [
          key,
          {
            ...(localComponent ?? remoteComponent),
            available: Boolean(localComponent?.available || remoteComponent?.available),
            active: Boolean(localComponent?.active || remoteComponent?.active),
          },
        ];
      })
    );
    return { ...runtime, selected_backend: remote.selected_backend, components };
  }, [runtime]);
  const counts = useMemo(() => {
    const values = Object.values(displayedRuntime?.components ?? {});
    return {
      active: values.filter((component) => component.active).length,
      available: values.filter((component) => component.available).length,
    };
  }, [displayedRuntime]);

  if (offline) return null;

  return (
    <section className="mb-6 overflow-hidden rounded-2xl border border-cyan-400/20 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.14),transparent_38%),linear-gradient(135deg,rgba(12,18,28,0.96),rgba(9,14,22,0.82))] shadow-2xl shadow-cyan-950/20">
      <div className="flex flex-col gap-4 border-b border-white/5 px-5 py-4 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl border border-cyan-300/30 bg-cyan-300/10 text-cyan-200">
            <Cpu size={20} />
          </div>
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.28em] text-cyan-300/70">Vision runtime</p>
            <h2 className="font-mono text-sm font-bold text-white">
              {runtime ? `${counts.active}/${Object.keys(displayedRuntime?.components ?? {}).length} modules active` : "Scanning AI stack..."}
            </h2>
          </div>
        </div>

        {runtime && (
          <div className="flex flex-wrap gap-2 text-[11px] font-semibold">
            <span className="flex items-center gap-1.5 rounded-full border border-white/10 bg-black/20 px-3 py-1.5 text-gray-300">
              <Server size={12} /> {runtime.inference_service?.reachable ? "Flask remote" : "Local inference"}
            </span>
            <span className="flex items-center gap-1.5 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1.5 text-emerald-300">
              <Activity size={12} /> {counts.available} available
            </span>
            <span className="flex items-center gap-1.5 rounded-full border border-amber-400/20 bg-amber-400/10 px-3 py-1.5 text-amber-200">
              <Zap size={12} /> {displayedRuntime?.selected_backend ?? "auto"}
            </span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-3 gap-px bg-white/5 sm:grid-cols-5 lg:grid-cols-[repeat(15,minmax(0,1fr))]">
        {Object.entries(LABELS).map(([key, label]) => {
          const component = displayedRuntime?.components[key];
          const state = component?.active ? "active" : component?.available ? "ready" : "missing";
          return (
            <div key={key} className="group bg-[#0b111a]/90 px-2 py-3 text-center" title={component?.version ?? component?.device ?? state}>
              <div
                className={`mx-auto mb-2 h-1.5 w-1.5 rounded-full ${
                  state === "active"
                    ? "bg-emerald-400 shadow-[0_0_10px_#34d399]"
                    : state === "ready"
                      ? "bg-amber-300"
                      : "bg-gray-700"
                }`}
              />
              <p className="truncate text-[9px] font-bold uppercase tracking-wide text-gray-400 group-hover:text-white">
                {label}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
