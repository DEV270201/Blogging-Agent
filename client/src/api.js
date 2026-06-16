// Thin wrapper around the FastAPI server. Every call surfaces a human-friendly
// message: network failures, FastAPI {detail} errors, and 422 validation arrays.

const BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(
  /\/$/,
  ""
);

export const TOPIC_MIN = 10;
export const TOPIC_MAX = 2000;

function extractDetail(data, status) {
  const detail = data?.detail;
  if (Array.isArray(detail)) {
    // FastAPI/Pydantic 422 -> [{ loc, msg, ... }]
    return detail.map((d) => d.msg || String(d)).join("; ");
  }
  if (typeof detail === "string") return detail;
  return `Request failed (${status})`;
}

async function request(path, options) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, options);
  } catch {
    throw new Error("Can't reach the server. Make sure it's running.");
  }

  if (!res.ok) {
    let data = null;
    try {
      data = await res.json();
    } catch {
      /* response had no JSON body */
    }
    throw new Error(extractDetail(data, res.status));
  }

  if (res.status === 204) return null;
  return res.json();
}

export function getHealth() {
  return request("/health", { method: "GET" });
}

export function createJob(topic) {
  return request("/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic }),
  });
}

export function getJob(jobId) {
  return request(`/jobs/${jobId}`, { method: "GET" });
}

export function getBlog(jobId) {
  return request(`/jobs/${jobId}/blog`, { method: "GET" });
}

export function retryJob(jobId) {
  return request(`/jobs/${jobId}/retry`, { method: "POST" });
}

export function listJobs(limit = 100, offset = 0) {
  return request(`/jobs?limit=${limit}&offset=${offset}`, { method: "GET" });
}
