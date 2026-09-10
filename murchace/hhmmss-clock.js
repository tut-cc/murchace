(() => {
  class HHMMSSClock extends HTMLElement {
    connectedCallback() {
      this.updateClock();
      setTimeout(() => {
        setInterval(() => this.updateClock(), 1000);
        this.updateClock();
      }, 1000 - new Date().getMilliseconds());
    }
    updateClock() {
      this.textContent = new Date().toTimeString().split(" ")[0];
    }
  }
  customElements.define("hhmmss-clock", HHMMSSClock);
})();
