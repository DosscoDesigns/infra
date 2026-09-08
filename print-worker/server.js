import http from "http"
import { createHash, timingSafeEqual } from "crypto"
import { spawn } from "child_process"

const PRINTERS = {
  "4x2": { host: "10.0.0.32", port: 9100 },
  "4x6": { host: "10.0.0.31", port: 9100 }
}

// ── Retry budget ───────────────────────────────────────────────────────────
// These three constants ARE the retry budget, and /health publishes the total
// derived from them. Callers (slime's src/lib/print.ts) must set their client
// timeout ABOVE it: aborting the HTTP request does not abort our `nc` child,
// so a caller that gives up first reports failure while a label is still on
// its way to the roll — and a retry then prints two.
//
// So: change these and the published number changes with them. Do NOT hardcode
// the total anywhere, here or downstream.
const ATTEMPTS = 3
const PER_ATTEMPT_TIMEOUT_MS = 8000
const RETRY_DELAY_MS = 600
const RETRY_BUDGET_MS = ATTEMPTS * PER_ATTEMPT_TIMEOUT_MS + (ATTEMPTS - 1) * RETRY_DELAY_MS

const PORT = Number(process.env.PRINT_WORKER_PORT || 1530)
const HOST = "127.0.0.1"          // loopback only; the tunnel is the front door
const TOKEN = process.env.PRINT_WORKER_TOKEN || ""

// Rate limit: printing burns physical stock, so the cap is deliberately low.
const RATE_LIMIT_MAX = Number(process.env.PRINT_WORKER_RATE_MAX || 30)
const RATE_LIMIT_WINDOW_MS = 60_000
let windowStart = Date.now()
let windowCount = 0

function rateLimited() {
  const now = Date.now()
  if (now - windowStart >= RATE_LIMIT_WINDOW_MS) { windowStart = now; windowCount = 0 }
  windowCount += 1
  return windowCount > RATE_LIMIT_MAX
}

// Compare digests, not the raw values: timingSafeEqual throws on a length
// mismatch, and that throw would itself leak the secret's length.
function tokenOk(presented) {
  if (!TOKEN || typeof presented !== "string" || presented.length === 0) return false
  const a = createHash("sha256").update(presented).digest()
  const b = createHash("sha256").update(TOKEN).digest()
  return timingSafeEqual(a, b)
}

// One send attempt to the printer via /usr/bin/nc.
//
// IMPORTANT: we shell out to nc instead of using Node's net.Socket. On modern
// macOS the Homebrew `node` binary is denied "Local Network" privacy access, so
// its direct LAN connects fail with EHOSTUNREACH — while Apple's nc/curl are
// allowed. Sending through nc (spawned per job) is the reliable path. This is
// why prints broke while `nc host 9100` still worked by hand.
function sendOnce(host, port, zpl) {
  return new Promise((resolve, reject) => {
    const nc = spawn("/usr/bin/nc", ["-w", "6", host, String(port)])
    let stderr = ""
    const timeout = setTimeout(() => { nc.kill("SIGKILL"); reject(new Error("Timeout")) }, PER_ATTEMPT_TIMEOUT_MS)
    nc.stderr.on("data", (d) => { stderr += d })
    nc.on("error", (err) => { clearTimeout(timeout); reject(err) })
    nc.on("close", (code) => {
      clearTimeout(timeout)
      if (code === 0) resolve()
      else reject(new Error(`nc exit ${code}${stderr ? ": " + stderr.trim() : " (host unreachable?)"}`))
    })
    nc.stdin.on("error", () => {})   // ignore EPIPE if nc dies early
    nc.stdin.write(zpl)
    nc.stdin.end()
  })
}

// Zebra printers with WiFi power-save nap and refuse the first connect
// (EHOSTUNREACH/ECONNREFUSED/timeout); the connection attempt itself wakes them.
// Retry a few times with a short delay so a sleeping printer still prints.
async function sendZPL(host, port, zpl, attempts = ATTEMPTS, delayMs = RETRY_DELAY_MS) {
  let lastErr
  for (let n = 1; n <= attempts; n++) {
    try {
      await sendOnce(host, port, zpl)
      if (n > 1) console.log(`[print] succeeded on attempt ${n} to ${host}:${port}`)
      return
    } catch (err) {
      lastErr = err
      console.warn(`[print] attempt ${n}/${attempts} to ${host}:${port} failed: ${err.message}`)
      if (n < attempts) await new Promise(r => setTimeout(r, delayMs))
    }
  }
  throw lastErr
}

function json(res, status, body) {
  res.writeHead(status, { "Content-Type": "application/json" })
  res.end(JSON.stringify(body))
}

const server = http.createServer(async (req, res) => {
  // No CORS headers, deliberately. This is a server-to-server endpoint: a
  // browser calling it would have to carry PRINT_WORKER_TOKEN, which is the
  // same mistake that put a Supabase service_role key in admin.dosscodesigns.com's
  // client bundle. Callers go through their own backend.

  if (req.method === "GET" && req.url === "/health") {
    // Open and unauthenticated by contract — cloudflared probes it, and it
    // discloses nothing but our own retry budget.
    if (!TOKEN) {
      return json(res, 503, {
        status: "degraded",
        reason: "PRINT_WORKER_TOKEN is not set; printing is disabled",
        retryBudgetMs: RETRY_BUDGET_MS
      })
    }
    return json(res, 200, { status: "ok", retryBudgetMs: RETRY_BUDGET_MS })
  }

  if (req.method === "POST" && req.url === "/print/zpl") {
    // Fail closed. A missing secret must never silently restore the open
    // endpoint this change exists to close.
    if (!TOKEN) {
      console.error("[print] refused: PRINT_WORKER_TOKEN is not set")
      return json(res, 503, { error: "print worker is not configured (PRINT_WORKER_TOKEN unset)" })
    }
    if (!tokenOk(req.headers["x-print-token"])) {
      console.warn("[print] refused: bad or missing X-Print-Token")
      return json(res, 401, { error: "invalid or missing X-Print-Token" })
    }
    if (rateLimited()) {
      console.warn("[print] refused: rate limit")
      return json(res, 429, { error: `rate limit: max ${RATE_LIMIT_MAX} prints per minute` })
    }

    let body = ""
    for await (const chunk of req) body += chunk
    try {
      const { zpl, printer } = JSON.parse(body)
      if (!zpl) return json(res, 400, { error: "zpl required" })
      const target = PRINTERS[printer] || PRINTERS["4x2"]
      await sendZPL(target.host, target.port, zpl)
      console.log(`[print] ZPL sent to ${target.host}:${target.port} (${zpl.length} bytes)`)
      return json(res, 200, { success: true, message: `Label sent to ${target.host}:${target.port}` })
    } catch (err) {
      console.error("[print] Failed:", err.message)
      return json(res, 500, { error: err.message })
    }
  }

  res.writeHead(404); res.end("Not found")
})

server.listen(PORT, HOST, () => {
  console.log(`Print worker listening on ${HOST}:${PORT} (retry budget ${RETRY_BUDGET_MS}ms)`)
  if (!TOKEN) console.error("[print] WARNING: PRINT_WORKER_TOKEN is not set — printing is DISABLED until it is")
})
