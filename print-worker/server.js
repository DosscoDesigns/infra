import http from "http"
import net from "net"

const PRINTERS = {
  "4x2": { host: "10.0.0.32", port: 9100 },
  "4x6": { host: "10.0.0.31", port: 9100 }
}

// One TCP attempt to the printer.
function sendOnce(host, port, zpl) {
  return new Promise((resolve, reject) => {
    const client = new net.Socket()
    const timeout = setTimeout(() => { client.destroy(); reject(new Error("Timeout")) }, 2500)
    let settled = false
    const done = (fn, arg) => { if (settled) return; settled = true; clearTimeout(timeout); fn(arg) }
    client.connect(port, host, () => {
      client.write(zpl, () => { client.end(); done(resolve) })
    })
    client.on("error", (err) => { client.destroy(); done(reject, err) })
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
