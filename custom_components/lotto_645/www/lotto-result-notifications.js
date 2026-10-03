/* Browser opt-in only. Open/background tabs use the existing entry-scoped WS. */
export function installResultNotifications(Panel) {
  Panel.prototype._notificationStorageKey = function () {
    return `lotto-result-alert:${this._hass?.user?.id || 'local'}:${this.node('entry')?.value || ''}`;
  };
  Panel.prototype._refreshNotificationButton = function () {
    const button = this.node('result-notifications');
    if (!button) return;
    const supported = window.isSecureContext && 'Notification' in window;
    let enabled = false;
    try { enabled = localStorage.getItem(this._notificationStorageKey()) === 'on'; } catch (_) {}
    button.disabled = !supported;
    button.textContent = enabled ? '브라우저 알림 끄기' : '브라우저 알림 켜기';
    button.setAttribute('aria-pressed', String(enabled));
    button.title = supported ? '브라우저가 열려 있을 때 알림. 닫혀 있으면 Home Assistant 알림에서 확인하세요.'
      : '이 브라우저에서는 지원하지 않습니다. Home Assistant 알림은 계속 제공됩니다.';
  };
  Panel.prototype._toggleResultNotifications = async function () {
    try {
      const key = this._notificationStorageKey();
      if (localStorage.getItem(key) === 'on') localStorage.removeItem(key);
      else {
        if (!window.isSecureContext || !('Notification' in window)) throw new Error('이 브라우저에서는 알림을 지원하지 않습니다.');
        // This method is called only by the user's button click.
        const permission = Notification.permission === 'default'
          ? await Notification.requestPermission() : Notification.permission;
        if (permission !== 'granted') throw new Error('브라우저 설정에서 알림을 허용해 주세요. Home Assistant 알림은 계속 제공됩니다.');
        localStorage.setItem(key, 'on');
        // Opt-in is not a request to replay a result already visible on screen.
        if (this._lastAnnouncement?.key) localStorage.setItem(key + ':last', this._lastAnnouncement.key);
      }
      this._refreshNotificationButton();
    } catch (error) { this.message(error.message || '브라우저 알림 설정을 저장하지 못했습니다.', true); }
  };
  Panel.prototype._notifyLottoAnnouncement = async function (alert) {
    if (!alert || typeof alert.key !== 'string' || typeof alert.title !== 'string' || typeof alert.message !== 'string') return;
    this._lastAnnouncement = alert;
    const key = this._notificationStorageKey();
    const send = async () => {
      try {
        if (!this.isConnected || key !== this._notificationStorageKey() || !window.isSecureContext || !('Notification' in window)
            || Notification.permission !== 'granted' || localStorage.getItem(key) !== 'on'
            || localStorage.getItem(key + ':last') === alert.key) return;
        const note = new Notification(alert.title, {body: alert.message, tag: `${key}:${alert.round}`});
        localStorage.setItem(key + ':last', alert.key);
        note.onclick = () => { window.focus(); note.close(); };
      } catch (_) { /* iOS/unsupported desktop APIs fall back to the HA card. */ }
    };
    try {
      if (navigator.locks?.request) await navigator.locks.request(key, send);
      else await send();
    } catch (_) {}
  };
  const render = Panel.prototype.render;
  Panel.prototype.render = function (...args) {
    const value = render.apply(this, args);
    const button = this.node('result-notifications');
    if (button) button.onclick = () => this._toggleResultNotifications();
    this._refreshNotificationButton();
    return value;
  };
  const update = Panel.prototype.updateResults;
  Panel.prototype.updateResults = function (data, ...args) {
    const value = update.call(this, data, ...args);
    this._refreshNotificationButton();
    void this._notifyLottoAnnouncement(data.announcement);
    const waiting = this.node('publication-waiting');
    if (waiting) {
      const pending = data.result_verification?.publication_wait;
      waiting.hidden = !pending?.pending;
      waiting.textContent = pending?.pending ? `${pending.round}회 ${['provisional','cross_checked'].includes(data.result_verification?.status) ? '공식 결과 대조 중' : '발표 확인 중'} · 방송 편성에 따라 늦어질 수 있으며 서버에서 결과를 계속 확인합니다. 화면은 결과 확인 버튼으로 갱신하세요.` : '';
    }
    return value;
  };
}
