/* SPDX-License-Identifier: AGPL-3.0-or-later */
(function (load) {
    utility.loadScript = function (url, attributes, callback) {
        if (url === "apps/system/js/systemApp.js") {
            url = "file:///tmp/open-connect/feature/system-app.js";
        }
        return load.call(this, url, attributes, callback);
    };
}(utility.loadScript));
