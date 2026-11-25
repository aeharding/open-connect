/* SPDX-License-Identifier: AGPL-3.0-or-later */
(() => {
  "use strict";

  const logo = document.querySelector('[data-md-component="logo"]');
  const header = document.querySelector('[data-md-component="header-title"]');
  const name = header?.querySelector(".md-header__topic:first-child .md-ellipsis");
  if (logo && name) {
    const home = document.createElement("a");
    home.href = logo.getAttribute("href");
    home.className = `${name.className} oc-header-home`;
    home.textContent = name.textContent.trim();
    home.setAttribute("aria-label", `${home.textContent} home`);
    name.replaceWith(home);
    const visibility = () => {
      const hidden = header.classList.contains("md-header__title--active");
      home.tabIndex = hidden ? -1 : 0;
      home.setAttribute("aria-hidden", String(hidden));
    };
    new MutationObserver(visibility).observe(header, { attributes: true, attributeFilter: ["class"] });
    visibility();
  }

  // Resolve from this file, including on nested pages and GitHub Pages subpaths.
  const assets = new URL("../assets/guide/", document.currentScript.src);
  // Reviewed Home-first Commander Dial videos; identities are in the asset notes.
  const root = ["open-connect.mp4", "Home → Settings → System → Open Connect"];
  const phone = ["carplay-android-auto.mp4", `${root[1]} → CarPlay & Android Auto`];
  const audio = ["audio-sources.mp4", `${root[1]} → Audio sources (dev.20 capture)`];
  const paths = {
    "open-connect": root,
    touchscreen: root,
    disclaimer: root,
    "startup-optimizations": root,
    "apply-changes": root,
    uninstall: root,
    about: root,
    "carplay-android-auto": phone,
    "wireless-carplay": phone,
    "carplay-on-connection": phone,
    "android-auto": phone,
    "wireless-setup": phone,
    "phone-connections": phone,
    "audio-sources": audio,
    services: audio,
    dvd: root,
    pandora: audio,
    siriusxm: audio,
    "developer-options": ["developer-options.mp4", `${root[1]} → Developer options`],
    "version-info": ["version-info.mp4", "Home → Settings → System → About → Version Information"],
  };
  const audioNote = "This dev.20 video shows the published dev.19/dev.20 layout, with DVD under Audio sources. In the upcoming North American candidate, Audio sources contains only Pandora and SiriusXM; DVD is managed by Startup optimizations.";
  const notes = {
    touchscreen: "Select Touchscreen While Driving, then choose Allow or Factory Default.",
    disclaimer: "Select Startup disclaimer, then choose Skip or Show.",
    "wireless-carplay": "Turn on Wireless CarPlay and confirm Enable. The inline screenshot shows it on; fresh installations leave it off unless factory enabled.",
    "carplay-on-connection": "Select Show CarPlay on connection, then choose Factory behavior or Automatically show. The inline screenshot shows the Factory default.",
    "android-auto": "Turn Android Auto on or off and confirm the change.",
    "startup-optimizations": "Turn Startup optimizations on or off and confirm the change. The inline screenshot shows it on; the fresh-install default is Off.",
    "audio-sources": audioNote,
    services: audioNote,
    dvd: "Published dev.19/dev.20 have DVD under Audio sources. In the upcoming North American candidate, use Startup optimizations in Open Connect to manage the unused DVD service. Audio CDs still work. This video shows dev.20.",
    pandora: "Turn Pandora on or off and confirm the change. This controls Mazda’s integration, not Pandora through CarPlay or Bluetooth.",
    siriusxm: "Turn SiriusXM on or off and confirm the change. This controls satellite radio and SiriusXM data.",
    "apply-changes": "Select Apply changes, then confirm Restart to apply saved choices. It is disabled when there are no pending changes. Keep the car on until Mazda Connect restarts.",
    uninstall: "Select Uninstall and confirm Uninstall. Keep the car on until the automatic restart finishes.",
    about: "Select About to see the installed Open Connect version.",
  };
  const motion = matchMedia("(prefers-reduced-motion: reduce)");
  const panel = document.createElement("dialog");
  panel.className = "oc-nav-preview";
  panel.id = "oc-nav-preview";
  panel.setAttribute("aria-labelledby", "oc-nav-title");
  panel.setAttribute("aria-describedby", "oc-nav-step oc-nav-note");
  panel.innerHTML = `
    <div class="oc-nav-preview__header">
      <strong id="oc-nav-title">Navigation walkthrough</strong>
      <button type="button" data-action="close" aria-label="Close navigation preview" autofocus>×</button>
    </div>
    <div class="oc-screen-frame"><video muted loop playsinline preload="none" width="800" height="480" aria-label="Commander Dial navigation walkthrough"></video></div>
    <p id="oc-nav-step" aria-atomic="true"></p>
    <p id="oc-nav-note" class="oc-nav-preview__note" hidden></p>
    <div class="oc-nav-preview__controls">
      <button type="button" data-action="play">Play</button>
      <button type="button" data-action="restart" aria-label="Restart walkthrough">Restart</button>
    </div>`;
  document.body.append(panel);
  const screen = panel.querySelector("video");
  screen.muted = true;
  const label = panel.querySelector("#oc-nav-step");
  const note = panel.querySelector("#oc-nav-note");
  const play = panel.querySelector('[data-action="play"]');
  let trigger = null;
  let backdropPress = false;

  function playback() {
    play.textContent = screen.paused ? "Play" : "Pause";
    play.setAttribute("aria-label", screen.paused ? "Play walkthrough" : "Pause walkthrough");
  }

  function start() {
    screen.play().catch(playback);
  }

  screen.addEventListener("play", playback);
  screen.addEventListener("pause", playback);
  screen.addEventListener("error", playback);

  function close() {
    if (!trigger) return;
    const previous = trigger;
    trigger = null;
    screen.pause();
    screen.currentTime = 0;
    screen.removeAttribute("src");
    // Release the media resource and stop fetching/decoding after dismissal.
    screen.load();
    panel.close();
    document.documentElement.classList.remove("oc-nav-modal-open");
    previous.setAttribute("aria-expanded", "false");
    previous.focus({ preventScroll: true });
  }

  function open(button) {
    trigger = button;
    const [file, route] = paths[button.dataset.walkthrough];
    // No src or poster exists before a click. Only this video loads on demand.
    screen.src = new URL(`walkthroughs/${file}`, assets).href;
    screen.setAttribute("aria-label", `${route} — Commander Dial walkthrough`);
    label.textContent = route;
    note.textContent = notes[button.dataset.walkthrough] || "";
    note.hidden = !note.textContent;
    button.setAttribute("aria-expanded", "true");
    document.documentElement.classList.add("oc-nav-modal-open");
    panel.showModal();
    playback();
    if (!motion.matches) start();
  }

  document.querySelectorAll(".oc-nav-path[data-walkthrough]").forEach(path => {
    if (!paths[path.dataset.walkthrough]?.length) return;
    // The source is plain inline text in GitHub and when JavaScript is absent.
    const button = document.createElement("button");
    button.type = "button";
    button.className = "oc-nav-path";
    button.dataset.walkthrough = path.dataset.walkthrough;
    button.textContent = path.textContent;
    button.setAttribute("aria-label", `${path.textContent} — preview navigation`);
    button.setAttribute("aria-haspopup", "dialog");
    button.setAttribute("aria-controls", panel.id);
    button.setAttribute("aria-expanded", "false");
    path.replaceWith(button);
    button.addEventListener("click", () => open(button));
  });

  function outside(event) {
    const rect = panel.getBoundingClientRect();
    return event.clientX < rect.left || event.clientX > rect.right ||
      event.clientY < rect.top || event.clientY > rect.bottom;
  }

  panel.addEventListener("pointerdown", event => {
    backdropPress = event.target === panel && outside(event);
  });
  panel.addEventListener("click", event => {
    if (event.target === panel && backdropPress && outside(event)) { close(); return; }
    const button = event.target.closest("button");
    if (!button) return;
    const action = button.dataset.action;
    if (action === "close") close();
    else if (action === "play") {
      if (screen.paused) start();
      else screen.pause();
    } else if (action === "restart") screen.currentTime = 0;
  });
  panel.addEventListener("cancel", event => { event.preventDefault(); close(); });
  window.addEventListener("keydown", event => {
    if (!panel.open) return;
    const key = event.key;
    const lower = key.toLowerCase();
    if (key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close();
      return;
    }
    if (key === "Tab") {
      const controls = [...panel.querySelectorAll("button:not(:disabled)")];
      const idx = controls.indexOf(document.activeElement);
      event.preventDefault();
      event.stopPropagation();
      const next = idx === -1 ? (event.shiftKey ? controls.length - 1 : 0) :
        (idx + (event.shiftKey ? -1 : 1) + controls.length) % controls.length;
      controls[next].focus();
      return;
    }
    if ((event.metaKey || event.ctrlKey) && lower === "k") {
      event.preventDefault();
      event.stopPropagation();
      return;
    }
    if (!event.altKey && !event.ctrlKey && !event.metaKey && key === "/") {
      event.preventDefault();
    }
    // Keep Zensical global keyboard shortcuts from firing behind the open modal.
    event.stopPropagation();
  }, true);
  document.addEventListener("visibilitychange", () => { if (document.hidden) screen.pause(); });
  motion.addEventListener("change", () => { if (motion.matches) screen.pause(); });
})();
