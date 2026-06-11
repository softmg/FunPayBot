/**
 * Session configuration shared between the Edge middleware and the Node runtime.
 *
 * This module must stay free of Node-only APIs (e.g. `node:crypto`) so it can be
 * imported from the Edge middleware bundle.
 */

export const SESSION_COOKIE = "funpaybot_user";
export const SESSION_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;
export const SESSION_MAX_AGE_SECONDS = SESSION_MAX_AGE_MS / 1000;

const DEV_FALLBACK_SECRET = "dev-fallback-secret";

/**
 * Values that must never be used to sign sessions in production. They are the
 * placeholders shipped in `.env.example` plus the historical dev fallback.
 */
const PLACEHOLDER_SECRETS = new Set(["", "replace-me", "change-me", DEV_FALLBACK_SECRET]);

/**
 * Resolves the HMAC secret used to sign session cookies.
 *
 * In production a missing or placeholder secret is a fatal misconfiguration that
 * would let anyone forge sessions, so we throw instead of silently falling back.
 * Outside production we allow a fixed dev secret so local development works.
 */
export function getSessionSecret(): string {
  const secret = process.env.NEXTAUTH_SECRET ?? "";
  if (PLACEHOLDER_SECRETS.has(secret)) {
    if (process.env.NODE_ENV === "production") {
      throw new Error(
        "NEXTAUTH_SECRET must be set to a strong, unique value in production. " +
          "Refusing to sign sessions with a placeholder secret."
      );
    }
    return DEV_FALLBACK_SECRET;
  }
  return secret;
}
