import { describe, expect, it } from "vitest";
import { refusedAccountFrom, signInErrorFrom } from "./signinErrors";

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

describe("refusedAccountFrom", () => {
  it("reads which account Google reported from the one-off cookie", () => {
    const cookies = "theme=dark; yde_refused_account=pseudo-rush%40pages.plusgoogle.com; other=1";
    expect(refusedAccountFrom(cookies)).toBe("pseudo-rush@pages.plusgoogle.com");
  });

  it("is null when there is no such cookie", () => {
    expect(refusedAccountFrom("theme=dark")).toBeNull();
  });
});
