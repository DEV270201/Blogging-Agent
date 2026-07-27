import { useCallback, useEffect, useRef, useState } from "react";

import {
  createJob,
  getBlog,
  getHealth,
  getJob,
  getReview,
  listJobs,
  retryJob,
  submitDecision,
} from "./api.js";
import Sidebar from "./components/Sidebar.jsx";
import BlogForm from "./components/BlogForm.jsx";
import ProgressView from "./components/ProgressView.jsx";
import BlogView from "./components/BlogView.jsx";
import Toasts from "./components/Toasts.jsx";

const POLL_INTERVAL_MS = 3000;
// Consecutive poll failures before we treat the server as unreachable (~12s).
const POLL_MAX_FAILURES = 4;

let toastSeq = 0;

export default function App() {
  const [jobs, setJobs] = useState([]);
  const [tab, setTab] = useState("library");
  const [view, setView] = useState("create"); // "create" | "progress" | "blog"
  const [activeJob, setActiveJob] = useState(null);
  const [review, setReview] = useState(null);
  const [blog, setBlog] = useState(null);
  const [blogLoading, setBlogLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [pollId, setPollId] = useState(null);
  const [connectionLost, setConnectionLost] = useState(false);
  const [serverOk, setServerOk] = useState(null);
  const [toasts, setToasts] = useState([]);

  // --- toasts ---------------------------------------------------------------
  const dismissToast = useCallback((id) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  const addToast = useCallback(
    (type, message) => {
      const id = ++toastSeq;
      setToasts((t) => [...t, { id, type, message }]);
      setTimeout(() => dismissToast(id), 5000);
    },
    [dismissToast]
  );

  // --- data loading ---------------------------------------------------------
  const refreshJobs = useCallback(async () => {
    try {
      const data = await listJobs();
      setJobs(data.jobs);
    } catch (e) {
      addToast("error", e.message);
    }
  }, [addToast]);

  useEffect(() => {
    (async () => {
      try {
        await getHealth();
        setServerOk(true);
        refreshJobs();
      } catch (e) {
        setServerOk(false);
        addToast("error", e.message);
      }
    })();
  }, [refreshJobs, addToast]);

  const loadBlog = useCallback(
    async (job) => {
      setBlogLoading(true);
      setView("blog");
      try {
        const data = await getBlog(job.id);
        setBlog(data);
      } catch (e) {
        addToast("error", e.message);
        setView("create");
      } finally {
        setBlogLoading(false);
      }
    },
    [addToast]
  );

  // Fetch the pending research-review for a paused job. Kept separate from the
  // poll loop (like loadBlog) so its setReview isn't gated by the poll effect's
  // `alive` flag — the poll stops the moment it sees AWAITING_INPUT, which would
  // otherwise cancel an inline fetch before it could set state.
  //
  // reviewReqRef tracks which job's review the user currently wants, giving
  // "last-request-wins" semantics: if they switch jobs (or navigate away) while
  // a fetch is in flight, the stale response is dropped instead of overwriting
  // the current review. A ref (not the poll's `alive` flag) is used because it
  // survives re-renders and is tied to the user's selection, not the effect.
  const reviewReqRef = useRef(null);
  const loadReview = useCallback(
    async (job) => {
      reviewReqRef.current = job.id;
      try {
        const r = await getReview(job.id);
        if (reviewReqRef.current !== job.id) return; // superseded
        if (r.pending) setReview(r);
      } catch (e) {
        if (reviewReqRef.current === job.id) addToast("error", e.message);
      }
    },
    [addToast]
  );

  // --- polling --------------------------------------------------------------
  // Keep a ref to the latest callbacks so the interval always sees fresh state.
  const handlersRef = useRef({});
  handlersRef.current = { loadBlog, loadReview, refreshJobs, addToast };

  const pollFailuresRef = useRef(0);

  useEffect(() => {
    if (!pollId) return;
    let alive = true;
    // Fresh run: clear any stale connection-lost state from a previous poll.
    pollFailuresRef.current = 0;
    setConnectionLost(false);

    const tick = async () => {
      try {
        const job = await getJob(pollId);
        if (!alive) return;
        pollFailuresRef.current = 0;
        setActiveJob(job);

        if (job.status === "COMPLETE") {
          setPollId(null);
          handlersRef.current.addToast("success", "Your blog is ready! 🎉");
          handlersRef.current.refreshJobs();
          handlersRef.current.loadBlog(job);
        } else if (job.status === "AWAITING_INPUT") {
          // Paused at the research-review gate. Stop polling and load the
          // pending review so the user can proceed or re-research. loadReview
          // runs outside the `alive` guard so stopping the poll doesn't cancel it.
          setPollId(null);
          handlersRef.current.loadReview(job);
          handlersRef.current.refreshJobs();
        } else if (job.status === "HALTED") {
          setPollId(null);
          handlersRef.current.addToast(
            "error",
            "Generation was interrupted. You can retry it from the Recoverable tab."
          );
          handlersRef.current.refreshJobs();
        } else if (job.status === "FAILED") {
          setPollId(null);
          jobs.map((_job) => {
            if (_job.id === job.id) {
              _job.status = "FAILED";
            }
          });
          setJobs(jobs);
          handlersRef.current.addToast(
            "error",
            "Something went wrong and we couldn't generate your blog. Please try again shortly. If the problem persists, please contact support."
          );
        }
      } catch (e) {
        if (!alive) return;
        pollFailuresRef.current += 1;
        // Toast only on the first failure so we don't spam it every 3s.
        if (pollFailuresRef.current === 1) {
          handlersRef.current.addToast("error", e.message);
        }
        // Sustained failure: stop hammering and surface a clear error state.
        if (pollFailuresRef.current >= POLL_MAX_FAILURES) {
          setConnectionLost(true);
          setPollId(null);
        }
      }
    };

    tick();
    const handle = setInterval(tick, POLL_INTERVAL_MS);
    return () => {
      alive = false;
      clearInterval(handle);
    };
  }, [pollId]);

  // --- actions --------------------------------------------------------------
  const handleCreate = async (topic) => {
    setCreating(true);
    try {
      const res = await createJob(topic);
      const job = {
        id: res.job_id,
        topic,
        status: res.status,
        stage: res.stage,
        recoverable: false,
        created_at: new Date().toISOString(),
      };
      setActiveJob(job);
      setReview(null);
      reviewReqRef.current = null;
      setBlog(null);
      setView("progress");
      setTab("library");
      setPollId(res.job_id);
      refreshJobs();
    } catch (e) {
      addToast("error", e.message);
    } finally {
      setCreating(false);
    }
  };

  const handleRetry = async (job) => {
    try {
      await retryJob(job.id);
      setReview(null);
      reviewReqRef.current = null;
      setActiveJob({ ...job, status: "IN-PROGRESS", stage: "queued" });
      setBlog(null);
      setView("progress");
      setTab("library");
      setPollId(job.id);
      addToast("info", "Resuming generation…");
      refreshJobs();
    } catch (e) {
      addToast("error", e.message);
    }
  };

  const handleDecision = async (job, decision) => {
    try {
      await submitDecision(job.id, decision);
      setReview(null);
      reviewReqRef.current = null;
      setActiveJob({ ...job, status: "IN-PROGRESS", stage: "planning" });
      setBlog(null);
      setView("progress");
      setPollId(job.id);
      addToast(
        "info",
        decision === "redo" ? "Researching again…" : "Continuing with current research…"
      );
      refreshJobs();
    } catch (e) {
      addToast("error", e.message);
    }
  };

  const handleSelect = (job) => {
    setConnectionLost(false);
    setActiveJob(job);
    setReview(null);
    reviewReqRef.current = null;
    if (job.status === "COMPLETE") {
      loadBlog(job);
    } else if (job.status === "IN-PROGRESS") {
      setView("progress");
      setPollId(job.id);
    } else if (job.status === "AWAITING_INPUT") {
      // Re-open the pending research-review for a paused job.
      setView("progress");
      loadReview(job);
    } else {
      // HALTED selected from the recoverable tab
      setView("progress");
    }
  };

  const handleNew = () => {
    setView("create");
    setActiveJob(null);
    setReview(null);
    reviewReqRef.current = null;
    setBlog(null);
    setPollId(null);
    setConnectionLost(false);
  };

  // --- render ---------------------------------------------------------------
  return (
    <div className="app">
      <Sidebar
        jobs={jobs}
        tab={tab}
        setTab={setTab}
        activeJobId={activeJob?.id}
        onSelect={handleSelect}
        onRetry={handleRetry}
        onNew={handleNew}
        serverOk={serverOk}
      />

      <main className="main">
        {view === "create" && (
          <BlogForm onSubmit={handleCreate} busy={creating} />
        )}
        {view === "progress" && activeJob && (
          <ProgressView
            job={activeJob}
            review={review}
            connectionLost={connectionLost}
            onRetry={handleRetry}
            onDecision={handleDecision}
            onBack={handleNew}
          />
        )}
        {view === "blog" && (
          <BlogView blog={blog} job={activeJob} loading={blogLoading} />
        )}
      </main>

      <Toasts toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
