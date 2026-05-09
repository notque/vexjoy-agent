// Speaker notes panel — toggle with 'n' key
// Add inside _initKeyboard() event listener:
//   if (e.key === 'n') { toggleNotesPanel(); }

function toggleNotesPanel() {
  const panel = document.getElementById('notes-panel');
  if (!panel) return;
  const hidden = panel.getAttribute('aria-hidden') === 'true';
  panel.setAttribute('aria-hidden', String(!hidden));
  panel.style.visibility = hidden ? 'visible' : 'hidden';
  panel.style.transform = hidden ? 'translateY(0)' : 'translateY(100%)';
}
