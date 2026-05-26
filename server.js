const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");

const root = __dirname;
const vehicles = JSON.parse(fs.readFileSync(path.join(root, "data", "vehicles.json"), "utf8"));
const port = Number(process.env.PORT || 4173);
const model = process.env.OPENAI_MODEL || "gpt-5.5";

const mimeTypes = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".svg": "image/svg+xml"
};

function sendJson(res, status, payload) {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(payload));
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
      if (body.length > 1_000_000) {
        reject(new Error("Request body too large"));
        req.destroy();
      }
    });
    req.on("end", () => resolve(body));
    req.on("error", reject);
  });
}

function formatVehicle(vehicle) {
  return `${vehicle.brand} ${vehicle.model}: ${vehicle.body}, ${vehicle.seats} seats, ₹${vehicle.priceLakh[0]}-${vehicle.priceLakh[1]} lakh, fuel ${vehicle.fuel.join("/")}, transmissions ${vehicle.transmission.join("/")}, mileage/range ${vehicle.mileage}, safety ${vehicle.safety}, best for ${vehicle.bestFor.join(", ")}, features ${vehicle.features.join(", ")}, pros ${vehicle.pros.join(", ")}, cons ${vehicle.cons.join(", ")}.`;
}

function scoreVehicle(vehicle, questionnaire) {
  const answers = questionnaire || {};
  const budget = Number(answers.budgetLakh || 25);
  const fuel = answers.fuel || "Any";
  const mainUse = String(answers.mainUse || "").toLowerCase();
  const priority = String(answers.priority || "").toLowerCase();
  const text = `${vehicle.bestFor.join(" ")} ${vehicle.features.join(" ")} ${vehicle.pros.join(" ")} ${vehicle.safety}`.toLowerCase();
  let score = 0;

  if (vehicle.priceLakh[0] <= budget) score += 2;
  if (vehicle.priceLakh[1] <= budget) score += 2;
  if (fuel === "Any" || vehicle.fuel.includes(fuel)) score += 2;
  if (mainUse.includes("seven") && vehicle.seats >= 7) score += 4;
  if (mainUse.includes("electric") && vehicle.fuel.includes("Electric")) score += 4;
  if (mainUse.includes("low running") && vehicle.fuel.some((item) => ["CNG", "Hybrid", "Electric"].includes(item))) score += 3;
  if (priority.includes("safety") && text.includes("5-star")) score += 3;
  if (priority.includes("space") && vehicle.seats >= 7) score += 2;
  if (priority.includes("features") && /adas|sunroof|ventilated|screen|camera/i.test(vehicle.features.join(" "))) score += 2;
  if (priority.includes("resale") && /maruti|toyota|hyundai/i.test(vehicle.brand)) score += 2;
  if (priority.includes("performance") && /turbo|powerful|performance/i.test(vehicle.features.join(" "))) score += 2;

  return score;
}

function inferNeeds(message, questionnaire) {
  const text = String(message || "").toLowerCase();
  const needs = {
    budget: Number(questionnaire?.budgetLakh || 25),
    dailyKm: 0,
    wantsEv: /\bev\b|electric|charging|battery/.test(text),
    wantsHybrid: /hybrid/.test(text),
    wantsCng: /\bcng\b/.test(text),
    wantsPetrol: /petrol/.test(text),
    wantsDiesel: /diesel/.test(text),
    city: /city|urban|traffic|commute|bengaluru|bangalore|mumbai|delhi|pune|chennai|hyderabad/.test(text),
    highway: /highway|long drive|road trip|touring/.test(text),
    family: /family|kids|parents|rear seat|space/.test(text),
    sevenSeats: /7 seat|seven seat|third row|large family/.test(text),
    safety: /safe|safety|airbag|ncap|bharat ncap/.test(text),
    lowCost: /running cost|mileage|efficient|fuel bill|economy|daily/.test(text)
  };
  const kmMatch = text.match(/(\d{2,3})\s*(km|kilomet)/);
  if (kmMatch) needs.dailyKm = Number(kmMatch[1]);
  return needs;
}

function scoreVehicleForMessage(vehicle, needs, questionnaire) {
  let score = scoreVehicle(vehicle, questionnaire);
  const fuels = vehicle.fuel;
  const text = `${vehicle.bestFor.join(" ")} ${vehicle.features.join(" ")} ${vehicle.pros.join(" ")} ${vehicle.safety}`.toLowerCase();

  if (needs.dailyKm >= 50) {
    if (fuels.includes("Electric")) score += 5;
    if (fuels.includes("Hybrid")) score += 4;
    if (fuels.includes("CNG")) score += 3;
    if (fuels.includes("Diesel") && needs.highway) score += 2;
  }
  if (needs.wantsEv && fuels.includes("Electric")) score += 4;
  if (needs.wantsHybrid && fuels.includes("Hybrid")) score += 4;
  if (needs.wantsCng && fuels.includes("CNG")) score += 4;
  if (needs.wantsPetrol && fuels.includes("Petrol")) score += 2;
  if (needs.wantsDiesel && fuels.includes("Diesel")) score += 2;
  if (needs.family && vehicle.seats >= 5) score += 1;
  if (needs.sevenSeats && vehicle.seats >= 7) score += 5;
  if (needs.safety && text.includes("5-star")) score += 3;
  if (needs.city && /compact|city|urban|easy|parking/i.test(text)) score += 2;
  if (vehicle.priceLakh[0] <= needs.budget) score += 1;
  if (vehicle.priceLakh[1] <= needs.budget) score += 2;

  return score;
}

