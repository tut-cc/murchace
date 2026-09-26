customElements.define(
  "register-items",
  class extends HTMLElement {
    #intl = new Intl.NumberFormat("ja-JP", {
      style: "currency",
      currency: "JPY",
    });

    static get observedAttributes() {
      return ["items"];
    }
    attributeChangedCallback(name, _oldValue, newValue) {
      if (name == "items") {
        const items = JSON.parse(newValue);
        this.innerHTML = this.render(items);
      }
    }
    render(items) {
      let list = "";
      for (const [idx, product] of items.entries()) {
        list += `<li class="flex justify-between">
          <div class="overflow-x-auto whitespace-nowrap sm:flex sm:flex-1 sm:justify-between p-4">
            <p class="sm:flex-1">${product.name}</p>
            <p>${this.#intl.format(product.price)}${product.count == 1 ? "" : ` x ${product.count}`}</p>
          </div>
          <div class="flex items-center">
            <button
              onclick="this.dispatchEvent(new CustomEvent('delete-item', {detail: {'index': ${idx} }, bubbles: true}))"
              class="font-bold text-white text-2xl bg-red-600 px-2 rounded-sm"
            >✕</button>
          </div>
        </li>`;
      }
      return `<ul class="text-lg divide-y-4 divide-gray-200">${list}</ul>`;
    }
  },
);
