"use client";

import { useState } from "react";

interface GithubRepoInputProps {
  onSubmit?: (url: string) => void;
}

export default function GithubRepoInput({ onSubmit }: GithubRepoInputProps) {
  const [url, setUrl] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    if (onSubmit) {
      onSubmit(url);
    } else {
      console.log("Submitted repo URL:", url);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex w-full max-w-xl gap-3">
      <label htmlFor="github-repo-url" className="sr-only">
        Github Repo URL
      </label>
      <input
        id="github-repo-url"
        type="url"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://github.com/owner/repo"
        className="flex-1 rounded-lg border border-gray-300 bg-white px-4 py-3 text-base text-foreground shadow-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30 dark:border-gray-600 dark:bg-gray-800 dark:placeholder:text-gray-500"
      />
      <button
        type="submit"
        className="rounded-lg bg-blue-600 px-6 py-3 text-base font-medium text-white shadow-sm transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
      >
        Next
      </button>
    </form>
  );
}
