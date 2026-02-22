"use client";

import { useState, useEffect } from "react";
import GithubRepoInput from "@/components/GithubRepoInput";
import TrainingConfig from "@/components/TrainingConfig";

interface HeroFlowProps {
  initialRepo?: string;
}

export default function HeroFlow({ initialRepo }: HeroFlowProps) {
  const [step, setStep] = useState<"repo" | "config">("repo");
  const [repoUrl, setRepoUrl] = useState(initialRepo || "");

  useEffect(() => {
    if (initialRepo) {
      setStep("config");
    }
  }, [initialRepo]);

  async function handleRepoSubmit(url: string) {
    const trimmed = url.trim();
    setRepoUrl(trimmed);
    setStep("config");
    fetch("/api/prepare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_url: trimmed }),
    }).catch(() => {});
  }

  return (
    <div className="w-full max-w-xl mx-auto">
      {step === "repo" && (
        <GithubRepoInput onSubmit={handleRepoSubmit} />
      )}
      {step === "config" && (
        <div className="space-y-4">
          <div className="text-sm text-gray-500 text-center">
            Repository: <span className="font-mono text-gray-700">{repoUrl}</span>
            <button 
              onClick={() => setStep("repo")}
              className="ml-2 text-blue-500 hover:underline"
            >
              Change
            </button>
          </div>
          <TrainingConfig />
        </div>
      )}
    </div>
  );
}
