        # Open Connect: a failed selection leaves Mazda's normal configuration.
        if timeout -t 25 sh -c '
            set -eu
            D=/tmp/mnt/data_persist/open-connect
            test -f "$D/record" && test ! -L "$D/record"
            test "$(wc -l < "$D/record")" -eq 1
            IFS="|" read -r format phase rev package rest < "$D/record"
            test "$format" = OC1 && test "${#package}" -eq 64
            case "$package" in *[!a-f0-9]*) exit 1;; esac
            P=$D/packages/$package
            test "$(readlink -f "$P")" = "$P"
            test -f "$P/files.sha256" && test ! -L "$P/files.sha256"
            digest=$(openssl dgst -sha256 < "$P/files.sha256")
            test "${digest##* }" = "$package"
            # Verify the entry and its directly sourced libraries before execution.
            # boot.sh checks the complete package once before any effects.
            for name in boot.sh state.sh firmware.sh transaction.sh; do
                digest=$(awk -v name="$name" '\''$2==name && NF==2 {n++;hash=$1} END{if(n!=1)exit 1;print hash}'\'' "$P/files.sha256")
                test "${#digest}" -eq 64
                case "$digest" in *[!a-f0-9]*) exit 1;; esac
                test -f "$P/$name" && test ! -L "$P/$name"
                actual=$(openssl dgst -sha256 < "$P/$name")
                test "${actual##* }" = "$digest"
            done
            exec sh "$P/boot.sh"
        '; then
            SMCFG_NORMALMODE=/tmp/open-connect/feature/sm.conf
            SMCFG_WCPMODE=/tmp/open-connect/feature/sm_WCP.conf
        fi
