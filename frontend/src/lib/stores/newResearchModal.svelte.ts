let _open = $state(false);

export const showNewResearchModal = {
  get open() { return _open; },
  set open(v: boolean) { _open = v; },
};
