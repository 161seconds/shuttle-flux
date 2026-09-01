import React from "react";
import { PlayCircle, Clock, Zap } from "lucide-react";
import { RallyData, HitItem } from "../lib/api";

interface RallyTimelineProps {
  rallies: RallyData[];
  hits?: HitItem[];
  onSelectRally: (startTime: number) => void;
}

export const RallyTimeline: React.FC<RallyTimelineProps> = ({
  rallies = [],
  hits = [],
  onSelectRally,
}) => {
  const safeRallies = Array.isArray(rallies) ? rallies : [];
  const safeHits = Array.isArray(hits) ? hits : [];

  return (
    <div className="glass-panel rounded-2xl p-6 border border-gray-700 shadow-xl my-8">
      <div className="flex items-center justify-between mb-4 border-b border-gray-800 pb-3">
        <div className="flex items-center space-x-2">
          <Zap className="w-5 h-5 text-brand-amber" />
          <h3 className="font-bold text-lg text-white">Phân Đoạn Pha Cầu & Cú Đánh (Rally Timeline)</h3>
        </div>
        <span className="text-xs text-gray-400">Nhấn vào từng pha cầu để tua nhanh video</span>
      </div>

      {safeRallies.length === 0 ? (
        <div className="text-center py-6 text-xs text-gray-400 border border-dashed border-gray-800 rounded-xl bg-surface/50">
          <Clock className="w-6 h-6 mx-auto mb-2 text-gray-500 animate-spin" />
          <p className="font-medium text-gray-300">Đang theo dõi & phân đoạn các pha cầu trực tiếp...</p>
          <p className="text-gray-500 mt-0.5">Các pha cầu (Rallies) và loại cú đánh sẽ tự động xuất hiện tại đây khi trận đấu diễn ra.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {safeRallies.map((rally) => {
            const rallyHits = safeHits.filter(
              (h) => h.timestamp >= rally.start_time - 0.2 && h.timestamp <= rally.end_time + 0.2
            );

          return (
            <div
              key={rally.rally_id}
              onClick={() => onSelectRally(rally.start_time)}
              className="group cursor-pointer bg-surface hover:bg-surface-light border border-gray-800 hover:border-cyan-500/50 rounded-xl p-4 transition-all duration-200 shadow-md hover:scale-[1.02]"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2">
                  <PlayCircle className="w-5 h-5 text-cyan-400 group-hover:text-brand-cyan transition-colors" />
                  <span className="font-bold text-white text-sm">{rally.name}</span>
                </div>
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800">
                  {rally.duration_seconds}s
                </span>
              </div>

              {rallyHits.length > 0 && (
                <div className="flex flex-wrap gap-1.5 my-2">
                  {rallyHits.map((h, i) => (
                    <span
                      key={i}
                      className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded border ${
                        h.shot_type === "smash"
                          ? "bg-red-950/60 text-red-400 border-red-800/60"
                          : h.shot_type === "clear"
                          ? "bg-blue-950/60 text-blue-400 border-blue-800/60"
                          : h.shot_type === "drop"
                          ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/60"
                          : "bg-purple-950/60 text-purple-400 border-purple-800/60"
                      }`}
                    >
                      P{h.player_id}: {h.shot_type}
                    </span>
                  ))}
                </div>
              )}

              <div className="flex items-center justify-between text-xs text-gray-400 mt-3 pt-2 border-t border-gray-800/80">
                <div className="flex items-center space-x-1">
                  <Clock className="w-3.5 h-3.5" />
                  <span>
                    {rally.start_time}s - {rally.end_time}s
                  </span>
                </div>
                <div className="flex items-center space-x-1 text-gray-300 font-medium">
                  <span>{rally.estimated_shot_count} shots</span>
                  <span className="text-gray-600">•</span>
                  <span className="text-brand-green">{(rally.confidence * 100).toFixed(0)}% conf</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      )}
    </div>
  );
};
