(() => {
  class NotifRingtone extends HTMLElement {
    constructor() {
      super();
      this.audio = new Audio();
    }
    static get observedAttributes() {
      return ["notification", "src"];
    }
    attributeChangedCallback(name, _oldValue, newValue) {
      if (name === "notification" && newValue) {
        this.audio.muted = false;
        this.audio.play();
        this.dispatchEvent(new CustomEvent("playing"));
      } else if (name === "src") {
        this.audio.src = newValue;
        this.audio.load();
        this.audio.muted = true;
        // Load audio in the background on a screen touch to
        // circumvent the autoplay policy on iOS.
        // Details: https://stackoverflow.com/a/10448078
        document.addEventListener("touchstart", () => this.audio.play(), {
          once: true,
        });
      }
    }
  }
  customElements.define("notif-ringtone", NotifRingtone);
})();
