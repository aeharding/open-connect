
            "noLongerDisplayedFunction" : function(template) {
                // The stock Disclaimer displayed callback already owns this case.
                if (template === this._outgoingContextTemplate &&
                    this._currentContext && this._currentContext.ctxtId === "Disclaimer")
                    return;
                // GuiFramework has completed the incoming transition and hidden
                // outgoing native surfaces before calling this lifecycle hook.
                framework.sendEventToMmui("system", "DisposeIntroVideo");
            }.bind(this),
