import { NextRequest, NextResponse } from "next/server";

const RAILS_API_URL = process.env.RAILS_API_URL ?? "http://localhost:3001";

async function fetchRails(path: string) {
  const response = await fetch(`${RAILS_API_URL}${path}`);
  const data = await response.json().catch(() => []);

  if (!response.ok) {
    throw new Error(
      typeof data === "object" && data !== null && "error" in data
        ? String((data as { error: unknown }).error)
        : `Rails API request failed (${response.status})`
    );
  }

  return data;
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ jobId: string }> }
) {
  const { jobId } = await params;
  const override = request.nextUrl.searchParams.get("job_external_id");
  const jobExternalId = override ?? jobId;
  const query = `?job_external_id=${encodeURIComponent(jobExternalId)}`;

  try {
    const [schedulingDecisions, migrationEvents] = await Promise.all([
      fetchRails(`/api/scheduling_decisions${query}`),
      fetchRails(`/api/migration_events${query}`),
    ]);

    return NextResponse.json({
      job_external_id: jobExternalId,
      schedulingDecisions,
      migrationEvents,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Rails audit request failed";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
