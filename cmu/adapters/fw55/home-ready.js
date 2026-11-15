/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Firmware55 Home-only readiness probe. Install before GuiFramework construction.
 * This reports a completed OEM transition and a later visible DOM observation,
 * not compositor pixels, every app's health, or permission to renew retries.
 */
(function (prototype, report) {
    var original = prototype._templateTransitionCompleteCallback;
    var reported = false;
    var session = window.openConnectStartupSession;
    var acknowledgementImage = null;
    try {
        log.jciLogger.JCILog("framework ERROR oc_ready.js[1] OCRENDER|@GENERATION@|probe-loaded");
    } catch (ignored) {} // The acknowledgement must not depend on logging.

    if (typeof original !== "function") {
        throw new Error("Open Connect: unsupported transition callback");
    }

    function inspect(fw, template, snapshot) {
        if (!template || fw._currTmpltInstance !== template ||
            fw._frameworkState !== fw._FWK_STATE_IDLE || !fw._browserShown ||
            !template.contextInfo || template.contextInfo.uiaId !== "system" ||
            template.contextInfo.ctxtId !== "HomeScreen" ||
            !snapshot || snapshot.uiaId !== "system" || snapshot.ctxtId !== "HomeScreen" ||
            template.contextInfo.contextSeq !== snapshot.contextSeq) {
            return false;
        }
        var node = template.divElt;
        if (!node || typeof node.getBoundingClientRect !== "function") {
            return false;
        }
        var rect = node.getBoundingClientRect();
        if (!(rect.right > rect.left && rect.bottom > rect.top &&
              rect.right > 0 && rect.bottom > 0 &&
              rect.left < window.innerWidth && rect.top < window.innerHeight)) {
            return false;
        }
        while (node && node.nodeType === 1) {
            var style = window.getComputedStyle(node, null);
            if (!style || style.display === "none" || style.visibility !== "visible" ||
                Number(style.opacity) !== 1) {
                return false;
            }
            if (node === document.body) {
                return true;
            }
            node = node.parentNode;
        }
        return false;
    }

    function eligible(fw, template, snapshot) {
        try {
            return inspect(fw, template, snapshot);
        } catch (error) {
            // Observability must not break the OEM callback or pretend to be ready.
            return false;
        }
    }

    function acknowledge() {
        try { report(); } catch (ignored) {}
        try {
            if (session && session.port === Math.floor(session.port) &&
                session.port >= 1024 && session.port <= 65535 &&
                typeof session.token === "string" &&
                /^@GENERATION@\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(session.token)) {
                // Keep the request alive. HTTP receipt, not image decoding, is the signal.
                acknowledgementImage = new Image();
                acknowledgementImage.onload = acknowledgementImage.onerror = function () {
                    acknowledgementImage = null;
                };
                acknowledgementImage.src = "http://127.0.0.1:" + session.port + "/" + session.token;
            }
        } catch (error) {
            // Transport failure must not escape into the OEM event loop.
            try {
                log.jciLogger.JCILog("framework ERROR oc_ready.js[1] OCRENDER|@GENERATION@|transport-error|" + String(error));
            } catch (ignored) {}
        }
    }

    prototype._templateTransitionCompleteCallback = function () {
        var fw = this;
        var template = fw._currTmpltInstance;
        var context = template && template.contextInfo;
        var snapshot = context ? {uiaId: context.uiaId, ctxtId: context.ctxtId,
            contextSeq: context.contextSeq} : null;
        var wasTransition = fw._frameworkState === fw._FWK_STATE_TMPLT_CHANGE;
        var result = original.apply(fw, arguments);
        if (!reported && wasTransition && snapshot &&
            snapshot.uiaId === "system" && snapshot.ctxtId === "HomeScreen") {
            // Completion can precede the final fade. Sample 40 times, nominally two seconds;
            // require two stable samples, never waive the identity/visibility checks.
            var remaining = 40, stable = 0;
            function sample() {
                if (reported) { return; }
                stable = eligible(fw, template, snapshot) ? stable + 1 : 0;
                if (stable === 2) {
                    reported = true;
                    acknowledge();
                } else if (--remaining > 0) {
                    setTimeout(sample, 50);
                }
            }
            setTimeout(sample, 50);
        }
        return result;
    };
}(GuiFramework.prototype, function () {
    log.jciLogger.JCILog("framework ERROR oc_ready.js[1] OCRENDER|@GENERATION@|HomeScreen");
}));
