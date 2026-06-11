import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { signSession, verifySession } from "./session";
import { getSessionSecret, SESSION_MAX_AGE_MS } from "./session-config";

const ORIGINAL_SECRET = process.env.NEXTAUTH_SECRET;
const ORIGINAL_NODE_ENV = process.env.NODE_ENV;

function setNodeEnv(value: string | undefined) {
  // NODE_ENV is read-only in the Next type defs; assign through a cast for tests.
  (process.env as Record<string, string | undefined>).NODE_ENV = value;
}

describe("session tokens", () => {
  beforeEach(() => {
    process.env.NEXTAUTH_SECRET = "a-strong-test-secret";
    setNodeEnv("test");
  });

  afterEach(() => {
    process.env.NEXTAUTH_SECRET = ORIGINAL_SECRET;
    setNodeEnv(ORIGINAL_NODE_ENV);
  });

  it("signs and verifies a round-trip token", () => {
    const token = signSession("user-123");
    expect(verifySession(token)).toBe("user-123");
  });

  it("rejects a tampered signature", () => {
    const token = signSession("user-123");
    const tampered = token.slice(0, -1) + (token.endsWith("0") ? "1" : "0");
    expect(verifySession(tampered)).toBeNull();
  });

  it("rejects a token whose payload was altered", () => {
    const [, timestamp, signature] = signSession("user-123").split(".");
    expect(verifySession(`attacker.${timestamp}.${signature}`)).toBeNull();
  });

  it("rejects malformed tokens", () => {
    expect(verifySession("not-a-token")).toBeNull();
    expect(verifySession("a.b")).toBeNull();
  });

  it("rejects a correctly-signed but expired token", () => {
    vi.useFakeTimers();
    try {
      vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
      const token = signSession("user-123");
      expect(verifySession(token)).toBe("user-123");

      vi.setSystemTime(Date.now() + SESSION_MAX_AGE_MS + 1000);
      expect(verifySession(token)).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("getSessionSecret", () => {
  const ORIGINAL = process.env.NEXTAUTH_SECRET;

  afterEach(() => {
    process.env.NEXTAUTH_SECRET = ORIGINAL;
    setNodeEnv(ORIGINAL_NODE_ENV);
  });

  it("returns the configured secret", () => {
    process.env.NEXTAUTH_SECRET = "real-secret";
    setNodeEnv("production");
    expect(getSessionSecret()).toBe("real-secret");
  });

  it("throws in production when the secret is missing or a placeholder", () => {
    setNodeEnv("production");
    for (const placeholder of ["", "replace-me", "change-me", "dev-fallback-secret"]) {
      process.env.NEXTAUTH_SECRET = placeholder;
      expect(() => getSessionSecret()).toThrow(/NEXTAUTH_SECRET/);
    }
  });

  it("falls back to a dev secret outside production", () => {
    setNodeEnv("development");
    process.env.NEXTAUTH_SECRET = "";
    expect(getSessionSecret()).toBe("dev-fallback-secret");
  });
});
