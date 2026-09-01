import React from "react";
import { Zap, Clock, Navigation, Target, Activity } from "lucide-react";
import { MatchAnalytics } from "../lib/api";

interface OverviewCardsProps {
  analytics: MatchAnalytics;
}

export const OverviewCards: React.FC<OverviewCardsProps> = ({ analytics }) => {
  const overview = analytics.overview || {
    active_play_duration_sec: 0,
    total_rallies: 0,
    total_shots: 0,
    total_distance_player_1_m: 0,
    total_distance_player_2_m: 0,
  };
  const metadata = analytics.metadata || {
    duration_seconds: 0,
    fps: 30,
    total_frames: 0,
    match_id: "",
  };
  const players = analytics.players || {};

  const activePlayTime = overview.active_play_duration_sec ?? 0;
  const totalDuration = metadata.duration_seconds ?? 0;
  const totalRallies = overview.total_rallies ?? 0;
  const totalShots = overview.total_shots ?? 0;
  const avgRallySec = totalRallies > 0 ? (activePlayTime / totalRallies).toFixed(1) : "0.0";

  const cards = [
    {
      title: "Active Play Time",
      value: `${activePlayTime}s`,
      subtitle: `Total match: ${totalDuration}s`,
      icon: Clock,
      color: "text-brand-cyan",
      border: "border-cyan-500/20",
    },
    {
      title: "Total Rallies",
      value: totalRallies,
      subtitle: `Avg ${avgRallySec}s / rally`,
      icon: Zap,
      color: "text-brand-amber",
      border: "border-amber-500/20",
    },
    {
      title: "Player 1 Distance",
      value: `${players.player_1?.distance_meters || 0}m`,
      subtitle: `Max: ${players.player_1?.max_speed_mps || 0} m/s`,
      icon: Navigation,
      color: "text-cyan-400",
      border: "border-cyan-500/20",
    },
    {
      title: "Player 2 Distance",
      value: `${players.player_2?.distance_meters || 0}m`,
      subtitle: `Max: ${players.player_2?.max_speed_mps || 0} m/s`,
      icon: Navigation,
      color: "text-amber-400",
      border: "border-amber-500/20",
    },
    {
      title: "Total Shots",
      value: totalShots,
      subtitle: "Smash, clear, net & drop",
      icon: Target,
      color: "text-brand-green",
      border: "border-emerald-500/20",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 my-6">
      {cards.map((card, idx) => {
        const Icon = card.icon;
        return (
          <div
            key={idx}
            className={`glass-panel rounded-xl p-4 border ${card.border} hover:scale-[1.02] transition-transform duration-200 shadow-lg`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
                {card.title}
              </span>
              <Icon className={`w-4 h-4 ${card.color}`} />
            </div>
            <div className="text-2xl font-black text-white tracking-tight">{card.value}</div>
            <div className="text-xs text-gray-400 mt-1 font-medium">{card.subtitle}</div>
          </div>
        );
      })}
    </div>
  );
};