function fuelAdvice(needs) {
  if (needs.dailyKm >= 50) {
    return "For a daily 50 km+ commute, EV makes the most financial sense if you can charge at home or office. If charging is uncertain, strong hybrid is the easiest no-compromise choice; CNG is the budget alternative if boot loss and filling queues are acceptable.";
  }
  if (needs.city) {
    return "For mostly city use, petrol is simplest, CNG lowers fuel bills, hybrid gives excellent efficiency without charging, and EV works best with dependable home charging.";
  }
  if (needs.highway) {
    return "For frequent highways, diesel still makes sense in larger SUVs, while hybrid is smoother and cleaner for mixed use. EV needs route charging confidence.";
  }
  return "The right fuel depends on daily distance, charging access, city restrictions, and how long you plan to keep the vehicle.";
}

function localAssistant(payload) {
  const question = String(payload.message || "").toLowerCase();
  const needs = inferNeeds(payload.message, payload.questionnaire);
  const shortlist = vehicles
    .map((vehicle) => ({ vehicle, score: scoreVehicleForMessage(vehicle, needs, payload.questionnaire) }))
    .sort((a, b) => b.score - a.score)
    .slice(0, 5)
    .map(({ vehicle }) => vehicle);

  if (question.includes("compare") && payload.selected?.length) {
    return `Here is the useful comparison:

${payload.selected
  .map(
    (vehicle) =>
      `${vehicle.brand} ${vehicle.model}: ${vehicle.body}, ${vehicle.seats} seats, ${vehicle.fuel.join("/")}, ${vehicle.mileage}. Strength: ${vehicle.pros[0]}. Watch-out: ${vehicle.cons[0]}.`
  )
  .join("\n")}

My bias: choose the one whose weakest point you can actually live with every day. On-road price, dealer support near you, and a test drive should break the tie.`;
  }

  return `My shortlist from the current catalog:

${shortlist
  .map(
    (vehicle, index) =>
      `${index + 1}. ${vehicle.brand} ${vehicle.model} - ₹${vehicle.priceLakh[0]}-${vehicle.priceLakh[1]} lakh, ${vehicle.fuel.join("/")}. Best for ${vehicle.bestFor.join(", ")}. Watch-out: ${vehicle.cons[0]}.`
  )
  .join("\n")}

${fuelAdvice(needs)}

Best first test drive: ${shortlist[0].brand} ${shortlist[0].model}. Also test drive ${shortlist[1].brand} ${shortlist[1].model} if you want a clear contrast.`;
}

function extractOutputText(data) {
  if (typeof data.output_text === "string") return data.output_text;
  const chunks = [];

  for (const item of data.output || []) {
    for (const content of item.content || []) {
      if (content.type === "output_text" && content.text) chunks.push(content.text);
      if (content.type === "text" && content.text) chunks.push(content.text);
    }
  }

  return chunks.join("\n").trim();
}

async function openaiAssistant(payload) {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) return { mode: "local", reply: localAssistant(payload) };

  const selectedText = payload.selected?.length
    ? payload.selected.map(formatVehicle).join("\n")
    : "No vehicles currently selected by the user.";

  const catalog = vehicles.map(formatVehicle).join("\n");
  const messages = Array.isArray(payload.messages)
    ? payload.messages.slice(-8).map((message) => `${message.role}: ${message.content}`).join("\n")
    : "";

  const instructions = `You are AutoSense India's vehicle buying assistant.
Use careful reasoning, but do not expose hidden chain-of-thought. Give concise, decision-oriented answers.
Ground recommendations in the provided Indian market catalog. If information is missing or city-specific, say what must be verified with a dealer.
When recommending, include: best pick, 2 alternatives, why, watch-outs, and what to test-drive.
Do not invent exact on-road prices, discounts, waiting periods, or current dealer offers.
Catalog:
${catalog}`;

  const input = `Questionnaire: ${JSON.stringify(payload.questionnaire || {})}
Selected vehicles: ${selectedText}
Recent chat:
${messages}
User question: ${payload.message}`;

  const response = await fetch("https://api.openai.com/v1/responses", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      model,
      instructions,
      input,
      max_output_tokens: 1200
    })
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`OpenAI request failed: ${response.status} ${errorText}`);
  }

  const data = await response.json();
  return { mode: "openai", reply: extractOutputText(data) || localAssistant(payload) };
}

async function handleChat(req, res) {
  let payload = {};
  try {
    const body = await readBody(req);
    payload = JSON.parse(body || "{}");
    const result = await openaiAssistant(payload);
    sendJson(res, 200, result);
  } catch (error) {
    sendJson(res, 200, {
      mode: "local",
      reply: `${localAssistant(payload || {})}\n\nServer note: ${error.message}`
    });
  }
}

function serveStatic(req, res) {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const pathname = decodeURIComponent(url.pathname === "/" ? "/index.html" : url.pathname);
  const filePath = path.normalize(path.join(root, pathname));

  if (!filePath.startsWith(root)) {
    res.writeHead(403);
    res.end("Forbidden");
    return;
  }

  fs.readFile(filePath, (error, content) => {
    if (error) {
      res.writeHead(404);
      res.end("Not found");
      return;
    }

    const ext = path.extname(filePath);
    res.writeHead(200, { "Content-Type": mimeTypes[ext] || "application/octet-stream" });
    res.end(content);
  });
}

const server = http.createServer((req, res) => {
  if (req.method === "POST" && req.url === "/api/chat") {
    handleChat(req, res);
    return;
  }

  if (req.method === "GET" || req.method === "HEAD") {
    serveStatic(req, res);
    return;
  }

  res.writeHead(405);
  res.end("Method not allowed");
});

server.listen(port, () => {
  console.log(`AutoSense India running at http://localhost:${port}`);
  console.log(process.env.OPENAI_API_KEY ? `AI mode: OpenAI Responses API (${model})` : "AI mode: local fallback. Set OPENAI_API_KEY for stronger answers.");
});
