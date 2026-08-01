import http from "http"
import { spawn } from "child_process"

const PRINTERS = {
  "4x2": { host: "10.0.0.32", port: 9100 },
  "4x6": { host: "10.0.0.31", port: 9100 }
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
    const timeout = setTimeout(() => { nc.kill("SIGKILL"); reject(new Error("Timeout")) }, 8000)
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
async function sendZPL(host, port, zpl, attempts = 3, delayMs = 600) {
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

const server = http.createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*")
  res.setHeader("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
  res.setHeader("Access-Control-Allow-Headers", "Content-Type")

  if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return }
  if (req.method === "GET" && req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" })
    res.end(JSON.stringify({ status: "ok" }))
    return
  }
  if (req.method === "POST" && req.url === "/print/zpl") {
    let body = ""
    for await (const chunk of req) body += chunk
    try {
      const { zpl, printer } = JSON.parse(body)
      if (!zpl) { res.writeHead(400); res.end(JSON.stringify({ error: "zpl required" })); return }
      const target = PRINTERS[printer] || PRINTERS["4x2"]
      await sendZPL(target.host, target.port, zpl)
      console.log(`[print] ZPL sent to ${target.host}:${target.port} (${zpl.length} bytes)`)
      res.writeHead(200, { "Content-Type": "application/json" })
      res.end(JSON.stringify({ success: true, message: `Label sent to ${target.host}:${target.port}` }))
    } catch (err) {
      console.error("[print] Failed:", err.message)
      res.writeHead(500, { "Content-Type": "application/json" })
      res.end(JSON.stringify({ error: err.message }))
    }
    return
  }
  res.writeHead(404); res.end("Not found")
})

server.listen(3001, () => console.log("Print worker listening on :3001"))
