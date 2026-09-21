/* === Keyboard Navigation Component === */
function setupKeyNav(containerSelector, itemSelector) {
  const container = document.querySelector(containerSelector);
  const items = () => container.querySelectorAll(itemSelector);
  let current = 0;
  const counter = container.querySelector('.key-nav-counter');
  function update() {
    const all = items();
    all.forEach((el, i) => el.classList.toggle('active', i === current));
    if (counter) counter.textContent = (current + 1) + '/' + all.length;
  }
  document.addEventListener('keydown', e => {
    const all = items();
    if (!all.length) return;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); current = (current + 1) % all.length; update(); }
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); current = (current - 1 + all.length) % all.length; update(); }
  });
  update();
}
