/* SPDX-License-Identifier: AGPL-3.0-or-later */
(() => {
  "use strict";

  // Resolve from this file, including on nested pages and GitHub Pages subpaths.
  const assets = new URL("../assets/guide/", document.currentScript.src);
  const entry = ["settings-entry.png", "System tab → Open Connect"];
  const settings = ["settings.png", "Open Connect settings"];
  const paths = {
    "open-connect": [entry, settings],
    touchscreen: [entry, settings, ["touch.png", "Touchscreen While Driving → Allow"]],
    disclaimer: [entry, settings, ["warning.png", "Startup disclaimer → Skip"]],
    "wireless-setup": [entry, settings,
      ["wireless-enable.png", "Wireless CarPlay → Enable"],
      ["wireless-mode.png", "After a full restart: Devices → Wi-Fi → Apple CarPlay"]],
    "wireless-wifi": [["wireless-mode.png", "Devices → Wi-Fi → Apple CarPlay"]],
    "wireless-connect": [["wireless-mode.png", "First choose Apple CarPlay in Devices → Wi-Fi"]],
    services: [entry, settings, ["services.png", "Services"]],
    "developer-options": [entry, settings, ["developer-options.png", "Developer options"]],
    uninstall: [entry, settings, ["uninstall.png", "Uninstall confirmation"]],
    "version-info": [["settings-entry.png", "System tab → About (below Open Connect)"],
      ["version-info.png", "Version Information → OS Version"]],
  };
  const notes = {
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
  panel.addEventListener("keydown", event => {
    if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      event.preventDefault();
      paused = true;
      showStep(index + (event.key === "ArrowRight" ? 1 : -1));
    } else if (event.key === "Tab") {
      const controls = [...panel.querySelectorAll("button:not(:disabled)")];
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && event.target === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && event.target === last) {
        event.preventDefault();
        first.focus();
      }
    }
  });
  document.addEventListener("visibilitychange", playback);
  motion.addEventListener("change", () => { if (motion.matches) paused = true; playback(); });
})();
