const API_BASE = "";
let allProducts = [];
let selectedTempPref = "";

// SPA Tab Switching Logic
function switchTab(tabId) {
    const tabs = ["assistant", "menu", "preferences", "orders", "faq"];
    tabs.forEach(t => {
        const page = document.getElementById(`page-${t}`);
        const nav = document.getElementById(`nav-${t}`);
        if (page) {
            if (t === tabId) {
                page.classList.remove("hidden");
                page.classList.add("flex");
            } else {
                page.classList.add("hidden");
                page.classList.remove("flex");
            }
        }
        if (nav) {
            if (t === tabId) {
                nav.classList.add("bg-surface-container-high", "border-r-2", "border-secondary", "text-secondary", "font-bold");
                nav.classList.remove("text-on-surface-variant");
            } else {
                nav.classList.remove("bg-surface-container-high", "border-r-2", "border-secondary", "text-secondary", "font-bold");
                nav.classList.add("text-on-surface-variant");
            }
        }
    });

    if (tabId === "menu" && allProducts.length === 0) {
        fetchMenu();
    }
}

async function fetchChatHistory() {
    try {
        const res = await fetch(`${API_BASE}/api/chat/history`);
        const history = await res.json();
        if (history && history.length > 0) {
            const container = document.getElementById("messages");
            container.innerHTML = "";
            history.forEach(item => {
                appendMessage(item.role, item.message);
            });
        }
    } catch (e) { console.error("Error fetching chat history", e); }
}

async function fetchCart() {
    try {
        const res = await fetch(`${API_BASE}/api/order`);
        const data = await res.json();
        renderCart(data);
    } catch (e) { console.error("Error fetching cart", e); }
}

function renderCart(cart) {
    const container = document.getElementById("cart-items");
    const statusContainer = document.getElementById("order-status-items");

    if (!cart.items || cart.items.length === 0) {
        if (container) container.innerHTML = `<p class="text-xs text-on-surface-variant">Your cart is empty.</p>`;
        if (statusContainer) statusContainer.innerHTML = `<p class="text-xs text-on-surface-variant">No active items. Place an order from the Assistant or Menu!</p>`;
    } else {
        const itemsHtml = cart.items.map(item => `
            <div class="flex items-center gap-3 p-3 bg-surface-container rounded-lg border border-outline-variant/30">
                <div class="flex-1">
                    <h4 class="font-bold text-sm text-on-surface">${item.product_name}</h4>
                    <p class="text-xs text-on-surface-variant">₹${item.unit_price} x ${item.quantity}</p>
                </div>
                <div class="text-right">
                    <span class="font-bold text-primary text-sm">₹${(item.unit_price * item.quantity).toFixed(0)}</span>
                    <button class="block ml-auto text-error text-xs mt-1" onclick="removeItem('${item.product_name}')">
                        <span class="material-symbols-outlined text-[16px]">delete</span>
                    </button>
                </div>
            </div>
        `).join("");

        if (container) container.innerHTML = itemsHtml;
        if (statusContainer) statusContainer.innerHTML = itemsHtml;
    }

    const subtotalStr = `₹${cart.subtotal.toFixed(2)}`;
    const taxStr = `₹${cart.tax.toFixed(2)}`;
    const totalStr = `₹${cart.total.toFixed(2)}`;

    if (document.getElementById("cart-subtotal")) document.getElementById("cart-subtotal").innerText = subtotalStr;
    if (document.getElementById("cart-tax")) document.getElementById("cart-tax").innerText = taxStr;
    if (document.getElementById("cart-total")) document.getElementById("cart-total").innerText = totalStr;

    if (document.getElementById("order-status-subtotal")) document.getElementById("order-status-subtotal").innerText = subtotalStr;
    if (document.getElementById("order-status-tax")) document.getElementById("order-status-tax").innerText = taxStr;
    if (document.getElementById("order-status-total")) document.getElementById("order-status-total").innerText = totalStr;
}

async function addToOrder(productName) {
    const res = await fetch(`${API_BASE}/api/order`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_name: productName, quantity: 1 })
    });
    const cart = await res.json();
    renderCart(cart);
}

