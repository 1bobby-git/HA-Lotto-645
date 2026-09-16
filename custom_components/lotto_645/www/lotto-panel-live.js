/* Entry-scoped invalidations, not lottery polling. No ticket or keyword data in events. */
export function installLiveSync(Panel) {
  if (Panel.prototype._lottoLiveInstalled) return;
  Panel.prototype._lottoLiveInstalled = true;

  Panel.prototype._scheduleLiveRetry = function () {
    if (!this.isConnected || (this._liveFailures || 0) >= 5 || this._liveRefreshRetry) return;
    this._liveFailures = (this._liveFailures || 0) + 1;
    this._liveRefreshRetry = setTimeout(() => {
      this._liveRefreshRetry = null;
      this._queueLiveRefresh();
    }, 2000);
  };
  const update = Panel.prototype.updateResults;
  Panel.prototype.updateResults = function (...args) {
    clearTimeout(this._liveRefreshRetry);this._liveRefreshRetry = null;this._liveFailures = 0;
    return update.apply(this, args);
  };
  Panel.prototype._queueLiveRefresh = function (reload = false) {
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
    clearTimeout(this._liveRefreshRetry);
    this._liveRefreshRetry = null;
    clearTimeout(this._liveRetry);
    this._liveRetry = null;
    if (unsubscribe) Promise.resolve().then(unsubscribe).catch(() => {});
    if (this._liveReadyConnection && this._liveReadyHandler) {
      this._liveReadyConnection.removeEventListener?.('ready', this._liveReadyHandler);
    }
    this._liveReadyConnection = null;
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
    this._liveReadyConnection = connection;
    this._liveReadyHandler = () => { if (valid()) this._queueLiveRefresh(); };
    connection.addEventListener?.('ready', this._liveReadyHandler);
    Promise.resolve().then(() => connection.subscribeMessage(event => {
      if (valid() && event.entry_id === entry) this._queueLiveRefresh();
    }, {type: 'lotto_645/subscribe', entry_id: entry})).then(unsubscribe => {
      if (!valid()) { Promise.resolve().then(unsubscribe).catch(() => {}); return; }
      this._liveUnsubscribe = unsubscribe;
      // Fetch after subscribing: closes the gap between initial load and listener registration.
      this._queueLiveRefresh();
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
  const connect = Panel.prototype._onLottoConnected;
  Panel.prototype._onLottoConnected = function (...args) {
    const value = connect?.apply(this, args);
    this._liveVisibility = () => { if (!document.hidden) this._queueLiveRefresh(); };
    document.addEventListener('visibilitychange', this._liveVisibility);
    this._queueLiveRefresh();
    return value;
  };
  const disconnect = Panel.prototype._onLottoDisconnected;
  Panel.prototype._onLottoDisconnected = function (...args) {
    document.removeEventListener('visibilitychange', this._liveVisibility);
    this._stopLiveSubscription();
    return disconnect?.apply(this, args);
  };
}
