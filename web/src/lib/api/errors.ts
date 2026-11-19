import { NextResponse } from "next/server";

import type { components } from "./schema";

export type ErrorResponse = components["schemas"]["ErrorResponse"];

/**
 * A JSON error in the same `ErrorResponse` shape FastAPI sends, for errors the web
 * server raises itself (a rejected Origin, an ended session, an unreachable API), so
 * browser code reads every error the same way.
 */
export function errorResponse(status: number, code: string, message: string): NextResponse {
  const body: ErrorResponse = { error: { code, message, details: [], request_id: null } };
  return NextResponse.json(body, { status });
}
