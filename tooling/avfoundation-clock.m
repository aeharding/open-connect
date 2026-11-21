/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* Read-only camera-clock qualification. Uses an already authorized camera. */
#import <AVFoundation/AVFoundation.h>
#import <CoreMedia/CoreMedia.h>
#import <Foundation/Foundation.h>
#include <mach/mach_time.h>

@interface ClockProbe : NSObject <AVCaptureVideoDataOutputSampleBufferDelegate>
@property AVCaptureSession *session;
@property atomic_uint *count;
@end

@implementation ClockProbe
- (void)captureOutput:(AVCaptureOutput *)output didOutputSampleBuffer:(CMSampleBufferRef)sample
       fromConnection:(AVCaptureConnection *)connection {
    (void)output; (void)connection;
    CMTime pts = CMSampleBufferGetPresentationTimeStamp(sample);
    CMClockRef clock = self.session.synchronizationClock;
    if (!clock) return;
    CMTime mapped = CMSyncConvertTime(pts, clock, CMClockGetHostTimeClock());
    CMTime now = CMClockGetTime(CMClockGetHostTimeClock());
    mach_timebase_info_data_t tb;
    mach_timebase_info(&tb);
    double mach = (double)mach_absolute_time() * tb.numer / tb.denom / 1e9;
    printf("CLOCK|%.9f|%.9f|%.9f|%.9f\n", CMTimeGetSeconds(pts),
           CMTimeGetSeconds(mapped), CMTimeGetSeconds(now), mach);
    fflush(stdout);
    atomic_fetch_add(self.count, 1);
}
@end

int main(int argc, const char **argv) {
    @autoreleasepool {
        if (argc != 2 || [AVCaptureDevice authorizationStatusForMediaType:AVMediaTypeVideo] != AVAuthorizationStatusAuthorized)
            return 77;
        AVCaptureDevice *device = nil;
        for (AVCaptureDevice *candidate in [AVCaptureDevice devicesWithMediaType:AVMediaTypeVideo])
            if ([candidate.uniqueID isEqualToString:[NSString stringWithUTF8String:argv[1]]]) {
                if (device) return 78;
                device = candidate;
            }
        if (!device) return 79;
        NSError *error = nil;
        AVCaptureDeviceInput *input = [AVCaptureDeviceInput deviceInputWithDevice:device error:&error];
        if (!input) return 80;
        AVCaptureSession *session = [AVCaptureSession new];
        AVCaptureVideoDataOutput *output = [AVCaptureVideoDataOutput new];
        if (![session canAddInput:input] || ![session canAddOutput:output]) return 81;
        [session addInput:input]; [session addOutput:output];
        atomic_uint count = 0;
        ClockProbe *probe = [ClockProbe new]; probe.session = session; probe.count = &count;
        dispatch_queue_t queue = dispatch_queue_create("open-connect.clock-probe", DISPATCH_QUEUE_SERIAL);
        [output setSampleBufferDelegate:probe queue:queue];
        [session startRunning];
        NSDate *deadline = [NSDate dateWithTimeIntervalSinceNow:8];
        while (atomic_load(&count) < 5 && [deadline timeIntervalSinceNow] > 0)
            [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
        [session stopRunning];
        [output setSampleBufferDelegate:nil queue:NULL];
        dispatch_sync(queue, ^{});
        return atomic_load(&count) >= 5 ? 0 : 82;
    }
}
