const state = {
  vehicles: [],
  filtered: [],
  selectedIds: new Set(),
  messages: []
};

const els = {
  vehicleCount: document.querySelector("#vehicleCount"),
  vehicleGrid: document.querySelector("#vehicleGrid"),
  searchInput: document.querySelector("#searchInput"),
  budgetRange: document.querySelector("#budgetRange"),
  budgetOutput: document.querySelector("#budgetOutput"),
  bodyFilter: document.querySelector("#bodyFilter"),
  fuelFilter: document.querySelector("#fuelFilter"),
  seatFilter: document.querySelector("#seatFilter"),
  resetFilters: document.querySelector("#resetFilters"),
  compareBody: document.querySelector("#compareTable tbody"),
  qBudget: document.querySelector("#qBudget"),
  qUse: document.querySelector("#qUse"),
  qFuel: document.querySelector("#qFuel"),
  qPriority: document.querySelector("#qPriority"),
  recommendButton: document.querySelector("#recommendButton"),
  chatLog: document.querySelector("#chatLog"),
  chatForm: document.querySelector("#chatForm"),
  chatInput: document.querySelector("#chatInput"),
  aiStatus: document.querySelector("#aiStatus")
};

const currency = new Intl.NumberFormat("en-IN", {
  maximumFractionDigits: 2
});

function priceLabel(vehicle) {
  return `₹${currency.format(vehicle.priceLakh[0])}-${currency.format(vehicle.priceLakh[1])}L`;
}

function getQuestionnaire() {
  return {
    budgetLakh: Number(els.qBudget.value),
    mainUse: els.qUse.value,
    fuel: els.qFuel.value,
    priority: els.qPriority.value
  };
}

function scoreVehicle(vehicle, answers) {
  let score = 0;
  const words = `${vehicle.bestFor.join(" ")} ${vehicle.features.join(" ")} ${vehicle.pros.join(" ")}`.toLowerCase();

  if (vehicle.priceLakh[0] <= answers.budgetLakh) score += 2;
  if (vehicle.priceLakh[1] <= answers.budgetLakh) score += 2;
  if (answers.fuel === "Any" || vehicle.fuel.includes(answers.fuel)) score += 2;
  if (words.includes(answers.mainUse.toLowerCase().split(" ")[0])) score += 1;
  if (words.includes(answers.priority.toLowerCase().split(" ")[0])) score += 2;
  if (answers.mainUse.includes("Seven") && vehicle.seats >= 7) score += 4;
  if (answers.mainUse.includes("Electric") && vehicle.fuel.includes("Electric")) score += 4;
  if (answers.priority === "Safety" && vehicle.safety.toLowerCase().includes("5-star")) score += 3;
  if (answers.priority === "Low running cost" && vehicle.fuel.some((fuel) => ["CNG", "Hybrid", "Electric"].includes(fuel))) score += 3;
  if (answers.priority === "Performance" && /turbo|powerful|performance/i.test(vehicle.features.join(" "))) score += 2;

  return score;
}

function populateFilters() {
  const bodies = [...new Set(state.vehicles.map((vehicle) => vehicle.body))].sort();
  const fuels = [...new Set(state.vehicles.flatMap((vehicle) => vehicle.fuel))].sort();

  for (const body of bodies) {
    els.bodyFilter.append(new Option(body, body));
  }

  for (const fuel of fuels) {
    els.fuelFilter.append(new Option(fuel, fuel));
  }
}

function applyFilters() {
  const query = els.searchInput.value.trim().toLowerCase();
  const budget = Number(els.budgetRange.value);
  const body = els.bodyFilter.value;
  const fuel = els.fuelFilter.value;
  const seats = els.seatFilter.value;

  els.budgetOutput.value = `₹${budget} lakh`;

  state.filtered = state.vehicles.filter((vehicle) => {
    const haystack = [
      vehicle.brand,
      vehicle.model,
      vehicle.body,
      vehicle.fuel.join(" "),
      vehicle.transmission.join(" "),
      vehicle.bestFor.join(" "),
      vehicle.features.join(" ")
    ]
      .join(" ")
      .toLowerCase();

    return (
      (!query || haystack.includes(query)) &&
      vehicle.priceLakh[0] <= budget &&
      (body === "all" || vehicle.body === body) &&
      (fuel === "all" || vehicle.fuel.includes(fuel)) &&
      (seats === "all" || vehicle.seats >= Number(seats))
    );
  });

  renderVehicles();
}

