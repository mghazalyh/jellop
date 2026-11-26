#pragma once
#include <stdio.h>
#include <string.h>

// 0 = server default. No additional heap or timer thread.
static const unsigned SURF_DWELL_OPTIONS[]={0,15,30,60,120,180,240,300,360,420,480,540,600};
static const unsigned SURF_DWELL_OPTION_COUNT=sizeof SURF_DWELL_OPTIONS/sizeof SURF_DWELL_OPTIONS[0];
static inline bool surf_dwell_valid(unsigned n){
    for(unsigned i=0;i<SURF_DWELL_OPTION_COUNT;i++)if(SURF_DWELL_OPTIONS[i]==n)return true;
    return false;
}
static inline unsigned surf_dwell_effective(unsigned local,unsigned server){
    if(local&&surf_dwell_valid(local))return local;
    return server>=15&&server<=600?server:60;
}
static inline bool surf_dwell_parse(const char *text,unsigned *out){
    if(!text||!out||!*text)return false;
    unsigned n=0,digits=0;
    while(*text>='0'&&*text<='9'){
        if(++digits>3)return false;
        n=n*10+(unsigned)(*text++-'0');
    }
    if(!digits||(*text&&strcmp(text,"\n")&&strcmp(text,"\r\n"))||!surf_dwell_valid(n))return false;
    *out=n;return true;
}
static inline unsigned surf_dwell_load(const char *path){
    FILE *f=path?fopen(path,"rb"):NULL;
    if(!f)return 0;
    char data[12];size_t n=fread(data,1,sizeof data,f);
    bool ok=!ferror(f)&&n<sizeof data&&!memchr(data,0,n);fclose(f);
    if(!ok)return 0;
    data[n]=0;unsigned value=0;
    return surf_dwell_parse(data,&value)?value:0;
}
static inline bool surf_dwell_save(const char *path,unsigned n){
    if(!path||!surf_dwell_valid(n))return false;
    char tmp[224],data[12];
    int l=snprintf(tmp,sizeof tmp,"%s.tmp",path);
    if(l<0||l>=(int)sizeof tmp)return false;
    int size=snprintf(data,sizeof data,"%u\n",n);
    if(size<=0||size>=(int)sizeof data)return false;
    FILE *f=fopen(tmp,"wb");
    if(!f)return false;
    bool ok=fwrite(data,1,(size_t)size,f)==(size_t)size&&fflush(f)==0;
    if(fclose(f)!=0)ok=false;
    if(ok&&rename(tmp,path)==0)return true;
    remove(tmp);return false;
}
