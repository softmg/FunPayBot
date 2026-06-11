import { NextResponse } from "next/server";

/**
 * Error type for API route handlers. Carries the HTTP status that should be
 * returned to the client. Use with {@link apiErrorResponse} in a route's
 * `catch` block.
 */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Converts a thrown {@link ApiError} into a JSON response. Unexpected errors are
 * re-thrown so they surface as 500s through Next's error handling instead of
 * being masked as a structured 4xx.
 */
export function apiErrorResponse(error: unknown): NextResponse {
  if (error instanceof ApiError) {
    return NextResponse.json({ error: error.message }, { status: error.status });
  }
  throw error;
}

/**
 * Wraps an API route handler so that any {@link ApiError} it (or its auth
 * guard) throws is converted into the matching JSON status response. Unexpected
 * errors propagate unchanged to Next's error handling.
 */
export function withApiErrors<A extends unknown[]>(
  handler: (...args: A) => Promise<Response>
): (...args: A) => Promise<Response> {
  return async (...args: A) => {
    try {
      return await handler(...args);
    } catch (error) {
      return apiErrorResponse(error);
    }
  };
}
