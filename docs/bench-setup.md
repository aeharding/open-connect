---
title: Wire a Mazda bench
hide:
  - navigation
  - toc
---

# Wire a Mazda bench

<div class="bench-guide">
<p class="bench-intro">2014–2016 Mazda3 · CMU, screen, commander and USB hub.<br>A silent development bench needs no TAU, amplifier or speakers.</p>

<nav class="bench-jumps" aria-label="Wiring guide sections">
<a href="#equipment">Equipment</a><a href="#pin-maps">Pin maps</a><a href="#power">Power</a><a href="#cables">Cables &amp; USB</a><a href="#first-boot">First boot</a>
</nav>

<section id="equipment" class="bench-section">
<div class="section-heading"><h2>What you'll need</h2></div>
<div class="kit-grid">
<section class="cable-card"><h3>Mazda hardware · one of each</h3>
<table class="kit-table" aria-label="Mazda parts and example part numbers"><tbody>
<tr><th scope="row">CMU</th><td><a href="https://static.nhtsa.gov/odi/tsbs/2018/MC-10134704-9999.pdf">BHP1-66-9C0N</a><small>2014–2016 Japan-built Mazda3, NA example</small></td></tr>
<tr><th scope="row">Display</th><td><a href="https://static.nhtsa.gov/odi/tsbs/2019/MC-10160602-0001.pdf">BHP1-61-1J0E</a></td></tr>
<tr><th scope="row">Commander</th><td><a href="https://www.mazdapartsnow.com/genuine/mazda~control-switch~bhn166cm0d">BHN1-66-CM0D</a></td></tr>
<tr><th scope="row">Stock USB hub</th><td><a href="https://mazda.oempartsonline.com/oem-parts/mazda-auxiliary-jack-bhp1669u0b">BHP1-66-9U0B</a></td></tr>
<tr><th scope="row">Plugs &amp; cables</th><td>Matching power plugs with wire tails, shielded display cable and hub data cable</td></tr>
</tbody></table>
<p>Ask the donor-parts seller to include the plugs and cables. These are sourcing examples; match connector shapes and check the CMU's firmware separately.</p>
</section>
<section class="cable-card"><h3>Power, computer &amp; tools</h3>
<table class="kit-table" aria-label="Bench equipment"><tbody>
<tr><th scope="row">12 V supply</th><td><a href="https://www.fnirsi.com/products/dps-150">FNIRSI DPS-150</a> + suitable input power source</td></tr>
<tr><th scope="row">USB UART</th><td><a href="https://www.sparkfun.com/sparkfun-ftdi-basic-breakout-3-3v.html">SparkFun FTDI Basic 3.3 V · DEV-09873</a> + Mini-B data cable</td></tr>
<tr><th scope="row">ACC control</th><td>Manual switch, or <a href="https://robiz.net/en-gb/rmt/lcus1channeltypec">USB-C LCUS-1 relay</a> + data cable</td></tr>
<tr><th scope="row">Wiring tools</th><td>Inline fuse/holder, wire, insulated connectors, crimper and multimeter</td></tr>
<tr><th scope="row">Computer</th><td>Linux or macOS; USB ports for UART and optional power controls</td></tr>
</tbody></table>
<p>Use only UART TX, RX and GND. Keep the SparkFun board at 3.3 V; its power and handshake pins stay disconnected.</p>
</section>
</div>
<p class="kit-options"><strong>Optional:</strong> USB Ethernet adapter + network cable; camera for recordings; Micro-USB data cable for DPS150 control.</p>
<details class="bench-detail"><summary>CarPlay hub instead of the stock hub</summary>
<p>OEM references: <a href="https://www.mazdaswag.com/oem-parts/mazda-genuine-oem-mazda-android-apple-car-play-auxiliary-unit-c922-v6-605a-required-for-installation-tk78669u0e">TK78-66-9U0E hub</a> (replaces C/D revisions) and <a href="https://www.mazdapartsfactor.com/oem-parts/mazda-smartphone-screen-mirroring-kit-c922v6605a">C922-V6-605A cable kit</a>. Aftermarket kits often use these reference numbers; that does not make them OEM.</p>
<p>Upgrade to compatible firmware <strong>before</strong> connecting the retrofit hub. Use the stock hub for a v55 bench; our incoming aftermarket kit is not yet qualified.</p>
</details>
</section>

