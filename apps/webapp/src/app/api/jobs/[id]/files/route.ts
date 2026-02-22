import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:9812";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const stage = request.nextUrl.searchParams.get("stage") ?? "prepared";
  try {
    const res = await fetch(`${BACKEND_URL}/jobs/${id}/files?stage=${stage}`);
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Backend request failed";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
