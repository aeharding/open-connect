# SPDX-License-Identifier: AGPL-3.0-or-later
# Unmodified boot_render_profiles from e29b5825; shared by dev.19 and dev.20.
boot_render_profiles() {
    # This function runs from the verified target package, before prepare.
    local destination=$1 config=$2 source setting=off profile digest asset xml
    config_decode "$config" && test "$S_SCHEMA" = OC2 &&
        test "$P" = "$D/packages/$S_PACKAGE" || return 1
    source=$D/composed/$S_PACKAGE
    composed_members_verify "$source" && verify_manifest "$source" || return 1
    test "$S_WARNING" != 1 || setting=on
    set -- system-hook.js ui-profile.awk ui-modules.tsv
    if test "$S_BASE" = 1; then base_ui_inputs_verify || return 1; set -- "$@" base-logging.js; fi
    for asset in "$@"; do
        file "$P/$asset" || return 1
        digest=$(awk -v name="$asset" '$2==name{n++;print $1}END{exit n!=1}' "$P/files.sha256") || return 1
        test "$(sha "$P/$asset")" = "$digest" || return 1
    done
    # Saved originals are writable data. Render only a private copy whose bytes
    # still match the supported stock pin, not a hash-then-reopened pathname.
    xml=$destination/.mmui-source
    digest=$(original_files | awk '$2=="mmui.xml"{n++;print $1}END{exit n!=1}') || return 1
    file "$D/originals/mmui.xml" && cp "$D/originals/mmui.xml" "$xml" &&
        test "$(sha "$xml")" = "$digest" || return 1
    for asset in mmui plugins; do
        if test "$asset" = mmui; then profile=mmui.xml; else profile=vui-plugins.list; fi
        awk -v operation=compose -v ui_mode="$asset" -v modules="$P/ui-modules.tsv" \
            -v catalog="$P/services.tsv" -v catalog_bytes="$(wc -c < "$P/services.tsv")" \
            -v input="$config" -v input_bytes="$(wc -c < "$config")" \
            -f "$P/preferences.awk" -f "$P/ui-profile.awk" "$xml" > "$destination/$profile" || return 1
    done
    rm "$xml" || return 1
    if test "$S_BASE" = 1; then vui_inputs_verify "$destination/vui-plugins.list" || return 1; fi
    for profile in normal wcp; do
        awk -v operation=compose -v catalog="$P/services.tsv" -v catalog_bytes="$(wc -c < "$P/services.tsv")" -v input="$config" \
            -v input_bytes="$(wc -c < "$config")" -f "$P/preferences.awk" -f "$P/sm-profile.awk" \
            "$source/sm-$profile-$setting.conf" > "$destination/sm-$profile.conf" || return 1
    done
    # Keep the OEM script available through compatible-media purge and browser
    # reload. The authored override lives inside the already RAM-owned index.
    awk -v base="$S_BASE" -v warning="$S_WARNING" -v services="$S_SERVICES" -v autoshow="$S_AUTOSHOW" \
        -v hook="$P/system-hook.js" -v logger="$P/base-logging.js" '
        BEGIN {
            count=split(services,entries,",")
            for(i=1;i<=count;i++) {split(entries[i],pair,"=");choice[pair[1]]=pair[2]}
            if(base=="1") hidden="stitcher,dab,tv,aharadio,"
            if(choice["pandora"]=="0") hidden=hidden "pandora,"
            if(choice["siriusxm"]=="0") hidden=hidden "satradio,xmaudio,xmdata,"
            if(choice["dvd"]=="0") hidden=hidden "dvd,"
            aa_guard=(base=="1" && choice["android-auto"]=="0")
            if(aa_guard) hidden=hidden "androidauto,"
            sub(/,$/,"",hidden)
            needed=(warning=="1" || hidden!="")
        }
        base=="1" && /src="common\/js\/logDefaults[.]js"/ {
            print
            print "<script>"
            while((r=getline line < logger)>0)print line
            if(r<0)exit 1
            close(logger)
            print "</script>"
            logging++;next
        }
        /framework[.]init[(][)][;]/ {
          if(needed) {
            while((r=getline line < hook)>0) {
                if(index(line,"/* OPEN_CONNECT_AA_BEGIN */")) {aa_block=1;continue}
                if(index(line,"/* OPEN_CONNECT_AA_END */")) {aa_block=0;continue}
                if(!aa_guard && (aa_block || index(line,"/* OPEN_CONNECT_AA_CALL */"))) continue
                sub(/ \/[*] OPEN_CONNECT_AA_CALL [*]\//,"",line)
                if(index(line,"/*OPEN_CONNECT_APPLIED*/")) {
                    if(sub(/\/[*]OPEN_CONNECT_APPLIED[*]\//,warning ",\"" hidden "\"",line)!=1)exit 1
                    applied++
                }
                sub(/^[ \t]+/,"",line);print line
            }
            if(r<0)exit 1
            close(hook);hooked++
          }
          if(autoshow=="1") {
            print "</script>"
            print "<script src=\"file:///tmp/open-connect/feature/carplay.js\"></script>"
            print "<script>"
          }
        }
        {print}
        END {if((base=="1" && logging!=1) || (needed && (hooked!=1 || applied!=1)))exit 1}
    ' "$source/index-$setting.html" > "$destination/index.html" || return 1
    awk '{n+=gsub(/@TOKEN@/,"@TOKEN@")}END{exit n!=1}' "$destination/index.html"
}
