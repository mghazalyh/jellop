#pragma once
#include <stddef.h>
#include <stdio.h>
#include <string.h>

// Two bounded gateway endpoints. No passwords or access tokens are stored here.
// Pending is an explicit switch on the next clean application launch.
struct JellopProfiles {
    char url[2][256];
    int pending;
};

static inline JellopProfiles profile_default() {
    JellopProfiles p={};p.pending=-1;return p;
}

static inline bool profile_host_char(char c) {
    return (c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='-'||c=='.';
}

// Match the native transport: DNS names/IPv4, optional numeric port and
// simple reverse-proxy path. No userinfo, query, fragment, escaped path,
// unsupported IPv6 literal or control characters.
static inline bool profile_normalize_url(const char *raw,char *out,size_t cap) {
    if(!raw||!out||cap==0)return false;
    size_t n=strlen(raw);
    if(n==0){out[0]=0;return true;}
    if(n>=256||n>=cap)return false;
    while(n&&raw[n-1]=='/')n--;
    const char *end=raw+n;
    const char *p=!strncmp(raw,"http://",7)?raw+7:
                  !strncmp(raw,"https://",8)?raw+8:NULL;
    if(!p||p>=end)return false;
    const char *host=p;
    for(;p<end&&*p!=':'&&*p!='/';p++){
        if(!profile_host_char(*p))return false;
        if(*p=='.'&&(p==host||p[-1]=='.'))return false;
    }
    if(p==host||p[-1]=='.'||p[-1]=='-'||*host=='-')return false;
    if(p<end&&*p==':'){
        ++p;
        unsigned port=0,digits=0;
        while(p<end&&*p>='0'&&*p<='9'){
            if(++digits>5)return false;
            port=port*10+unsigned(*p++-'0');
            if(port>65535)return false;
        }
        if(!digits||!port||(p<end&&*p!='/'))return false;
    }
    while(p<end){
        if(*p++!='/')return false;
        const char *segment=p;
        while(p<end&&*p!='/'){
            if(!profile_host_char(*p)&&*p!='_'&&*p!='~')return false;
            ++p;
        }
        size_t len=(size_t)(p-segment);
        if(!len||(len==1&&segment[0]=='.')||
           (len==2&&segment[0]=='.'&&segment[1]=='.'))return false;
    }
    memcpy(out,raw,n);out[n]=0;return true;
}

static inline bool profile_valid(const JellopProfiles *p) {
    if(!p||p->pending<-1||p->pending>1)return false;
    for(int i=0;i<2;i++){
        char canonical[256];
        if(!memchr(p->url[i],0,sizeof p->url[i])||
           !profile_normalize_url(p->url[i],canonical,sizeof canonical)||
           strcmp(canonical,p->url[i]))return false;
    }
    if(p->url[0][0]&&!strcmp(p->url[0],p->url[1]))return false;
    return p->pending<0||p->url[p->pending][0];
}

static inline int profile_format(const JellopProfiles *p,char *out,size_t cap) {
    if(!out||!cap||!profile_valid(p))return -1;
    int n=snprintf(out,cap,"JELLOP-PROFILES-1\n%d\n%s\n%s\n",p->pending,p->url[0],p->url[1]);
    return n>=0&&(size_t)n<cap?n:-1;
}

static inline bool profile_parse(const char *text,JellopProfiles *out) {
    if(!out||!text)return false;
    const char prefix[]="JELLOP-PROFILES-1\n";
    if(strncmp(text,prefix,sizeof prefix-1))return false;
    const char *p=text+sizeof prefix-1;
    JellopProfiles value=profile_default();
    if(!strncmp(p,"-1\n",3)){p+=3;}
    else if((p[0]=='0'||p[0]=='1')&&p[1]=='\n'){value.pending=p[0]-'0';p+=2;}
    else return false;
    for(int i=0;i<2;i++){
        const char *e=strchr(p,'\n');
        if(!e||e-p>=256)return false;
        char raw[256];memcpy(raw,p,(size_t)(e-p));raw[e-p]=0;
        if(!profile_normalize_url(raw,value.url[i],sizeof value.url[i]))return false;
        p=e+1;
    }
    if(*p||!profile_valid(&value))return false;
    *out=value;return true;
}

static inline int profile_active(const JellopProfiles *p,const char *server) {
    if(!p||!server||!*server)return -1;
    char normalized[256];
    if(!profile_normalize_url(server,normalized,sizeof normalized))return -1;
    for(int i=0;i<2;i++)if(p->url[i][0]&&!strcmp(p->url[i],normalized))return i;
    return -1;
}
