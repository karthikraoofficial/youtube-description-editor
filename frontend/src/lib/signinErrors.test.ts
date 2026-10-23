import { describe, expect, it } from "vitest";
import { signInErrorFrom } from "./signinErrors";

describe("signInErrorFrom", () => {
  it("explains a refused account without saying whose account is allowed", () => {
    const message = signInErrorFrom("?signin_error=not_allowed");
    expect(message).toMatch(/isn't allowed/);
    expect(message).not.toMatch(/@/);
  });

  it("explains each reason the callback can give", () => {
    for (const code of ["no_client_secret", "state", "access_denied", "channel", "google"]) {
      expect(signInErrorFrom(`?signin_error=${code}`)).toBeTruthy();
    }
  });

  it("falls back to a general message for an unknown reason, and to nothing without one", () => {
    expect(signInErrorFrom("?signin_error=something_new")).toMatch(/Sign-in didn't complete/);
    expect(signInErrorFrom("?other=1")).toBeNull();
  });
});
