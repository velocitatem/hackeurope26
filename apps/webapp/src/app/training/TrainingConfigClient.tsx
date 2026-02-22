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
    <div className="w-full max-w-xl mx-auto space-y-6">
      {/* Step indicator */}
      <div className="flex items-center gap-2 text-sm">
        <span className={step === "config" ? "font-medium text-blue-600" : "text-blue-500"}>1. Training</span>
        <span aria-hidden className="text-blue-400">→</span>
        <span className={step === "governance" ? "font-medium text-blue-600" : "text-blue-500"}>2. Data governance</span>
      </div>
      {step === "config" && (
        <>
      <div className="flex gap-1 p-1 bg-gray-100 rounded-lg">
        <button
          onClick={() => setMode("on-demand")}
          className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all ${
            mode === "on-demand"
              ? "bg-white shadow-sm text-gray-900"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          On-Demand
        </button>
        <button
          onClick={() => setMode("long-term")}
          className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all ${
            mode === "long-term"
              ? "bg-white shadow-sm text-gray-900"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          Long-Term
        </button>
      </div>

      {mode === "on-demand" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4 mb-4">
            <button
              onClick={() => setSpeed("fast")}
              className={`p-4 rounded-lg border-2 text-left transition-all ${
                speed === "fast"
                  ? "border-blue-500 shadow-md bg-blue-50"
                  : "border-amber-200 hover:border-amber-300"
              }`}
            >
              <div className="text-2xl mb-2">⚡</div>
              <div className="font-medium text-blue-900">Fast</div>
              <div className="text-sm text-gray-500">Lower accuracy</div>
            </button>
            <button
              onClick={() => setSpeed("deep")}
              className={`p-4 rounded-lg border-2 text-left transition-all ${
                speed === "deep"
                  ? "border-blue-500 shadow-md bg-blue-50"
                  : "border-gray-200 hover:border-gray-300"
              }`}
            >
              <div className="text-2xl mb-2"></div>
              <div className="font-medium text-blue-600">Deep</div>
              <div className="text-sm text-gray-500">Higher accuracy</div>
            </button>
          </div>
          <div className="text-center text-sm text-gray-500 mb-2">
            Duration: <span className="font-medium text-blue-600">{onDemandHours} Hours</span>
          </div>
          <input
            type="range"
            min="5"
            max="24"
            value={onDemandHours}
            onChange={(e) => setOnDemandHours(Number(e.target.value))}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
          />
          <div className="flex justify-between text-xs text-gray-400">
            <span className={onDemandHours === 5 ? "text-blue-500 font-medium" : ""}>5h</span>
            <span className={onDemandHours === 12 ? "text-blue-500 font-medium" : ""}>12h</span>
            <span className={onDemandHours === 24 ? "text-blue-500 font-medium" : ""}>24h</span>
          </div>
        </div>
      )}

      {mode === "long-term" && (
        <div className="space-y-4">
          <div className="text-center text-sm text-gray-500 mb-2">
            Training Duration: <span className="font-medium text-amber-900">{longTermDays} Days</span>
          </div>
          <input
            type="range"
            min="1"
            max="30"
            value={longTermDays}
            onChange={(e) => setLongTermDays(Number(e.target.value))}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
          />
          <div className="flex justify-between text-xs text-gray-400">
            <span className={longTermDays === 1 ? "text-blue-500 font-medium" : ""}>1 Day</span>
            <span className={longTermDays === 7 ? "text-blue-500 font-medium" : ""}>7 Days</span>
            <span className={longTermDays === 14 ? "text-blue-500 font-medium" : ""}>14 Days</span>
            <span className={longTermDays === 30 ? "text-blue-500 font-medium" : ""}>30 Days</span>
          </div>
        </div>
      )}
      </>
      )}

      {step === "governance" && (
        <div className="space-y-6 rounded-xl border border-neutral-200 dark:border-neutral-800 p-6 bg-neutral-50/50 dark:bg-neutral-900/30">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Data governance</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Choose the locations where you are fine with training and compliant with running the model. Data will only be processed in the regions you select.
          </p>
          <label className="flex items-center gap-3 cursor-pointer group">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleSelectAll}
              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300 group-hover:text-gray-900">Select all</span>
          </label>
          <div className="space-y-3">
            {DATA_LOCATIONS.map((loc) => (
              <label key={loc} className="flex items-center gap-3 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={selectedLocations.has(loc)}
                  onChange={() => toggleLocation(loc)}
                  className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300 group-hover:text-gray-900">{loc}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {step === "config" && initialRepo && (
        <div className="text-sm text-gray-500 text-center pt-4 border-t">
          Repository: <span className="font-mono text-gray-700">{initialRepo}</span>
        </div>
      )}

      <div className="flex gap-3 mt-6">
        {step === "governance" && (
          <button
            type="button"
            onClick={() => setStep("config")}
            className="rounded-lg border border-gray-300 dark:border-neutral-600 px-6 py-3 text-base font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-neutral-800"
          >
            Back
          </button>
        )}
        <button
          onClick={handleContinue}
          disabled={step === "governance" && !canContinueGovernance}
          className="flex-1 rounded-lg bg-blue-600 px-6 py-3 text-base font-medium text-white shadow-sm transition-colors hover:bg-blue-700 disabled:opacity-50 disabled:pointer-events-none"
        >
          {step === "config" ? "Continue" : "Continue to Dashboard"}
        </button>
      </div>
    </div>
  );
}
