/* Installed on this Utility instance before the OEM framework starts. */
(function (load) {
    if (typeof load !== "function") {
        throw new Error("Open Connect: unsupported script loader");
    }
    utility.loadScript = function (url, attributes, callback) {
        if (url === "apps/system/js/systemApp.js") {
            url = @SYSTEM_APP@;
        }
        return load.call(this, url, attributes, callback);
    };
}(utility.loadScript));
