#include <assert.h>
#include "../source/player/core/video_brightness.h"
int main(){
    assert(video_brightness_clamp(-100)==-20);
    assert(video_brightness_clamp(100)==10);
    assert(video_brightness_alpha(0)==0);
    assert(video_brightness_alpha(-20)==179);
    assert(video_brightness_alpha(10)==89);
    assert(video_brightness_alpha(-10)==89);
}
