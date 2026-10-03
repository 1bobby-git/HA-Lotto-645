/* Entry-scoped announcements only; visible data is refreshed by user actions. */
export function installLiveSync(Panel) {
  if (Panel.prototype._lottoLiveInstalled) return;
  Panel.prototype._lottoLiveInstalled = true;

  Panel.prototype._queueLiveRefresh = function (reload = false) {
    // Only initial/explicit entry selection can request a load. Background
    // invalidations must never rebuild the page the user is reading.
    if (!reload) return;
    this._livePending = true;
    this._liveReload = this._liveReload || reload;
    this._drainLiveRefresh();
  };
  Panel.prototype._drainLiveRefresh = function () {
    if (!this._livePending || this._busy || !this.isConnected || document.hidden || !this.node('entry')?.value) return;
    if (this._liveQueued) return;
    this._liveQueued = true;
    queueMicrotask(() => {
      this._liveQueued = false;
      if (!this._livePending || this._busy || !this.isConnected || document.hidden) return;
      const reload = this._liveReload && !this._editing;
      this._livePending = this._liveReload = false;
      void this.operation(() => reload ? this.load() : this.refreshStatus(), true);
    });
  };
  Panel.prototype._stopLiveSubscription = function () {
    this._liveToken = (this._liveToken || 0) + 1;
    const unsubscribe = this._liveUnsubscribe;
    this._liveUnsubscribe = null;
    this._liveConnection = null;
    this._liveEntry = null;
    clearTimeout(this._liveRetry);
    this._liveRetry = null;
    if (unsubscribe) Promise.resolve().then(unsubscribe).catch(() => {});
  };
  Panel.prototype._ensureLiveSubscription = function () {
    const connection = this._hass?.connection;
    const entry = this.node('entry')?.value;
    if (!this.isConnected || !entry || !connection?.subscribeMessage) return;
    if (this._liveConnection === connection && this._liveEntry === entry) return;
    this._stopLiveSubscription();
    this._liveConnection = connection;
    this._liveEntry = entry;
    const token = this._liveToken;
    const valid = () => this.isConnected && token === this._liveToken && entry === this.node('entry')?.value;
    Promise.resolve().then(() => connection.subscribeMessage(event => {
      if (valid() && event.entry_id === entry) {
        if (event.announcement) void this._notifyLottoAnnouncement?.(event.announcement);
      }
    }, {type: 'lotto_645/subscribe', entry_id: entry})).then(unsubscribe => {
      if (!valid()) { Promise.resolve().then(unsubscribe).catch(() => {}); return; }
      this._liveUnsubscribe = unsubscribe;
    }).catch(() => {
      if (!valid()) return;
      this._stopLiveSubscription();
      this._liveRetry = setTimeout(() => this._ensureLiveSubscription(), 5000);
    });
  };
  Panel.prototype._syncEntryOptions = function () {
    const select = this.node('entry');
    if (!select) return;
    const entries = this._panel?.config?.entries || {};
    const signature = JSON.stringify(entries);
    if (signature === this._liveEntriesSignature) return;
    this._liveEntriesSignature = signature;
    const previous = select.value;
    select.replaceChildren();
    for (const [id, title] of Object.entries(entries)) {
      const option = document.createElement('option');option.value = id;option.textContent = title;select.append(option);
    }
    if (previous && !(previous in entries) && this._editing) {
      const option = document.createElement('option');option.value = previous;
      option.textContent = '사용할 수 없는 통합 · 입력 보존됨';select.append(option);
    }
    if ([...select.options].some(option => option.value === previous)) select.value = previous;
    this.node('entry-field').hidden = select.options.length <= 1;
    if (select.value !== previous) {
      this._requestEpoch = (this._requestEpoch || 0) + 1;
      this._activeEntry = select.value;
      this._walletRound = this._walletData = this._loadedRound = null;
      this._roundSignature = null;
      this._resetFinalizationContext?.();
      this._queueLiveRefresh(true);
    }
    this.syncAvailability();
    this._ensureLiveSubscription();
  };

  const start = Panel.prototype._start;
  Panel.prototype._start = function (...args) {
    const result = start.apply(this, args);
    this._syncEntryOptions();
    this._ensureLiveSubscription();
    this._drainLiveRefresh();
    return result;
  };
  const disconnect = Panel.prototype._onLottoDisconnected;
  Panel.prototype._onLottoDisconnected = function (...args) {
    this._stopLiveSubscription();
    return disconnect?.apply(this, args);
  };
}