<section id="pin-maps" class="bench-section">
<div class="section-heading"><span class="step-number">01</span><h2>Find the pins</h2></div>
<div class="view-rule"><strong>WIRE-ENTRY VIEW ONLY</strong><span>Look at the back of the loose harness plug, where the wires enter. Hold the latch up.</span></div>
<div class="pin-legend" aria-label="Pin color legend">
<span class="batt">B+ · constant 12 V</span><span class="acc">ACC · switched 12 V</span><span class="ground">GND · common return</span><span class="lin">LIN · commander</span><span class="uart">UART · serial</span><span class="unused">Unused</span>
</div>
<p class="legend-note">Colors identify signals, not wire insulation. Match the plug's keys and terminal labels.</p>
<div class="connector-grid">
<section class="connector-card"><header><h3>CMU</h3><p>Blue 18-way · connector 2</p></header>
<div class="connector-view"><span class="latch"><svg class="wire-entry-icon" viewBox="0 0 48 38" aria-hidden="true" focusable="false"><rect x="7" y="4" width="34" height="21" rx="3"/><path d="M19 4V1h10v3"/><circle cx="15" cy="14" r="2"/><circle cx="24" cy="14" r="2"/><circle cx="33" cy="14" r="2"/><path class="entry-wires" d="M15 14v10c0 6-5 7-8 11M24 14v21M33 14v10c0 6 5 7 8 11"/></svg>WIRE ENTRY · LATCH UP ↑</span>
<table class="pin-map" aria-label="CMU: wire-entry side, latch up"><tbody>
<tr><td class="pin uart">2S</td><td class="pin acc">2Q</td><td class="pin unused">2O</td><td class="pin unused">2M</td><td class="pin lin">2K</td><td class="pin unused">2I</td><td class="pin unused">2G</td><td class="pin unused">2E</td><td class="pin ground">2C</td><td class="pin unused">2A</td></tr>
<tr><td class="pin uart">2T</td><td class="pin batt">2R</td><td class="pin unused">2P</td><td class="pin key">key</td><td class="pin ground">2L</td><td class="pin unused">2J</td><td class="pin key">key</td><td class="pin unused">2F</td><td class="pin ground">2D</td><td class="pin unused">2B</td></tr>
</tbody></table></div>
<dl class="pin-connections">
<div><dt class="batt">B+</dt><dd>2R</dd></div>
<div><dt class="acc">ACC</dt><dd>2Q</dd></div>
<div><dt class="ground">GND</dt><dd>2C · 2D · 2L</dd></div>
<div><dt class="lin">LIN</dt><dd>2K → commander E</dd></div>
<div><dt class="uart">UART TX</dt><dd>2S → adapter RX</dd></div>
<div><dt class="uart">UART RX</dt><dd>2T ← adapter TX</dd></div>
</dl><p class="card-note">Hatched gaps are keys, not terminals. Leave other wires isolated.</p></section>
<section class="connector-card"><header><h3>USB hub</h3><p>Large 12-way · power / AUX plug</p></header>
<div class="connector-view"><span class="latch"><svg class="wire-entry-icon" viewBox="0 0 48 38" aria-hidden="true" focusable="false"><rect x="7" y="4" width="34" height="21" rx="3"/><path d="M19 4V1h10v3"/><circle cx="15" cy="14" r="2"/><circle cx="24" cy="14" r="2"/><circle cx="33" cy="14" r="2"/><path class="entry-wires" d="M15 14v10c0 6-5 7-8 11M24 14v21M33 14v10c0 6 5 7 8 11"/></svg>WIRE ENTRY · LATCH UP ↑</span>
<table class="pin-map" aria-label="USB hub: wire-entry side, latch up"><tbody>
<tr><td class="pin acc">1K</td><td class="pin unused">1I</td><td class="pin unused">1G</td><td class="pin unused">1E</td><td class="pin unused">1C</td><td class="pin ground">1A</td></tr>
<tr><td class="pin batt">1L</td><td class="pin ground">1J</td><td class="pin unused">1H</td><td class="pin unused">1F</td><td class="pin unused">1D</td><td class="pin unused">1B</td></tr>
</tbody></table></div>
<dl class="pin-connections">
<div><dt class="batt">B+</dt><dd>1L</dd></div>
<div><dt class="acc">ACC</dt><dd>1K</dd></div>
<div><dt class="ground">GND</dt><dd>1A · 1J</dd></div>
</dl><p class="card-note">Keep the matching pigtail. Do not add contacts to factory-empty cavities.</p></section>
<section class="connector-card"><header><h3>Commander</h3><p>8-way · rotary controller</p></header>
<div class="connector-view"><span class="latch"><svg class="wire-entry-icon" viewBox="0 0 48 38" aria-hidden="true" focusable="false"><rect x="7" y="4" width="34" height="21" rx="3"/><path d="M19 4V1h10v3"/><circle cx="15" cy="14" r="2"/><circle cx="24" cy="14" r="2"/><circle cx="33" cy="14" r="2"/><path class="entry-wires" d="M15 14v10c0 6-5 7-8 11M24 14v21M33 14v10c0 6 5 7 8 11"/></svg>WIRE ENTRY · LATCH UP ↑</span>
<table class="pin-map" aria-label="Commander: wire-entry side, latch up"><tbody>
<tr><td class="pin ground">G</td><td class="pin lin">E</td><td class="pin unused">C</td><td class="pin acc">A</td></tr>
<tr><td class="pin unused">H</td><td class="pin unused">F</td><td class="pin unused">D</td><td class="pin unused">B</td></tr>
</tbody></table></div>
<dl class="pin-connections">
<div><dt class="acc">ACC</dt><dd>A</dd></div>
<div><dt class="ground">GND</dt><dd>G</dd></div>
<div><dt class="lin">LIN</dt><dd>E → CMU 2K</dd></div>
</dl><p class="card-note">One LIN wire carries the controls. B and H are unused lighting connections.</p></section>
<section class="connector-card"><header><h3>Display</h3><p>8-way · power plug at the screen</p></header>
<div class="connector-view"><span class="latch"><svg class="wire-entry-icon" viewBox="0 0 48 38" aria-hidden="true" focusable="false"><rect x="7" y="4" width="34" height="21" rx="3"/><path d="M19 4V1h10v3"/><circle cx="15" cy="14" r="2"/><circle cx="24" cy="14" r="2"/><circle cx="33" cy="14" r="2"/><path class="entry-wires" d="M15 14v10c0 6-5 7-8 11M24 14v21M33 14v10c0 6 5 7 8 11"/></svg>WIRE ENTRY · LATCH UP ↑</span>
<table class="pin-map" aria-label="Display: wire-entry side, latch up"><tbody>
<tr><td class="pin acc">1G</td><td class="pin unused">1E</td><td class="pin unused">1C</td><td class="pin unused">1A</td></tr>
<tr><td class="pin batt">1H</td><td class="pin unused">1F</td><td class="pin unused">1D</td><td class="pin ground">1B</td></tr>
</tbody></table></div>
<dl class="pin-connections">
<div><dt class="batt">B+</dt><dd>1H</dd></div>
<div><dt class="acc">ACC</dt><dd>1G</dd></div>
<div><dt class="ground">GND</dt><dd>1B</dd></div>
</dl><p class="card-note">This is the screen's 8-way plug, not a 4-way inline adapter. Keep its data cable intact.</p></section>
</div>
</section>

