#pragma once
#include "json_lite.h"

struct ViewsCursor { const char *p,*end; bool first; };
struct ViewFields { char collection_type[32],id[64],name[40]; };

static inline bool views_begin(const char *json,ViewsCursor *cursor){
    if(!json||!cursor)return false;
    const char *limit=json+strlen(json),*root=skip_ws(json,limit);
    const char *end=object_end(root,limit);
    if(!end||skip_ws(end,limit)!=limit)return false;
    const char *items=find_top_value(root,end,"Items");
    if(!items||items>=end||*items!='[')return false;
    cursor->p=items+1;cursor->end=end;cursor->first=true;return true;
}

// 1 = row, 0 = complete, -1 = malformed. No heap or input mutation.
static inline int views_next(ViewsCursor *cursor,ViewFields *out){
    if(!cursor||!out||!cursor->p)return -1;
    const char *end=cursor->end,*p=skip_ws(cursor->p,end);
    if(p>=end)return -1;
    if(*p==']'){cursor->p=p;return 0;}
    if(!cursor->first){
        if(*p!=',')return -1;
        p=skip_ws(p+1,end);
    }
    const char *e=object_end(p,end);
    if(!e)return -1;
    memset(out,0,sizeof *out);
    const char *value=find_top_value(p,e,"CollectionType");
    if(value&&!read_json_string(value,e,out->collection_type,sizeof out->collection_type))return -1;
    value=find_top_value(p,e,"Id");
    if(value&&!read_json_string(value,e,out->id,sizeof out->id))return -1;
    value=find_top_value(p,e,"Name");
    if(value&&!read_json_string(value,e,out->name,sizeof out->name))return -1;
    cursor->p=e;cursor->first=false;return 1;
}
