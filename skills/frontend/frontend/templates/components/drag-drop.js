/* === Drag and Drop Component === */
let dragEl = null;
document.querySelectorAll('.drag-item').forEach(item => {
  item.addEventListener('dragstart', e => { dragEl = item; item.classList.add('dragging'); e.dataTransfer.effectAllowed = 'move'; });
  item.addEventListener('dragend', () => { item.classList.remove('dragging'); document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over')); dragEl = null; });
  item.addEventListener('dragover', e => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; item.classList.add('drag-over'); });
  item.addEventListener('dragleave', () => { item.classList.remove('drag-over'); });
  item.addEventListener('drop', e => {
    e.preventDefault(); item.classList.remove('drag-over');
    if (dragEl && dragEl !== item) {
      const list = item.parentNode; const items = [...list.children];
      const fromIdx = items.indexOf(dragEl); const toIdx = items.indexOf(item);
      if (fromIdx < toIdx) { list.insertBefore(dragEl, item.nextSibling); } else { list.insertBefore(dragEl, item); }
    }
  });
});
