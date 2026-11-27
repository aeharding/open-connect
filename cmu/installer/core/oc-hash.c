/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Shared FIPS 180-4 SHA-256 translation unit.
 */
#include "oc-core.h"

static oc_u32 oc_rotr(oc_u32 x, unsigned n) { return (x >> n) | (x << (32 - n)); }

static void oc_hash_block(OcHash *h) {
    static const oc_u32 k[64] = {
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
    };
    oc_u32 w[64], a=h->state[0], b=h->state[1], c=h->state[2], d=h->state[3];
    oc_u32 e=h->state[4], f=h->state[5], g=h->state[6], z=h->state[7];
    unsigned i;
    for (i=0; i<16; ++i) {
        const oc_u8 *p=h->block+i*4;
        w[i]=((oc_u32)p[0]<<24)|((oc_u32)p[1]<<16)|((oc_u32)p[2]<<8)|p[3];
    }
    for (i=16; i<64; ++i) {
        oc_u32 x=w[i-15], y=w[i-2];
        w[i]=w[i-16]+(oc_rotr(x,7)^oc_rotr(x,18)^(x>>3))+w[i-7]
             +(oc_rotr(y,17)^oc_rotr(y,19)^(y>>10));
    }
    for (i=0; i<64; ++i) {
        oc_u32 t=z+(oc_rotr(e,6)^oc_rotr(e,11)^oc_rotr(e,25))+((e&f)^(~e&g))+k[i]+w[i];
        oc_u32 u=(oc_rotr(a,2)^oc_rotr(a,13)^oc_rotr(a,22))+((a&b)^(a&c)^(b&c));
        z=g; g=f; f=e; e=d+t; d=c; c=b; b=a; a=t+u;
    }
    h->state[0]+=a; h->state[1]+=b; h->state[2]+=c; h->state[3]+=d;
    h->state[4]+=e; h->state[5]+=f; h->state[6]+=g; h->state[7]+=z;
}

void oc_hash_init(OcHash *h) {
    static const oc_u32 initial[8]={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
                                    0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    for (unsigned i=0; i<8; ++i) h->state[i]=initial[i];
    h->bytes=0; h->used=0;
}

void oc_hash_add(OcHash *h, const void *input, unsigned size) {
    const oc_u8 *p=input;
    h->bytes+=size;
    while (size) {
        unsigned n=64-h->used;
        if (n>size) n=size;
        size-=n;
        while (n--) h->block[h->used++]=*p++;
        if (h->used==64) { oc_hash_block(h); h->used=0; }
    }
}

void oc_hash_finish(OcHash *h, char output[65]) {
    static const char digits[]="0123456789abcdef";
    oc_u32 hi=((oc_u32)(h->bytes>>32)<<3)|((oc_u32)h->bytes>>29);
    oc_u32 lo=(oc_u32)h->bytes<<3;
    h->block[h->used++]=0x80;
    if (h->used>56) {
        while (h->used<64) h->block[h->used++]=0;
        oc_hash_block(h); h->used=0;
    }
    while (h->used<56) h->block[h->used++]=0;
    h->block[56]=(oc_u8)(hi>>24); h->block[57]=(oc_u8)(hi>>16);
    h->block[58]=(oc_u8)(hi>>8);  h->block[59]=(oc_u8)hi;
    h->block[60]=(oc_u8)(lo>>24); h->block[61]=(oc_u8)(lo>>16);
    h->block[62]=(oc_u8)(lo>>8);  h->block[63]=(oc_u8)lo;
    oc_hash_block(h);
    for (unsigned i=0; i<64; ++i) output[i]=digits[(h->state[i/8]>>(28-(i%8)*4))&15];
    output[64]=0;
}
