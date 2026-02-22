import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t border-neutral-200 bg-white/80 dark:border-neutral-800 dark:bg-neutral-950/80">
      <div className="mx-auto grid w-full max-w-7xl grid-cols-1 gap-8 px-6 py-10 sm:grid-cols-2">
        <div>
          <h3 className="text-lg font-semibold tracking-tight">Sustain</h3>
          <p className="mt-2 max-w-sm text-sm text-neutral-600 dark:text-neutral-400">
            Optimize ML training carbon footprint with practical, guided workflows.
          </p>
        </div>
        <div className="sm:justify-self-end">
          <h4 className="text-sm font-semibold uppercase tracking-wider text-neutral-700 dark:text-neutral-300">Legal</h4>
          <ul className="mt-3 space-y-2 text-sm">
            <li>
              <Link href="/privacy-policy" className="text-neutral-600 transition-colors hover:text-black dark:text-neutral-400 dark:hover:text-white">
                Privacy Policy
              </Link>
            </li>
            <li>
              <Link href="/tos" className="text-neutral-600 transition-colors hover:text-black dark:text-neutral-400 dark:hover:text-white">
                Terms of Service
              </Link>
            </li>
          </ul>
        </div>
      </div>
      <div className="border-t border-neutral-200 dark:border-neutral-800">
        <div className="mx-auto w-full max-w-7xl px-6 py-4">
          <p className="text-sm text-neutral-600 dark:text-neutral-400">© 2026 Sustain. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
}
