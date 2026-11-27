// A placeholder Lovelace card for the BetaSeries integration: it only shows the name of the
// integration. Replace it with your own card; custom_components/betaseries/card.py serves it and adds it to every
// dashboard, so it needs no dashboard resource. Add it from the card picker or in YAML:
//
//   type: custom:betaseries-card
//
// JavaScript is checked by `scripts/lint js` (node --check, ESLint, Prettier) and by the `javascript` CI job.

const NAME = "BetaSeries";

class BetaseriesCard extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 1;
  }

  _render() {
    if (!this._config) return;
    if (!this._card) {
      this._card = document.createElement("ha-card");
      this.appendChild(this._card);
    }
    this._card.header = this._config.title ?? NAME;
  }
}

if (!customElements.get("betaseries-card")) {
  customElements.define("betaseries-card", BetaseriesCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "betaseries-card")) {
  window.customCards.push({
    type: "betaseries-card",
    name: NAME + " card",
    description: "A placeholder card of the " + NAME + " integration.",
  });
}
