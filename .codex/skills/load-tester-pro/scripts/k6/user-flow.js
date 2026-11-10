import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = (__ENV.TARGET_BASE_URL || "").replace(/\/$/, "");
const AUTHORIZED = __ENV.LOAD_TEST_AUTHORIZED === "YES";
const VUS = Number.parseInt(__ENV.VUS || "1", 10);
const DURATION = __ENV.DURATION || "30s";
const THINK_SECONDS = Number.parseInt(__ENV.THINK_SECONDS || "1", 10);
const rawPaths = __ENV.FLOW_PATHS || "/,/health";

function secondsFromDuration(value) {
  const match = /^(\d+)(s|m)$/.exec(value);
  if (!match) return NaN;
  return Number(match[1]) * (match[2] === "m" ? 60 : 1);
}

function validateTarget(value) {
  const match = /^(https?):\/\/([^/?#\s]+)(?:\/[^?#\s]*)?$/.exec(value);
  if (!match || match[2].includes("@")) return false;
  return true;
}

if (!AUTHORIZED) throw new Error("Refusing to send traffic: set LOAD_TEST_AUTHORIZED=YES only after the owner has approved this exact target and test scope.");
if (!validateTarget(BASE_URL)) throw new Error("Set TARGET_BASE_URL to an http(s) origin/path without embedded credentials.");
if (!Number.isInteger(VUS) || VUS < 1 || VUS > 10) throw new Error("VUS must be an integer from 1 to 10.");
if (secondsFromDuration(DURATION) < 1 || secondsFromDuration(DURATION) > 120) throw new Error("DURATION must be 1s–120s (for example 30s or 2m).");
if (!Number.isInteger(THINK_SECONDS) || THINK_SECONDS < 1 || THINK_SECONDS > 10) throw new Error("THINK_SECONDS must be an integer from 1 to 10.");

const FLOW_PATHS = rawPaths.split(",").map((path) => path.trim()).filter(Boolean);
if (FLOW_PATHS.length === 0 || FLOW_PATHS.some((path) => !path.startsWith("/") || path.startsWith("//") || /\s/.test(path))) {
  throw new Error("FLOW_PATHS must be comma-separated relative paths beginning with /; GET requests only.");
}

export const options = {
  vus: VUS,
  duration: DURATION,
  thresholds: {
    http_req_failed: [{ threshold: "rate<0.01", abortOnFail: true, delayAbortEval: "5s" }],
    http_req_duration: ["p(95)<2000"],
  },
};

export default function () {
  for (const path of FLOW_PATHS) {
    const response = http.get(`${BASE_URL}${path}`, {
      headers: { Accept: "*/*" },
      tags: { flow_step: path, method: "GET" },
      timeout: "10s",
    });
    check(response, {
      [`${path} responds with 2xx/3xx`]: (res) => res.status >= 200 && res.status < 400,
    });
    // Pace each step to avoid an unbounded request loop.
    sleep(THINK_SECONDS);
  }
}