<section id="power" class="bench-section">
<div class="section-heading"><span class="step-number">02</span><h2>Wire three power rails</h2></div>
<p>Join each pin above to its matching rail. All grounds share the supply's negative terminal.</p>
<div class="power-drawing">
<svg viewBox="0 0 1000 230" role="img" aria-labelledby="power-title power-desc">
<title id="power-title">Bench power: fused B+, switched ACC and common ground</title>
<desc id="power-desc">Supply positive passes through a fuse to the B+ rail. A branch after the fuse passes through a manual ACC switch or the COM and NO contacts of a USB relay. Supply negative connects directly to the common ground rail.</desc>
<g class="wire batt"><path d="M90 52 H205 M275 52 H944"/><circle cx="90" cy="52" r="5"/><circle cx="370" cy="52" r="5"/></g>
<rect x="205" y="36" width="70" height="32" rx="3" class="fuse"/>
<text x="240" y="24" text-anchor="middle">Fuse</text><text x="32" y="57">+</text>
<text x="405" y="40" class="rail-label batt">B+ · stays powered</text>
<g class="wire acc"><path d="M370 52 V128 H494 M556 128 H944"/><circle cx="494" cy="128" r="4"/><circle cx="556" cy="128" r="4"/><path d="M494 128 L548 99"/></g>
<text x="525" y="163" text-anchor="middle">ACC switch / relay</text><text x="622" y="116" class="rail-label acc">ACC · on / off</text>
<g class="wire ground"><path d="M90 203 H944"/><circle cx="90" cy="203" r="5"/></g>
<text x="32" y="208">−</text><text x="405" y="192" class="rail-label ground">GND · common return</text>
<text x="32" y="104" class="small-label">12 V DC</text><text x="32" y="125" class="small-label">supply</text>
</svg>
</div>
<div class="network-route relay-note">
<h3>Computer-controlled ACC</h3>
<p>For automated testing, use a USB serial relay such as a <a href="https://ae01.alicdn.com/kf/S61b00d8484144b179c33e457e19f6f16l.pdf">USB-C LCUS-1</a> in the switch position above.</p>
<p><strong>Fused B+ → COM</strong> · <strong>NO → ACC rail</strong> · <strong>NC → leave unused</strong><br>Computer USB → relay USB-C for power and control.</p>
<span>Follow the board's terminal labels; COM carries +12 V here, not ground. The relay switches ACC while B+ stays on. This option is not yet bench-tested; verify its power-up behavior before unattended use.</span>
</div>
<div class="short-notes"><p><strong>Before connecting:</strong> power off; verify nominal 12 V with modules disconnected; fit an inline fuse sized for the harness.</p><p><strong>Normal shutdown:</strong> ACC off first, with B+ retained. Turning the supply output off is a full power cut.</p></div>
</section>

