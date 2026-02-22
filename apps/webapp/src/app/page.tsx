import Link from "next/link";
import { TilesDemo } from "@/components/TilesDemo";

export default function Home() {
  return (
    <div className="relative min-h-screen">
      <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
        <TilesDemo />
      </div>
      <div className="relative z-10 flex flex-col items-center justify-center min-h-[80vh] px-4">
        <h1 className="text-5xl sm:text-6xl font-bold tracking-tight text-center mb-4">
          Sustain
        </h1>
        <p className="text-lg sm:text-xl text-neutral-600 dark:text-neutral-400 text-center max-w-2xl mb-8">
          Optimize your ML training carbon footprint. Upload your repo, configure training, and find the greenest compute window.
        </p>
        <div className="flex gap-4">
          <Link
            href="/questions"
            className="rounded-lg bg-blue-600 px-6 py-3 text-base font-medium text-white shadow-sm transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
          >
            Get Started
          </Link>
          <Link
            href="/blog"
            className="rounded-lg border border-neutral-300 dark:border-neutral-700 px-6 py-3 text-base font-medium text-neutral-700 dark:text-neutral-300 transition-colors hover:bg-neutral-100 dark:hover:bg-neutral-800"
          >
            Learn More
          </Link>
        </div>
      </div>
    </div>
  );
}
