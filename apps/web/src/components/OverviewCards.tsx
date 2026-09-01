import React from "react";
import { Zap, Clock, Navigation, Target, Activity } from "lucide-react";
import { MatchAnalytics } from "../lib/api";

interface OverviewCardsProps {
  analytics: MatchAnalytics;
}

export const OverviewCards: React.FC<OverviewCardsProps> = ({ analytics }) => {
  const { overview, metadata, players } = analytics;

  const cards = [
    {
      title: "Active Play Time",
      value: `${overview.active_play_duration_sec}s`,
      subtitle: `Total match: ${metadata.duration_seconds}s`,
      icon: Clock,
      color: "text-brand-cyan",
      border: "border-cyan-500/20",
    },
    {
      title: "Total Rallies",
      value: overview.total_rallies,
      subtitle: `Avg ${(overview.active_play_duration_sec / (overview.total_rallies || 1)).toFixed(1)}s / rally`,
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
      value: overview.total_shots,
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
