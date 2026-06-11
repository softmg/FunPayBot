/**
 * Builds request headers for calls to the internal funpay-api service,
 * attaching the shared internal token when configured.
 */
export function funpayHeaders(base: Record<string, string> = {}): Record<string, string> {
  const token = process.env.INTERNAL_API_TOKEN;
  return token ? { ...base, "x-internal-token": token } : base;
}
