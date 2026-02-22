import Link from "next/link";
import { ThemeToggle } from "@/components/ThemeToggle";

export default function Header() {
  return (
    <header className="sticky top-0 z-50 w-full bg-white/80 dark:bg-neutral-950/80 backdrop-blur-sm border-b border-neutral-200 dark:border-neutral-800">
      <div className="flex items-center justify-between px-6 py-3 max-w-7xl mx-auto">
        <Link href="/" className="text-lg font-bold tracking-tight shrink-0">
          Sustain
        </Link>
        <nav className="hidden md:flex items-center gap-6 absolute left-1/2 -translate-x-1/2">
          <Link href="/" className="text-sm text-neutral-600 dark:text-neutral-300 hover:text-black dark:hover:text-white transition-colors">Home</Link>
          <Link href="/dashboard" className="text-sm text-neutral-600 dark:text-neutral-300 hover:text-black dark:hover:text-white transition-colors">Dashboard</Link>
          <Link href="/blog" className="text-sm text-neutral-600 dark:text-neutral-300 hover:text-black dark:hover:text-white transition-colors">Blog</Link>
        </nav>
        <div className="flex items-center justify-end gap-3">
          <ThemeToggle />
          <Link href="/questions" className="text-sm text-neutral-600 dark:text-neutral-300 hover:text-black dark:hover:text-white transition-colors">Get Started</Link>
        </div>
      </div>
    </header>
  );
}
