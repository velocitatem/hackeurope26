"use client";

import { useState } from "react";

type Mode = "on-demand" | "long-term";
type Speed = "fast" | "deep";

export default function TrainingConfig() {
  const [mode, setMode] = useState<Mode>("on-demand");
  const [speed, setSpeed] = useState<Speed>("fast");
  const [onDemandHours, setOnDemandHours] = useState(12);
  const [longTermDays, setLongTermDays] = useState(7);

  return (
    <div className="w-full max-w-2xl mx-auto space-y-8">
      {/* Choose Training Mode */}
      <div>
        <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4">Choose Training Mode</h2>

        <div className="inline-flex gap-1 p-1 bg-gray-100 dark:bg-neutral-800 rounded-xl border border-gray-200 dark:border-neutral-700">
          <button
            onClick={() => setMode("on-demand")}
            className={`relative px-6 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200 ${
              mode === "on-demand"
                ? "bg-white dark:bg-neutral-700 text-gray-900 dark:text-white shadow-sm"
                : "text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
            }`}
          >
            On-Demand
          </button>
          <button
            onClick={() => setMode("long-term")}
            className={`relative px-6 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200 ${
              mode === "long-term"
                ? "bg-white dark:bg-neutral-700 text-gray-900 dark:text-white shadow-sm"
                : "text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
            }`}
          >
            Long-Term
          </button>
        </div>
      </div>

      {mode === "on-demand" && (
        <div className="space-y-6">
          {/* Speed Selection Cards */}
          <div>
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">Training Speed</h3>
            <div className="grid grid-cols-2 gap-4">
              <button
                onClick={() => setSpeed("fast")}
                className={`group relative p-6 rounded-xl border-2 text-left transition-all duration-200 ${
                  speed === "fast"
                    ? "border-blue-500 bg-blue-50 dark:bg-blue-950/40 shadow-lg shadow-blue-500/20 ring-2 ring-blue-500/20"
                    : "border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 hover:border-gray-300 dark:hover:border-neutral-600 hover:shadow-md"
                }`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="text-3xl">&#9889;</div>
                  {speed === "fast" && (
                    <div className="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center">
                      <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                  )}
                </div>
                <div className="font-bold text-gray-900 dark:text-white mb-1">Fast Training</div>
                <div className="text-sm text-gray-500 dark:text-gray-400 mb-2">Lower accuracy</div>
                <div className="text-xs text-gray-400 dark:text-gray-500">Quick iteration</div>
                <div className="mt-3 text-xs font-bold text-blue-600 dark:text-blue-400">~5-10 mins</div>
              </button>

              <button
                onClick={() => setSpeed("deep")}
                className={`group relative p-6 rounded-xl border-2 text-left transition-all duration-200 ${
                  speed === "deep"
                    ? "border-blue-500 bg-blue-50 dark:bg-blue-950/40 shadow-lg shadow-blue-500/20 ring-2 ring-blue-500/20"
                    : "border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 hover:border-gray-300 dark:hover:border-neutral-600 hover:shadow-md"
                }`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="text-3xl">&#129504;</div>
                  {speed === "deep" && (
                    <div className="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center">
                      <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                  )}
                </div>
                <div className="font-bold text-gray-900 dark:text-white mb-1">Deep Training</div>
                <div className="text-sm text-gray-500 dark:text-gray-400 mb-2">Higher accuracy</div>
                <div className="text-xs text-gray-400 dark:text-gray-500">Longer compute time</div>
                <div className="mt-3 text-xs font-bold text-blue-600 dark:text-blue-400">~30-60 mins</div>
              </button>
            </div>
          </div>

          {/* Duration Slider */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">Duration</span>
              <span className="text-sm font-bold text-gray-900 dark:text-white">{onDemandHours} Hours</span>
            </div>
            <input
              type="range"
              min="5"
              max="24"
              step="1"
              value={onDemandHours}
              onChange={(e) => setOnDemandHours(Number(e.target.value))}
              className="w-full h-2 bg-gray-200 dark:bg-neutral-700 rounded-lg appearance-none cursor-pointer accent-blue-600"
              style={{
                background: `linear-gradient(to right, #2563eb 0%, #2563eb ${((onDemandHours - 5) / 19) * 100}%, ${typeof window !== "undefined" && document.documentElement.classList.contains("dark") ? "#404040" : "#e5e7eb"} ${((onDemandHours - 5) / 19) * 100}%, ${typeof window !== "undefined" && document.documentElement.classList.contains("dark") ? "#404040" : "#e5e7eb"} 100%)`
              }}
            />
            <div className="flex justify-between text-xs font-medium text-gray-400 dark:text-gray-500">
              <span className={onDemandHours === 5 ? "text-blue-600 dark:text-blue-400 font-bold" : ""}>5h</span>
              <span className={onDemandHours === 12 ? "text-blue-600 dark:text-blue-400 font-bold" : ""}>12h</span>
              <span className={onDemandHours === 24 ? "text-blue-600 dark:text-blue-400 font-bold" : ""}>24h</span>
            </div>
          </div>
        </div>
      )}

      {mode === "long-term" && (
        <div className="space-y-6">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">Training Duration</span>
              <span className="text-sm font-bold text-gray-900 dark:text-white">{longTermDays} Days</span>
            </div>
            <input
              type="range"
              min="1"
              max="30"
              step="1"
              value={longTermDays}
              onChange={(e) => setLongTermDays(Number(e.target.value))}
              className="w-full h-2 bg-gray-200 dark:bg-neutral-700 rounded-lg appearance-none cursor-pointer accent-blue-600"
              style={{
                background: `linear-gradient(to right, #2563eb 0%, #2563eb ${((longTermDays - 1) / 29) * 100}%, ${typeof window !== "undefined" && document.documentElement.classList.contains("dark") ? "#404040" : "#e5e7eb"} ${((longTermDays - 1) / 29) * 100}%, ${typeof window !== "undefined" && document.documentElement.classList.contains("dark") ? "#404040" : "#e5e7eb"} 100%)`
              }}
            />
            <div className="flex justify-between text-xs font-medium text-gray-400 dark:text-gray-500">
              <span className={longTermDays === 1 ? "text-blue-600 dark:text-blue-400 font-bold" : ""}>1 Day</span>
              <span className={longTermDays === 7 ? "text-blue-600 dark:text-blue-400 font-bold" : ""}>7 Days</span>
              <span className={longTermDays === 14 ? "text-blue-600 dark:text-blue-400 font-bold" : ""}>14 Days</span>
              <span className={longTermDays === 30 ? "text-blue-600 dark:text-blue-400 font-bold" : ""}>30 Days</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