<section id="cables" class="bench-section">
<div class="section-heading"><span class="step-number">03</span><h2>Connect the cables</h2></div>
<div class="cable-grid">
<section class="cable-card"><h3>Screen</h3>
<div class="cable-route"><span>CMU</span><b>↔</b><span>Display</span></div>
<p>Use the matching shielded display cable. The screen also needs its power plug from the pin map above.</p>
</section>
<section class="cable-card"><h3>UART · 3.3 V TTL</h3>
<dl class="wire-list"><div><dt>CMU 2S · TX</dt><dd>→ Adapter RX</dd></div><div><dt>CMU 2T · RX</dt><dd>← Adapter TX</dd></div><div><dt>Common ground</dt><dd>↔ Adapter GND</dd></div></dl>
<p>Adapter USB → computer. Leave VCC, RTS, CTS and DTR disconnected.</p>
</section>
<section class="cable-card"><h3>CarPlay retrofit hub</h3>
<dl class="wire-list"><div><dt>CMU gray/green end</dt><dd>↔ Hub black socket</dd></div><div><dt>CMU gray/blue end</dt><dd>↔ Hub brown socket</dd></div></dl>
<p>Keep both supplied keyed cables and the large power plug. Colors refer to cable-end housings.</p>
</section>
<section class="cable-card"><h3>DPS150 USB control</h3>
<div class="cable-route"><span>Computer USB</span><b>↔</b><span>DPS150 Micro-USB</span></div>
<p>Use a data cable. This control connection is separate from the supply's USB-C/DC power input and its +/− outputs.</p>
</section>
</div>
<div class="network-route"><h3>Optional Ethernet</h3><p>Hub's front USB data port <b>→</b> USB Ethernet adapter <b>→</b> router / switch <b>→</b> computer</p><span>Adapter driver support and SSH access must be checked separately.</span></div>
<details class="bench-detail"><summary>Stock USB hub, firmware and supply notes</summary>
<ul>
<li><strong>Stock hub:</strong> use its original keyed USB cable instead of the two retrofit cables. Keep the power plug.</li>
<li><strong>CarPlay hub:</strong> requires compatible CMU firmware before installation. Our v55 bench has not qualified the incoming aftermarket hub or Ethernet adapter.</li>
<li><strong>DPS150 input:</strong> it is step-down only. Use a supported PD/QC or DC source above 12 V; an ordinary 5 V USB supply is insufficient. Use one power input at a time.</li>
<li><strong>Existing lab:</strong> leave its verified DPS150 voltage setting unchanged. ACC switching is planned; full-output power control is already working.</li>
</ul>
</details>
</section>

