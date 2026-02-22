import HeroFlow from '@/components/HeroFlow'

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ repo?: string }>
}) {
  const params = await searchParams

  return (
    <div className="flex flex-col items-center px-4 py-12 min-h-screen">
      <div className="w-full max-w-2xl space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
            <p className="text-sm text-neutral-500">No sign-in required</p>
          </div>
        </div>
        <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-6">
          <h2 className="text-lg font-semibold mb-4">Configure Training</h2>
          <HeroFlow initialRepo={params.repo} />
        </div>
      </div>
    </div>
  )
}
