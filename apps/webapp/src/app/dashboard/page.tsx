import { redirect } from 'next/navigation'
import { createClient } from '@/utils/supabase/server'
import { logout } from './actions'
import HeroFlow from '@/components/HeroFlow'

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ repo?: string }>
}) {
  const supabase = await createClient()
  const params = await searchParams

  const { data, error } = await supabase.auth.getUser()
  if (error || !data?.user) {
    redirect('/login')
  }

  return (
    <div className="flex flex-col items-center px-4 py-12 min-h-screen">
      <div className="w-full max-w-2xl space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
            <p className="text-sm text-neutral-500">{data.user.email}</p>
          </div>
          <form>
            <button
              formAction={logout}
              className="rounded-lg border border-neutral-300 dark:border-neutral-700 px-4 py-2 text-sm font-medium text-neutral-700 dark:text-neutral-300 transition-colors hover:bg-neutral-100 dark:hover:bg-neutral-800"
            >
              Logout
            </button>
          </form>
        </div>
        <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-6">
          <h2 className="text-lg font-semibold mb-4">Configure Training</h2>
          <HeroFlow initialRepo={params.repo} />
        </div>
      </div>
    </div>
  )
}