import http from "http"
import net from "net"

const PRINTERS = {
  "4x2": { host: "10.0.0.32", port: 9100 },
  "4x6": { host: "10.0.0.31", port: 9100 }
}

function sendZPL(host, port, zpl) {
  return new Promise((resolve, reject) => {
    const client = new net.Socket()
    const timeout = setTimeout(() => { client.destroy(); reject(new Error("Timeout")) }, 5000)
    client.connect(port, host, () => {
      client.write(zpl, () => { clearTimeout(timeout); client.end(); resolve() })
    })
    client.on("error", (err) => { clearTimeout(timeout); reject(err) })
  })
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
      res.end(JSON.stringify({ success: true, message: "Label sent to ${target.host}:${target.port}" }))
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
