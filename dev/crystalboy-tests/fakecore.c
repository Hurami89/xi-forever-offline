#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
typedef bool (*env_t)(unsigned, void*);
typedef void (*video_t)(const void*, unsigned, unsigned, size_t);
typedef size_t (*batch_t)(const int16_t*, size_t);
typedef void (*one_t)(int16_t,int16_t);
typedef void (*poll_t)(void);
typedef int16_t (*state_t)(unsigned,unsigned,unsigned,unsigned);
struct gi { const char *path; const void *data; size_t size; const char *meta; };
struct si { const char *a,*b,*c; bool need_fullpath, block_extract; };
struct av { unsigned bw,bh,mw,mh; float ar; double fps, sr; };
struct var { const char *key; const char *value; };
static env_t env; static video_t video; static batch_t batch; static poll_t poll; static state_t input;
static int fmt = 1; static uint32_t frame; static uint8_t sram[512]; static uint8_t rambuf[8192];
static uint8_t pix[144][300*4]; static int loaded, inited, deinits;
static char lastdir[256]; static char colorization[64];
static unsigned char romfirst;
int fc_fmt_request = 1; /* test sets this via env var */
void retro_set_environment(env_t e){ env=e; }
void retro_set_video_refresh(video_t v){ video=v; }
void retro_set_audio_sample(one_t o){ (void)o; }
void retro_set_audio_sample_batch(batch_t b){ batch=b; }
void retro_set_input_poll(poll_t p){ poll=p; }
void retro_set_input_state(state_t s){ input=s; }
void retro_init(void){
  inited++;
  const char *f=getenv("FC_FMT"); if(f) fc_fmt_request=atoi(f);
  int want=fc_fmt_request; if(env(10,&want)) fmt=want; else fmt=0;
  const char *d=0; if(env(9,(void*)&d) && d) strncpy(lastdir,d,255);
  bool dupe=false; env(3,&dupe); if(!dupe) fmt=99;
  env(0x10000|5000,0); /* unknown experimental */
}
void retro_deinit(void){ deinits++; }
unsigned retro_api_version(void){ const char *v=getenv("FC_API"); return v?atoi(v):1; }
void retro_get_system_info(struct si *i){ i->a="FakeCore"; i->b="1"; i->c="gb|gbc"; i->need_fullpath=false; i->block_extract=false; }
void retro_get_system_av_info(struct av *a){ a->bw=160; a->bh=144; a->mw=160; a->mh=144; a->ar=0; a->fps=59.7275; a->sr=32768; }
void retro_reset(void){ frame=0; }
void retro_run(void){
  poll();
  int bpp = fmt==1?4:2;
  int16_t a = input(0,1,0,8), st = input(0,1,0,3), other = input(1,1,0,8);
  frame++;
  if (a) sram[0]++;
  if (st) sram[1]=0x5A;
  if (other) sram[2]=1;
  rambuf[0x100] = (uint8_t)frame;
  for(int y=0;y<144;y++) for(int x=0;x<160*bpp;x++) pix[y][x]=(uint8_t)(x+y+frame);
  int w = 160;
  if (getenv("FC_DUPE") && frame%2==0) { video(NULL,160,144,0); return; }
  video(pix,w,144,300*4); /* padded pitch */
  int16_t buf[4]={0}; batch(buf,2);
}
size_t retro_serialize_size(void){ return getenv("FC_NOSTATE")?0:sizeof(frame)+sizeof(sram); }
bool retro_serialize(void *d, size_t n){ if(n<sizeof(frame)+sizeof(sram)) return false; memcpy(d,&frame,4); memcpy((char*)d+4,sram,512); return true; }
bool retro_unserialize(const void *d, size_t n){ if(n!=sizeof(frame)+sizeof(sram)) return false; memcpy(&frame,d,4); memcpy(sram,(char*)d+4,512); return true; }
bool retro_load_game(const struct gi *g){
  if(!g||g->size<0x150) return false;
  struct var v={"gambatte_gb_colorization",0};
  if(env(15,&v) && v.value) strncpy(colorization,v.value,63); else strcpy(colorization,"none");
  romfirst=((const unsigned char*)g->data)[0x134];
  loaded=1; frame=0; memset(sram,0,512); return true; }
void retro_unload_game(void){ loaded=0; }
void *retro_get_memory_data(unsigned id){ if(!loaded) return NULL; if(id==0) return getenv("FC_NOSRAM")?NULL:sram; if(id==2) return rambuf; return NULL; }
size_t retro_get_memory_size(unsigned id){ if(!loaded) return 0; if(id==0) return getenv("FC_NOSRAM")?0:512; if(id==2) return 8192; return 0; }
/* test introspection */
int fc_inited(void){return inited;} int fc_deinits(void){return deinits;} uint32_t fc_frame(void){return frame;}
const char *fc_dir(void){return lastdir;} const char *fc_color(void){return colorization;} int fc_fmt(void){return fmt;}
unsigned char fc_romfirst(void){return romfirst;}
