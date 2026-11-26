#include "jellop_profiles.h"
#include "profile_model.h"
#include "jellyfin_api.h"
#include "jf_paths.h"
#include "user_prefs.h"
#include "plog.h"

extern bool jf_login_resave(void);
namespace {
const char *const filename="jellop_profiles.txt";
JellopProfiles profiles=profile_default();
bool loaded=false;
int requested=-1;

void load() {
    if(loaded)return;
    loaded=true;
    FILE *f=fopen(jf_data_path(filename),"rb");
    if(!f)return;
    char text[560];
    size_t n=fread(text,1,sizeof text,f);
    bool ok=!ferror(f)&&n<sizeof text&&!memchr(text,0,n);
    fclose(f);
    if(ok){text[n]=0;ok=profile_parse(text,&profiles);}
    if(!ok)plog("profiles: invalid settings ignored");
}

bool write(const JellopProfiles &value) {
    char text[560],path[192],tmp[208];
    int n=profile_format(&value,text,sizeof text);
    if(n<0)return false;
    int size=snprintf(path,sizeof path,"%s",jf_data_path(filename));
    if(size<0||size>=(int)sizeof path)return false;
    size=snprintf(tmp,sizeof tmp,"%s.tmp",path);
    if(size<0||size>=(int)sizeof tmp)return false;
    // No concurrent preference bundle reader may see a half-written file.
    user_prefs_save_join();
    FILE *f=fopen(tmp,"wb");
    if(!f)return false;
    bool ok=fwrite(text,1,(size_t)n,f)==(size_t)n&&fflush(f)==0;
    if(fclose(f)!=0)ok=false;
    if(ok&&rename(tmp,path)==0){profiles=value;return true;}
    remove(tmp);plog("profiles: atomic settings write failed");return false;
}
}

const char *jf_profile_url(int index) {
    load();return index>=0&&index<2?profiles.url[index]:"";
}
int jf_profile_active(void) {
    load();return profile_active(&profiles,g_server);
}
bool jf_profile_set_url(int index,const char *url) {
    load();
    if(index<0||index>1)return false;
    JellopProfiles next=profiles;
    if(!profile_normalize_url(url,next.url[index],sizeof next.url[index]))return false;
    if(next.pending==index)next.pending=-1;
    if(!profile_valid(&next)||!write(next))return false;
    user_prefs_save_async();
    return true;
}
bool jf_profile_request(int index) {
    load();requested=-1;
    if(index<0||index>1||!profiles.url[index][0]||jf_profile_active()==index)return false;
    requested=index;return true;
}
int jf_profile_requested(void) {return requested;}
void jf_profile_cancel(void) {requested=-1;}
bool jf_profile_schedule_switch(void) {
    load();
    if(requested<0||requested>1||!profiles.url[requested][0])return false;
    JellopProfiles previous=profiles,next=profiles;
    next.pending=requested;
    if(!write(next))return false;
    // On systems with per-user saves, do not close the application unless
    // the actual saved-data write is confirmed. Legacy fallback uses the
    // atomic on-disk file, exactly like the existing settings.
    if(user_prefs_active()&&!jf_login_resave()){
        if(!write(previous))plog("profiles: failed to roll back pending switch");
        return false;
    }
    requested=-1;
    plog("profiles: gateway switch saved for clean relaunch");
    return true;
}
const char *jf_profile_boot_target(void) {
    load();return profiles.pending>=0?profiles.url[profiles.pending]:"";
}
void jf_profile_login_completed(void) {
    load();
    if(profiles.pending<0)return;
    JellopProfiles next=profiles;next.pending=-1;
    if(!write(next))plog("profiles: could not clear pending switch");
}
