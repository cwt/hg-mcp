#!/bin/bash
# Time test setup overhead

TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

echo "Creating test repo..."
time {
    hg init >/dev/null 2>&1
    cat > .hg/hgrc <<EOF
[ui]
username = Test <test@test.com>
[extensions]
EOF
    
    for i in 1 2 3 4 5; do
        echo "content $i" > file$i.txt
        hg add file$i.txt >/dev/null 2>&1
        hg commit -m "Commit $i" >/dev/null 2>&1
    done
    
    hg log -l 1 >/dev/null 2>&1
}

cd /home/cwt/Projects/hg-mcp
rm -rf "$TEMP_DIR"

echo ""
echo "Done! Above shows time for test fixture setup."
