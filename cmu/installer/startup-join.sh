        # Open Connect: finish the sole selector before board detection or SM.
        if test -n "${oc_pid:-}"; then
            oc_join_entered=; oc_join_returned=
            read -r oc_join_entered oc_idle < /proc/uptime || oc_join_entered=
            oc_wait_worker
            read -r oc_join_returned oc_idle < /proc/uptime || oc_join_returned=
            # G permitted overlap only. The exit result permits selection.
            case "$oc_result" in 0|2) ;; *) oc_result=1;; esac
            oc_finish_selection
            # Diagnostic writes never turn a completed selection into failure.
            if test -f /tmp/open-connect/startup-times && test ! -L /tmp/open-connect/startup-times; then
                if test -n "$oc_oem_start" && test -n "$oc_join_entered" && test -n "$oc_join_returned"; then
                    printf 'oem_window_start|%s\njoin_entered|%s\njoin_returned|%s\n' \
                        "$oc_oem_start" "$oc_join_entered" "$oc_join_returned" >> /tmp/open-connect/startup-times || :
                fi
            fi
        fi
