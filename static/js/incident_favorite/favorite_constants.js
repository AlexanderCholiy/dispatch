export const FavoriteConstants = Object.freeze({
  /** Порядок циклического переключения: off → normal → important → off */
  CYCLE: Object.freeze([
    null,
    'normal',
    'important',
  ]),

  PRIORITY_LABELS: Object.freeze({
    normal: 'Обычный',
    important: 'Важный',
  }),

  WS_BASE: '/ws/incidents/incident-favorite/',

  MSG: Object.freeze({
    TOGGLE: 'toggle_favorite',
    SET_PRIORITY: 'set_priority',
  }),

  MSG_SERVER: Object.freeze({
    STATE_UPDATE: 'state_update',
    ERROR: 'error',
  }),

  CLS: Object.freeze({
    BTN: 'incident-favorite-btn',
    ICON: 'incident-favorite-icon',
    TOOLTIP: 'tooltip',
    IS_ANIMATING: 'is-animating',
    IS_DISABLED: 'is-disabled',
    IS_INIT: 'is-init',
  }),

  MAX_WS_CONNECTIONS: 20,
  WS_MAX_RECONNECT: 5,
  WS_BASE_DELAY_MS: 1500,
});