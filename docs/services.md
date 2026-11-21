# Services

The **Services** page is under **Mazda Settings → System → Open Connect**.
Its first development control is **Pandora**, which defaults to **on**.
This controls Mazda's built-in Pandora integration.

Clear the checkbox to stop that integration from loading. The confirmation
explains that changes apply after restarting Mazda Connect. Switching ignition
off and immediately on may resume the existing session; let it shut down fully.
Updating preserves the selection. Uninstall restores the pre-install startup
configuration.

The setting changes Open Connect's selected RAM service configuration before
Mazda's service manager starts. It does not hot-stop or hot-restart the service,
and does not edit Mazda's original service configuration files.

Other service choices and a Base optimizations bundle remain under investigation.
They are not a preset purge: Aha, for example, has declared consumers in Wi-Fi,
voice and other startup stages. See [performance evidence](performance.md) and
the [service-manager findings](reverse-engineering.md#service-manager-dependencies-and-pandora-restart).

This is a development candidate. Bench startup, resource, UI and restoration
qualification must be recorded before treating the new control as supported;
the owner's deferred physical-input/audio and first-car checks remain separate.
