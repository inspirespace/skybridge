export function navigateWithFade(event: React.MouseEvent<HTMLElement>, href: string) {
  if (
    event.defaultPrevented ||
    event.button !== 0 ||
    event.metaKey ||
    event.altKey ||
    event.ctrlKey ||
    event.shiftKey
  ) {
    return;
  }
  event.preventDefault();
  const html = document.documentElement;
  html.classList.add("page-exit");
  window.setTimeout(() => {
    window.location.assign(href);
  }, 160);
}
