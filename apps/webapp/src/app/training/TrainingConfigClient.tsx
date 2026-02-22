"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type Mode = "on-demand" | "long-term";
type Speed = "fast" | "deep";
type FlowStep = "config" | "governance";

const DATA_LOCATIONS = ["France", "UK", "Italy", "Finland"] as const;
type DataLocation = (typeof DATA_LOCATIONS)[number];

interface TrainingConfigClientProps {
  initialRepo?: string;
}

export default function TrainingConfigClient({ initialRepo }: TrainingConfigClientProps) {
  const router = useRouter();
  const [step, setStep] = useState<FlowStep>("config");
  const [mode, setMode] = useState<Mode>("on-demand");
  const [speed, setSpeed] = useState<Speed>("fast");
  const [onDemandHours, setOnDemandHours] = useState(12);
  const [longTermDays, setLongTermDays] = useState(7);
  const [selectedLocations, setSelectedLocations] = useState<Set<DataLocation>>(
    new Set(DATA_LOCATIONS)
  );

  const allSelected = DATA_LOCATIONS.every((loc) => selectedLocations.has(loc));
  const toggleLocation = (loc: DataLocation) => {
    setSelectedLocations((prev) => {
      const next = new Set(prev);
      if (next.has(loc)) next.delete(loc);
      else next.add(loc);
      return next;
    });
  };
  const toggleSelectAll = () => {
    if (allSelected) setSelectedLocations(new Set());
    else setSelectedLocations(new Set(DATA_LOCATIONS));
  };
  const canContinueGovernance = selectedLocations.size > 0;

  function handleContinue() {
    if (step === "config") {
      setStep("governance");
      return;
    }
    router.push("/dashboard");
  }

  return (
    <div className="w-full max-w-xl mx-auto space-y-8">
      {/* Step indicator */}
      <div className="flex items-center gap-3 text-sm font-medium">
        <span className={step === "config" ? "text-blue-600 dark:text-blue-400" : "text-gray-400 dark:text-gray-500"}>
          1. Training
        </span>
        <span aria-hidden className="text-gray-300 dark:text-gray-600">&rarr;</span>
        <span className={step === "governance" ? "text-blue-600 dark:text-blue-400" : "text-gray-400 dark:text-gray-500"}>
          2. Data governance
        </span>
      </div>

      {step === "config" && (
        <>
          {/* Segmented control */}
          <div className="flex gap-1 p-1 bg-gray-100 dark:bg-neutral-800 rounded-xl">
            <button
              onClick={() => setMode("on-demand")}
              className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-semibold transition-all ${
                mode === "on-demand"
                  ? "bg-white dark:bg-neutral-700 shadow-sm text-gray-900 dark:text-white"
                  : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
              }`}
            >
              On-Demand
            </button>
            <button
              onClick={() => setMode("long-term")}
              className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-semibold transition-all ${
                mode === "long-term"
                  ? "bg-white dark:bg-neutral-700 shadow-sm text-gray-900 dark:text-white"
                  : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
              }`}
            >
              Long-Term
            </button>
          </div>

          {mode === "on-demand" && (
            <div className="space-y-6">
              {/* Speed cards */}
              <div className="grid grid-cols-2 gap-4">
                <button
                  onClick={() => setSpeed("fast")}
                  className={`p-5 rounded-xl border-2 text-left transition-all ${
                    speed === "fast"
                      ? "border-blue-500 bg-blue-50 dark:bg-blue-950/40 shadow-md ring-1 ring-blue-500/20"
                      : "border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 hover:border-gray-300 dark:hover:border-neutral-600 hover:shadow-sm"
                  }`}
                >
                  <div className="text-2xl mb-3">&#9889;</div>
                  <div className="font-semibold text-gray-900 dark:text-white">Fast</div>
                  <div className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">Lower accuracy</div>
                </button>
                <button
                  onClick={() => setSpeed("deep")}
                  className={`p-5 rounded-xl border-2 text-left transition-all ${
                    speed === "deep"
                      ? "border-blue-500 bg-blue-50 dark:bg-blue-950/40 shadow-md ring-1 ring-blue-500/20"
                      : "border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 hover:border-gray-300 dark:hover:border-neutral-600 hover:shadow-sm"
                  }`}
                >
                  <div className="text-2xl mb-3">&#129504;</div>
                  <div className="font-semibold text-gray-900 dark:text-white">Deep</div>
                  <div className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">Higher accuracy</div>
                </button>
              </div>

              {/* Duration slider */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">Duration</span>
                  <span className="text-sm font-bold text-blue-600 dark:text-blue-400">{onDemandHours} Hours</span>
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
                  <span className="text-sm font-bold text-blue-600 dark:text-blue-400">{longTermDays} Days</span>
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
        </>
      )}

      {step === "governance" && (
        <div className="space-y-5 rounded-xl border border-gray-200 dark:border-neutral-700 p-6 bg-gray-50 dark:bg-neutral-800/50">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white">Data governance</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
            Choose the locations where you are fine with training and compliant with running the model. Data will only be processed in the regions you select.
          </p>
          <label className="flex items-center gap-3 cursor-pointer group">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleSelectAll}
              className="h-4 w-4 rounded border-gray-300 dark:border-neutral-600 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm font-semibold text-gray-800 dark:text-gray-200 group-hover:text-gray-900 dark:group-hover:text-white">Select all</span>
          </label>
          <div className="space-y-3">
            {DATA_LOCATIONS.map((loc) => (
              <label key={loc} className="flex items-center gap-3 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={selectedLocations.has(loc)}
                  onChange={() => toggleLocation(loc)}
                  className="h-4 w-4 rounded border-gray-300 dark:border-neutral-600 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white">{loc}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {step === "config" && initialRepo && (
        <div className="text-sm text-gray-500 dark:text-gray-400 text-center pt-4 border-t border-gray-200 dark:border-neutral-700">
          Repository: <span className="font-mono font-medium text-gray-700 dark:text-gray-300">{initialRepo}</span>
        </div>
      )}

      <div className="flex gap-3 pt-2">
        {step === "governance" && (
          <button
            type="button"
            onClick={() => setStep("config")}
            className="rounded-xl border border-gray-300 dark:border-neutral-600 px-6 py-3 text-base font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-neutral-800 transition-colors"
          >
            Back
          </button>
        )}
        <button
          onClick={handleContinue}
          disabled={step === "governance" && !canContinueGovernance}
          className="flex-1 rounded-xl bg-blue-600 px-6 py-3 text-base font-semibold text-white shadow-sm transition-colors hover:bg-blue-700 disabled:opacity-50 disabled:pointer-events-none"
        >
          {step === "config" ? "Continue" : "Continue to Dashboard"}
        </button>
      </div>
    </div>
  );
}
