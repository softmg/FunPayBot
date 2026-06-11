import { createHmac, timingSafeEqual } from "crypto";
import { getSessionSecret, SESSION_MAX_AGE_MS } from "./session-config";

function hmac(data: string): string {
  return createHmac("sha256", getSessionSecret()).update(data).digest("hex");
}

/**
 * Creates a signed session token: `userId.timestamp.signature`.
 */
export function signSession(userId: string): string {
  const timestamp = Date.now().toString(36);
  const payload = `${userId}.${timestamp}`;
  return `${payload}.${hmac(payload)}`;
}

/**
 * Verifies an HMAC-signed session token and returns the userId,
 * or null if the token is invalid or expired.
 */
export function verifySession(token: string): string | null {
  const parts = token.split(".");
  if (parts.length !== 3) {
    return null;
  }

  const [userId, timestamp, signature] = parts;
  const payload = `${userId}.${timestamp}`;
  const expected = hmac(payload);

  const sigBuf = Buffer.from(signature, "hex");
  const expectedBuf = Buffer.from(expected, "hex");
  if (sigBuf.length !== expectedBuf.length || !timingSafeEqual(sigBuf, expectedBuf)) {
    return null;
  }

  const createdAt = parseInt(timestamp, 36);
  if (isNaN(createdAt) || Date.now() - createdAt > SESSION_MAX_AGE_MS) {
    return null;
  }

  return userId;
}
