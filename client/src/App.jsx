import { useCallback, useEffect, useRef, useState } from "react";

import {
  createJob,
  getBlog,
  getHealth,
  getJob,
  listJobs,
  retryJob,
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

  // --- polling --------------------------------------------------------------
  // Keep a ref to the latest callbacks so the interval always sees fresh state.
  const handlersRef = useRef({});
  handlersRef.current = { loadBlog, refreshJobs, addToast };

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

  const handleSelect = (job) => {
    setConnectionLost(false);
    setActiveJob(job);
    if (job.status === "COMPLETE") {
      loadBlog(job);
    } else if (job.status === "IN-PROGRESS") {
      setView("progress");
      setPollId(job.id);
    } else {
      // HALTED selected from the recoverable tab
      setView("progress");
    }
  };

  const handleNew = () => {
    setView("create");
    setActiveJob(null);
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
            connectionLost={connectionLost}
            onRetry={handleRetry}
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
