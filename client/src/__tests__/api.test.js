import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test-setup.js";

import {
  TOPIC_MIN,
  TOPIC_MAX,
  createJob,
  getJob,
  getBlog,
  retryJob,
  getReview,
  submitDecision,
  listJobs,
} from "../api.js";

const BASE = "http://localhost:8000";

describe("constants", () => {
  it("TOPIC_MIN is 10", () => {
    expect(TOPIC_MIN).toBe(10);
  });

  it("TOPIC_MAX is 2000", () => {
    expect(TOPIC_MAX).toBe(2000);
  });
});

describe("createJob", () => {
  it("sends POST /jobs and returns data", async () => {
    server.use(
      http.post(`${BASE}/jobs`, () =>
        HttpResponse.json(
          { job_id: "abc", status: "IN-PROGRESS", stage: "queued" },
          { status: 202 }
        )
      )
    );
    const result = await createJob("Test topic here");
    expect(result.job_id).toBe("abc");
  });

  it("throws with detail string on error response", async () => {
    server.use(
      http.post(`${BASE}/jobs`, () =>
        HttpResponse.json({ detail: "Topic too short" }, { status: 422 })
      )
    );
    await expect(createJob("x")).rejects.toThrow("Topic too short");
  });

  it("joins array detail from Pydantic 422", async () => {
    server.use(
      http.post(`${BASE}/jobs`, () =>
        HttpResponse.json(
          { detail: [{ msg: "too short" }, { msg: "invalid chars" }] },
          { status: 422 }
        )
      )
    );
    await expect(createJob("x")).rejects.toThrow("too short; invalid chars");
  });

  it("throws server-unreachable message on network error", async () => {
    server.use(
      http.post(`${BASE}/jobs`, () => HttpResponse.error())
    );
    await expect(createJob("some topic")).rejects.toThrow(
      "Can't reach the server"
    );
  });
});

describe("getJob", () => {
  it("sends GET /jobs/:id", async () => {
    server.use(
      http.get(`${BASE}/jobs/job-1`, () =>
        HttpResponse.json({ id: "job-1", status: "COMPLETE" })
      )
    );
    const result = await getJob("job-1");
    expect(result.id).toBe("job-1");
  });

  it("throws on 404", async () => {
    server.use(
      http.get(`${BASE}/jobs/missing`, () =>
        HttpResponse.json({ detail: "Job not found" }, { status: 404 })
      )
    );
    await expect(getJob("missing")).rejects.toThrow("Job not found");
  });
});

describe("getBlog", () => {
  it("sends GET /jobs/:id/blog", async () => {
    server.use(
      http.get(`${BASE}/jobs/job-1/blog`, () =>
        HttpResponse.json({ content: "# Blog", title: "Blog" })
      )
    );
    const result = await getBlog("job-1");
    expect(result.content).toBe("# Blog");
  });

  it("throws on 409 when blog not ready", async () => {
    server.use(
      http.get(`${BASE}/jobs/job-1/blog`, () =>
        HttpResponse.json({ detail: "Blog is not ready yet" }, { status: 409 })
      )
    );
    await expect(getBlog("job-1")).rejects.toThrow("Blog is not ready yet");
  });
});

describe("retryJob", () => {
  it("sends POST /jobs/:id/retry", async () => {
    server.use(
      http.post(`${BASE}/jobs/job-1/retry`, () =>
        HttpResponse.json(
          { job_id: "job-1", status: "IN-PROGRESS", stage: "queued" },
          { status: 202 }
        )
      )
    );
    const result = await retryJob("job-1");
    expect(result.job_id).toBe("job-1");
  });
});

describe("getReview", () => {
  it("sends GET /jobs/:id/review", async () => {
    server.use(
      http.get(`${BASE}/jobs/job-1/review`, () =>
        HttpResponse.json({ pending: false, job_id: "job-1" })
      )
    );
    const result = await getReview("job-1");
    expect(result.pending).toBe(false);
  });
});

describe("submitDecision", () => {
  it("sends POST /jobs/:id/decision with decision body", async () => {
    let capturedBody;
    server.use(
      http.post(`${BASE}/jobs/job-1/decision`, async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json(
          { job_id: "job-1", status: "IN-PROGRESS", stage: "queued" },
          { status: 202 }
        );
      })
    );
    await submitDecision("job-1", "proceed");
    expect(capturedBody.decision).toBe("proceed");
  });
});

describe("listJobs", () => {
  it("sends GET /jobs with limit and offset", async () => {
    let capturedUrl;
    server.use(
      http.get(`${BASE}/jobs`, ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json({ jobs: [], total: 0, limit: 10, offset: 0 });
      })
    );
    await listJobs(10, 5);
    expect(capturedUrl).toContain("limit=10");
    expect(capturedUrl).toContain("offset=5");
  });
});
