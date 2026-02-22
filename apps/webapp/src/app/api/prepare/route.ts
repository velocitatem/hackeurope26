import { NextRequest, NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://localhost:9812";

export async function POST(request: NextRequest) {
  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  if (!body.repo_url || typeof body.repo_url !== "string") {
    return NextResponse.json({ error: "repo_url is required" }, { status: 400 });
  }

  const base = process.env.BACKEND_URL ?? DEFAULT_BACKEND_URL;
  const url = `${base.replace(/\/$/, "")}/prepare`;

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repo_url: body.repo_url,
        branch: body.branch ?? "main",
        allowed_geos: body.allowed_geos ?? [],
        max_price_usd_hour: body.max_price_usd_hour ?? 0,
        image: body.image ?? "",
        timeout: body.timeout ?? 300,
        verbose: body.verbose ?? false,
      }),
    });
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Backend request failed";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}