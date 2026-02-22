import TrainingConfigClient from './TrainingConfigClient'

export default async function TrainingPage({
  searchParams,
}: {
  searchParams: Promise<{ repo?: string }>
}) {
  const params = await searchParams

  return (
    <div className="flex flex-col items-center px-4 py-12 min-h-screen">
      <div className="w-full max-w-2xl space-y-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Configure Training</h1>
          <p className="text-sm text-neutral-500">Set up your training parameters</p>
        </div>
        <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-6">
          <TrainingConfigClient initialRepo={params.repo} />
        </div>
      </div>
    </div>
  )
}
