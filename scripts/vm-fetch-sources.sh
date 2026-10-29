#!/bin/bash
# Fetch the two large kernel trees as GitHub tarballs (git clone of them died with "invalid index-pack output").
set -o pipefail; cd ~/kb/src
get() { name=$1; url=$2; top=$3
  if [ -d "$name" ]; then echo "$name exists"; return; fi
  echo "[$(date -Is)] fetching $name"
  for i in 1 2 3 4 5; do curl -L --retry 5 --retry-all-errors -C - -o "$name.tgz" "$url" && break; sleep 10; done
  ls -la "$name.tgz"; mkdir -p "$name.tmp" && tar xzf "$name.tgz" -C "$name.tmp" && mv "$name.tmp"/* "$name" && rmdir "$name.tmp" && rm -f "$name.tgz"
  echo "[$(date -Is)] $name: $(find "$name" -type f | wc -l) files"
}
get zte-w205ds https://github.com/Ssrml/android_kernel_zte_ums9620_p720_w205ds/archive/refs/heads/master.tar.gz
get w200ds https://github.com/WiteTanuki/W200DS-SukiSU-Kernel/archive/refs/heads/main.tar.gz
(cd odin && git sparse-checkout set tools/mix4 kernel-patches configs 2>&1 | tail -1; ls)
ls -la ~/kb/src; echo "[$(date -Is)] FETCH DONE"
