class SlideController {
  constructor(deck) {
    this.deck = deck;
    this.slides = Array.from(deck.querySelectorAll('.slide'));
    this.current = 0;
    this.total = this.slides.length;
    this.navigating = false;       // blocks re-entry during transition
    this.wheelTimer = null;        // debounce handle
    this.touchStartX = 0;
    this.touchStartY = 0;

    this._initIndicator();
    this._initKeyboard();
    this._initTouch();
    this._initWheel();
    this._initIntersectionObserver();
    this._updateIndicator();
  }

  go(index) {
    if (this.navigating) return;
    if (index < 0 || index >= this.total) return;
    this.navigating = true;
    this.current = index;
    this.deck.scrollTo({ left: index * this.deck.offsetWidth, behavior: 'smooth' });
    this._updateIndicator();
    setTimeout(() => { this.navigating = false; }, 500);
  }

  next() { this.go(this.current + 1); }
  prev() { this.go(this.current - 1); }

  _initKeyboard() {
    document.addEventListener('keydown', e => {
      if (e.key === 'ArrowRight' || e.key === 'Space') { e.preventDefault(); this.next(); }
      if (e.key === 'ArrowLeft'  || e.key === 'Backspace') { e.preventDefault(); this.prev(); }
      if (e.key === 'Home') { e.preventDefault(); this.go(0); }
      if (e.key === 'End')  { e.preventDefault(); this.go(this.total - 1); }
    });
  }

  _initTouch() {
    this.deck.addEventListener('touchstart', e => {
      this.touchStartX = e.changedTouches[0].screenX;
      this.touchStartY = e.changedTouches[0].screenY;
    }, { passive: true });

    this.deck.addEventListener('touchend', e => {
      const dx = e.changedTouches[0].screenX - this.touchStartX;
      const dy = e.changedTouches[0].screenY - this.touchStartY;
      if (Math.abs(dx) < 50 || Math.abs(dy) > Math.abs(dx)) return;
      dx < 0 ? this.next() : this.prev();
    }, { passive: true });
  }

  _initWheel() {
    this.deck.addEventListener('wheel', e => {
      e.preventDefault();
      clearTimeout(this.wheelTimer);
      this.wheelTimer = setTimeout(() => {
        e.deltaY > 0 ? this.next() : this.prev();
      }, 150); // 150ms debounce prevents multi-slide jumps on trackpad
    }, { passive: false });
  }

  _initIntersectionObserver() {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) entry.target.classList.add('visible');
      });
    }, { threshold: 0.5 });
    this.slides.forEach(s => observer.observe(s));
  }

  _initIndicator() {
    this.indicator = document.createElement('div');
    this.indicator.className = 'slide-indicator';
    document.body.appendChild(this.indicator);
  }

  _updateIndicator() {
    this.indicator.textContent = `${this.current + 1} / ${this.total}`;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  new SlideController(document.querySelector('.deck'));
});
