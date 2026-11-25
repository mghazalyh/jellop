#!/usr/bin/env python3
"""Apply Jellop's initial delta to the pinned upstream tree; fail on drift."""
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
def edit(path, old, new, expected=1):
    f=root/path
    s=f.read_text(encoding="utf-8")
    if s.count(old)!=expected:
        raise RuntimeError(f"{path}: expected {expected} matches, got {s.count(old)}")
    f.write_text(s.replace(old,new),encoding="utf-8")

# Keep a distinct install identity and save identity. Do not download upstream
# updates into a derivative package. Preserve upstream notices and credits.
for folder in ("source","tests","tools","docs"):
    for f in (root/folder).rglob("*"):
        if not f.is_file() or f.suffix not in {".c",".cpp",".h",".inc",".py",".md",".xml",".txt",".sh",".S",".json",".host"}:
            continue
        if f.stat().st_size>8*1024*1024: continue
        try: s=f.read_text(encoding="utf-8")
        except UnicodeDecodeError: continue
        if "JFPS30000" in s:
            f.write_text(s.replace("JFPS30000","JELP30001"),encoding="utf-8")
edit("Makefile","APPID       := JFPS30000","APPID       := JELP30001")
edit("Makefile","TITLE       := JellyFin [PS]","TITLE       := Jellop")
edit("sfo.xml","JFPS30000","JELP30001")
edit("sfo.xml","JellyFin [PS]","Jellop")
edit("tools/verify_pkg.py",'"TITLE": "JellyFin [PS]"','"TITLE": "Jellop"')
edit("source/net/update_check.h",'#define UPDATE_REPO "jw-notes/JellyFin-PS3"','#define UPDATE_REPO "mghazalyh/jellop"')
edit("source/net/update_page.h",'github.com/jw-notes/JellyFin-PS3/releases','github.com/mghazalyh/jellop/releases')

# Bounded client state. 384 slots fit the known ~299-channel gateway catalogue.
# Preserve all 1080p decoder sizing and network safety from upstream.
edit("source/api/api_livetv.h","#define LIVETV_MAX_CHANNELS 700","#define LIVETV_MAX_CHANNELS 384")
edit("source/api/api_livetv.cpp","#define CHANNEL_PAGE   50","#define CHANNEL_PAGE   25")
edit("source/api/api_livetv.cpp","#define GUIDE_PAGE      8","#define GUIDE_PAGE      4")
edit("source/api/api_livetv.cpp","#define NUMBER_PAGE 200","#define NUMBER_PAGE 50")
edit("source/player/core/live_buffer.h","#define LIVE_RING_BYTES_MAX (10u * 1024u * 1024u)","#define LIVE_RING_BYTES_MAX (6u * 1024u * 1024u)")
# Programmes with no reliable UTC schedule can still show a current title.
# Store expiry separately from real schedule dates (8 bytes per channel).
edit("source/api/livetv.h","    uint64_t now_start_ticks, now_end_ticks;","    uint64_t now_start_ticks, now_end_ticks;\n    uint64_t now_evidence_expiry_ticks; // 0 for ordinary Jellyfin EPG")
edit("source/api/livetv.h","void livetv_sort_channels(JFChannel *c, int n);","void livetv_sort_channels(JFChannel *c, int n);\nbool livetv_current_title_valid(const JFChannel *c, uint64_t now);")
edit("source/api/livetv.cpp","            c->now_end_ticks   = time_field(cp, ce, \"EndDate\");",r'''            c->now_end_ticks   = time_field(cp, ce, "EndDate");
            const char *ev = find_top_value(cp, ce, "JealousfinProgramme");
            if (ev && *ev == '{') {
                const char *ee = object_end(ev, ce);
                char source[48] = "";
                if (ee) str_field(ev, ee, "source", source, sizeof source);
                const char *v = ee ? find_top_value(ev, ee, "observedAt") : NULL;
                long long observed = v ? read_json_int(v, ee, 0) : 0;
                int ttl = !strcmp(source, "provider-catalogue") ? 150 :
                          !strcmp(source, "corroborated-external-schedule") ? 1800 : 0;
                if (ttl && observed >= 946684800LL && observed <= 4102444800LL) {
                    c->now_evidence_expiry_ticks = jf_ticks_from_unix((uint64_t)observed + ttl);
                } else {
                    // Present but invalid evidence cannot be treated as a
                    // conventional, indefinitely cached programme.
                    c->now_title[0] = '\0';
                }
                const char prefix[] = "Scheduled: ";
                if (!strncmp(c->now_title, prefix, sizeof prefix - 1))
                    memmove(c->now_title, c->now_title + sizeof prefix - 1,
                            strlen(c->now_title + sizeof prefix - 1) + 1);
            }''')
edit("source/api/livetv.cpp","int livetv_parse_channels(const char *json, int len, JFChannel *out, int max,",r'''bool livetv_current_title_valid(const JFChannel *c, uint64_t now) {
    if (!c || !c->now_title[0] || !now) return false;
    if (c->now_evidence_expiry_ticks && now >= c->now_evidence_expiry_ticks) return false;
    if (c->now_start_ticks || c->now_end_ticks)
        return c->now_start_ticks <= now && now < c->now_end_ticks;
    return c->now_evidence_expiry_ticks != 0;
}

int livetv_parse_channels(const char *json, int len, JFChannel *out, int max,''')
edit("source/ui/xmb/ui_livetv.cpp","c->now_title[0] && c->now_start_ticks <= now && now < c->now_end_ticks","livetv_current_title_valid(c, now)")
# The title comes from server Name (including verified year), not local guessing.
# Current-only records have zero start/end, so no fake guide/progress bar.
