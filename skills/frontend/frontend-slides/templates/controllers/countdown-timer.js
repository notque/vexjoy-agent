class CountdownTimer {
  constructor(totalSeconds) {
    this.remaining = totalSeconds;
    this.el = document.createElement('div');
    this.el.className = 'countdown-timer';
    document.body.appendChild(this.el);
    this._render();
    this.interval = setInterval(() => {
      this.remaining = Math.max(0, this.remaining - 1);
      this._render();
      if (this.remaining === 0) clearInterval(this.interval);
    }, 1000);
  }
  _render() {
    const m = Math.floor(this.remaining / 60).toString().padStart(2, '0');
    const s = (this.remaining % 60).toString().padStart(2, '0');
    this.el.textContent = `${m}:${s}`;
    this.el.classList.toggle('urgent', this.remaining < 120);
  }
}
