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
      {/* Step 2: Choose Training Mode */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Choose Training Mode</h2>
        
        {/* Modern Pill-Style Segmented Control */}
        <div className="inline-flex gap-1 p-1 bg-gray-100 rounded-xl border border-gray-200">
          <button
            onClick={() => setMode("on-demand")}
            className={`relative px-6 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
              mode === "on-demand"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            On-Demand
          </button>
          <button
            onClick={() => setMode("long-term")}
            className={`relative px-6 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
              mode === "long-term"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
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
            <h3 className="text-sm font-medium text-gray-700 mb-4">Training Speed</h3>
            <div className="grid grid-cols-2 gap-4">
              {/* Fast Option */}
              <button
                onClick={() => setSpeed("fast")}
                className={`group relative p-6 rounded-xl border-2 text-left transition-all duration-200 ${
                  speed === "fast"
                    ? "border-blue-500 bg-blue-50/50 shadow-lg shadow-blue-500/20 ring-2 ring-blue-500/20"
                    : "border-gray-200 bg-white hover:border-gray-300 hover:shadow-md"
                }`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="text-3xl">⚡</div>
                  {speed === "fast" && (
                    <div className="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center">
                      <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                  )}
                </div>
                <div className="font-semibold text-gray-900 mb-1">Fast Training</div>
                <div className="text-sm text-gray-600 mb-2">Lower accuracy</div>
                <div className="text-xs text-gray-500">Quick iteration</div>
                <div className="mt-3 text-xs font-medium text-blue-600">~5–10 mins</div>
              </button>

              {/* Deep Option */}
              <button
                onClick={() => setSpeed("deep")}
                className={`group relative p-6 rounded-xl border-2 text-left transition-all duration-200 ${
                  speed === "deep"
                    ? "border-blue-500 bg-blue-50/50 shadow-lg shadow-blue-500/20 ring-2 ring-blue-500/20"
                    : "border-gray-200 bg-white hover:border-gray-300 hover:shadow-md"
                }`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="text-3xl">🧠</div>
                  {speed === "deep" && (
                    <div className="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center">
                      <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                  )}
                </div>
                <div className="font-semibold text-gray-900 mb-1">Deep Training</div>
                <div className="text-sm text-gray-600 mb-2">Higher accuracy</div>
                <div className="text-xs text-gray-500">Longer compute time</div>
                <div className="mt-3 text-xs font-medium text-blue-600">~30–60 mins</div>
              </button>
            </div>
          </div>

          {/* Duration Slider */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">Duration</span>
              <span className="text-sm font-semibold text-gray-900">{onDemandHours} Hours</span>
            </div>
            <input
              type="range"
              min="5"
              max="24"
              step="1"
              value={onDemandHours}
              onChange={(e) => setOnDemandHours(Number(e.target.value))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
              style={{
                background: `linear-gradient(to right, #2563eb 0%, #2563eb ${((onDemandHours - 5) / 19) * 100}%, #e5e7eb ${((onDemandHours - 5) / 19) * 100}%, #e5e7eb 100%)`
              }}
            />
            <div className="flex justify-between text-xs text-gray-500">
              <span className={onDemandHours === 5 ? "text-blue-600 font-semibold" : ""}>5h</span>
              <span className={onDemandHours === 12 ? "text-blue-600 font-semibold" : ""}>12h</span>
              <span className={onDemandHours === 24 ? "text-blue-600 font-semibold" : ""}>24h</span>
            </div>
          </div>
        </div>
      )}

      {mode === "long-term" && (
        <div className="space-y-6">
          {/* Duration Slider */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">Training Duration</span>
              <span className="text-sm font-semibold text-gray-900">{longTermDays} Days</span>
            </div>
            <input
              type="range"
              min="1"
              max="30"
              step="1"
              value={longTermDays}
              onChange={(e) => setLongTermDays(Number(e.target.value))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
              style={{
                background: `linear-gradient(to right, #2563eb 0%, #2563eb ${((longTermDays - 1) / 29) * 100}%, #e5e7eb ${((longTermDays - 1) / 29) * 100}%, #e5e7eb 100%)`
              }}
            />
            <div className="flex justify-between text-xs text-gray-500">
              <span className={longTermDays === 1 ? "text-blue-600 font-semibold" : ""}>1 Day</span>
              <span className={longTermDays === 7 ? "text-blue-600 font-semibold" : ""}>7 Days</span>
              <span className={longTermDays === 14 ? "text-blue-600 font-semibold" : ""}>14 Days</span>
              <span className={longTermDays === 30 ? "text-blue-600 font-semibold" : ""}>30 Days</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
