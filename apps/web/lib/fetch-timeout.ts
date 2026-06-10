export class UpstreamTimeoutError extends Error {
  constructor(message = "Upstream request timed out") {
    super(message);
    this.name = "UpstreamTimeoutError";
  }
}

function parseTimeoutMs(value: string | undefined, fallback: number) {
  if (!value) {
    return fallback;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

export const FUNPAY_API_TIMEOUT_MS = parseTimeoutMs(process.env.FUNPAY_API_TIMEOUT_MS, 15_000);
export const TELEGRAM_API_TIMEOUT_MS = parseTimeoutMs(process.env.TELEGRAM_API_TIMEOUT_MS, 10_000);

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

export async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit = {},
  timeoutMs = FUNPAY_API_TIMEOUT_MS
) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  timeout.unref?.();

  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (error) {
    if (isAbortError(error)) {
      throw new UpstreamTimeoutError();
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}
