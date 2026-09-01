import React from "react";
import { User, Activity, Gauge, MapPin } from "lucide-react";
import { MatchAnalytics, PlayerStatsData } from "../lib/api";

interface PlayerStatsProps {
  analytics: MatchAnalytics;
}

export const PlayerStats: React.FC<PlayerStatsProps> = ({ analytics }) => {
  const p1 = analytics.players.player_1;
  const p2 = analytics.players.player_2;

  const renderPlayerCard = (p: PlayerStatsData, color: string, border: string, badge: string) => {
    return (
      <div className={`glass-panel rounded-2xl p-6 border ${border} shadow-xl flex-1`}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-3">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-black ${badge}`}>
              P{p.player_id}
            </div>
            <div>
              <h4 className="text-lg font-bold text-white">{p.label}</h4>
              <p className="text-xs text-gray-400">{p.side}</p>
            </div>
          </div>
          <span className="text-xs font-semibold px-2.5 py-1 rounded bg-surface border border-gray-700 text-gray-300">
            Active: {p.active_time_seconds}s
          </span>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 my-4">
          <div className="bg-surface p-3 rounded-xl border border-gray-800 text-center">
            <span className="text-[11px] text-gray-400 block mb-1">Quãng đường</span>
            <span className="text-base font-extrabold text-white">{p.distance_meters}m</span>
          </div>
          <div className="bg-surface p-3 rounded-xl border border-gray-800 text-center">
            <span className="text-[11px] text-gray-400 block mb-1">Tốc độ TB</span>
            <span className="text-base font-extrabold text-white">
              {(p.avg_speed_mps * 3.6).toFixed(1)} <span className="text-[10px] text-gray-400">km/h</span>
            </span>
          </div>
          <div className="bg-surface p-3 rounded-xl border border-gray-800 text-center">
            <span className="text-[11px] text-gray-400 block mb-1">Tốc độ Max</span>
            <span className="text-base font-extrabold text-white">
              {(p.max_speed_mps * 3.6).toFixed(1)} <span className="text-[10px] text-gray-400">km/h</span>
            </span>
          </div>
          <div className="bg-surface p-3 rounded-xl border border-gray-800 text-center">
            <span className="text-[11px] text-gray-400 block mb-1">Kiểm soát sân</span>
            <span className="text-base font-extrabold text-brand-cyan">
              {p.court_control_pct !== undefined ? `${p.court_control_pct}%` : "50%"}
            </span>
          </div>
        </div>

        {/* Tactical Zone Occupancy */}
        <div className="mt-4 pt-3 border-t border-gray-800">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block mb-2">
            Tactical Court Zone Occupancy
          </span>
          <div className="space-y-2">
            {Object.entries(p.zone_occupancy || {}).map(([zone, pct]) => {
              const cleanZoneName = zone.replace(/^P[12]_/, "").replace("_", " ").toUpperCase();
              return (
                <div key={zone} className="text-xs">
                  <div className="flex justify-between text-gray-300 mb-1">
                    <span>{cleanZoneName}</span>
                    <span className="font-mono">{pct}%</span>
                  </div>
                  <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${color}`}
                      style={{ width: `${Math.min(100, pct * 2)}%` }}
                    ></div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="my-8">
      <div className="flex items-center space-x-2 mb-4">
        <Activity className="w-5 h-5 text-brand-cyan" />
        <h3 className="font-bold text-lg text-white">Player Movement & Performance Profile</h3>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {renderPlayerCard(p1, "bg-brand-cyan", "border-cyan-500/30", "bg-brand-cyan")}
        {renderPlayerCard(p2, "bg-brand-amber", "border-amber-500/30", "bg-brand-amber")}
      </div>
    </div>
  );
};
