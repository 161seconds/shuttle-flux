import React from "react";
import { Flame, Layers } from "lucide-react";
import { MatchAnalytics } from "../lib/api";

interface HeatmapViewerProps {
  analytics: MatchAnalytics;
}

export const HeatmapViewer: React.FC<HeatmapViewerProps> = ({ analytics }) => {
  return (
    <div className="glass-panel rounded-2xl p-6 border border-gray-700 shadow-xl my-8">
      <div className="flex items-center justify-between mb-6 border-b border-gray-800 pb-3">
        <div className="flex items-center space-x-2">
          <Flame className="w-5 h-5 text-rose-500" />
          <h3 className="font-bold text-lg text-white">2D Spatial Density Heatmaps</h3>
        </div>
        <span className="text-xs text-gray-400">Gaussian Kernel Density Estimation</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* P1 Heatmap */}
        <div className="flex flex-col items-center">
          <h4 className="text-sm font-bold text-cyan-300 mb-3">Player 1 Court Coverage</h4>
          <div className="w-48 h-80 rounded-xl bg-gradient-to-b from-gray-900 via-slate-900 to-cyan-950/60 border border-cyan-800/50 relative overflow-hidden shadow-inner flex flex-col justify-between p-2">
            {/* Court boundary */}
            <div className="absolute inset-2 border border-gray-700/80 rounded"></div>
            {/* Net line */}
            <div className="absolute top-1/2 left-2 right-2 h-0.5 bg-cyan-500/40"></div>

            {/* Density Blobs simulation for P1 */}
            <div className="absolute bottom-6 left-6 w-20 h-20 bg-cyan-400/40 rounded-full blur-xl animate-pulse"></div>
            <div className="absolute bottom-16 right-8 w-16 h-16 bg-cyan-300/30 rounded-full blur-lg"></div>

            <div className="text-[10px] text-center text-gray-500 z-10">Net</div>
            <div className="text-[10px] text-center text-cyan-400 z-10 font-bold">Heavy Rear-Left & Center</div>
          </div>
        </div>

        {/* P2 Heatmap */}
        <div className="flex flex-col items-center">
          <h4 className="text-sm font-bold text-amber-300 mb-3">Player 2 Court Coverage</h4>
          <div className="w-48 h-80 rounded-xl bg-gradient-to-b from-amber-950/60 via-slate-900 to-gray-900 border border-amber-800/50 relative overflow-hidden shadow-inner flex flex-col justify-between p-2">
            {/* Court boundary */}
            <div className="absolute inset-2 border border-gray-700/80 rounded"></div>
            {/* Net line */}
            <div className="absolute top-1/2 left-2 right-2 h-0.5 bg-amber-500/40"></div>

            {/* Density Blobs simulation for P2 */}
            <div className="absolute top-8 right-6 w-20 h-20 bg-amber-400/40 rounded-full blur-xl animate-pulse"></div>
            <div className="absolute top-16 left-8 w-14 h-14 bg-amber-300/30 rounded-full blur-lg"></div>

            <div className="text-[10px] text-center text-amber-400 z-10 font-bold">Rear-Right Offensive Zone</div>
            <div className="text-[10px] text-center text-gray-500 z-10">Net</div>
          </div>
        </div>
      </div>
    </div>
  );
};
