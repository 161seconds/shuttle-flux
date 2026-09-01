import React from "react";
import { Activity, Play, Sparkles, Video, RefreshCw } from "lucide-react";

interface NavbarProps {
  onLoadDemo: () => void;
  isLoadingDemo: boolean;
  activeMatchId: string | null;
  onReset: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  onLoadDemo,
  isLoadingDemo,
  activeMatchId,
  onReset,
}) => {
  return (
    <header className="sticky top-0 z-50 glass-panel border-b border-gray-800 px-6 py-4 flex items-center justify-between">
      <div className="flex items-center space-x-3 cursor-pointer" onClick={onReset}>
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-cyan to-brand-amber flex items-center justify-center shadow-lg shadow-cyan-500/20">
          <Activity className="w-6 h-6 text-black font-bold" />
        </div>
        <div>
          <h1 className="text-xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white via-gray-200 to-brand-cyan">
            SHUTTLE FLUX
          </h1>
          <p className="text-xs text-gray-400 font-medium">Badminton AI Match Analytics</p>
        </div>
      </div>

      <div className="flex items-center space-x-4">
        {activeMatchId && (
          <div className="hidden sm:flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-surface border border-gray-700 text-xs text-gray-300">
            <span className="w-2 h-2 rounded-full bg-brand-green animate-pulse"></span>
            <span>Match: <strong>{activeMatchId}</strong></span>
          </div>
        )}

        <button
          id="load-demo-btn"
          onClick={onLoadDemo}
          disabled={isLoadingDemo}
          className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-500/20 to-amber-500/20 hover:from-cyan-500/30 hover:to-amber-500/30 border border-cyan-500/40 text-cyan-300 text-sm font-semibold transition-all duration-200 shadow-md shadow-cyan-500/10 disabled:opacity-50"
        >
          {isLoadingDemo ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <Sparkles className="w-4 h-4 text-brand-cyan" />
          )}
          <span>{isLoadingDemo ? "Loading..." : "Load Demo Match"}</span>
        </button>

        {activeMatchId && (
          <button
            onClick={onReset}
            className="text-xs text-gray-400 hover:text-white px-2 py-1.5 transition-colors"
          >
            Upload New
          </button>
        )}
      </div>
    </header>
  );
};
