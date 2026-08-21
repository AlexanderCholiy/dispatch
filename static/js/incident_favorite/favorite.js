import { FavoriteConstants } from './favorite_constants.js';
import { FavoriteCore } from './favorite_core.js';
import { FavoriteWebSocket } from './favorite_websocket.js';

let observer = null;

function init() {
  FavoriteCore.initAll();
  document.addEventListener('click', onClick, false);
  startObserver();
  window.addEventListener('beforeunload', onUnload, false);
}

function onClick(e) {
  const btn = e.target.closest(`.${FavoriteConstants.CLS.BTN}`);
  if (!btn || btn.hasAttribute('disabled')) return;

  e.preventDefault();
  e.stopPropagation();

  const incidentId = btn.dataset.incidentId;
  const prevState = FavoriteCore.getState(incidentId);

  const newState = FavoriteCore.cycle(btn);
  if (!newState) return;

  FavoriteWebSocket.ensureConnected(incidentId);
  FavoriteCore.setDisabled(btn, true);

  // Определяем, что отправить
  if (newState.isFavorite) {
    if (!prevState?.isFavorite) {
      // off → normal: toggle on
      FavoriteWebSocket.sendToggle(incidentId, true);
    } else if (newState.priority === 'important') {
      // normal → important: set_priority
      FavoriteWebSocket.sendSetPriority(incidentId, 'important');
    }
  } else {
    // important → off: toggle off
    FavoriteWebSocket.sendToggle(incidentId, false);
  }

  setTimeout(() => FavoriteCore.setDisabled(btn, false), 400);
}

function startObserver() {
  observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
      for (const node of m.addedNodes) {
        if (node.nodeType !== Node.ELEMENT_NODE) continue;
        const btns = node.classList?.contains(FavoriteConstants.CLS.BTN)
          ? [node]
          : node.querySelectorAll?.(`.${FavoriteConstants.CLS.BTN}`) || [];
        btns.forEach((btn) => FavoriteCore.initButton(btn));
      }
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
}

function onUnload() {
  FavoriteWebSocket.disconnectAll();
  observer?.disconnect();
  observer = null;
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true });
} else {
  init();
}