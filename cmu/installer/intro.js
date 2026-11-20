
            "contextInFunction" : function() {
                var app = this, fw = framework;
                if (app._openConnectIntroCleanup) { app._openConnectIntroCleanup(); }
                var original = fw._templateTransitionCompleteCallback, active = true;
                var local = Object.prototype.hasOwnProperty.call(fw, "_templateTransitionCompleteCallback");
                function stop() {
                    active = false;
                    if (fw._templateTransitionCompleteCallback === complete) {
                        if (local) { fw._templateTransitionCompleteCallback = original; }
                        else { delete fw._templateTransitionCompleteCallback; }
                    }
                    if (app._openConnectIntroCleanup === stop) { delete app._openConnectIntroCleanup; }
                }
                function complete() {
                    var incoming = fw._currTmpltInstance;
                    var changing = fw._frameworkState === fw._FWK_STATE_TMPLT_CHANGE;
                    var result = original.apply(this, arguments);
                    if (!active || !changing || !incoming || !incoming.contextInfo) { return result; }
                    var info = incoming.contextInfo;
                    if (info.uiaId === "system" &&
                        (info.ctxtId === "IntroAnimation" || info.ctxtId === "QuickStartLoop")) { return result; }
                    // The OEM callback has hidden outgoing native surfaces and
                    // displayed the incoming template. It need not own an Intro
                    // template for this boundary to occur.
                    stop();
                    if (info.uiaId !== "system" || info.ctxtId !== "Disclaimer") {
                        fw.sendEventToMmui("system", "DisposeIntroVideo");
                        fw.sendEventToMmui("system", "NotifyDisclaimerEnd");
                    }
                    return result;
                }
                app._openConnectIntroCleanup = stop;
                fw._templateTransitionCompleteCallback = complete;
            }.bind(this),
