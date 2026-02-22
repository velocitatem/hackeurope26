import TrainingConfigClient from './TrainingConfigClient'

export default async function TrainingPage({
  searchParams,
}: {
  searchParams: Promise<{ repo?: string }>
}) {
  const params = await searchParams

  return (
    <div className="flex flex-col items-center px-4 py-16 min-h-screen">
      <div className="w-full max-w-2xl space-y-10">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">Configure Training</h1>
          <p className="mt-1 text-base text-gray-500 dark:text-gray-400">Set up your training parameters</p>
        </div>
        <div className="rounded-2xl border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-8 shadow-sm">
          <TrainingConfigClient initialRepo={params.repo} />
        </div>
      </div>
    </div>
  )
}
