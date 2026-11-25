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
  const entry = ["settings-entry.png", "System tab → Open Connect"];
  const settings = ["setting-touchscreen-while-driving.png", "Open Connect settings"];
  const phone = ["setting-carplay-android-auto.png", "Open Connect → CarPlay & Android Auto"];
  const wireless = ["setting-wireless-carplay.png", "CarPlay & Android Auto → Wireless CarPlay"];
  const audio = ["setting-audio-sources.png", "Open Connect → Audio sources"];
  const sources = ["setting-dvd.png", "Audio sources → DVD"];
  // Reviewed native Commander Dial highlights; per-file identities are in the asset notes.
  const paths = {
    "open-connect": [entry, settings],
    touchscreen: [entry, ["setting-touchscreen-while-driving.png", "Open Connect → Touchscreen While Driving"]],
    disclaimer: [entry, ["setting-startup-disclaimer.png", "Open Connect → Startup disclaimer"]],
    "startup-optimizations": [entry, ["setting-startup-optimizations.png", "Open Connect → Startup optimizations"]],
    "wireless-carplay": [entry, phone, wireless],
    "carplay-on-connection": [entry, phone,
      ["setting-show-carplay-on-connection.png", "CarPlay & Android Auto → Show CarPlay on connection"]],
    "android-auto": [entry, phone, ["setting-android-auto.png", "CarPlay & Android Auto → Android Auto"]],
    "wireless-setup": [entry, phone, wireless,
      ["wireless-enable.png", "Wireless CarPlay → Enable"],
      ["wireless-mode.png", "After a full restart: Devices → Wi-Fi → Apple CarPlay"]],
    "wireless-wifi": [["wireless-mode.png", "Devices → Wi-Fi → Apple CarPlay"]],
    "wireless-connect": [["wireless-mode.png", "First choose Apple CarPlay in Devices → Wi-Fi"]],
    services: [entry, audio, sources],
    "phone-connections": [entry, phone, wireless],
    "audio-sources": [entry, audio, sources],
    dvd: [entry, audio, sources],
    pandora: [entry, audio, ["setting-pandora.png", "Audio sources → Pandora"]],
    siriusxm: [entry, audio, ["setting-siriusxm.png", "Audio sources → SiriusXM"]],
    "developer-options": [entry, ["setting-developer-options.png", "Open Connect → Developer options"],
      ["developer-options.png", "Developer options"]],
    uninstall: [entry, ["setting-uninstall.png", "Open Connect → Uninstall"]],
    about: [entry, ["setting-about.png", "Open Connect → About"]],
    "version-info": [["settings-entry.png", "System tab → About (below Open Connect)"],
      ["version-info.png", "Version Information → OS Version"]],
  };
  const notes = {
    touchscreen: "Select Touchscreen While Driving, then choose Allow or Factory Default.",
    disclaimer: "Select Startup disclaimer, then choose Skip or Show.",
    "wireless-carplay": "Turn on Wireless CarPlay and confirm Enable. The screenshot shows it on; fresh installations leave it off unless factory enabled.",
    "carplay-on-connection": "Select Show CarPlay on connection, then choose Factory behavior or Automatically show. The screenshot shows the Factory default.",
    "android-auto": "Turn Android Auto on or off and confirm the change.",
    "startup-optimizations": "Turn Startup optimizations on or off and confirm the change. The screenshot shows it on; the fresh-install default is Off.",
    dvd: "Turn DVD on or off and confirm the change. Audio CDs are independent of DVD video support.",
    pandora: "Turn Pandora on or off and confirm the change. This controls Mazda’s integration, not Pandora through CarPlay or Bluetooth.",
    siriusxm: "Turn SiriusXM on or off and confirm the change. This controls satellite radio and SiriusXM data.",
    uninstall: "Select Uninstall and confirm Uninstall. Keep the car on until the automatic restart finishes.",
    about: "Select About to see the installed Open Connect version.",
    "wireless-connect": "After choosing Apple CarPlay here, return to Devices → Apple CarPlay, select your iPhone and choose Connect.",
  };
  const motion = matchMedia("(prefers-reduced-motion: reduce)");
  const panel = document.createElement("dialog");
  panel.className = "oc-nav-preview";
  panel.id = "oc-nav-preview";
  panel.setAttribute("aria-labelledby", "oc-nav-title");
  panel.setAttribute("aria-describedby", "oc-nav-step oc-nav-note");
  panel.innerHTML = `
    <div class="oc-nav-preview__header">
      <strong id="oc-nav-title">Navigation preview</strong>
      <button type="button" data-action="close" aria-label="Close navigation preview" autofocus>×</button>
    </div>
    <div class="oc-screen-frame"><img width="800" height="480" alt=""></div>
    <p id="oc-nav-step" aria-atomic="true"></p>
    <p id="oc-nav-note" class="oc-nav-preview__note" hidden></p>
    <div class="oc-nav-preview__controls">
      <button type="button" data-action="previous" aria-label="Previous step">←</button>
      <div class="oc-nav-preview__dots" role="group" aria-label="Choose a step"></div>
      <button type="button" data-action="next" aria-label="Next step">→</button>
      <button type="button" data-action="play"></button>
    </div>`;
  document.body.append(panel);
  const screen = panel.querySelector("img");
  const label = panel.querySelector("#oc-nav-step");
  const note = panel.querySelector("#oc-nav-note");
  const dots = panel.querySelector(".oc-nav-preview__dots");
  const play = panel.querySelector('[data-action="play"]');
  let trigger = null;
  let steps = [];
  let index = 0;
  let paused = false;
  let timer;
  let backdropPress = false;

  function playback() {
    clearTimeout(timer);
    const stopped = paused || steps.length < 2;
    play.textContent = stopped ? "Play" : "Pause";
    play.setAttribute("aria-label", stopped ? "Play automatic steps" : "Pause automatic steps");
    play.disabled = steps.length < 2;
    label.setAttribute("aria-live", paused || steps.length < 2 ? "polite" : "off");
    if (trigger && !paused && steps.length > 1 && !document.hidden) {
      timer = setTimeout(() => showStep(index + 1), 2200);
    }
  }

  function showStep(next) {
    index = (next + steps.length) % steps.length;
    screen.src = new URL(steps[index][0], assets).href;
    screen.alt = steps[index][1];
    label.setAttribute("aria-live", paused || steps.length < 2 ? "polite" : "off");
    label.textContent = `Step ${index + 1} of ${steps.length} — ${steps[index][1]}`;
    [...dots.children].forEach((dot, i) => {
      if (i === index) dot.setAttribute("aria-current", "step");
      else dot.removeAttribute("aria-current");
    });
    playback();
  }

  function close() {
    if (!trigger) return;
    const previous = trigger;
    trigger = null;
    clearTimeout(timer);
    panel.close();
    document.documentElement.classList.remove("oc-nav-modal-open");
    previous.setAttribute("aria-expanded", "false");
    previous.focus({ preventScroll: true });
  }

  function open(button) {
    trigger = button;
    paused = motion.matches;
    steps = paths[button.dataset.walkthrough];
    dots.replaceChildren();
    steps.forEach((step, i) => {
      const dot = document.createElement("button");
      dot.type = "button";
      dot.dataset.step = i;
      dot.setAttribute("aria-label", `Step ${i + 1}: ${step[1]}`);
      dots.append(dot);
      // Fetch only the active walkthrough, on demand.
      const image = new Image();
      image.src = new URL(step[0], assets).href;
    });
    note.textContent = notes[button.dataset.walkthrough] || "";
    note.hidden = !note.textContent;
    panel.querySelector('[data-action="previous"]').disabled = steps.length < 2;
    panel.querySelector('[data-action="next"]').disabled = steps.length < 2;
    button.setAttribute("aria-expanded", "true");
    showStep(0);
    document.documentElement.classList.add("oc-nav-modal-open");
    panel.showModal();
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
    else if (action === "play") { paused = !paused; playback(); }
    else {
      // A deliberate step selection stays put until the owner chooses Play.
      paused = true;
      if (action === "previous") showStep(index - 1);
      else if (action === "next") showStep(index + 1);
      else if (button.dataset.step !== undefined) showStep(Number(button.dataset.step));
    }
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
    if ((key === "ArrowRight" || key === "ArrowLeft") && !event.altKey && !event.ctrlKey && !event.metaKey) {
      event.preventDefault();
      event.stopPropagation();
      if (steps.length > 1) {
        paused = true;
        showStep(index + (key === "ArrowRight" ? 1 : -1));
      }
      return;
    }
    if (key === "Tab") {
      const controls = [...panel.querySelectorAll("button:not(:disabled)")];
      const first = controls[0];
      const last = controls[controls.length - 1];
      const idx = controls.indexOf(document.activeElement);
      if (event.shiftKey) {
        if (idx <= 0) {
          event.preventDefault();
          last.focus();
        }
      } else if (idx === -1 || idx === controls.length - 1) {
        event.preventDefault();
        first.focus();
      }
      event.stopPropagation();
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
  document.addEventListener("visibilitychange", playback);
  motion.addEventListener("change", () => { if (motion.matches) paused = true; playback(); });
})();
