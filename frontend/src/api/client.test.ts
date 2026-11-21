import { describe, expect, it } from "vitest";

import { ApiError, errorMessage, unwrap } from "./client";

function result<T>(status: number, data?: T, error?: unknown) {
  return Promise.resolve({ data, error, response: new Response(null, { status }) });
}

describe("unwrap", () => {
  it("returns the data of a successful response", async () => {
    await expect(unwrap(result(200, { status: "ok" }))).resolves.toEqual({ status: "ok" });
  });

  it("throws ApiError with status and message", async () => {
    const error = await unwrap(result(404, undefined, { detail: "Filter not found" })).catch(
      (e: unknown) => e,
    );
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(404);
    expect((error as ApiError).message).toBe("Filter not found");
  });
});

describe("errorMessage", () => {
  it("joins validation messages", () => {
    const body = { detail: [{ msg: "Field required" }, { msg: "Invalid radius" }] };
    expect(errorMessage(422, body)).toBe("Field required; Invalid radius");
  });

  it("falls back to the status code", () => {
    expect(errorMessage(500, undefined)).toBe("Request failed (HTTP 500)");
    expect(errorMessage(502, "Bad Gateway")).toBe("Request failed (HTTP 502)");
  });
});
