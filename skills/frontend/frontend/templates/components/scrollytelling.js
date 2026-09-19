/* === Scrollytelling Component === */

document.addEventListener('DOMContentLoaded', () => {
  // --- IntersectionObserver for .reveal, .fade-in, .slide-left ---
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target); // fire once
        }
      }
    },
    { threshold: 0.15, rootMargin: '0px' }
  );

  document.querySelectorAll('.reveal, .fade-in, .slide-left, .stagger-group')
    .forEach(el => observer.observe(el));

  // --- Animated Counters ---
  const counters = document.querySelectorAll('.counter');
  if (counters.length > 0) {
    const counterObserver = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          const el = entry.target;
          const target = parseInt(el.dataset.target, 10);
          const suffix = el.dataset.suffix || '';
          const duration = 800;
          const start = performance.now();

          function tick(now) {
            const elapsed = now - start;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
            el.textContent = Math.round(target * eased).toLocaleString() + suffix;
            if (progress < 1) requestAnimationFrame(tick);
          }

          requestAnimationFrame(tick);
          counterObserver.unobserve(el);
        }
      }
    }, { threshold: 0.3 });

    counters.forEach(el => counterObserver.observe(el));
  }

  // --- Reading Progress Bar ---
  const progressFill = document.getElementById('progress-fill');
  if (progressFill) {
    window.addEventListener('scroll', () => {
      const scrollTop = window.scrollY;
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      const progress = docHeight > 0 ? Math.min((scrollTop / docHeight) * 100, 100) : 0;
      progressFill.style.width = progress + '%';
    }, { passive: true });
  }
});
