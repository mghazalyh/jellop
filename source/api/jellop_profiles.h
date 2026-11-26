#pragma once
// Native per-user gateway settings; switching deliberately crosses a clean
// process boundary, not an in-place replacement of global credentials.
const char *jf_profile_url(int index);
int jf_profile_active(void);
bool jf_profile_set_url(int index,const char *url);
bool jf_profile_request(int index);
int jf_profile_requested(void);
void jf_profile_cancel(void);
bool jf_profile_schedule_switch(void);
const char *jf_profile_boot_target(void);
void jf_profile_login_completed(void);
