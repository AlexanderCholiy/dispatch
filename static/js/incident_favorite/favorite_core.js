import { FavoriteConstants } from './favorite_constants.js';

const stateMap = new Map();

export const FavoriteCore = (() => {

  /**
   * Следующее состояние в цикле.
   * null → 'normal' → 'important' → null
   * @param {string|null} current
   * @returns {string|null}
   */
  function nextPriority(current) {
    const cycle = FavoriteConstants.CYCLE;
    const idx = cycle.indexOf(current);
    return cycle[(idx + 1) % cycle.length];
  }

  function initButton(btn) {
    const id = btn.dataset.incidentId;
    if (!id || btn.classList.contains(FavoriteConstants.CLS.IS_INIT)) return;

    btn.classList.add(FavoriteConstants.CLS.IS_INIT);

    const state = {
      isFavorite: btn.dataset.isFavorite === 'true',
      priority: btn.dataset.priority || null,
    };

    stateMap.set(id, state);
    _render(btn, state);
  }

  function initAll() {
    document
      .querySelectorAll(`.${FavoriteConstants.CLS.BTN}`)
      .forEach((btn) => initButton(btn));
  }

  /**
   * Циклический переход: null → normal → important → null
   * @param {HTMLElement} btn
   * @returns {{isFavorite: boolean, priority: string|null} | null}
   */
  function cycle(btn) {
    const id = btn.dataset.incidentId;
    const state = stateMap.get(id);
    if (!state) return null;

    state.priority = nextPriority(state.priority);
    state.isFavorite = state.priority !== null;

    _renderAll(id, state);
    _animate(btn);

    return { ...state };
  }

  function applyExternalState(incidentId, newState) {
    const state = {
      isFavorite: newState.isFavorite,
      priority: newState.priority || null,
    };
    stateMap.set(incidentId, state);
    _renderAll(incidentId, state);
  }

  function getState(incidentId) {
    const s = stateMap.get(incidentId);
    return s ? { ...s } : null;
  }

  function setDisabled(btn, disabled) {
    btn.classList.toggle(FavoriteConstants.CLS.IS_DISABLED, disabled);
    if (disabled) {
      btn.setAttribute('disabled', '');
    } else {
      btn.removeAttribute('disabled');
    }
  }

  // ─── Private ─────────────────────────────────────────────────

  function _renderAll(incidentId, state) {
    document
      .querySelectorAll(
        `.${FavoriteConstants.CLS.BTN}[data-incident-id="${incidentId}"]`
      )
      .forEach((btn) => _render(btn, state));
  }

  function _render(btn, { isFavorite, priority }) {
    const { CLS } = FavoriteConstants;

    btn.dataset.priority = isFavorite ? priority : '';

    btn.setAttribute(
      'aria-label',
      !isFavorite
        ? 'Добавить в избранное'
        : priority === 'important'
          ? 'Избранное (важный)'
          : 'Избранное (обычный)'
    );

    const tooltip = btn.querySelector(`.${CLS.TOOLTIP}`);
    if (tooltip) {
      if (!isFavorite) {
        tooltip.dataset.title = 'Добавить в избранное';
      } else if (priority === 'important') {
        tooltip.dataset.title = 'Избранное (важный)';
      } else {
        tooltip.dataset.title = 'Избранное (обычный)';
      }
    }
  }

  function _animate(btn) {
    const { CLS } = FavoriteConstants;
    btn.classList.remove(CLS.IS_ANIMATING);
    void btn.offsetWidth;
    btn.classList.add(CLS.IS_ANIMATING);

    btn.addEventListener(
      'animationend',
      () => btn.classList.remove(CLS.IS_ANIMATING),
      { once: true }
    );
  }

  return Object.freeze({
    initButton,
    initAll,
    cycle,
    applyExternalState,
    getState,
    setDisabled,
    nextPriority,
  });
})();