function renderVehicles() {
  if (!state.filtered.length) {
    els.vehicleGrid.innerHTML = `<p class="empty">No vehicles match these filters. Try widening the budget or fuel choice.</p>`;
    return;
  }

  els.vehicleGrid.innerHTML = state.filtered
    .map((vehicle) => {
      const selected = state.selectedIds.has(vehicle.id);
      return `
        <article class="vehicle-card ${selected ? "selected" : ""}">
          <div class="vehicle-art" aria-hidden="true"><span></span></div>
          <div class="vehicle-content">
            <div class="vehicle-title">
              <h3>${vehicle.brand} ${vehicle.model}</h3>
              <span class="price">${priceLabel(vehicle)}</span>
            </div>
            <div class="chips">
              <span class="chip">${vehicle.body}</span>
              <span class="chip">${vehicle.seats} seats</span>
              ${vehicle.fuel.slice(0, 3).map((fuel) => `<span class="chip">${fuel}</span>`).join("")}
            </div>
            <p><strong>Best for:</strong> ${vehicle.bestFor.join(", ")}</p>
            <p><strong>Safety:</strong> ${vehicle.safety}</p>
            <div class="card-actions">
              <button class="button ghost" type="button" data-action="compare" data-id="${vehicle.id}">
                ${selected ? "Remove" : "Compare"}
              </button>
              <button class="button primary" type="button" data-action="ask" data-id="${vehicle.id}">
                Ask AI
              </button>
            </div>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderCompare() {
  const selected = state.vehicles.filter((vehicle) => state.selectedIds.has(vehicle.id));

  if (!selected.length) {
    els.compareBody.innerHTML = `
      <tr>
        <td colspan="6">Select up to three vehicles from the catalog to compare them here.</td>
      </tr>
    `;
    return;
  }

  els.compareBody.innerHTML = selected
    .map(
      (vehicle) => `
        <tr>
          <td><strong>${vehicle.brand} ${vehicle.model}</strong><br>${vehicle.body}</td>
          <td>${priceLabel(vehicle)}</td>
          <td>${vehicle.fuel.join(", ")}</td>
          <td>${vehicle.seats}</td>
          <td>${vehicle.bestFor.join(", ")}</td>
          <td>${vehicle.cons.join(", ")}</td>
        </tr>
      `
    )
    .join("");
}

function toggleCompare(id) {
  if (state.selectedIds.has(id)) {
    state.selectedIds.delete(id);
  } else {
    if (state.selectedIds.size >= 3) {
      addMessage("assistant", "You can compare up to three vehicles at once. Remove one from the shortlist first.");
      return;
    }
    state.selectedIds.add(id);
  }

  renderVehicles();
  renderCompare();
}

function addMessage(role, content) {
  state.messages.push({ role, content });
  const node = document.createElement("div");
  node.className = `message ${role}`;
  node.textContent = content;
  els.chatLog.append(node);
  els.chatLog.scrollTop = els.chatLog.scrollHeight;
}

function localRecommendationText() {
  const answers = getQuestionnaire();
  const ranked = [...state.vehicles]
    .map((vehicle) => ({ vehicle, score: scoreVehicle(vehicle, answers) }))
    .sort((a, b) => b.score - a.score)
    .slice(0, 4);

  return `Based on your answers, I would shortlist:

${ranked
  .map(
    ({ vehicle }, index) =>
      `${index + 1}. ${vehicle.brand} ${vehicle.model} (${priceLabel(vehicle)}) - ${vehicle.bestFor.join(", ")}. Main watch-out: ${vehicle.cons[0]}.`
  )
  .join("\n")}

My practical pick is ${ranked[0].vehicle.brand} ${ranked[0].vehicle.model}. It fits the stated budget/use case best, but confirm the exact variant, on-road price, waiting period, and test-drive comfort before booking.`;
}

async function askAssistant(prompt) {
  addMessage("user", prompt);
  const thinking = document.createElement("div");
  thinking.className = "message assistant";
  thinking.textContent = "Thinking through the catalog...";
  els.chatLog.append(thinking);
  els.chatLog.scrollTop = els.chatLog.scrollHeight;

  try {
    const selected = state.vehicles.filter((vehicle) => state.selectedIds.has(vehicle.id));
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: prompt,
        messages: state.messages.slice(-8),
        questionnaire: getQuestionnaire(),
        selected
      })
    });

    if (!response.ok) throw new Error(`Request failed with ${response.status}`);
    const data = await response.json();
    thinking.remove();
    els.aiStatus.textContent = data.mode === "openai" ? "OpenAI mode" : "Local mode";
    addMessage("assistant", data.reply);
  } catch (error) {
    thinking.remove();
    addMessage("assistant", `${localRecommendationText()}\n\nThe AI server was not reachable, so I used the local recommender.`);
  }
}

function handleCatalogClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const vehicle = state.vehicles.find((item) => item.id === button.dataset.id);
  if (!vehicle) return;

  if (button.dataset.action === "compare") {
    toggleCompare(vehicle.id);
    return;
  }

  askAssistant(`Tell me whether the ${vehicle.brand} ${vehicle.model} is a good fit for my questionnaire answers. Include what I should compare it against.`);
}

function resetFilters() {
  els.searchInput.value = "";
  els.budgetRange.value = "25";
  els.bodyFilter.value = "all";
  els.fuelFilter.value = "all";
  els.seatFilter.value = "all";
  applyFilters();
}

async function init() {
  const response = await fetch("/data/vehicles.json");
  state.vehicles = await response.json();
  state.filtered = state.vehicles;
  els.vehicleCount.textContent = state.vehicles.length;
  populateFilters();
  applyFilters();
  renderCompare();
  addMessage(
    "assistant",
    "Tell me your budget, usage, fuel preference, and biggest priority. I can recommend vehicles, compare shortlisted models, and explain ownership trade-offs."
  );

  for (const input of [els.searchInput, els.budgetRange, els.bodyFilter, els.fuelFilter, els.seatFilter]) {
    input.addEventListener("input", applyFilters);
  }

  els.resetFilters.addEventListener("click", resetFilters);
  els.vehicleGrid.addEventListener("click", handleCatalogClick);
  els.recommendButton.addEventListener("click", () => askAssistant(localRecommendationText()));
  els.chatForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const prompt = els.chatInput.value.trim();
    if (!prompt) return;
    els.chatInput.value = "";
    askAssistant(prompt);
  });
}

init();
