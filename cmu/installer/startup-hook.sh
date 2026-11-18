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
            while read -r digest name extra; do
                test "${#digest}" -eq 64 && test -n "$name" && test -z "$extra"
                case "$digest" in *[!a-f0-9]*) exit 1;; esac
                case "$name" in .|..|*[!a-zA-Z0-9.-]*) exit 1;; esac
                test -f "$P/$name" && test ! -L "$P/$name"
                actual=$(openssl dgst -sha256 < "$P/$name")
                test "${actual##* }" = "$digest"
            done < "$P/files.sha256"
            exec sh "$P/boot.sh"
        '; then
            SMCFG_NORMALMODE=/tmp/open-connect/feature/sm.conf
        fi
