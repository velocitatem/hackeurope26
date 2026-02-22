import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:9812";

export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/health`);
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Backend unreachable";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}