<section id="first-boot" class="bench-section">
<div class="section-heading"><span class="step-number">04</span><h2>First boot</h2></div>
<ol class="boot-steps"><li><strong>Open UART</strong><span>115200 baud · 8N1<br>No flow control · RTS/DTR off</span></li><li><strong>Enable B+</strong><span>Supply output on.<br>Start with ACC off.</span></li><li><strong>Switch ACC on</strong><span>Watch the serial log<br>and the display.</span></li><li><strong>Wait for startup</strong><span>Don't type during<br>the bootloader countdown.</span></li></ol>
<details class="bench-detail"><summary>Show the serial-terminal commands</summary>
<p>Install the <a href="development.md">host tools</a>, then find the adapter's actual port.</p>
<pre><code>python -m serial.tools.list_ports -v
python -m serial.tools.miniterm --rts 0 --dtr 0 --eol CR UART_PORT 115200</code></pre>
<p>Replace UART_PORT with your adapter. Exit with <strong>Ctrl+]</strong> before using <a href="cli.md">oc commands</a>; only one program can own the port.</p>
</details>
<p class="next-link">Once it boots: <a href="cli.md">use the CLI and enable the silent Entertainment profile →</a></p>
</section>

<details class="bench-detail bench-sources"><summary>Sources &amp; connector reference notes</summary>
<p>Wire-entry orientation follows <a href="https://mazda3.neocities.org/esicont/srvc/html/id000000800400">Mazda's harness-side viewing convention</a>. These are terminal maps, not scale drawings. Leave unused wires individually insulated; depinning is unnecessary.</p>
<ul>
<li><a href="https://mazda3.neocities.org/esicont/srvc/html/id0902n7103100">CMU / commander / LIN</a> · <a href="https://mazda3.neocities.org/esicont/srvc/html/id0902n7103400">Display power</a> · <a href="https://mazda3.neocities.org/esicont/srvc/html/id0902n7103500">Display data</a> · <a href="https://mazda3.neocities.org/esicont/srvc/html/id0902n7106800">CMU ACC</a></li>
<li><a href="https://www.scribd.com/document/796872875/New-Model-Mazda3-Bm">Mazda3 TN-M3-1311 terminal tables</a>, sections 09-33, 09-83, 09-89 and 09-93.</li>
<li><a href="https://www.mx5manual.com/assets/service_manuals/en_us/2016/MX5/pdf/0920_2b.pdf">Hub connector 0920-206A</a>, PDF page 2: shared connector cross-check from Mazda's 2016 MX-5 manual. Aftermarket internal wiring remains unverified.</li>
<li><a href="https://mazdaparts.org/content/MAZDA3SCREENMIRRORC922V6605.pdf">Mazda C922 V6 605 retrofit instructions</a>, Common-4: cable routing. <a href="https://mazda3.neocities.org/esicont/srvc/html/id0902n7105300">Stock USB data</a> · <a href="https://mazda3.neocities.org/esicont/srvc/html/id0902n7105100">Stock USB power</a>.</li>
<li><a href="https://github.com/silverchris/mazda-cmu-documentation/blob/gh-pages/hardware.md#connectors">UART terminal functions</a>, also established on our bench; <a href="https://ftdichip.com/wp-content/uploads/2020/08/DS_FT232R.pdf">FTDI I/O levels</a>.</li>
<li><a href="https://www.100y.com.tw/pdf_file/57-LCUS-1.pdf">LC Technology LCUS-1 manual</a>: isolated relay contacts and USB serial control. The linked <a href="https://ae01.alicdn.com/kf/S61b00d8484144b179c33e457e19f6f16l.pdf">USB-C product sheet</a> describes a CH340 variant; use the actual board labels.</li>
<li>FNIRSI: <a href="https://www.fnirsi.com/pages/software-downloads">DPS150 USB control</a> · <a href="https://www.fnirsi.com/products/dps-150">power inputs and step-down requirement</a>.</li>
</ul>
</details>
</div>