async function removeItem(productName) {
    const res = await fetch(`${API_BASE}/api/order/${encodeURIComponent(productName)}`, { method: "DELETE" });
    const cart = await res.json();
    renderCart(cart);
}

async function clearCart() {
    const res = await fetch(`${API_BASE}/api/order`, { method: "DELETE" });
    const cart = await res.json();
    renderCart(cart);
}

async function clearChat() {
    await fetch(`${API_BASE}/api/chat/history`, { method: "DELETE" });
    document.getElementById("messages").innerHTML = `
        <div class="flex items-start gap-4 max-w-2xl">
            <div class="w-10 h-10 rounded-full bg-secondary-container flex items-center justify-center shrink-0">
                <span class="material-symbols-outlined text-on-secondary-container">smart_toy</span>
            </div>
            <div class="bg-surface-container rounded-xl rounded-tl-sm p-4 text-on-surface font-body-md text-sm shadow-sm">
                <p>Chat cleared! How can BrewBuddy help you now?</p>
            </div>
        </div>
    `;
    clearCart();
}

function sendChip(text) {
    switchTab('assistant');
    document.getElementById("user-input").value = text;
    document.getElementById("chat-form").dispatchEvent(new Event("submit"));
}

document.getElementById("chat-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = document.getElementById("user-input");
    const msg = input.value.trim();
    if (!msg) return;

    appendMessage("user", msg);
    input.value = "";

    const preferences = {
        temperature: selectedTempPref,
        caffeine: document.getElementById("studio-caffeine") ? document.getElementById("studio-caffeine").value : "",
        diet: document.getElementById("studio-diet") ? document.getElementById("studio-diet").value : ""
    };

    try {
        const res = await fetch(`${API_BASE}/api/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: msg, preferences: preferences })
        });
        const data = await res.json();
        
        appendMessage("assistant", data.response, data.recommended_products);

        if (data.order) {
            renderCart(data.order);
        }
    } catch (err) {
        appendMessage("assistant", "Sorry, I had trouble connecting to the server.");
    }
});

function appendMessage(role, text, products = []) {
    const container = document.getElementById("messages");
    const div = document.createElement("div");
    const parsedHtml = (typeof marked !== 'undefined') ? marked.parse(text) : text;

    let productsHtml = "";
    if (products && products.length > 0) {
        productsHtml = `<div class="mt-4 space-y-3">` + products.map(p => `
            <div class="bg-surface-container-lowest rounded-xl overflow-hidden border border-outline-variant/40 shadow-sm flex flex-col sm:flex-row">
                ${p.image_url ? `
                <div class="sm:w-44 h-36 shrink-0 overflow-hidden bg-surface-variant">
                    <img src="${p.image_url}" alt="${p.name}" class="w-full h-full object-cover">
                </div>` : ''}
                <div class="p-4 flex flex-col justify-between flex-1">
                    <div>
                        <div class="flex justify-between items-start mb-1">
                            <h4 class="font-bold text-base text-primary">${p.name}</h4>
                            <span class="font-bold text-secondary text-sm">₹${p.price}</span>
                        </div>
                        <p class="text-xs text-on-surface-variant mb-2 line-clamp-2">${p.description}</p>
                        <div class="flex flex-wrap gap-2 text-[11px] text-outline mb-2">
                            <span class="bg-surface-container px-2 py-0.5 rounded font-bold">🔥 ${p.calories} kcal</span>
                            <span class="bg-surface-container px-2 py-0.5 rounded font-bold">⚡ ${p.caffeine}</span>
                            <span class="bg-surface-container px-2 py-0.5 rounded font-bold">🌾 ${p.allergens && p.allergens.length ? p.allergens.join(', ') : 'No Allergens'}</span>
                        </div>
                    </div>
                    <div class="flex gap-2 mt-2">
                        <button onclick="addToOrder('${p.name}')" class="px-4 py-2 bg-secondary text-white text-xs font-bold rounded-lg hover:bg-secondary-container transition-colors flex items-center justify-center gap-1 shadow-sm">
                            <span class="material-symbols-outlined text-[16px]">add_shopping_cart</span> Add to Order
                        </button>
                        <button onclick="showDetails('${p.id}')" class="px-3 py-2 border border-primary text-primary text-xs font-bold rounded-lg hover:bg-primary hover:text-white transition-colors">
                            Full Details
                        </button>
                    </div>
                </div>
            </div>
        `).join("") + `</div>`;
    }

    if (role === 'user') {
        div.className = "flex items-start gap-4 max-w-2xl self-end flex-row-reverse";
        div.innerHTML = `
            <div class="w-10 h-10 rounded-full bg-primary flex items-center justify-center shrink-0 text-white font-bold text-xs shadow-sm">YOU</div>
            <div class="bg-primary text-white rounded-xl rounded-tr-sm p-4 text-sm shadow-md leading-relaxed">${parsedHtml}</div>
        `;
    } else {
        div.className = "flex items-start gap-4 max-w-2xl";
        div.innerHTML = `
            <div class="w-10 h-10 rounded-full bg-secondary-container flex items-center justify-center shrink-0 shadow-sm">
                <span class="material-symbols-outlined text-on-secondary-container">smart_toy</span>
            </div>
            <div class="bg-surface-container rounded-xl rounded-tl-sm p-5 text-on-surface text-sm shadow-sm leading-relaxed markdown-bubble">
                ${parsedHtml}
                ${productsHtml}
            </div>
        `;
    }
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    setTimeout(() => { container.scrollTop = container.scrollHeight; }, 100);
}

// Explore Menu View Logic
async function fetchMenu() {
    try {
        const res = await fetch(`${API_BASE}/api/menu`);
        allProducts = await res.json();
        renderMenuGrid(allProducts);
    } catch (e) { console.error("Error fetching menu", e); }
}

function renderMenuGrid(products) {
    const grid = document.getElementById("menu-grid");
    if (!grid) return;
    grid.innerHTML = products.map(p => `
        <div class="bg-surface-container-lowest rounded-xl overflow-hidden border border-outline-variant/40 flex flex-col group hover:-translate-y-1 transition-all duration-300 shadow-sm">
            <div class="aspect-square w-full relative bg-surface-container-high overflow-hidden">
                <img src="${p.image_url}" alt="${p.name}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500">
                <span class="absolute top-2 right-2 bg-surface/80 backdrop-blur-sm text-[10px] font-bold px-2 py-0.5 rounded-full text-primary border border-outline-variant/40">${p.category}</span>
            </div>
            <div class="p-4 flex flex-col flex-grow">
                <div class="flex justify-between items-start mb-1">
                    <h3 class="font-headline-lg text-xl text-primary font-bold">${p.name}</h3>
                    <span class="font-label-md text-sm font-bold text-secondary">₹${p.price}</span>
                </div>
                <p class="font-body-md text-xs text-on-surface-variant mb-3 flex-grow line-clamp-2">${p.description}</p>
                <div class="flex items-center gap-3 mb-3 text-xs text-outline">
                    <span>🔥 ${p.calories} kcal</span>
                    <span>⚡ ${p.caffeine}</span>
                </div>
                <div class="flex gap-2">
                    <button class="flex-1 py-2 border border-primary text-primary text-xs font-bold rounded-lg hover:bg-primary hover:text-on-primary transition-colors" onclick="showDetails('${p.id}')">
                        Details
                    </button>
                    <button class="flex-1 py-2 bg-secondary text-on-secondary text-xs font-bold rounded-lg hover:bg-secondary-container transition-colors" onclick="addToOrder('${p.name}')">
                        + Add
                    </button>
                </div>
            </div>
        </div>
    `).join("");
}

function filterCategory(cat) {
    document.querySelectorAll(".cat-btn").forEach(btn => {
        if (btn.innerText.trim() === cat || (cat === 'All' && btn.innerText.trim() === 'All Items')) {
            btn.className = "cat-btn active px-4 py-2 rounded-full bg-primary text-on-primary text-xs font-bold transition-all";
        } else {
            btn.className = "cat-btn px-4 py-2 rounded-full bg-surface-container border border-outline-variant text-on-surface text-xs font-bold transition-all";
        }
    });

    if (cat === "All") {
        renderMenuGrid(allProducts);
    } else {
        renderMenuGrid(allProducts.filter(p => p.category.toLowerCase() === cat.toLowerCase()));
    }
}

function searchMenuGrid() {
    const q = document.getElementById("menu-search-input").value.lowerCase();
    renderMenuGrid(allProducts.filter(p => p.name.toLowerCase().includes(q) || p.description.toLowerCase().includes(q)));
}

// Studio Preference Controls
function setPrefOption(type, val) {
    if (type === 'temp') {
        selectedTempPref = val;
        document.querySelectorAll(".pref-temp-btn").forEach(btn => {
            if (btn.innerText.toLowerCase().includes(val) || (val === "" && btn.innerText === "Any")) {
                btn.className = "pref-temp-btn px-4 py-3 rounded-xl border border-secondary text-xs font-bold bg-secondary text-on-secondary shadow-md";
            } else {
                btn.className = "pref-temp-btn px-4 py-3 rounded-xl border border-outline-variant text-xs font-bold bg-surface-container text-on-surface";
            }
        });
    }
}

function applyStudioPreferences() {
    const temp = selectedTempPref;
    const caff = document.getElementById("studio-caffeine").value;
    const diet = document.getElementById("studio-diet").value;
    const sweet = document.getElementById("studio-sweetness").value;

    let queryParts = [];
    if (temp) queryParts.push(`${temp} coffee`);
    if (caff) queryParts.push(`${caff} caffeine`);
    if (diet) queryParts.push(`${diet}`);
    if (sweet) queryParts.push(`${sweet} sweetness`);

    const query = `Recommend coffee items based on my preferences: ${queryParts.join(", ")}`;
    sendChip(query);
}

async function showDetails(productId) {
    let p = allProducts.find(x => x.id === productId);
    if (!p) {
        const res = await fetch(`${API_BASE}/api/menu/${productId}`);
        p = await res.json();
    }
    const modalBody = document.getElementById("modal-body");
    modalBody.innerHTML = `
        ${p.image_url ? `<div class="w-full h-48 rounded-xl overflow-hidden mb-3"><img src="${p.image_url}" alt="${p.name}" class="w-full h-full object-cover"></div>` : ''}
        <h2 class="text-2xl font-bold text-primary mb-1">${p.name}</h2>
        <p class="text-xs text-on-surface-variant mb-2">${p.description}</p>
        <span class="text-xl font-bold text-secondary">₹${p.price}</span>
        <hr class="my-3 border-outline-variant/40">
        <p class="text-xs text-on-surface"><strong>Ingredients:</strong> ${p.ingredients.join(", ")}</p>
        <p class="text-xs text-on-surface mt-1"><strong>Allergens:</strong> ${p.allergens.length ? p.allergens.join(", ") : 'None'}</p>
        <p class="text-xs text-on-surface mt-1"><strong>Dietary:</strong> ${p.dietary_tags.join(", ")}</p>
        <div class="flex gap-2 mt-4">
            <button class="flex-1 bg-primary text-on-primary py-3 rounded-xl font-bold text-xs hover:bg-primary-container" onclick="addToOrder('${p.name}'); closeModal();">Add to Order</button>
            <button class="flex-1 border border-primary text-primary py-3 rounded-xl font-bold text-xs hover:bg-primary hover:text-on-primary" onclick="sendChip('Tell me more about ${p.name}'); closeModal();">Ask Assistant</button>
        </div>
    `;
    document.getElementById("modal").classList.remove("hidden");
}

function closeModal() { document.getElementById("modal").classList.add("hidden"); }

function confirmOrder() {
    alert("Thank you! Your order has been placed with BrewBuddy.");
    clearCart();
    switchTab('orders');
}

// Initial Loads
fetchChatHistory();
fetchCart();
fetchMenu();
