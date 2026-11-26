#pragma once
// Match Jealousfin's -20..+10 overlay scale without another video buffer.
static inline int video_brightness_clamp(int v){return v<-20?-20:v>10?10:v;}
static inline unsigned video_brightness_alpha(int v){
    v=video_brightness_clamp(v);if(v<0)v=-v;
    return (unsigned)(v*35*255+500)/1000;
}
